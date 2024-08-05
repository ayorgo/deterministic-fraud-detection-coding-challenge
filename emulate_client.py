#!/usr/bin/env python

import time
from collections import deque
from datetime import datetime, timedelta
from typing import Deque

import pandas as pd

from client import Client


def format_time(time_seconds: float) -> str:
    minutes = int(time_seconds // 60)
    seconds = int(time_seconds % 60)
    return f"{minutes}m {seconds}s"


def log_progress(
    total: int, processed: int, rejected: int, accepted: int, elapsed_time: str
) -> None:
    print(
        f"Processed: {processed} ({processed/total:.2%}) | "
        f"Rejected: {rejected} ({rejected/total:.2%}) | "
        f"Accepted: {accepted} ({accepted/total:.2%}) | "
        f"Time: {elapsed_time}"
    )


def process_order(
    client: Client,
    order: pd.Series,
    deferred_fraud_updates: Deque,
    timestamp_now: datetime,
) -> tuple:
    response = client.process_order(
        timestamp_now,
        order["lon"],
        order["lat"],
        order["fraud_score"],
    )

    # If the order is accepted but fraudulent, we schedule
    # an update to mark it as fraud after 2 hours
    if response["accepted"]:
        if order["is_fraud"] == "True":
            deferred_fraud_updates.append(
                (
                    response["order_id"],
                    timestamp_now + timedelta(hours=2),
                )
            )
        return 1, 0
    return 0, 1


def emulate_client() -> None:
    df = pd.read_parquet("data/data.parquet")
    df = df.sort_values(by=["timestamp"])

    total = len(df)
    processed = rejected = accepted = 0
    deferred_fraud_updates = deque()
    with Client("http://service:8005") as client:
        start = time.time()
        for _, order in df.iterrows():
            # Update fraud status for fraudulent orders
            # that are now past the 2 hour mark
            timestamp_now = order["timestamp"].to_pydatetime()
            while (
                deferred_fraud_updates
                and deferred_fraud_updates[0][1] <= timestamp_now
            ):
                client.update_fraud(deferred_fraud_updates[0][0], True)
                deferred_fraud_updates.popleft()

            is_accepted, is_rejected = process_order(
                client, order, deferred_fraud_updates, timestamp_now
            )
            accepted += is_accepted
            rejected += is_rejected
            processed += 1

            elapsed = format_time(time.time() - start)
            if processed % 1000 == 0:
                log_progress(
                    total,
                    processed,
                    rejected,
                    accepted,
                    elapsed,
                )

        elapsed = format_time(time.time() - start)
        log_progress(
            total,
            processed,
            rejected,
            accepted,
            elapsed,
        )


if __name__ == "__main__":
    emulate_client()
