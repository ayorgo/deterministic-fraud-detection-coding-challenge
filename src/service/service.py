# TODO: Add docstrings
# TODO: Implement logging

import uuid
from datetime import datetime, timedelta
from functools import lru_cache

import redis
import settings
from fastapi import FastAPI
from geopandas import read_file as gpd_read_file
from pydantic import BaseModel
from shapely import Point


class Order(BaseModel):
    timestamp: datetime
    longitude: float
    latitude: float
    fraud_score: float


class OrderUpdateFraud(BaseModel):
    order_id: str
    is_fraud: bool


class OrderId(BaseModel):
    order_id: str


app = FastAPI(debug=settings.DEBUG)


@lru_cache(maxsize=1)
def _get_redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
    )


@lru_cache(maxsize=1)
def _get_high_fraud_areas() -> list:
    return gpd_read_file("data/high_fraud_areas.geojson")


def calculate_ttl(
    current_time: datetime, past_time: datetime, seconds: int
) -> int:
    ttl_seconds = timedelta(seconds=seconds)
    ttl_seconds = (past_time + ttl_seconds - current_time).total_seconds()
    return int(ttl_seconds)


def get_nearby(order: Order) -> list:
    redis_client = _get_redis_client()

    # `geosearch` runs in O(M + log(N)) where N is the number of elements
    # in the index, and M the number of elements returned. In our case,
    # N is bounded by the number of (suspected to be) fraudulent orders
    # in the last 24 hours, and M is bounded by the number of orders in
    # the proximity of the order in question.
    nearby_order_ids = redis_client.geosearch(
        "orders",
        longitude=order.longitude,
        latitude=order.latitude,
        radius=settings.PROXIMITY_METERS,
        unit="m",
    )
    nearby_orders = []
    for order_id in nearby_order_ids:
        nearby_order = redis_client.hgetall(f"orders:{order_id}")
        if len(nearby_order) == 0:
            continue
        nearby_timestamp = datetime.fromisoformat(nearby_order["timestamp"])

        # Remove suspected orders that have expired
        if (
            calculate_ttl(
                order.timestamp,
                nearby_timestamp,
                settings.SUSPECTED_TTL_SECONDS,
            )
            > 0
        ):
            nearby_orders.append(nearby_order)
        else:
            redis_client.delete(f"orders:{order_id}")

        # Remove accepted orders that have expired
        if (
            calculate_ttl(
                order.timestamp, nearby_timestamp, settings.ACCEPTED_TTL_SECONDS
            )
            > 0
        ):
            nearby_orders.append(nearby_order)
        else:
            redis_client.delete(f"orders:{order_id}")
    return nearby_orders


def cache(order: Order, order_id: str, suspected_fraud: bool) -> None:
    redis_client = _get_redis_client()
    redis_client.hset(
        f"orders:{order_id}",
        mapping={
            "timestamp": order.timestamp.isoformat(),
            "longitude": order.longitude,
            "latitude": order.latitude,
            "fraud_score": order.fraud_score,
            "suspected_fraud": str(suspected_fraud),
        },
    )
    redis_client.geoadd("orders", (order.longitude, order.latitude, order_id))


def is_in_fraud_area(point: Point) -> bool:
    high_fraud_areas = _get_high_fraud_areas()
    return high_fraud_areas.contains(point).any()


def is_suspected_fraud(order: Order) -> bool:
    if order.fraud_score > settings.FRAUD_SCORE_THRESHOLD:
        return True

    if is_in_fraud_area(Point(order.longitude, order.latitude)):
        return True

    nearby_orders = get_nearby(order)
    if any("is_fraud" in nearby_order for nearby_order in nearby_orders):
        return True

    if any(
        nearby_order["suspected_fraud"] == "True"
        for nearby_order in nearby_orders
    ):
        return True

    return False


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/process/")
def process(order: Order) -> dict:
    suspected_fraud = is_suspected_fraud(order)

    order_id = str(uuid.uuid4())
    cache(order, order_id, suspected_fraud)

    return {"order_id": order_id, "accepted": not suspected_fraud}


@app.post("/update_fraud/")
def update_fraud(order_update: OrderUpdateFraud) -> None:
    redis_client = _get_redis_client()

    key = f"orders:{order_update.order_id}"
    if not redis_client.exists(key):
        return

    if order_update.is_fraud:
        redis_client.hset(key, "is_fraud", "True")
    else:
        redis_client.delete(key)


@app.get("/get_order")
def get_order(order_id: OrderId) -> dict:
    redis_client = _get_redis_client()
    order = redis_client.hgetall(f"orders:{order_id.order_id}")
    return {"order": order}


@app.delete("/delete_all_orders")
def delete_all_orders() -> None:
    redis_client = _get_redis_client()
    redis_client.flushall()
