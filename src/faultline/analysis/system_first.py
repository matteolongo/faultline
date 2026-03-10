from __future__ import annotations

from collections import Counter

from faultline.models import (
    ActionRecommendation,
    Actor,
    CalibrationSignal,
    EventCluster,
    EvidenceItem,
    Force,
    MarketImplication,
    Mechanism,
    Prediction,
    RelatedSituation,
    Relation,
    SignalEvent,
    SituationSnapshot,
    StageAssessment,
)
from faultline.utils.config import load_mechanisms, load_stages

COMPETITION_TAGS = {
    "pricing-power",
    "margin-pressure",
    "developer-flight",
    "commoditization",
    "market-stress",
    "competition",
}
ALLIANCE_TAGS = {
    "alliance",
    "coalition",
    "procurement",
    "portability",
}
CONSTRAINT_TAGS = {
    "debt",
    "refinancing",
    "regulation",
    "pricing-power",
    "sabotage",
    "chokepoint",
    "supply-strain",
}
TECH_OPEN_TAGS = {"open-source", "protocol", "portability", "plugin-ecosystem", "developer-tools"}
FINANCIAL_STRESS_TAGS = {"debt", "refinancing", "spread-widening", "market-stress", "cloud-spend"}


class MechanismAnalyzer:
    def __init__(self) -> None:
        self.config = load_mechanisms()["mechanisms"]

    def infer(self, cluster: EventCluster, events: list[SignalEvent]) -> list[Mechanism]:
        tag_pool = set(cluster.tags)
        inferred: list[Mechanism] = []
        for item in self.config:
            matched = sorted(tag_pool.intersection(set(item["trigger_tags"])))
            if not matched:
                continue
            inferred.append(
                Mechanism(
                    mechanism_id=item["id"],
                    name=item["name"],
                    explanation=item["explanation"],
                    evidence_refs=[event.raw_payload_reference for event in events[:2]],
                    confidence=min(0.92, 0.45 + len(matched) * 0.1 + cluster.agreement_score * 0.15),
                )
            )
        if inferred:
            return inferred
        return [
            Mechanism(
                mechanism_id="timing_mismatch",
                name="Timing Mismatch",
                explanation="The situation shows uneven adaptation speeds even if tags are sparse.",
                evidence_refs=[event.raw_payload_reference for event in events[:2]],
                confidence=0.42,
            )
        ]


class SituationMapper:
    def __init__(self) -> None:
        self.mechanisms = MechanismAnalyzer()
        self.stage_config = load_stages()["stages"]

    def map(
        self,
        cluster: EventCluster,
        events: list[SignalEvent],
        related_situations: list[RelatedSituation] | None = None,
    ) -> SituationSnapshot:
        related_situations = related_situations or []
        key_actors = self._build_actors(cluster, events)
        relations = self._build_relations(cluster, key_actors)
        mechanisms = self.mechanisms.infer(cluster, events)
        stage = self._assess_stage(cluster, mechanisms)
        evidence = [
            EvidenceItem(
                signal_id=event.id,
                title=event.title,
                summary=event.summary,
                source=event.source,
                source_url=event.source_url,
                rationale=f"Supports {stage.stage} stage and {mechanisms[0].name} mechanism.",
            )
            for event in events[:3]
        ]
        system_under_pressure = self._infer_system(cluster)
        return SituationSnapshot(
            situation_id=cluster.cluster_id,
            title=cluster.canonical_title,
            summary=cluster.summary,
            domain=self._infer_domain(cluster),
            system_under_pressure=system_under_pressure,
            key_actors=key_actors,
            forces=self._build_forces(cluster, key_actors, mechanisms, related_situations),
            relations=relations,
            mechanisms=mechanisms,
            stage=stage,
            risks=self._build_risks(cluster, mechanisms),
            evidence=evidence,
            confidence=min(0.95, 0.45 + cluster.cluster_strength * 0.35 + cluster.agreement_score * 0.2),
        )

    def _infer_domain(self, cluster: EventCluster) -> str:
        tags = set(cluster.tags)
        if tags.intersection(TECH_OPEN_TAGS):
            return "organization"
        if tags.intersection(FINANCIAL_STRESS_TAGS):
            return "macro_market"
        return "complex_system"

    def _infer_system(self, cluster: EventCluster) -> str:
        tags = set(cluster.tags)
        if tags.intersection(TECH_OPEN_TAGS):
            return "software platform competition"
        if "undersea" in tags or "chokepoint" in tags:
            return "strategic infrastructure routing"
        if tags.intersection(FINANCIAL_STRESS_TAGS):
            return "capital allocation and balance-sheet defense"
        return f"{cluster.region} coordination system"

    def _build_actors(self, cluster: EventCluster, events: list[SignalEvent]) -> list[Actor]:
        counts = Counter(entity for event in events for entity in event.entities)
        actors: list[Actor] = []
        tags = set(cluster.tags)
        for index, (name, _) in enumerate(counts.most_common(4)):
            role = "incumbent" if index == 0 else "challenger"
            if index > 1:
                role = "ally" if tags.intersection(ALLIANCE_TAGS) else "counterparty"
            actors.append(
                Actor(
                    name=name,
                    role=role,
                    objectives=self._objectives_for(name, tags, role),
                    constraints=self._constraints_for(tags),
                    resources=self._resources_for(tags, role),
                    alliances=[actor.name for actor in actors[:1]] if role in {"ally", "counterparty"} else [],
                    narrative_position=self._narrative_position(role, tags),
                    adaptability=0.72 if role == "challenger" else 0.48,
                    influence=0.75 if role == "incumbent" else 0.58,
                )
            )
        if actors:
            return actors
        return [
            Actor(
                name=cluster.region,
                role="participant",
                objectives=["Preserve system stability"],
                constraints=self._constraints_for(tags),
                resources=["attention"],
            )
        ]

    def _build_relations(self, cluster: EventCluster, actors: list[Actor]) -> list[Relation]:
        if len(actors) < 2:
            return []
        tags = set(cluster.tags)
        relation_type = "alliance" if tags.intersection(ALLIANCE_TAGS) else "competition"
        description = (
            "Actors are repositioning around the same system pressure."
            if relation_type == "alliance"
            else "Actors are contesting control, pricing, or legitimacy."
        )
        relations = [
            Relation(
                relation_type=relation_type,
                source_actor=actors[0].name,
                target_actor=actors[1].name,
                description=description,
                strength=min(0.9, 0.45 + cluster.agreement_score * 0.3),
            )
        ]
        if len(actors) > 2:
            relations.append(
                Relation(
                    relation_type="leverage",
                    source_actor=actors[2].name,
                    target_actor=actors[0].name,
                    description="Third-party actor can amplify or constrain the main contest.",
                    strength=0.52,
                )
            )
        return relations

    def _build_forces(
        self,
        cluster: EventCluster,
        actors: list[Actor],
        mechanisms: list[Mechanism],
        related_situations: list[RelatedSituation],
    ) -> list[Force]:
        tags = set(cluster.tags)
        return [
            Force(
                force_type="power",
                description=f"{actors[0].name if actors else cluster.region} still controls the largest visible surface.",
                strength=min(0.95, 0.5 + cluster.cluster_strength * 0.3),
                directional_bias="incumbent",
            ),
            Force(
                force_type="constraints",
                description=self._constraint_force(tags),
                strength=min(0.95, 0.35 + len(tags.intersection(CONSTRAINT_TAGS)) * 0.12),
                directional_bias="challenger" if tags.intersection(TECH_OPEN_TAGS) else "mixed",
            ),
            Force(
                force_type="alliances",
                description="Coalitions, buyers, or third parties are part of the outcome path.",
                strength=min(0.95, 0.45 + len(related_situations) * 0.08),
                directional_bias="mixed",
            ),
            Force(
                force_type="resources",
                description=f"Resources are being redirected through {mechanisms[0].name.lower()}.",
                strength=0.5 + cluster.agreement_score * 0.2,
                directional_bias="reallocating",
            ),
            Force(
                force_type="timing",
                description="Adaptation speed matters more than static size in the current phase.",
                strength=min(0.95, 0.45 + cluster.novelty_score * 0.35),
                directional_bias="fast_adapters",
            ),
        ]

    def _build_risks(self, cluster: EventCluster, mechanisms: list[Mechanism]) -> list[str]:
        risks = [
            "The visible signals may describe positioning rather than a durable shift.",
            "A stronger incumbent response could interrupt the current mechanism.",
        ]
        if any(item.mechanism_id == "reputation_spiral" for item in mechanisms):
            risks.append("Narrative damage may reverse quickly if the next news cycle changes focus.")
        if "market-stress" in cluster.tags:
            risks.append("Market reaction may front-run the thesis before the real structural change is confirmed.")
        return risks

    def _assess_stage(self, cluster: EventCluster, mechanisms: list[Mechanism]) -> StageAssessment:
        tags = set(cluster.tags)
        stage = "signal_emergence"
        explanation = "Signals are emerging but not yet broad enough to imply repricing."
        if "market-stress" in tags or "cloud-spend" in tags:
            stage = "repricing"
            explanation = (
                "Market-linked evidence suggests the structural tension is already affecting valuations or budgets."
            )
        elif cluster.agreement_score > 0.7 and len(mechanisms) >= 2:
            stage = "strategic_positioning"
            explanation = "Actors and counterparties are adjusting before a full open confrontation."
        elif cluster.cluster_strength > 0.7:
            stage = "pattern_formation"
            explanation = "The signals cohere into a recurring mechanism rather than a one-off event."
        valid_stages = {item["id"] for item in self.stage_config}
        if stage not in valid_stages:
            stage = "signal_emergence"
        return StageAssessment(stage=stage, explanation=explanation, confidence=0.55 + cluster.cluster_strength * 0.25)

    def _objectives_for(self, name: str, tags: set[str], role: str) -> list[str]:
        if role == "incumbent":
            return ["Defend position", "Preserve pricing power", f"Keep {name} central to the system"]
        if tags.intersection(TECH_OPEN_TAGS):
            return ["Expand adoption", "Increase portability", "Exploit incumbent rigidity"]
        return ["Gain leverage", "Reposition before the next stage", "Reduce exposure"]

    def _constraints_for(self, tags: set[str]) -> list[str]:
        matched = sorted(tags.intersection(CONSTRAINT_TAGS))
        if matched:
            return [f"Constraint from {tag.replace('-', ' ')}" for tag in matched[:3]]
        return ["Limited clarity", "Response timing uncertainty"]

    def _resources_for(self, tags: set[str], role: str) -> list[str]:
        base = ["attention", "distribution", "capital"]
        if role == "challenger" and tags.intersection(TECH_OPEN_TAGS):
            base.append("open ecosystem velocity")
        if tags.intersection(FINANCIAL_STRESS_TAGS):
            base.append("balance sheet")
        return base

    def _narrative_position(self, role: str, tags: set[str]) -> str:
        if role == "incumbent":
            return "defending legitimacy" if "reputation" in tags or "backlash" in tags else "defending stability"
        return "claiming adaptability"

    def _constraint_force(self, tags: set[str]) -> str:
        matched = sorted(tags.intersection(CONSTRAINT_TAGS))
        if matched:
            return f"Constraints are concentrated around {', '.join(matched[:3]).replace('-', ' ')}."
        return "Constraints are emerging through coordination and timing friction."


class PredictionEngine:
    def predict(
        self,
        snapshot: SituationSnapshot,
        cluster: EventCluster,
        calibration_signals: list[CalibrationSignal] | None = None,
    ) -> list[Prediction]:
        calibration_index = {item.prediction_type: item for item in (calibration_signals or [])}
        incumbent = snapshot.key_actors[0].name if snapshot.key_actors else cluster.region
        challenger = snapshot.key_actors[1].name if len(snapshot.key_actors) > 1 else snapshot.system_under_pressure
        predictions = [
            Prediction(
                prediction_type="actor_move",
                description=f"{incumbent} will respond by tightening control or repricing the defended surface.",
                rationale=f"{snapshot.stage.stage} stage plus {snapshot.mechanisms[0].name} favors defensive repositioning.",
                time_horizon="1-4 weeks",
                related_actors=[incumbent, challenger],
                confidence=min(0.92, snapshot.confidence * 0.9),
            ),
            Prediction(
                prediction_type="narrative",
                description=f"The next narrative will shift from isolated event coverage toward {snapshot.system_under_pressure}.",
                rationale="The situation is moving from event description toward mechanism recognition.",
                time_horizon="days to weeks",
                related_actors=[incumbent],
                confidence=0.6 + cluster.agreement_score * 0.2,
            ),
        ]
        if cluster.source_families and "market" in cluster.source_families:
            predictions.append(
                Prediction(
                    prediction_type="asset_repricing",
                    description="Assets tied to flexibility and neutral infrastructure should outperform exposed incumbents.",
                    rationale="Cross-source confirmation plus market-linked signals imply repricing pressure.",
                    time_horizon="1-8 weeks",
                    affected_assets=self._affected_assets(cluster),
                    confidence=0.58 + cluster.cluster_strength * 0.2,
                )
            )
        predictions.append(
            Prediction(
                prediction_type="timing_window",
                description="The useful decision window is before the mechanism becomes consensus narrative.",
                rationale="Stage progression compresses edge once the repricing story is obvious.",
                time_horizon="immediate",
                confidence=0.57 + cluster.novelty_score * 0.22,
            )
        )
        return [self._apply_calibration(item, calibration_index.get(item.prediction_type)) for item in predictions]

    def _apply_calibration(self, prediction: Prediction, calibration: CalibrationSignal | None) -> Prediction:
        if calibration is None or calibration.sample_size == 0:
            return prediction
        adjusted_confidence = max(
            0.05,
            min(
                0.95,
                prediction.confidence
                + (calibration.confirmed_rate - calibration.unconfirmed_rate) * 0.08
                + calibration.average_confidence_delta * 0.35,
            ),
        )
        rationale = f"{prediction.rationale} Calibration: {calibration.guidance}"
        return prediction.model_copy(update={"confidence": adjusted_confidence, "rationale": rationale})

    def _affected_assets(self, cluster: EventCluster) -> list[str]:
        tags = set(cluster.tags)
        if tags.intersection(TECH_OPEN_TAGS):
            return ["open ecosystem enablers", "bundled incumbents"]
        if "undersea" in tags or "chokepoint" in tags:
            return ["routing alternatives", "defensive infrastructure operators"]
        if tags.intersection(FINANCIAL_STRESS_TAGS):
            return ["funding-sensitive equities", "capital-light beneficiaries"]
        return [cluster.region]


class MarketMapper:
    def map(
        self, snapshot: SituationSnapshot, predictions: list[Prediction], cluster: EventCluster
    ) -> list[MarketImplication]:
        tags = set(cluster.tags)
        if tags.intersection(TECH_OPEN_TAGS):
            return [
                MarketImplication(
                    target="Open ecosystem enablers",
                    direction="positive",
                    thesis_type="asymmetric_opportunity",
                    rationale="Portability and interoperability benefit from platform bypass before consensus fully catches up.",
                    time_horizon="1-3 months",
                    confidence=0.72,
                    references=[item.title for item in snapshot.evidence[:2]],
                ),
                MarketImplication(
                    target="Bundled AI incumbents",
                    direction="negative",
                    thesis_type="high_confidence_opportunity",
                    rationale="Defensive repricing and margin pressure are already visible in the evidence set.",
                    time_horizon="2-8 weeks",
                    confidence=0.76,
                    references=[item.title for item in snapshot.evidence[:2]],
                ),
            ]
        if "undersea" in tags or "chokepoint" in tags:
            return [
                MarketImplication(
                    target="Alternative routing and monitoring plays",
                    direction="positive",
                    thesis_type="asymmetric_opportunity",
                    rationale="The market may underprice the value of bypass capacity until repeated disruption makes it obvious.",
                    time_horizon="1-6 months",
                    confidence=0.68,
                    references=[item.title for item in snapshot.evidence[:2]],
                )
            ]
        return [
            MarketImplication(
                target="Exposed incumbents",
                direction="negative",
                thesis_type="high_confidence_opportunity",
                rationale="The current mechanism points to pressured execution capacity and weaker platform position.",
                time_horizon="2-6 weeks",
                confidence=0.61,
                references=[item.title for item in snapshot.evidence[:2]],
            )
        ]


class ActionEngine:
    def generate(
        self,
        snapshot: SituationSnapshot,
        implications: list[MarketImplication],
        predictions: list[Prediction],
    ) -> tuple[list[ActionRecommendation], list[ActionRecommendation]]:
        actions: list[ActionRecommendation] = []
        exits: list[ActionRecommendation] = []
        for implication in implications:
            if implication.thesis_type == "asymmetric_opportunity":
                actions.append(
                    ActionRecommendation(
                        action="watch" if implication.confidence < 0.7 else "enter",
                        target=implication.target,
                        rationale=implication.rationale,
                        confidence=implication.confidence,
                        urgency="medium",
                        thesis_type=implication.thesis_type,
                    )
                )
            else:
                action = "avoid" if implication.direction == "negative" else "enter"
                actions.append(
                    ActionRecommendation(
                        action=action,
                        target=implication.target,
                        rationale=implication.rationale,
                        confidence=implication.confidence,
                        urgency="high" if implication.confidence >= 0.72 else "medium",
                        thesis_type=implication.thesis_type,
                    )
                )
            exits.append(
                ActionRecommendation(
                    action="exit" if implication.direction == "negative" else "trim",
                    target=implication.target,
                    rationale=(
                        "Leave or reduce exposure if the incumbent response restores stability "
                        "or if follow-up signals fail to confirm the mechanism."
                    ),
                    confidence=max(0.5, implication.confidence - 0.05),
                    urgency="medium",
                    thesis_type=implication.thesis_type,
                )
            )
        if not implications:
            actions.append(
                ActionRecommendation(
                    action="watch",
                    target=snapshot.system_under_pressure,
                    rationale="The structure matters, but the market translation is still weak.",
                    confidence=0.4,
                )
            )
        return actions, exits
