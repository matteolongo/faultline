# Prediction Package

This package scores prior predictions against later follow-up evidence.

## Main Module

- `outcome.py` contains `OutcomeEvaluator`, which compares predicted actor moves, narrative shifts, repricing calls, and timing windows against later raw signals.

## What It Is For

- Turning later evidence into `OutcomeRecord` objects.
- Measuring whether predictions were confirmed, partial, or unconfirmed.
- Producing calibration signals that can improve future judgment.

## Relationship To Analysis

- `analysis/` creates forward-looking predictions.
- `prediction/` looks backward later and grades how those predictions held up.

## Use This Package When

- You are extending follow-up scoring logic.
- You want to tighten calibration loops for specific prediction types.
- You need post-run outcome measurement separate from the main graph execution.
