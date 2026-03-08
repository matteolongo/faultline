from __future__ import annotations

import json
import os
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class StructuredReasoner:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("SWARM_LLM_MODEL", "gpt-4.1-mini")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def refine_model(self, *, system_prompt: str, user_payload: dict[str, Any], model_class: type[T], fallback: T) -> tuple[T, dict[str, Any]]:
        if not self.enabled:
            return fallback, {"llm_used": False, "llm_status": "disabled"}
        schema = model_class.model_json_schema()
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
            return fallback, {"llm_used": True, "llm_status": "fallback", "llm_error": str(exc)}
