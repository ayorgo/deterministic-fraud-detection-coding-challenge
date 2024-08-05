# TODO: Add docstrings

from datetime import datetime

import environ
import requests

env = environ.Env()

CONNECT_TIMEOUT = env.float("CONNECT_TIMEOUT", default=0.02)
READ_TIMEOUT = env.float("READ_TIMEOUT", default=5.0)


class Client:
    def __init__(
        self,
        base_url: str,
        connect_timeout: float = CONNECT_TIMEOUT,
        read_timeout: float = READ_TIMEOUT,
    ):
        self.base_url = base_url
        self._timeout = (connect_timeout, read_timeout)
        self.session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.session.close()

    def _request(self, method: str, url: str, **kwargs):
        kwargs["timeout"] = kwargs.get("timeout", self._timeout)
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response

    def health(self):
        url = f"{self.base_url}/health"
        response = self._request("GET", url)
        return response.json()

    def process_order(
        self,
        timestamp: datetime,
        longitude: float,
        latitude: float,
        fraud_score: float,
    ):
        url = f"{self.base_url}/process/"
        data = {
            "timestamp": timestamp.isoformat(),
            "longitude": longitude,
            "latitude": latitude,
            "fraud_score": fraud_score,
        }
        response = self._request("POST", url, json=data)
        return response.json()

    def update_fraud(self, order_id: str, is_fraud: bool):
        url = f"{self.base_url}/update_fraud/"
        data = {"order_id": order_id, "is_fraud": is_fraud}
        response = self._request("POST", url, json=data)
        return response.json()

    def get_order(self, order_id: str):
        url = f"{self.base_url}/get_order"
        data = {"order_id": order_id}
        response = self._request("GET", url, json=data)
        return response.json()

    def delete_all_orders(self):
        url = f"{self.base_url}/delete_all_orders"
        response = self._request("DELETE", url)
        return response.json()
