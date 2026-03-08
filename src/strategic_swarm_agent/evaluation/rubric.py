from __future__ import annotations

from strategic_swarm_agent.models import FinalReport


def evaluate_report(report: FinalReport) -> dict[str, float]:
    topology_quality = 1.0 if "Empire:" in report.system_topology and "Disruptor:" in report.system_topology else 0.4
    second_order_insight = min(1.0, len(report.ripple_map) / 8)
    opportunity_originality = 1.0 if any("indirect" in item.lower() or "picks-and-shovels" in item.lower() for item in report.execution_recommendations) else 0.55
    explainability = min(1.0, (len(report.provenance) + len(report.fragility_map)) / 10)
    overall = round((topology_quality + second_order_insight + opportunity_originality + explainability) / 4, 3)
    return {
        "topology_quality": round(topology_quality, 3),
        "second_order_insight": round(second_order_insight, 3),
        "opportunity_originality": round(opportunity_originality, 3),
        "explainability": round(explainability, 3),
        "overall": overall,
    }
