from faultline.llm.backend import StructuredReasoner
from faultline.models import Prediction


def test_structured_reasoner_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reasoner = StructuredReasoner()
    fallback = Prediction(
        prediction_type="actor_move",
        description="Incumbent cuts price to defend share.",
        rationale="Fallback object.",
        time_horizon="1-4 weeks",
        related_actors=["Incumbent", "Challenger"],
        confidence=0.7,
    )
    result, diagnostics = reasoner.refine_model(
        system_prompt="Return JSON.",
        user_payload={"fallback": fallback.model_dump(mode="json")},
        model_class=Prediction,
        fallback=fallback,
    )
    assert result == fallback
    assert diagnostics["llm_status"] == "disabled"


def test_structured_reasoner_uses_langchain_client(monkeypatch) -> None:
    class _FakeStructuredClient:
        def invoke(self, _messages):
            return {
                "prediction_type": "actor_move",
                "description": "Incumbent cuts price to defend share.",
                "rationale": "Returned from structured client.",
                "time_horizon": "1-4 weeks",
                "related_actors": ["Incumbent", "Challenger"],
                "confidence": 0.7,
            }

    class _FakeClient:
        def with_structured_output(self, _model_class):
            return _FakeStructuredClient()

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    reasoner = StructuredReasoner()
    monkeypatch.setattr(reasoner, "_build_client", lambda: _FakeClient())
    fallback = Prediction(
        prediction_type="actor_move",
        description="Fallback",
        rationale="Fallback object.",
        time_horizon="1-4 weeks",
        related_actors=["Incumbent", "Challenger"],
        confidence=0.5,
    )

    result, diagnostics = reasoner.refine_model(
        system_prompt="Return JSON.",
        user_payload={"topic": "pricing pressure"},
        model_class=Prediction,
        fallback=fallback,
    )

    assert result.description == "Incumbent cuts price to defend share."
    assert diagnostics["llm_status"] == "ok"
