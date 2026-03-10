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
    PortfolioPosition,
    Prediction,
    RelatedSituation,
    Relation,
    ScenarioPath,
    SignalEvent,
    SituationSnapshot,
    StageAssessment,
    StageTransitionWarning,
    WatchlistEntry,
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
ASYMMETRY_CONFIDENCE_MIN = 0.58
HIGH_CONFIDENCE_MIN = 0.74
STAGE_SEQUENCE = [stage["id"] for stage in load_stages()["stages"]]


def _calibration_by_type(calibration_signals: list[CalibrationSignal] | None) -> dict[str, CalibrationSignal]:
    return {item.prediction_type: item for item in (calibration_signals or [])}


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
    ) -> tuple[list[Prediction], list[ScenarioPath], list[StageTransitionWarning]]:
        calibration_index = _calibration_by_type(calibration_signals)
        incumbent = snapshot.key_actors[0].name if snapshot.key_actors else cluster.region
        challenger = snapshot.key_actors[1].name if len(snapshot.key_actors) > 1 else snapshot.system_under_pressure
        priors = self._prediction_priors(snapshot, cluster)
        affected_assets = self._affected_assets(cluster)
        mechanism_descriptor = snapshot.mechanisms[0].name if snapshot.mechanisms else snapshot.system_under_pressure
        predictions = [
            Prediction(
                prediction_type="actor_move",
                description=f"{incumbent} will respond by tightening control or repricing the defended surface.",
                rationale=f"{snapshot.stage.stage} stage plus {mechanism_descriptor} favors defensive repositioning.",
                time_horizon="1-4 weeks",
                related_actors=[incumbent, challenger],
                confidence=min(0.92, snapshot.confidence * 0.9),
                prior_evidence=priors,
            ),
            Prediction(
                prediction_type="narrative",
                description=f"The next narrative will shift from isolated event coverage toward {snapshot.system_under_pressure}.",
                rationale="The situation is moving from event description toward mechanism recognition.",
                time_horizon="days to weeks",
                related_actors=[incumbent],
                confidence=0.6 + cluster.agreement_score * 0.2,
                prior_evidence=priors,
            ),
        ]
        if cluster.source_families and "market" in cluster.source_families:
            predictions.append(
                Prediction(
                    prediction_type="asset_repricing",
                    description="Assets tied to flexibility and neutral infrastructure should outperform exposed incumbents.",
                    rationale="Cross-source confirmation plus market-linked signals imply repricing pressure.",
                    time_horizon="1-8 weeks",
                    affected_assets=affected_assets,
                    confidence=0.58 + cluster.cluster_strength * 0.2,
                    prior_evidence=priors,
                )
            )
        predictions.append(
            Prediction(
                prediction_type="timing_window",
                description="The useful decision window is before the mechanism becomes consensus narrative.",
                rationale="Stage progression compresses edge once the repricing story is obvious.",
                time_horizon="immediate",
                confidence=0.57 + cluster.novelty_score * 0.22,
                prior_evidence=priors,
            )
        )
        calibrated_predictions = [
            self._apply_calibration(item, calibration_index.get(item.prediction_type)) for item in predictions
        ]
        scenario_tree = self._scenario_tree(
            snapshot=snapshot,
            cluster=cluster,
            incumbent=incumbent,
            challenger=challenger,
            affected_assets=affected_assets,
            priors=priors,
        )
        calibrated_tree = [
            self._apply_scenario_calibration(item, calibration_index.get("asset_repricing")) for item in scenario_tree
        ]
        warnings = self._stage_transition_warnings(snapshot=snapshot, cluster=cluster, priors=priors)
        calibrated_warnings = [
            self._apply_warning_calibration(item, calibration_index.get("timing_window")) for item in warnings
        ]
        return calibrated_predictions, calibrated_tree, calibrated_warnings

    def _apply_calibration(self, prediction: Prediction, calibration: CalibrationSignal | None) -> Prediction:
        if calibration is None or calibration.sample_size == 0:
            return prediction.model_copy(update={"confidence_band": self._confidence_band(prediction.confidence)})
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
        return prediction.model_copy(
            update={
                "confidence": adjusted_confidence,
                "confidence_band": self._confidence_band(adjusted_confidence),
                "rationale": rationale,
            }
        )

    def _prediction_priors(self, snapshot: SituationSnapshot, cluster: EventCluster) -> list[str]:
        priors = [
            f"{cluster.agreement_score:.0%} cross-source agreement in current cluster.",
            f"{cluster.cluster_strength:.0%} cluster strength across {len(cluster.source_families)} source families.",
        ]
        if snapshot.mechanisms:
            priors.append(f"{snapshot.stage.stage} stage with mechanism {snapshot.mechanisms[0].name}.")
        else:
            priors.append(f"{snapshot.stage.stage} stage (no dominant mechanism identified yet).")
        if snapshot.evidence:
            priors.append(f"Lead evidence: {snapshot.evidence[0].title}.")
        return priors

    def _scenario_tree(
        self,
        *,
        snapshot: SituationSnapshot,
        cluster: EventCluster,
        incumbent: str,
        challenger: str,
        affected_assets: list[str],
        priors: list[str],
    ) -> list[ScenarioPath]:
        base_probability = min(0.72, 0.42 + cluster.agreement_score * 0.2 + cluster.cluster_strength * 0.15)
        acceleration_probability = min(0.5, 0.18 + cluster.novelty_score * 0.25)
        reversal_probability = max(0.14, 1.0 - (base_probability + acceleration_probability))
        branches = [
            ScenarioPath(
                name="Base case: controlled response with gradual repricing",
                branch_type="base_case",
                probability=base_probability,
                confidence_band=self._confidence_band(base_probability),
                trigger_signals=[priors[0], "Follow-up signals confirm defensive incumbent moves."],
                expected_moves=[
                    f"{incumbent} defends the core surface with repricing and tighter bundling.",
                    f"{challenger} keeps capturing edge use-cases while avoiding direct confrontation.",
                ],
                market_effects=[
                    "Relative outperformance persists for adaptable or neutral infrastructure names.",
                    f"Pressure remains on {', '.join(affected_assets[:1])} if execution weakens.",
                ],
                timeframe="1-8 weeks",
            ),
            ScenarioPath(
                name="Bull case: transition accelerates before incumbents adapt",
                branch_type="upside",
                probability=acceleration_probability,
                confidence_band=self._confidence_band(acceleration_probability),
                trigger_signals=[
                    "Additional alliance or distribution shifts toward open alternatives.",
                    "Narrative moves from debate to implementation urgency.",
                ],
                expected_moves=[
                    f"{challenger} coalition gains distribution and mindshare quickly.",
                    "Buyers increase migration pace and reduce tolerance for lock-in.",
                ],
                market_effects=["Fast repricing in beneficiaries and abrupt derating in lagging incumbents."],
                timeframe="days to 4 weeks",
            ),
            ScenarioPath(
                name="Bear case: incumbent restores stability and stalls transition",
                branch_type="downside",
                probability=reversal_probability,
                confidence_band=self._confidence_band(reversal_probability),
                trigger_signals=[
                    "Policy, procurement, or pricing terms blunt portability incentives.",
                    "Follow-up clusters narrow rather than broaden.",
                ],
                expected_moves=[
                    f"{incumbent} restores platform control and narrative legitimacy.",
                    "Challenger adoption slows outside early adopters.",
                ],
                market_effects=["Recent relative winners mean-revert; crowded thematic trades unwind."],
                timeframe="2-10 weeks",
            ),
        ]
        return self._normalize_scenario_probabilities(branches)

    def _normalize_scenario_probabilities(self, branches: list[ScenarioPath]) -> list[ScenarioPath]:
        total = sum(item.probability for item in branches)
        if total <= 0:
            return branches
        normalized = [item.model_copy(update={"probability": item.probability / total}) for item in branches]
        return sorted(normalized, key=lambda item: item.probability, reverse=True)

    def _stage_transition_warnings(
        self,
        *,
        snapshot: SituationSnapshot,
        cluster: EventCluster,
        priors: list[str],
    ) -> list[StageTransitionWarning]:
        warnings: list[StageTransitionWarning] = []
        next_stage = self._next_stage(snapshot.stage.stage)
        if next_stage:
            warnings.append(
                StageTransitionWarning(
                    from_stage=snapshot.stage.stage,
                    to_stage=next_stage,
                    trigger="Cross-source agreement and narrative convergence continue broadening.",
                    lead_time=self._lead_time(snapshot.stage.stage),
                    probability=min(0.9, 0.4 + cluster.agreement_score * 0.25 + cluster.novelty_score * 0.2),
                    rationale="When agreement broadens while novelty remains elevated, stage progression accelerates.",
                    evidence_refs=priors[:2],
                )
            )
        # Skip this warning if the standard next-stage progression already targets exhaustion_or_reversal
        # (i.e., for the repricing stage), to avoid emitting duplicate (from_stage, to_stage) warnings.
        if snapshot.stage.stage in {"open_contestation", "repricing"} and next_stage != "exhaustion_or_reversal":
            warnings.append(
                StageTransitionWarning(
                    from_stage=snapshot.stage.stage,
                    to_stage="exhaustion_or_reversal",
                    trigger="Incumbent response restores execution capacity faster than challengers can scale.",
                    lead_time="2-10 weeks",
                    probability=min(0.78, 0.22 + (1.0 - cluster.novelty_score) * 0.32 + cluster.cluster_strength * 0.2),
                    rationale="Late-stage contests often reverse if response capacity recovers before narrative lock-in.",
                    evidence_refs=priors[1:3],
                )
            )
        return warnings

    def _next_stage(self, stage: str) -> str | None:
        if stage not in STAGE_SEQUENCE:
            return None
        index = STAGE_SEQUENCE.index(stage)
        if index >= len(STAGE_SEQUENCE) - 1:
            return None
        return STAGE_SEQUENCE[index + 1]

    def _lead_time(self, stage: str) -> str:
        if stage in {"signal_emergence", "pattern_formation"}:
            return "1-6 weeks"
        if stage in {"strategic_positioning", "open_contestation"}:
            return "days to 4 weeks"
        if stage == "repricing":
            return "days to 2 weeks"
        return "2-8 weeks"

    def _apply_scenario_calibration(
        self,
        path: ScenarioPath,
        calibration: CalibrationSignal | None,
    ) -> ScenarioPath:
        if calibration is None or calibration.sample_size == 0:
            return path.model_copy(update={"confidence_band": self._confidence_band(path.probability)})
        adjustment = (calibration.confirmed_rate - calibration.unconfirmed_rate) * 0.05
        probability = max(0.05, min(0.9, path.probability + adjustment))
        return path.model_copy(
            update={"probability": probability, "confidence_band": self._confidence_band(probability)}
        )

    def _apply_warning_calibration(
        self,
        warning: StageTransitionWarning,
        calibration: CalibrationSignal | None,
    ) -> StageTransitionWarning:
        if calibration is None or calibration.sample_size == 0:
            return warning
        adjustment = (calibration.confirmed_rate - calibration.unconfirmed_rate) * 0.08
        probability = max(0.05, min(0.95, warning.probability + adjustment))
        return warning.model_copy(update={"probability": probability})

    def _confidence_band(self, confidence: float) -> str:
        if confidence >= HIGH_CONFIDENCE_MIN:
            return "high_confidence"
        if confidence >= ASYMMETRY_CONFIDENCE_MIN:
            return "asymmetric"
        return "speculative"

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
        self,
        snapshot: SituationSnapshot,
        predictions: list[Prediction],
        cluster: EventCluster,
        calibration_signals: list[CalibrationSignal] | None = None,
    ) -> list[MarketImplication]:
        calibration_index = _calibration_by_type(calibration_signals)
        tags = set(cluster.tags)
        if tags.intersection(TECH_OPEN_TAGS):
            implications = [
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
        elif "undersea" in tags or "chokepoint" in tags:
            implications = [
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
        else:
            implications = [
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
        return [self._apply_calibration(item, calibration_index) for item in implications]

    def _apply_calibration(
        self,
        implication: MarketImplication,
        calibration_index: dict[str, CalibrationSignal],
    ) -> MarketImplication:
        relevant_types = ["asset_repricing"]
        if implication.thesis_type == "high_confidence_opportunity":
            relevant_types.append("actor_move")
        deltas = []
        guidance = []
        for prediction_type in relevant_types:
            signal = calibration_index.get(prediction_type)
            if signal is None or signal.sample_size == 0:
                continue
            deltas.append(
                (signal.confirmed_rate - signal.unconfirmed_rate) * 0.08 + signal.average_confidence_delta * 0.3
            )
            guidance.append(signal.guidance)
        if not deltas:
            return implication
        adjusted_confidence = max(0.05, min(0.95, implication.confidence + (sum(deltas) / len(deltas))))
        return implication.model_copy(
            update={
                "confidence": adjusted_confidence,
                "rationale": f"{implication.rationale} Calibration: {' '.join(guidance[:2])}",
            }
        )


class ActionEngine:
    def generate(
        self,
        snapshot: SituationSnapshot,
        implications: list[MarketImplication],
        predictions: list[Prediction],
        calibration_signals: list[CalibrationSignal] | None = None,
        portfolio_positions: list[PortfolioPosition] | None = None,
        watchlist: list[WatchlistEntry] | None = None,
        stage_transition_warnings: list[StageTransitionWarning] | None = None,
    ) -> tuple[list[ActionRecommendation], list[ActionRecommendation], list[str]]:
        calibration_index = _calibration_by_type(calibration_signals)
        portfolio_positions = portfolio_positions or []
        watchlist = watchlist or []
        stage_transition_warnings = stage_transition_warnings or []
        actions: list[ActionRecommendation] = []
        exits: list[ActionRecommendation] = []
        endangered_symbols: list[str] = []
        for implication in implications:
            conviction = self._conviction_for(implication, calibration_index)
            if implication.thesis_type == "asymmetric_opportunity":
                actions.append(
                    ActionRecommendation(
                        action="watch" if conviction < 0.72 else "enter",
                        target=implication.target,
                        rationale=f"{implication.rationale} Calibrated conviction={conviction:.2f}.",
                        confidence=conviction,
                        urgency="medium" if conviction < 0.8 else "high",
                        thesis_type=implication.thesis_type,
                    )
                )
            else:
                action = "avoid" if implication.direction == "negative" and conviction < 0.68 else "enter"
                if implication.direction == "negative" and conviction < 0.6:
                    action = "watch"
                actions.append(
                    ActionRecommendation(
                        action=action,
                        target=implication.target,
                        rationale=f"{implication.rationale} Calibrated conviction={conviction:.2f}.",
                        confidence=conviction,
                        urgency="high" if conviction >= 0.72 else "medium",
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
                    confidence=max(0.35, conviction - 0.08),
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
        portfolio_actions = self._portfolio_actions(portfolio_positions, implications, calibration_index)
        actions.extend(portfolio_actions)
        exits.extend([item for item in portfolio_actions if item.action in {"trim", "exit"}])
        watchlist_actions = self._watchlist_actions(watchlist, implications, calibration_index)
        actions.extend(watchlist_actions)
        exits.extend([item for item in watchlist_actions if item.action in {"avoid", "trim", "exit"}])
        warning_actions, warning_exits = self._warning_actions(snapshot, stage_transition_warnings)
        actions.extend(warning_actions)
        exits.extend(warning_exits)
        endangered_symbols.extend(self._endangered_symbols(portfolio_positions, implications, calibration_index))
        return actions, exits, sorted(set(endangered_symbols))

    def _conviction_for(
        self,
        implication: MarketImplication,
        calibration_index: dict[str, CalibrationSignal],
    ) -> float:
        relevant_type = "asset_repricing"
        signal = calibration_index.get(relevant_type)
        if signal is None or signal.sample_size == 0:
            return implication.confidence
        adjustment = (signal.confirmed_rate - signal.unconfirmed_rate) * 0.1 + signal.average_confidence_delta * 0.35
        return max(0.05, min(0.95, implication.confidence + adjustment))

    def _portfolio_actions(
        self,
        positions: list[PortfolioPosition],
        implications: list[MarketImplication],
        calibration_index: dict[str, CalibrationSignal],
    ) -> list[ActionRecommendation]:
        actions: list[ActionRecommendation] = []
        for position in positions:
            relevant = [
                item
                for item in implications
                if self._matches(item.target, position.symbol, position.tags, default_generic=True)
            ]
            if not relevant:
                continue
            worst_negative = max(
                (
                    self._conviction_for(item, calibration_index)
                    for item in relevant
                    if item.direction == "negative" and position.direction == "long"
                ),
                default=0.0,
            )
            if worst_negative >= 0.72:
                actions.append(
                    ActionRecommendation(
                        action="exit",
                        target=position.symbol,
                        rationale="Held symbol is exposed to a high-conviction negative implication.",
                        confidence=worst_negative,
                        urgency="high",
                        thesis_type="portfolio_position",
                    )
                )
            elif worst_negative >= 0.55:
                actions.append(
                    ActionRecommendation(
                        action="trim",
                        target=position.symbol,
                        rationale="Held symbol is exposed to medium-conviction downside pressure.",
                        confidence=worst_negative,
                        urgency="medium",
                        thesis_type="portfolio_position",
                    )
                )
        return actions

    def _watchlist_actions(
        self,
        watchlist: list[WatchlistEntry],
        implications: list[MarketImplication],
        calibration_index: dict[str, CalibrationSignal],
    ) -> list[ActionRecommendation]:
        actions: list[ActionRecommendation] = []
        for item in watchlist:
            relevant = [imp for imp in implications if self._matches(imp.target, item.symbol, item.tags)]
            if not relevant:
                continue
            best = max(relevant, key=lambda imp: self._conviction_for(imp, calibration_index))
            conviction = self._conviction_for(best, calibration_index)
            if best.direction == "positive":
                action = "enter" if conviction >= 0.72 else "watch"
            else:
                action = "avoid" if conviction >= 0.65 else "watch"
            actions.append(
                ActionRecommendation(
                    action=action,
                    target=item.symbol,
                    rationale=f"Watchlist symbol mapped to {best.target} ({best.direction}) with conviction {conviction:.2f}.",
                    confidence=conviction,
                    urgency="medium" if conviction < 0.8 else "high",
                    thesis_type="watchlist_symbol",
                )
            )
        return actions

    def _endangered_symbols(
        self,
        positions: list[PortfolioPosition],
        implications: list[MarketImplication],
        calibration_index: dict[str, CalibrationSignal],
    ) -> list[str]:
        endangered: list[str] = []
        for position in positions:
            relevant_negative = [
                self._conviction_for(item, calibration_index)
                for item in implications
                if self._matches(item.target, position.symbol, position.tags, default_generic=True)
                and item.direction == "negative"
                and position.direction == "long"
            ]
            if relevant_negative and max(relevant_negative) >= 0.6:
                endangered.append(position.symbol)
        return endangered

    def _matches(self, target: str, symbol: str, tags: list[str], default_generic: bool = False) -> bool:
        hay = target.lower()
        if symbol.lower() in hay:
            return True
        if any(tag.lower() in hay for tag in tags):
            return True
        if default_generic and any(token in hay for token in {"incumbent", "exposed", "beneficiaries", "enablers"}):
            return True
        return False

    def _warning_actions(
        self,
        snapshot: SituationSnapshot,
        warnings: list[StageTransitionWarning],
    ) -> tuple[list[ActionRecommendation], list[ActionRecommendation]]:
        actions: list[ActionRecommendation] = []
        exits: list[ActionRecommendation] = []
        for warning in warnings:
            if warning.probability < 0.6:
                continue
            action = "trim" if warning.probability >= 0.72 else "watch"
            recommendation = ActionRecommendation(
                action=action,
                target=snapshot.system_under_pressure,
                rationale=(
                    f"Stage-transition risk {warning.from_stage}->{warning.to_stage} in {warning.lead_time}. "
                    f"Trigger: {warning.trigger}"
                ),
                confidence=warning.probability,
                urgency="high" if warning.probability >= 0.72 else "medium",
                thesis_type="stage_transition_warning",
            )
            actions.append(recommendation)
            if action == "trim":
                exits.append(
                    ActionRecommendation(
                        action="trim",
                        target=snapshot.system_under_pressure,
                        rationale=f"Reduce gross exposure before {warning.to_stage} risk fully prices in.",
                        confidence=max(0.35, warning.probability - 0.05),
                        urgency="high",
                        thesis_type="stage_transition_warning",
                    )
                )
        return actions, exits
