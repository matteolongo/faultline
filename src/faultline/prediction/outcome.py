from __future__ import annotations

import re

from faultline.models import OutcomeRecord, Prediction, RawSignal

ACTOR_MOVE_KEYWORDS = {
    "respond",
    "response",
    "retaliate",
    "retaliation",
    "defend",
    "defense",
    "discount",
    "tighten",
    "cut",
    "hedge",
    "repricing",
    "counter",
}
NARRATIVE_KEYWORDS = {
    "pressure",
    "bypass",
    "portability",
    "legitimacy",
    "pricing",
    "fragility",
    "platform",
    "system",
}
POSITIVE_REPRICING_KEYWORDS = {"outperform", "gain", "rises", "surges", "premium", "benefit", "demand"}
NEGATIVE_REPRICING_KEYWORDS = {"drops", "falls", "cuts", "weakens", "stress", "pressure", "decline"}


class OutcomeEvaluator:
    def score(self, predictions: list[Prediction], followup_signals: list[RawSignal]) -> list[OutcomeRecord]:
        if not predictions:
            return []
        return [self._score_prediction(prediction, followup_signals) for prediction in predictions]

    def _score_prediction(self, prediction: Prediction, signals: list[RawSignal]) -> OutcomeRecord:
        matcher = {
            "actor_move": self._score_actor_move,
            "narrative": self._score_narrative,
            "asset_repricing": self._score_asset_repricing,
            "timing_window": self._score_timing_window,
        }.get(prediction.prediction_type, self._score_generic)
        status, explanation, confidence_delta, signal_ids = matcher(prediction, signals)
        target = ", ".join(prediction.affected_assets or prediction.related_actors or ["system"])
        return OutcomeRecord(
            prediction_id=prediction.prediction_id or "unknown",
            prediction_type=prediction.prediction_type,
            target=target,
            outcome_status=status,
            explanation=explanation,
            confidence_delta=confidence_delta,
            supporting_signal_ids=signal_ids,
        )

    def _score_actor_move(self, prediction: Prediction, signals: list[RawSignal]) -> tuple[str, str, float, list[str]]:
        matched = self._matching_signals(signals, prediction.related_actors, ACTOR_MOVE_KEYWORDS)
        if matched:
            return (
                "confirmed",
                "Follow-up coverage shows actor behavior consistent with the predicted defensive or strategic move.",
                0.18,
                [signal.id for signal in matched[:3]],
            )
        related_actor_signals = self._matching_signals(signals, prediction.related_actors, set())
        if related_actor_signals:
            return (
                "partial",
                "Related actors stayed in the story, but the expected move is not clearly confirmed yet.",
                0.05,
                [signal.id for signal in related_actor_signals[:3]],
            )
        return (
            "unconfirmed",
            "No follow-up signal clearly supports the predicted actor move.",
            -0.12,
            [],
        )

    def _score_narrative(self, prediction: Prediction, signals: list[RawSignal]) -> tuple[str, str, float, list[str]]:
        matched = self._matching_signals(signals, prediction.related_actors, NARRATIVE_KEYWORDS, use_description=True)
        if matched:
            return (
                "confirmed",
                "The follow-up narrative shifted toward the predicted mechanism or framing.",
                0.15,
                [signal.id for signal in matched[:3]],
            )
        return (
            "unconfirmed",
            "The later coverage does not yet reflect the predicted narrative shift.",
            -0.08,
            [],
        )

    def _score_asset_repricing(
        self, prediction: Prediction, signals: list[RawSignal]
    ) -> tuple[str, str, float, list[str]]:
        text = prediction.description.lower()
        expected_positive = "outperform" in text or "positive" in text or "benefit" in text
        keyword_pool = POSITIVE_REPRICING_KEYWORDS if expected_positive else NEGATIVE_REPRICING_KEYWORDS
        matched = self._matching_signals(signals, prediction.affected_assets, keyword_pool, asset_mode=True)
        if matched:
            return (
                "confirmed",
                "Market-linked follow-up signals support the predicted repricing direction.",
                0.2,
                [signal.id for signal in matched[:3]],
            )
        asset_mentions = self._matching_signals(signals, prediction.affected_assets, set(), asset_mode=True)
        if asset_mentions:
            return (
                "partial",
                "Affected assets reappear in follow-up data, but the repricing direction is still ambiguous.",
                0.04,
                [signal.id for signal in asset_mentions[:3]],
            )
        return (
            "unconfirmed",
            "No follow-up market evidence confirms the predicted repricing path.",
            -0.15,
            [],
        )

    def _score_timing_window(
        self, prediction: Prediction, signals: list[RawSignal]
    ) -> tuple[str, str, float, list[str]]:
        if not signals:
            return ("unconfirmed", "There is no follow-up evidence to assess timing yet.", -0.05, [])
        return (
            "partial",
            "Timing-window predictions need more than one follow-up batch, so this remains provisional.",
            0.0,
            [signal.id for signal in signals[:2]],
        )

    def _score_generic(self, prediction: Prediction, signals: list[RawSignal]) -> tuple[str, str, float, list[str]]:
        matched = self._matching_signals(signals, prediction.related_actors + prediction.affected_assets, set())
        if matched:
            return (
                "partial",
                "Related follow-up evidence exists, but the prediction type is generic.",
                0.03,
                [signal.id for signal in matched[:3]],
            )
        return ("unconfirmed", "No usable follow-up evidence found for this prediction.", -0.05, [])

    def _matching_signals(
        self,
        signals: list[RawSignal],
        anchors: list[str],
        keywords: set[str],
        *,
        use_description: bool = False,
        asset_mode: bool = False,
    ) -> list[RawSignal]:
        anchor_tokens = {
            token for anchor in anchors for token in re.findall(r"[a-z0-9]+", anchor.lower()) if len(token) > 2
        }
        matched: list[RawSignal] = []
        for signal in signals:
            haystack = " ".join(
                [
                    signal.title.lower(),
                    signal.summary.lower(),
                    " ".join(tag.lower() for tag in signal.tags),
                    " ".join(entity.lower() for entity in signal.entities),
                ]
            )
            if use_description:
                haystack = f"{haystack} {signal.signal_type.lower()}"
            if (
                asset_mode
                and signal.source not in {"market", "macro"}
                and signal.signal_type not in {"market", "market-quote"}
            ):
                continue
            anchor_hit = not anchor_tokens or any(token in haystack for token in anchor_tokens)
            keyword_hit = not keywords or any(keyword in haystack for keyword in keywords)
            if anchor_hit and keyword_hit:
                matched.append(signal)
        return matched
