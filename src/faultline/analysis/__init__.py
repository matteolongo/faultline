import warnings as _warnings

from faultline.analysis.portfolio_engine import PortfolioActionEngine as _PortfolioActionEngine
from faultline.analysis.system_first import (
    ActionEngine,
    MarketMapper,
    MechanismAnalyzer,
    PredictionEngine,
    SituationMapper,
)
from faultline.analysis.utils import calibration_by_type


class PortfolioActionEngine(_PortfolioActionEngine):
    """Deprecated: use ActionEngine which now handles portfolio/watchlist/endangered logic."""

    def __init__(self, *args, **kwargs):
        _warnings.warn(
            "PortfolioActionEngine is deprecated and will be removed in a future release. Use ActionEngine instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


__all__ = [
    "ActionEngine",
    "MarketMapper",
    "MechanismAnalyzer",
    "PortfolioActionEngine",  # deprecated
    "PredictionEngine",
    "SituationMapper",
    "calibration_by_type",
]
