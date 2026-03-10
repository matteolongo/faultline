from __future__ import annotations

from faultline.models import (
    EventCluster,
    OpportunityIdea,
    ReviewedOpportunity,
)
from faultline.utils.config import load_scoring_config


class ExecutionCritic:
    def __init__(self) -> None:
        scoring = load_scoring_config()
        self.weak_convexity = scoring["thresholds"]["weak_convexity"]
        self.crowded_trade = scoring["thresholds"]["crowded_trade"]

    def review(self, ideas: list[OpportunityIdea], cluster: EventCluster) -> list[ReviewedOpportunity]:
        reviewed = []
        for idea in ideas:
            rejection_reasons = []
            if idea.convexity_score.value < self.weak_convexity:
                rejection_reasons.append("Convexity is too weak for the structural thesis.")
            if idea.crowdedness_risk > self.crowded_trade:
                rejection_reasons.append("The expression looks too crowded or too obvious.")
            if idea.directness == "direct":
                rejection_reasons.append("Direct headline exposure is usually too linear for this system.")
            if len(cluster.source_families) < 2:
                rejection_reasons.append("Cross-source agreement is too weak to surface an execution thesis.")
            approved = not rejection_reasons
            summary = (
                "Approved because it captures indirect nonlinear upside with explicit invalidation."
                if approved
                else "Rejected because the expression is too linear, crowded, or weakly asymmetric."
            )
            risk_notes = [
                f"Timing horizon: {idea.time_horizon}.",
                f"Crowdedness risk: {idea.crowdedness_risk:.2f}.",
                f"Convexity score: {idea.convexity_score.value:.2f}.",
            ]
            reviewed.append(
                ReviewedOpportunity(
                    idea=idea,
                    approved=approved,
                    review_summary=summary,
                    rejection_reasons=rejection_reasons,
                    risk_notes=risk_notes,
                )
            )
        return reviewed
