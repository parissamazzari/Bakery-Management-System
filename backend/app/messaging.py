"""RabbitMQ publishing helper. The backend publishes one message per new order;
the worker service (see /worker) consumes that queue and processes the order.
"""
import json
import logging

import pika

from app.config import settings

logger = logging.getLogger("bakery.backend")


def _connection_params() -> pika.ConnectionParameters:
    credentials = pika.PlainCredentials(settings.RABBITMQ_USER, settings.RABBITMQ_PASSWORD)
    return pika.ConnectionParameters(
        host=settings.RABBITMQ_HOST,
        port=settings.RABBITMQ_PORT,
        credentials=credentials,
        heartbeat=30,
        blocked_connection_timeout=5,
        connection_attempts=3,
        retry_delay=2,
    )


def publish_order_created(order_id: int) -> bool:
    """Publish a durable message announcing a new order to process.

    Returns True on success, False if RabbitMQ could not be reached (the order
    still exists in the DB with status="pending"; nothing is lost, it just
    won't be auto-processed until RabbitMQ/worker are back up).
    """
    try:
        connection = pika.BlockingConnection(_connection_params())
        channel = connection.channel()
        channel.queue_declare(queue=settings.ORDER_QUEUE_NAME, durable=True)
        channel.basic_publish(
            exchange="",
            routing_key=settings.ORDER_QUEUE_NAME,
            body=json.dumps({"order_id": order_id}),
            properties=pika.BasicProperties(delivery_mode=2, content_type="application/json"),
        )
        connection.close()
        logger.info("published order to queue", extra={"order_id": order_id})
        return True
    except (pika.exceptions.AMQPError, OSError) as exc:
        logger.error("failed to publish order to queue", extra={"order_id": order_id, "error": str(exc)})
        return False


def ping() -> bool:
    try:
        connection = pika.BlockingConnection(_connection_params())
        connection.close()
        return True
    except (pika.exceptions.AMQPError, OSError):
        return False
