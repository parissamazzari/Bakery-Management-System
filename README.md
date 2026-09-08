# Bakery Management System

A containerized bakery management system built with Docker and Docker Compose,
demonstrating multi-service orchestration, container networking, caching,
asynchronous processing, health checks, and structured logging.

## 1. System Architecture

```
                          ┌─────────────────────┐
                          │   frontend (nginx)   │  :8080 -> :80
                          │  static HTML/JS/CSS  │
                          └──────────┬───────────┘
                                     │ proxies /api/* to backend:8000
                                     ▼
                          ┌─────────────────────┐
                          │   backend (FastAPI)  │  :8000 -> :8000
                          └───┬─────────┬────────┘
                    reads/    │         │ publishes
                    writes    │         │ "order created"
                    caches    │         ▼
              ┌───────────┐  │   ┌─────────────┐
              │   redis    │◄┘   │  rabbitmq   │  :15672 (mgmt UI)
              │  (cache)   │     │   (queue)   │
              └───────────┘     └──────┬──────┘
                                        │ consumes
                                        ▼
              ┌───────────┐     ┌─────────────┐
              │ postgres   │◄────┤   worker    │
              │  (db)      │     │ (processes  │
              └───────────┘     │   orders)   │
                                └─────────────┘
```

All five containers (`db`, `redis`, `rabbitmq`, `backend`, `worker`,
`frontend`) run on a single user-defined bridge network (`bakery-net`)
created by Docker Compose. Containers reach each other by **service name**
(e.g. the backend connects to `db:5432`, `redis:6379`, `rabbitmq:5672`) -
no hardcoded IPs, and no port needs to be published to the host except the
ones a human/browser needs to reach directly (`8080` frontend, `8000`
backend API + docs, `15672` RabbitMQ management UI).

### Request flow

1. The browser loads the frontend at `http://localhost:8080`.
2. The frontend's JavaScript calls `/api/products`, `/api/orders`, etc.
   nginx reverse-proxies anything under `/api/` to the `backend` container,
   so the browser only ever talks to one origin and no CORS configuration
   is needed.
3. `GET /products` first checks Redis; on a cache miss it queries Postgres
   and populates the cache with a short TTL (default 30s).
4. `POST /orders` validates the request, inserts an `orders` row (status
   `pending`) plus its `order_items` rows in Postgres, then publishes an
   `{"order_id": ...}` message to the `order_processing` RabbitMQ queue.
5. The `worker` service consumes that queue independently of the API
   request/response cycle, moves the order to `processing`, simulates the
   baking/fulfillment work, then marks it `completed`.
6. `GET /orders/{id}` (used by "Check Order Status") always reads straight
   from Postgres so the client can poll and see the status change from
   `pending` -> `processing` -> `completed`.

## 2. Components

| Service    | Image / Base           | Role                                                        |
|------------|-------------------------|-------------------------------------------------------------|
| `db`       | `postgres:16-alpine`    | Persists products, orders, and order items                  |
| `redis`    | `redis:7-alpine`        | Caches the product listing to reduce DB load                |
| `rabbitmq` | `rabbitmq:3.13-management-alpine` | Durable queue decoupling order intake from processing |
| `backend`  | Python 3.12 / FastAPI   | REST API (products, orders, health)                          |
| `worker`   | Python 3.12             | Consumes `order_processing` queue, updates order status      |
| `frontend` | `nginx:1.27-alpine`     | Serves the static UI and reverse-proxies `/api/*`             |

## 3. Advanced Features Implemented

1. **Redis caching for product listings** — `backend/app/cache.py`. The
   `GET /products` endpoint reads/writes a JSON blob under the key
   `products:all` with a configurable TTL (`PRODUCT_CACHE_TTL_SECONDS`). A
   Redis outage degrades gracefully to hitting Postgres directly rather than
   failing the request.
2. **Order-processing worker service** — `worker/worker.py`. A standalone
   container that consumes the `order_processing` RabbitMQ queue and drives
   each order through `pending -> processing -> completed`, fully decoupled
   from the API.
3. **Health checks on every container** — each `Dockerfile`/service defines
   a `HEALTHCHECK` (Postgres: `pg_isready`; Redis: `redis-cli ping`;
   RabbitMQ: `rabbitmq-diagnostics ping`; backend: `GET /health`; worker: a
   heartbeat file refreshed every 5s; frontend: `GET /healthz`).
   `docker-compose.yml` also uses `depends_on: condition: service_healthy`
   so dependent services only start once their dependencies are actually
   ready, not merely running.
4. **Structured (JSON) logging** — `backend/app/logging_config.py` and
   `worker/logging_config.py` configure `python-json-logger` so every log
   line is a single JSON object (timestamp, service, level, message, plus
   contextual fields like `order_id`), making the logs easy to pipe into
   any aggregator: `docker compose logs -f backend | jq`.

## 4. Setup Instructions

### Prerequisites

- Docker Engine 24+ and Docker Compose v2 (`docker compose version`)

### Run it

```bash
git clone <this-repository-url>
cd bakery-management-system

cp .env.example .env      # adjust credentials if you want; defaults work locally

docker compose up --build
```

Wait for all services to report healthy (`docker compose ps`), then open:

- Frontend UI: http://localhost:8080
- Backend API docs (Swagger): http://localhost:8000/docs
- Backend health: http://localhost:8000/health
- RabbitMQ management UI: http://localhost:15672 (user/pass from `.env`)

To stop everything:

```bash
docker compose down          # keep data (named volumes persist)
docker compose down -v       # also wipe the Postgres/RabbitMQ volumes
```

### Verifying the RabbitMQ -> worker flow

1. Place an order from the UI (or via `curl`, see below).
2. Watch the worker's logs: `docker compose logs -f worker`
3. Poll `GET /orders/{id}` (or use "Check Order Status" in the UI) and see
   the status move from `pending` to `processing` to `completed` over a few
   seconds.

## 5. API Documentation

Interactive OpenAPI docs are auto-generated by FastAPI at `/docs` and
`/redoc`. Summary of the three required endpoints plus health:

### `GET /products`

Returns every product. Served from Redis when available.

```bash
curl http://localhost:8000/products
```

```json
[
  {
    "id": 1,
    "name": "Sourdough Loaf",
    "description": "Classic slow-fermented sourdough bread",
    "price": "6.50",
    "category": "bread",
    "in_stock": true
  }
]
```

### `POST /orders`

Creates an order for one or more products and enqueues it for processing.

```bash
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
        "customer_name": "Jane Doe",
        "items": [
          {"product_id": 1, "quantity": 2},
          {"product_id": 3, "quantity": 1}
        ]
      }'
```

```json
{
  "id": 1,
  "customer_name": "Jane Doe",
  "status": "pending",
  "total_amount": "15.00",
  "created_at": "2026-01-01T12:00:00Z",
  "updated_at": "2026-01-01T12:00:00Z",
  "items": [
    {"product_id": 1, "quantity": 2, "unit_price": "6.50"},
    {"product_id": 3, "quantity": 1, "unit_price": "2.00"}
  ]
}
```

Errors: `404` for an unknown `product_id`, `409` if a product is out of
stock.

### `GET /orders/{order_id}`

Returns the current status and full detail of an order.

```bash
curl http://localhost:8000/orders/1
```

### `GET /health`

Used by the Docker `HEALTHCHECK` and for manual verification; reports the
reachability of Postgres, Redis, and RabbitMQ from the backend's point of
view.

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "database": "ok", "redis": "ok", "rabbitmq": "ok"}
```

## 6. Project Structure

```
bakery-management-system/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── REPORT.md
├── db/
│   └── init.sql              # schema + seed data, run once on first db start
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   └── app/
│       ├── main.py           # FastAPI app & routes
│       ├── config.py
│       ├── database.py
│       ├── models.py
│       ├── schemas.py
│       ├── cache.py           # Redis caching (advanced feature)
│       ├── messaging.py       # RabbitMQ publisher
│       └── logging_config.py  # structured logging (advanced feature)
├── worker/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── .dockerignore
│   ├── worker.py               # RabbitMQ consumer (advanced feature)
│   └── logging_config.py
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── .dockerignore
    └── public/
        ├── index.html
        ├── style.css
        └── app.js
```

## 7. Environment Variables

See `.env.example` for the full list (Postgres/RabbitMQ credentials, cache
TTL, log level, simulated processing delay). Copy it to `.env` before
running Compose; `.env` is gitignored so credentials never get committed.
