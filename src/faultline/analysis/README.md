# Analysis Package

This package contains the core system-first reasoning engines used after signals have been normalized and clustered. It is where Faultline turns evidence into a situation model, forward scenarios, market translation, and operator actions.

## Workflow Responsibilities

- `map_situation` uses `SituationMapper` to build a `SituationSnapshot`.
- `generate_predictions` uses `PredictionEngine` to create predictions, scenario branches, and stage warnings.
- `map_market_implications` uses `MarketMapper` to connect the situation to assets, sectors, and transmission paths.
- `generate_actions` uses `ActionEngine` to propose actions, exits, and endangered symbols.

## Main Modules

- `system_first.py` contains `MechanismAnalyzer`, `SituationMapper`, `PredictionEngine`, `MarketMapper`, and `ActionEngine`.
- `portfolio_engine.py` contains the older portfolio action engine kept for compatibility.
- `utils.py` contains calibration lookup helpers shared by the reasoning code.

## What It Produces

- Actor, force, relation, mechanism, and stage maps.
- Scenario and timing predictions with confidence bands.
- Market implications tied to the detected situation.
- Action recommendations shaped by predictions, warnings, portfolio context, and policy constraints.

## Use This Package When

- You want to change the analytical behavior of the production graph.
- You are adding a new mechanism, stage rule, prediction rule, or action policy.
- You need to keep report sections traceable back to evidence and intermediate reasoning artifacts.
