# Strategic Swarm Agent

Strategic Swarm Agent is a structural fragility reasoning engine. It ingests heterogeneous live signals, clusters them into structural stories, abstracts them into an `Empire vs Disruptor` topology, scores fragility and asymmetry, builds ripple scenarios, and surfaces only higher-convexity opportunity ideas with explicit invalidation logic.

The design goal is not headline summarization. The system is built to answer:

- What is the structural topology of the conflict?
- Where is the cheap weapon versus the expensive defense surface?
- Which nodes are fragile?
- Which systems become antifragile?
- Is there an indirect, nonlinear execution thesis worth surfacing?

## Current capabilities

- Modular provider layer with sample providers plus live adapters for NewsAPI, Alpha Vantage, FRED, and GDELT
- Typed contracts with `pydantic`
- Versioned archetype knowledge base in YAML
- Deterministic normalization, dedupe, clustering, and fragility heuristics
- Hybrid reasoning pipeline with optional structured LLM refinement for Pattern Matcher, Signal Alchemist, Ripple Architect, and synthesis
- SQLite or PostgreSQL-backed persistence for raw signals, normalized events, clusters, runs, reports, and dead letters
- Four sub-agent style nodes orchestrated in `langgraph`
- Explainable final report with provenance, invalidation logic, and `monitor_only` gating
- Three end-to-end demo scenarios
- JSON and Markdown output export
- Replay, backfill, provider health, and signal listing CLI workflows

## Repository layout

```text
configs/
  archetypes.yaml
  prompts.yaml
  scoring.yaml
data/
  samples/
src/strategic_swarm_agent/
  agents/
  evaluation/
  graph/
  models/
  providers/
  scoring/
  synthesis/
  utils/
tests/
```

## Quickstart

1. Create a virtual environment and install the package:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

2. Run a demo:

```bash
python3 -m strategic_swarm_agent run-demo --scenario arctic_cable_bypass
```

3. Run all demos and evaluation:

```bash
python3 -m strategic_swarm_agent run-all-demos
python3 -m strategic_swarm_agent evaluate --scenario open_model_breakout
pytest
```

## Obtaining API keys

The live ingestion providers each require a free or freemium API key. All four can be obtained without a paid plan to get started.

| Key | Service | Sign-up URL | Notes |
|-----|---------|-------------|-------|
| `NEWSAPI_API_KEY` | NewsAPI | <https://newsapi.org/register> | Free developer tier; 100 requests/day, no credit card required. |
| `ALPHAVANTAGE_API_KEY` | Alpha Vantage | <https://www.alphavantage.co/support/#api-key> | Free tier; 25 requests/day. Premium tiers available for higher volume. |
| `FRED_API_KEY` | FRED (Federal Reserve Economic Data) | <https://fredaccount.stlouisfed.org/apikeys> | Free, no rate-limit concerns for typical research workloads. Requires creating a St. Louis Fed account. |
| `OPENAI_API_KEY` | OpenAI | <https://platform.openai.com/api-keys> | **Optional.** Enables LLM-backed refinement nodes **and** cluster-driven web search enrichment (via `web_search_preview`). Requires a paid account with credits. |

Steps:
1. Register at each URL above and copy the key shown after creation.
2. Copy `.env.example` to `.env` in the repository root: `cp .env.example .env`
3. Paste each key into the corresponding variable in `.env`.
4. Verify connectivity with: `python3 -m strategic_swarm_agent provider-health`

> **Tip:** `NEWSAPI_API_KEY`, `ALPHAVANTAGE_API_KEY`, and `FRED_API_KEY` are required for live/latest-window flows. Without them, demo and replay paths remain fully functional.

## Environment

Core environment variables:

- `SWARM_OUTPUT_DIR`: output folder for reports and traces. Defaults to `outputs/`.
- `SWARM_DATABASE_URL`: persistence database URL or local SQLite path. Defaults to `outputs/swarm_runs.sqlite`.
- `SWARM_LOG_LEVEL`: logging level. Defaults to `INFO`.
- `SWARM_PROVIDER_TIMEOUT`: provider timeout in seconds.
- `SWARM_DEFAULT_LOOKBACK_MINUTES`: default window for `run-latest`.
- `NEWSAPI_API_KEY`: required for NewsAPI live ingestion.
- `ALPHAVANTAGE_API_KEY`: required for Alpha Vantage live ingestion.
- `FRED_API_KEY`: required for FRED live ingestion.
- `OPENAI_API_KEY`: optional. Enables structured refinement for the LLM-backed nodes.

See [.env.example](/Users/matteo.longo/projects/streategic_swarm_agent/.env.example).

The CLI, notebook, and Streamlit app auto-load `.env` and `.env.local` from the repository root. The shortest path to live mode is to copy `.env.example` to `.env` and fill in your keys there.

## CLI usage

```bash
python3 -m strategic_swarm_agent run-demo --scenario debt_defense_spiral
python3 -m strategic_swarm_agent run-all-demos
python3 -m strategic_swarm_agent evaluate --scenario arctic_cable_bypass
python3 -m strategic_swarm_agent run-latest --lookback-minutes 60
python3 -m strategic_swarm_agent run-live --start 2026-03-08T10:00:00Z --end 2026-03-08T11:00:00Z
python3 -m strategic_swarm_agent ingest-window --start 2026-03-08T10:00:00Z --end 2026-03-08T11:00:00Z
python3 -m strategic_swarm_agent backfill --start 2026-03-01T00:00:00Z --end 2026-03-02T00:00:00Z --step-minutes 60
python3 -m strategic_swarm_agent replay --run-id <previous-run-id>
python3 -m strategic_swarm_agent list-signals --limit 20
python3 -m strategic_swarm_agent provider-health
python3 -m strategic_swarm_agent evaluate-goldset
```

## Operator Surfaces

The recommended first operator surface is the notebook at [strategic_swarm_operator_surface.ipynb](/Users/matteo.longo/projects/streategic_swarm_agent/notebooks/strategic_swarm_operator_surface.ipynb). It is the clearest way to run demo, live, latest-window, and replay flows while inspecting provider health, recent signals, and the rendered report inline.

Install the operator extras:

```bash
pip install -e '.[dev,operator]'
```

Launch Jupyter:

```bash
jupyter lab notebooks/strategic_swarm_operator_surface.ipynb
```

There is also a thin Streamlit wrapper over the same runner API:

```bash
streamlit run src/strategic_swarm_agent/operator_app.py
```

The notebook is the recommended operator surface. The Streamlit app is a small convenience wrapper over the same execution path.

### LangGraph Studio

The graph can also be visualised and run step-by-step in [LangGraph Studio](https://smith.langchain.com/studio). A `langgraph.json` config is included.

**Requirements**: the package must be installed in editable mode so `langgraph dev` can import it:

```bash
pip install -e '.[dev]'        # only needed once
langgraph dev                  # starts the local Studio server
```

Then open: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024

The graph appears as `strategic_swarm`. You will need a free [LangSmith](https://smith.langchain.com) account for the Studio UI; the local API at `http://127.0.0.1:2024` works without one.

For live mode you will need `NEWSAPI_API_KEY`, `ALPHAVANTAGE_API_KEY`, and `FRED_API_KEY`. If keys are missing, live/provider-health flows stay non-crashing and the demo/replay paths remain fully usable.

Adding `OPENAI_API_KEY` is optional but recommended for two reasons: it enables the LLM refinement nodes (PatternMatcher, SignalAlchemist, etc.) **and** automatically triggers cluster-driven web search enrichment — after clustering, the system derives targeted fragility questions from each significant cluster and fetches live synthesis via OpenAI's `web_search_preview` tool before fragility scoring.

Minimal live setup:

```bash
cp .env.example .env
```

Then edit `.env` and set:

```bash
NEWSAPI_API_KEY=your_key
ALPHAVANTAGE_API_KEY=your_key
FRED_API_KEY=your_key
OPENAI_API_KEY=your_key_optional
```

Then verify the providers and run a live pull:

```bash
python3 -m strategic_swarm_agent provider-health
python3 -m strategic_swarm_agent run-latest --lookback-minutes 60
```

In the notebook, switch `MODE` from `demo` to `latest` or `live` after the keys are in place.

## Live source configuration

Live provider defaults live in [providers.yaml](/Users/matteo.longo/projects/streategic_swarm_agent/configs/providers.yaml). The defaults are intentionally small and opinionated:

- News discovery through NewsAPI `everything` plus `top-headlines`
- Market and sentiment context through Alpha Vantage news sentiment and global quotes
- Macro updates through FRED `series/updates` and `series/observations`
- Alternative structural event pressure through GDELT DOC

The ingestion contract is window-based: each provider implements `fetch_window(start_at, end_at) -> list[RawSignal]`.

## Persistence and replay

The runtime persists:

- raw signals
- normalized signals
- event clusters
- runs
- published reports
- dead-letter fetch failures

Replay rebuilds a report from stored raw signals without refetching the internet. For solo-workstation use, SQLite is the default. PostgreSQL is also supported through `SWARM_DATABASE_URL`.

## What is intentionally excluded

- Real-time trading or execution
- Portfolio management
- Backtesting
- Large-scale data engineering
- Broad external integrations

The system optimizes for traceable structural reasoning, modularity, replayability, and operator-grade unattended research workflows.
