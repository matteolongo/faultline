# Faultline — Agent Context

Read this file before making architecture or workflow changes.

## Project Identity

Faultline is a system-first strategic analysis engine built on LangGraph.  
It converts clustered live/sample signals into:

- structured situation maps
- scenario and timing predictions
- market implications
- operator actions
- follow-up outcome calibration

It is not an execution engine, broker, or backtester.

## Main Execution Route

The active production workflow is `src/faultline/graph/workflow.py`:

1. `ingest_signals`
2. `normalize_events`
3. `retrieve_related_situations`
4. `retrieve_calibration`
5. `map_situation`
6. `generate_predictions`
7. `map_market_implications`
8. `generate_actions`
9. `synthesize_report`
10. `remember_situation`

If you add/remove nodes, update this file and associated state contracts in `models/state.py`.

## Key Modules

- `src/faultline/analysis/system_first.py`
  - `SituationMapper`
  - `PredictionEngine`
  - `MarketMapper`
  - `ActionEngine`
- `src/faultline/synthesis/report_builder.py`
  - final memo synthesis and markdown rendering
- `src/faultline/persistence/store.py`
  - raw signals, runs, predictions, outcomes, calibration retrieval
- `src/faultline/graph/runner.py`
  - run modes, follow-up scoring, output artifacts

Legacy archetype/fragility pipelines have been removed from the main codebase.

## Model Contracts

Core contracts live in `src/faultline/models/contracts.py`:

- `SituationSnapshot`, `Actor`, `Force`, `Relation`, `Mechanism`, `StageAssessment`
- `Prediction`, `ScenarioPath`, `StageTransitionWarning`
- `MarketImplication`, `ActionRecommendation`, `OutcomeRecord`
- `FinalReport`, `OperatorPolicyConfig`

State wiring lives in `src/faultline/models/state.py`.

## Operator Policy & Follow-Up Loop

- Policy thresholds are configurable through `OperatorPolicyConfig`.
- Runner accepts policy overrides (`run_demo`, `run_live`, `run_latest`).
- Automatic follow-up rescoring exists via:
  - CLI `auto-followup`
  - runner `auto_score_followups(...)`
  - optional `--auto-followup` on `run-live` / `run-latest`

## LLM Rules

All structured LLM calls must go through `src/faultline/llm/backend.py`.

Do not bypass schema enforcement logic for structured outputs.

## Testing Rules

- Tests must run locally with no external API calls.
- Use fixtures/sample scenarios for deterministic behavior.
- Required checks before commit:
  - `ruff check .`
  - `ruff format --check src/ tests/ docs/`
  - `pytest -q`

## Safe Change Boundaries

- Keep input/state contracts explicit and typed.
- Keep report sections traceable to evidence and predictions.
- Prefer replacing stale abstractions over preserving semantic mismatch.
- If removing fields, update:
  - report synthesis
  - operator surfaces
  - tests
  - docs
