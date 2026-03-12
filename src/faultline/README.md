# Faultline Source Package

This package contains the production Faultline application. The active runtime is a system-first analysis workflow that turns raw signals into structured situation maps, predictions, market implications, operator actions, and a publishable report.

## Entry Points

- `graph/workflow.py` defines the production LangGraph node sequence.
- `graph/runner.py` wraps the workflow with persistence, checkpointing, replay, and follow-up scoring helpers.
- `__main__.py` exposes the CLI for demo, live, replay, evaluation, and follow-up runs.
- `operator_app.py` exposes the Streamlit operator surface for checkpointed human-in-the-loop review.

## Workflow Map

1. `providers` ingests and normalizes raw signals.
2. `memory` retrieves related past situations and stores new ones.
3. `analysis` maps the situation, predicts scenarios, translates them into market implications, and generates actions.
4. `synthesis` builds the final report.
5. `prediction` scores predictions against later evidence.
6. `persistence` stores inputs, intermediate artifacts, reports, outcomes, and diagnostics.

## Supporting Packages

- `models` defines the typed contracts used across the workflow.
- `llm` handles optional structured LLM refinement.
- `intake` converts a topic chat into a research brief and retrieval questions.
- `presentation` contains view-layer helpers for the operator surface.
- `evaluation` provides simple report scoring utilities.
- `utils` handles config loading, environment bootstrap, logging, and file I/O.

## Use This Package When

- You need to run or extend the end-to-end strategic analysis workflow.
- You need to add a new system-first analysis capability while preserving typed state contracts.
- You need to inspect how live ingestion, report generation, and operator review fit together.
