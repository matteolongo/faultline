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
