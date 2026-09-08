import logging
import time

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.logging_config import configure_logging
from app.config import settings
from app.database import get_db, engine, Base
from app import models, schemas, cache, messaging

logger = configure_logging("bakery.backend", settings.LOG_LEVEL)

app = FastAPI(title="Bakery Management API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # For a class assignment, letting SQLAlchemy create any tables the
    # init.sql seed script didn't (idempotent, no-op if they already exist)
    # keeps things resilient. init.sql remains the source of truth + seed data.
    Base.metadata.create_all(bind=engine)
    logger.info("backend service started")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000, 2)
    logger.info(
        "request handled",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


@app.get("/health", response_model=schemas.HealthOut, tags=["health"])
def health_check(db: Session = Depends(get_db)):
    """Used by Docker's HEALTHCHECK and for manual/VIVA verification."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    redis_status = "ok" if cache.ping() else "error"
    rabbitmq_status = "ok" if messaging.ping() else "error"

    overall = "ok" if db_status == "ok" else "degraded"
    return schemas.HealthOut(
        status=overall,
        database=db_status,
        redis=redis_status,
        rabbitmq=rabbitmq_status,
    )


# --- Endpoint 1: List all bakery products -----------------------------------
@app.get("/products", response_model=list[schemas.ProductOut], tags=["products"])
def list_products(db: Session = Depends(get_db)):
    cached = cache.get_cached_products()
    if cached is not None:
        logger.info("products served from cache")
        return cached

    products = db.query(models.Product).order_by(models.Product.id).all()
    result = [schemas.ProductOut.model_validate(p).model_dump(mode="json") for p in products]
    cache.set_cached_products(result)
    logger.info("products served from database", extra={"count": len(result)})
    return result


# --- Endpoint 2: Place an order ---------------------------------------------
@app.post("/orders", response_model=schemas.OrderOut, status_code=201, tags=["orders"])
def place_order(order_in: schemas.OrderCreate, db: Session = Depends(get_db)):
    product_ids = [item.product_id for item in order_in.items]
    products = db.query(models.Product).filter(models.Product.id.in_(product_ids)).all()
    products_by_id = {p.id: p for p in products}

    missing = [pid for pid in product_ids if pid not in products_by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Unknown product id(s): {missing}")

    out_of_stock = [pid for pid in product_ids if not products_by_id[pid].in_stock]
    if out_of_stock:
        raise HTTPException(status_code=409, detail=f"Product(s) out of stock: {out_of_stock}")

    total = sum(products_by_id[item.product_id].price * item.quantity for item in order_in.items)

    order = models.Order(customer_name=order_in.customer_name, status="pending", total_amount=total)
    db.add(order)
    db.flush()  # assigns order.id

    for item in order_in.items:
        db.add(
            models.OrderItem(
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=products_by_id[item.product_id].price,
            )
        )

    db.commit()
    db.refresh(order)
    logger.info("order created", extra={"order_id": order.id, "total_amount": str(total)})

    published = messaging.publish_order_created(order.id)
    if not published:
        logger.warning("order created but queue publish failed; worker will not auto-process", extra={"order_id": order.id})

    return order


# --- Endpoint 3: Check order status -----------------------------------------
@app.get("/orders/{order_id}", response_model=schemas.OrderOut, tags=["orders"])
def get_order_status(order_id: int, db: Session = Depends(get_db)):
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
