from __future__ import annotations

from faultline.models import FinalReport


def evaluate_report(report: FinalReport) -> dict[str, float]:
    situation_quality = 1.0 if report.situation and report.stage else 0.45
    mechanism_quality = min(1.0, len(report.mechanism_map) / 3)
    prediction_quality = min(1.0, len(report.scenario_map) / 4)
    action_quality = 1.0 if report.actions_now and report.exit_signals else 0.5
    explainability = min(1.0, (len(report.evidence) + len(report.references) + len(report.provenance)) / 10)
    overall = round(
        (situation_quality + mechanism_quality + prediction_quality + action_quality + explainability) / 5,
        3,
    )
    return {
        "situation_quality": round(situation_quality, 3),
        "mechanism_quality": round(mechanism_quality, 3),
        "prediction_quality": round(prediction_quality, 3),
        "action_quality": round(action_quality, 3),
        "explainability": round(explainability, 3),
        "overall": overall,
    }
