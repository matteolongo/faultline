from __future__ import annotations

from faultline.models import CalibrationSignal


def calibration_by_type(calibration_signals: list[CalibrationSignal] | None) -> dict[str, CalibrationSignal]:
    """Index calibration signals by prediction_type for O(1) lookup."""
    return {item.prediction_type: item for item in (calibration_signals or [])}
