"""Structured (JSON) logging configuration shared by the backend service.

Emitting one JSON object per line makes logs trivial to ship to any log
aggregator (Loki, ELK, CloudWatch, ...) and to `docker compose logs | jq`.
"""
import logging
import sys

from pythonjsonlogger import jsonlogger


def configure_logging(service_name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(level)

    # Avoid duplicate handlers if configure_logging() is called more than once
    # (e.g. during uvicorn's --reload worker re-import).
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "service"},
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False
    return logger
