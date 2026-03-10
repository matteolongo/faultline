from faultline.llm.backend import StructuredReasoner
from faultline.models import AbstractPattern


def test_structured_reasoner_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reasoner = StructuredReasoner()
    fallback = AbstractPattern(
        pattern_name="Monolith vs Protocol",
        empire_type="Integrated incumbent",
        disruptor_type="Open protocol",
        asymmetry_type="Open ecosystem erodes proprietary moat",
        empire_actor="Closed Suite",
        disruptor_actor="Open Collective",
        cheap_weapon="Open distribution",
        armor_breach="Pricing power weakens",
        historical_analogs=[],
        explanation="Fallback object.",
        confidence=0.7,
    )
    result, diagnostics = reasoner.refine_model(
        system_prompt="Return JSON.",
        user_payload={"fallback": fallback.model_dump(mode="json")},
        model_class=AbstractPattern,
        fallback=fallback,
    )
    assert result == fallback
    assert diagnostics["llm_status"] == "disabled"
