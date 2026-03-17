from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from time import sleep
from typing import Any

import httpx

from faultline.models import RawSignal

logger = logging.getLogger(__name__)


class SignalProvider(ABC):
    provider_name: str
    source_family: str
    enabled: bool = True

    @abstractmethod
    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        raise NotImplementedError


class ProviderError(RuntimeError):
    pass


class HTTPProvider(SignalProvider):
    base_url: str

    def __init__(
        self,
        *,
        timeout_seconds: float = 20.0,
        retries: int = 3,
        backoff_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.backoff_seconds = backoff_seconds
        self._transport = transport

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds, transport=self._transport) as client:
                    response = client.request(method, url, params=params, headers=headers, json=json_body)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:  # pragma: no cover
                logger.warning(
                    "HTTP %s from %s (attempt %d/%d): %s",
                    exc.response.status_code,
                    url,
                    attempt,
                    self.retries,
                    exc.response.text[:500],
                )
                last_error = exc
                if attempt == self.retries:
                    break
                retry_after = exc.response.headers.get("Retry-After")
                try:
                    retry_after_seconds = float(retry_after) if retry_after else 0.0
                except ValueError:
                    retry_after_seconds = 0.0
                delay = max(self.backoff_seconds * attempt, retry_after_seconds)
                if exc.response.status_code == 429:
                    delay = max(delay, 5.0)
                sleep(delay)
            except Exception as exc:  # pragma: no cover - exercised through provider tests
                logger.warning("Request error (attempt %d/%d): %s", attempt, self.retries, exc)
                last_error = exc
                if attempt == self.retries:
                    break
                sleep(self.backoff_seconds * attempt)
        raise ProviderError(str(last_error))
