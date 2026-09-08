"""Thin Redis caching helper used to speed up the product listing endpoint.

Advanced feature: Redis caching for product listings.
"""
import json
from decimal import Decimal
from typing import Optional

import redis

from app.config import settings

_redis_client: Optional[redis.Redis] = None

PRODUCTS_CACHE_KEY = "products:all"


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


def get_cached_products() -> Optional[list]:
    try:
        raw = get_redis().get(PRODUCTS_CACHE_KEY)
    except redis.RedisError:
        return None
    if raw is None:
        return None
    return json.loads(raw)


def set_cached_products(products: list) -> None:
    try:
        get_redis().set(
            PRODUCTS_CACHE_KEY,
            json.dumps(products, cls=_DecimalEncoder),
            ex=settings.PRODUCT_CACHE_TTL_SECONDS,
        )
    except redis.RedisError:
        # Caching is a performance optimization, not a correctness requirement:
        # if Redis is briefly unavailable we just fall through to the DB.
        pass


def invalidate_products_cache() -> None:
    try:
        get_redis().delete(PRODUCTS_CACHE_KEY)
    except redis.RedisError:
        pass


def ping() -> bool:
    try:
        return get_redis().ping()
    except redis.RedisError:
        return False
