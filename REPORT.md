# Design Decisions Report

## Why this stack

**FastAPI** for the backend gives request validation (Pydantic), automatic
OpenAPI docs, and async-friendly I/O with very little boilerplate — useful
for an assignment where the API surface itself (3 endpoints) is small but
still needs to be demonstrably correct and well-documented.

**PostgreSQL** was the required database. SQLAlchemy Core/ORM sits on top
of it so the schema is expressed once as Python models, while `db/init.sql`
remains the authoritative schema + seed data that runs automatically via
Postgres's `docker-entrypoint-initdb.d` mechanism — no separate migration
tool was justified for a system this size.

**RabbitMQ** decouples "an order was placed" from "an order was processed."
The backend's job is to validate input and persist state quickly; baking,
inventory checks, and payment capture (simulated here as a sleep) belong in
a separate consumer so a slow downstream step never blocks the HTTP
response. A **durable** queue and **persistent** messages
(`delivery_mode=2`) mean an order survives a RabbitMQ or worker restart —
it just resumes processing once they're back.

**Redis** caches the product list because it's the highest-read, lowest-
write endpoint in the system (products change rarely; they're read on
every page load). A short TTL (30s default) bounds staleness without
needing explicit cache invalidation logic for the common case; the two
places that *do* mutate stock in a fuller version of this system would call
`invalidate_products_cache()` explicitly.

## Container design decisions

- **One process per container.** Each service (db, redis, rabbitmq,
  backend, worker, frontend) is a separate container with a single
  responsibility, so each can be scaled, restarted, or replaced
  independently — the worker, for example, could be scaled to N replicas
  under load without touching the API.
- **Non-root users.** Both Python images (`backend`, `worker`) create and
  switch to an unprivileged `appuser` rather than running as root, following
  container security best practice.
- **Named volumes, not bind mounts, for data.** `db_data` and
  `rabbitmq_data` are Docker-managed volumes so container recreation
  (`docker compose up --build`) never loses data, while `docker compose
  down -v` gives a clean-slate option for grading/testing.
- **`depends_on` with `condition: service_healthy`**, not just plain
  `depends_on`. Plain `depends_on` only waits for a container to *start*,
  not for Postgres/RabbitMQ/Redis to actually be ready to accept
  connections — a classic source of "connection refused" flakiness on
  `docker compose up`. Health checks plus `service_healthy` conditions fix
  that at the orchestration level. Application code also retries on
  startup (see `worker.py`'s `get_db_connection`/`make_channel`) as
  defense in depth.
- **A reverse proxy for the frontend, not CORS.** nginx proxies `/api/*` to
  the backend container, so the browser only ever talks to the frontend's
  origin. This avoids configuring/loosening CORS for a browser-facing
  service and means the backend's internal port/hostname never need to be
  exposed to the client.
- **Structured JSON logs** on backend and worker so `docker compose logs`
  output is machine-parseable (`| jq`) rather than free-text — closer to
  how these services would be operated in production alongside a real log
  aggregator.

## Trade-offs and things a production system would do differently

- The worker `nack`s a failed message with `requeue=False` after a single
  attempt rather than implementing a dead-letter queue with retry limits —
  simpler for an assignment-scale system, but a production version would
  add a DLQ and exponential backoff.
- Redis cache invalidation is TTL-only; a system with frequent stock
  changes would explicitly invalidate on write.
- No authentication/authorization layer — out of scope for the assignment,
  but the first thing to add before this touched real customer data.
- Resource limits (`mem_limit`/`cpus`) and TLS between services were left
  out to keep the compose file focused on the four advanced features that
  were chosen to be graded.
