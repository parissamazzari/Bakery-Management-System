"""Order-processing worker.

Advanced feature: a dedicated worker service that consumes order-created
events from RabbitMQ and moves each order through pending -> processing ->
completed, independent of the request/response cycle of the backend API.
"""
import json
import os
import time
import threading

import pika
import psycopg2

from logging_config import configure_logging

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
logger = configure_logging("bakery.worker", LOG_LEVEL)

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "bakery")
POSTGRES_USER = os.getenv("POSTGRES_USER", "bakery_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "bakery_pass")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "bakery")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "bakery_pass")
ORDER_QUEUE_NAME = os.getenv("ORDER_QUEUE_NAME", "order_processing")

PROCESSING_DELAY_SECONDS = float(os.getenv("PROCESSING_DELAY_SECONDS", "3"))
HEARTBEAT_FILE = "/tmp/worker_heartbeat"


def touch_heartbeat():
    """Written on every loop iteration; the Docker HEALTHCHECK checks its mtime."""
    with open(HEARTBEAT_FILE, "w") as f:
        f.write(str(time.time()))


def heartbeat_loop(stop_event: threading.Event):
    while not stop_event.is_set():
        touch_heartbeat()
        stop_event.wait(5)


def get_db_connection(retries: int = 10, delay: int = 3):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return psycopg2.connect(
                host=POSTGRES_HOST,
                port=POSTGRES_PORT,
                dbname=POSTGRES_DB,
                user=POSTGRES_USER,
                password=POSTGRES_PASSWORD,
            )
        except psycopg2.OperationalError as exc:
            last_exc = exc
            logger.warning("database not ready, retrying", extra={"attempt": attempt})
            time.sleep(delay)
    raise last_exc


def update_order_status(conn, order_id: int, status: str):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE orders SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, order_id),
        )
    conn.commit()


def process_order(conn, order_id: int):
    logger.info("processing order", extra={"order_id": order_id})
    update_order_status(conn, order_id, "processing")

    # Simulate real work: inventory checks, payment capture, baking queue, etc.
    time.sleep(PROCESSING_DELAY_SECONDS)

    update_order_status(conn, order_id, "completed")
    logger.info("order completed", extra={"order_id": order_id})


def make_channel(retries: int = 10, delay: int = 3):
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=30,
    )
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            channel.queue_declare(queue=ORDER_QUEUE_NAME, durable=True)
            channel.basic_qos(prefetch_count=1)
            return connection, channel
        except (pika.exceptions.AMQPError, OSError) as exc:
            last_exc = exc
            logger.warning("rabbitmq not ready, retrying", extra={"attempt": attempt})
            time.sleep(delay)
    raise last_exc


def main():
    stop_event = threading.Event()
    threading.Thread(target=heartbeat_loop, args=(stop_event,), daemon=True).start()

    conn = get_db_connection()
    connection, channel = make_channel()
    logger.info("worker started, waiting for orders", extra={"queue": ORDER_QUEUE_NAME})

    def callback(ch, method, properties, body):
        try:
            payload = json.loads(body)
            order_id = payload["order_id"]
            process_order(conn, order_id)
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to process order message", extra={"error": str(exc)})
            # Requeue once; if it keeps failing the message will loop, which is
            # acceptable for an assignment-scale system (a production system
            # would route to a dead-letter queue after N attempts).
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_consume(queue=ORDER_QUEUE_NAME, on_message_callback=callback)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    finally:
        stop_event.set()
        connection.close()
        conn.close()


if __name__ == "__main__":
    main()
