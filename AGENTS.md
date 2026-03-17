# Faultline — Agent Instructions

Read this file before making code, workflow, or architecture changes.

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

If you add or remove nodes, update this file and the related state contracts in `src/faultline/models/state.py`.

## Key Modules

- `src/faultline/analysis/system_first.py`
- `src/faultline/synthesis/report_builder.py`
- `src/faultline/persistence/store.py`
- `src/faultline/graph/runner.py`
- `src/faultline/llm/backend.py`

All structured LLM calls must go through `src/faultline/llm/backend.py`.

## Working Rules

- Keep input and state contracts explicit and typed.
- Keep report sections traceable to evidence and predictions.
- Prefer replacing stale abstractions over preserving semantic mismatch.
- If you remove fields, update report synthesis, operator surfaces, tests, and docs in the same change.

## Required Checks

Before handing work back, agents must run these checks locally when relevant:

- `ruff format src/ tests/ docs/`
- `ruff check .`
- `pytest -q`

Do not stop at `ruff format --check`. Agents should run `ruff format` to apply formatting whenever they touch Python or docs files.
