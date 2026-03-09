from __future__ import annotations

import json
import logging
import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


def _enforce_additional_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """Recursively enforce OpenAI structured output schema requirements:
    - additionalProperties: false on every object
    - required must list every key in properties (no optional fields)

    Pydantic generates optional fields as missing from 'required'. OpenAI rejects this.
    We set required = list(properties.keys()) on every object node.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            schema.setdefault("additionalProperties", False)
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
        for value in schema.values():
            if isinstance(value, dict):
                _enforce_additional_properties(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _enforce_additional_properties(item)
    return schema


class StructuredReasoner:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("SWARM_LLM_MODEL", "gpt-4o-mini")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def refine_model(self, *, system_prompt: str, user_payload: dict[str, Any], model_class: type[T], fallback: T) -> tuple[T, dict[str, Any]]:
        if not self.enabled:
            return fallback, {"llm_used": False, "llm_status": "disabled"}
        schema = _enforce_additional_properties(model_class.model_json_schema())
        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, default=str)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": model_class.__name__,
                    "schema": schema,
                }
            },
        }
        try:  # pragma: no cover - live network not exercised in tests
            response = httpx.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30.0,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("output_text")
            if not content:
                for item in payload.get("output", []):
                    for piece in item.get("content", []):
                        if piece.get("type") == "output_text":
                            content = piece.get("text")
                            break
            if not content:
                return fallback, {"llm_used": True, "llm_status": "empty_response"}
            candidate = model_class.model_validate_json(content)
            return candidate, {"llm_used": True, "llm_status": "ok"}
        except (httpx.HTTPError, ValidationError, json.JSONDecodeError) as exc:
            error_body: str | None = None
            if isinstance(exc, httpx.HTTPStatusError):
                error_body = exc.response.text[:1000]
                logger.warning("OpenAI API %s: %s", exc.response.status_code, error_body)
            else:
                logger.warning("LLM call failed (%s): %s", type(exc).__name__, exc)
            diag: dict[str, Any] = {"llm_used": True, "llm_status": "fallback", "llm_error": str(exc)}
            if error_body:
                diag["llm_error_body"] = error_body
            return fallback, diag
