from __future__ import annotations

from faultline.analysis.system_first import _calibration_by_type
from faultline.models import (
    ActionRecommendation,
    CalibrationSignal,
    MarketImplication,
    PortfolioPosition,
    WatchlistEntry,
)


class PortfolioActionEngine:
    def generate(
        self,
        implications: list[MarketImplication],
        calibration_signals: list[CalibrationSignal] | None = None,
        portfolio_positions: list[PortfolioPosition] | None = None,
        watchlist: list[WatchlistEntry] | None = None,
    ) -> tuple[list[ActionRecommendation], list[str]]:
        calibration_index = _calibration_by_type(calibration_signals)
        portfolio_positions = portfolio_positions or []
        watchlist = watchlist or []
        actions: list[ActionRecommendation] = []
        actions.extend(self._portfolio_actions(portfolio_positions, implications, calibration_index))
        actions.extend(self._watchlist_actions(watchlist, implications, calibration_index))
        endangered = sorted(set(self._endangered_symbols(portfolio_positions, implications, calibration_index)))
        return actions, endangered

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
