from __future__ import annotations

import json
import logging
import os
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class StructuredReasoner:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("FAULTLINE_LLM_MODEL", "gpt-4o-mini")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def refine_model(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        model_class: type[T],
        fallback: T,
    ) -> tuple[T, dict[str, Any]]:
        if not self.enabled:
            return fallback, {"llm_used": False, "llm_status": "disabled"}

        try:  # pragma: no cover - live network not exercised in tests
            client = self._build_client().with_structured_output(model_class)
            candidate = client.invoke(
                [
                    ("system", system_prompt),
                    ("human", json.dumps(user_payload, default=str)),
                ]
            )
            if isinstance(candidate, model_class):
                return candidate, {"llm_used": True, "llm_status": "ok"}
            return model_class.model_validate(candidate), {"llm_used": True, "llm_status": "ok"}
        except (ValidationError, ValueError, TypeError) as exc:
            logger.warning("Structured LLM validation failed (%s): %s", type(exc).__name__, exc)
            return fallback, {
                "llm_used": True,
                "llm_status": "fallback",
                "llm_error": str(exc),
            }
        except Exception as exc:  # pragma: no cover - network/runtime failures
            logger.warning("Structured LLM call failed (%s): %s", type(exc).__name__, exc)
            return fallback, {
                "llm_used": True,
                "llm_status": "fallback",
                "llm_error": str(exc),
            }

    def _build_client(self) -> ChatOpenAI:
        return ChatOpenAI(
            model=self.model,
            api_key=self.api_key,
            temperature=0,
            timeout=30,
        )
