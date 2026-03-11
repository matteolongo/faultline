# Faultline

[![CI](https://github.com/matteolongo/faultline/actions/workflows/ci.yml/badge.svg)](https://github.com/matteolongo/faultline/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/built%20with-LangGraph-6f42c1)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

System-first strategic analysis engine for complex systems and market-linked decisions.

Faultline ingests live and sample signals, maps them into a structured situation model, predicts likely next moves, and produces action-oriented analyst memos with calibrated confidence and explicit traceability.

## What It Produces

For each clustered situation, Faultline outputs:

- Situation summary and why-now context
- Actors, forces, relations, and active mechanisms
- Stage assessment and stage-transition warnings
- Predictions (actor move, narrative, repricing, timing window)
- Scenario tree with confidence bands
- Market implications
- Actions now (`watch`, `enter`, `trim`, `exit`, `avoid`)
- Exit signals and endangered symbols
- Evidence, references, and action traceability

## Current Workflow (Main Path)

The production graph is in `src/faultline/graph/workflow.py`:

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

## Quickstart

### Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

### Run demo scenarios (no API keys required)

```bash
faultline run-demo --scenario open_model_breakout
faultline run-all-demos
```

Available sample scenarios:

- `arctic_cable_bypass`
- `debt_defense_spiral`
- `open_model_breakout`

### Run live window

```bash
faultline provider-health
faultline run-latest --lookback-minutes 60
faultline run-live --start 2026-03-08T10:00:00Z --end 2026-03-08T11:00:00Z
```

### Portfolio/watchlist-aware execution

```bash
faultline run-demo \
  --scenario open_model_breakout \
  --positions AAPL,MSFT \
  --watchlist NVDA,AMD
```

Or pass structured JSON:

```bash
faultline run-live \
  --start 2026-03-08T10:00:00Z \
  --end 2026-03-08T11:00:00Z \
  --positions-json positions.json \
  --watchlist-json watchlist.json \
  --policy-json policy.json
```

### Automatic follow-up scoring loop

```bash
faultline auto-followup \
  --start 2026-03-08T11:00:00Z \
  --end 2026-03-08T13:00:00Z \
  --min-run-age-minutes 60 \
  --limit-runs 20
```

Or trigger after a live/latest run:

```bash
faultline run-latest --auto-followup
faultline run-live --start ... --end ... --auto-followup
```

## Operator Surfaces

- Notebook: `notebooks/faultline_operator_surface.ipynb`
- Streamlit app: `streamlit run src/faultline/operator_app.py`
- LangGraph Studio: `langgraph dev`

## Environment Variables

- `FAULTLINE_OUTPUT_DIR` (default `outputs/`)
- `FAULTLINE_DATABASE_URL` (default SQLite in `outputs/`)
- `FAULTLINE_DEFAULT_LOOKBACK_MINUTES` (default `60`)
- `FAULTLINE_LOG_LEVEL` (default `INFO`)
- `NEWSAPI_API_KEY`
- `ALPHAVANTAGE_API_KEY`
- `FRED_API_KEY`
- `OPENAI_API_KEY` (optional for selected enrichment paths)

## Repository Layout

```text
configs/
  mechanisms.yaml
  stages.yaml
  prompts.yaml
  providers.yaml
data/samples/
src/faultline/
  analysis/
  evaluation/
  graph/
  llm/
  memory/
  models/
  persistence/
  prediction/
  presentation/
  providers/
  synthesis/
  utils/
tests/
docs/
```

## Development

```bash
pip install -e '.[dev]'
ruff format --check src/ tests/ docs/
pytest -q
```

## Scope

Faultline is a research and decision-support engine. It does not execute orders, run a broker, or manage live portfolios.
