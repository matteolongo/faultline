# 🌋 Faultline

[![CI](https://github.com/YOUR_ORG/faultline/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/faultline/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/built%20with-LangGraph-6f42c1)](https://github.com/langchain-ai/langgraph)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Where structural fragility becomes asymmetric alpha.**

Faultline is a geopolitical structural fragility reasoning engine. It ingests live signals from news, markets, and macro data — then reasons about *what is actually breaking* and *who profits from the crack*.

It doesn't summarize headlines. It maps **Empire vs. Disruptor** topologies, identifies cheap-weapon / expensive-defense asymmetries, scores structural fragility across nodes, and surfaces high-convexity opportunity theses with explicit invalidation logic.

---

## 🧠 What Faultline Answers

Instead of asking "what happened?", Faultline asks:

| Question | Output |
|----------|--------|
| 🗺️ What is the structural topology? | Empire–Disruptor graph with labeled dependencies |
| 💥 Where is the cheap weapon? | Asymmetry score per fragility node |
| 🔗 Which nodes are critically fragile? | Weighted fragility scores with provenance |
| 🌊 What are the second-order ripples? | Scenario tree with cascade paths |
| 📈 Is there a non-obvious trade? | Equity opportunity ideas with invalidation theses |

---

## 🏗️ How It Works

Faultline runs a 12-node LangGraph pipeline. Signals flow in, intelligence flows out.

```mermaid
graph LR
    A[🔌 Ingest Signals] --> B[🧹 Normalize & Dedupe]
    B --> C[🔎 Detect Scenario]
    C --> D[📦 Cluster Events]
    D --> E[🌐 Web Enrich]
    E --> F[🤖 Pattern Match]
    F --> G[⚗️ Signal Alchemist]
    G --> H[🗺️ Abstract Topology]
    H --> I[📊 Score Fragility]
    I --> J[🌊 Ripple Architect]
    J --> K[💡 Opportunity Generator]
    K --> L[🔍 Execution Critic]
    L --> M[📝 Synthesize Report]
```

Each node is independently testable, replaceable, and observable via LangGraph Studio.

### The Pipeline Explained

| # | Node | What it does |
|---|------|-------------|
| 1 | **Ingest** | Pulls raw signals from NewsAPI, Alpha Vantage, FRED, GDELT |
| 2 | **Normalize** | Dedupes, scores salience, enriches metadata |
| 3 | **Scenario Detect** | Matches against known geopolitical archetypes |
| 4 | **Cluster** | Groups signals into structural stories |
| 5 | **Web Enrich** | Targeted live web search per cluster via OpenAI |
| 6 | **Pattern Match** | LLM-backed archetype and fragility pattern identification |
| 7 | **Signal Alchemist** | Converts structural patterns into quantified signals |
| 8 | **Abstract Topology** | Builds Empire–Disruptor graph with asymmetry mapping |
| 9 | **Score Fragility** | Weighted multi-factor fragility scoring per node |
| 10 | **Ripple Architect** | Projects cascade scenarios and second-order effects |
| 11 | **Opportunity Generator** | Surfaces high-convexity opportunity ideas |
| 12 | **Execution Critic** | Validates, stress-tests, and gates each idea |

The final report includes provenance chains, invalidation logic, confidence scores, and a `monitor_only` flag for ideas that need more evidence.

---

## 🚀 Quickstart

### 1. Install

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .[dev]
```

### 2. Run a demo scenario (no API keys needed)

```bash
faultline run-demo --scenario arctic_cable_bypass
```

Three scenarios are included out of the box:

| Scenario | Description |
|----------|-------------|
| `arctic_cable_bypass` | Russia–China bypass of NATO undersea infrastructure |
| `debt_defense_spiral` | Emerging market debt distress + defense spending feedback |
| `open_model_breakout` | Open-source AI model proliferation vs. frontier model lock-in |

### 3. Run all demos + evaluate

```bash
faultline run-all-demos
faultline evaluate --scenario open_model_breakout
```

### 4. Run against live signals

```bash
cp .env.example .env   # fill in your API keys (see below)
faultline provider-health
faultline run-latest --lookback-minutes 60
```

---

## 🔑 API Keys

All four providers have **free tiers** — no credit card required except OpenAI.

| Variable | Service | Get it here | Free tier |
|----------|---------|-------------|-----------|
| `NEWSAPI_API_KEY` | [NewsAPI](https://newsapi.org) | [newsapi.org/register](https://newsapi.org/register) | 100 req/day |
| `ALPHAVANTAGE_API_KEY` | [Alpha Vantage](https://www.alphavantage.co) | [alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key) | 25 req/day |
| `FRED_API_KEY` | [FRED (St. Louis Fed)](https://fred.stlouisfed.org) | [fredaccount.stlouisfed.org/apikeys](https://fredaccount.stlouisfed.org/apikeys) | Unlimited |
| `OPENAI_API_KEY` | [OpenAI](https://openai.com) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) | Paid account required |

> 💡 `OPENAI_API_KEY` is **optional but recommended** — it unlocks LLM-backed refinement nodes *and* live cluster-driven web search enrichment. Without it, all heuristic nodes and demo/replay paths still work fully.

Setup:

```bash
cp .env.example .env
# Then edit .env and paste your keys
```

---

## 🖥️ LangGraph Studio

Faultline runs natively in [LangGraph Studio](https://smith.langchain.com/studio) — visualize node-by-node execution, inspect intermediate state, and add breakpoints.

```bash
pip install -e '.[dev]'   # required for editable import
langgraph dev             # starts local Studio server
```

Open: **https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024**

The graph is named `faultline`. The Studio input panel shows four fields:

| Field | Default | Description |
|-------|---------|-------------|
| `scenario_id` | `arctic_cable_bypass` | Which demo scenario to load |
| `run_mode` | `demo` | `demo` \| `live` \| `latest` \| `replay` |
| `window_start` | — | ISO-8601 start (live/latest only) |
| `window_end` | — | ISO-8601 end (live/latest only) |

> 🐛 Click the **Interrupts** button (top-right) to pause before any node and inspect state.

---

## 💻 CLI Reference

```bash
# Demo scenarios
faultline run-demo --scenario arctic_cable_bypass
faultline run-all-demos

# Live ingestion
faultline run-latest --lookback-minutes 60
faultline run-live --start 2026-03-08T10:00:00Z --end 2026-03-08T11:00:00Z
faultline ingest-window --start 2026-03-08T10:00:00Z --end 2026-03-08T11:00:00Z

# Backfill & replay
faultline backfill --start 2026-03-01T00:00:00Z --end 2026-03-02T00:00:00Z --step-minutes 60
faultline replay --run-id <previous-run-id>

# Utilities
faultline list-signals --limit 20
faultline provider-health
faultline evaluate --scenario debt_defense_spiral
faultline evaluate-goldset
```

---

## 📓 Operator Notebook

The notebook at `notebooks/faultline_operator_surface.ipynb` is the richest operator surface — run demo, live, latest-window, and replay flows while inspecting provider health and rendered reports inline.

```bash
pip install -e '.[dev,operator]'
jupyter lab notebooks/faultline_operator_surface.ipynb
```

There is also a lightweight Streamlit UI:

```bash
streamlit run src/faultline/operator_app.py
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FAULTLINE_OUTPUT_DIR` | `outputs/` | Where reports and traces are saved |
| `FAULTLINE_DATABASE_URL` | `outputs/faultline_runs.sqlite` | Persistence: SQLite path or PostgreSQL URL |
| `FAULTLINE_LOG_LEVEL` | `INFO` | Logging verbosity |
| `FAULTLINE_PROVIDER_TIMEOUT` | `30` | Provider fetch timeout in seconds |
| `FAULTLINE_DEFAULT_LOOKBACK_MINUTES` | `60` | Default window for `run-latest` |
| `NEWSAPI_API_KEY` | — | Required for live NewsAPI ingestion |
| `ALPHAVANTAGE_API_KEY` | — | Required for live Alpha Vantage ingestion |
| `FRED_API_KEY` | — | Required for live FRED ingestion |
| `OPENAI_API_KEY` | — | Optional; enables LLM nodes + web enrichment |

---

## 🗂️ Repository Layout

```text
configs/
  archetypes.yaml     # Known geopolitical archetype knowledge base
  prompts.yaml        # LLM prompt templates
  scoring.yaml        # Fragility scoring weights
data/samples/         # Fixture signals for demo/test runs
src/faultline/
  agents/             # LLM-backed reasoning nodes
  evaluation/         # Scoring rubrics and goldset evaluation
  graph/              # LangGraph workflow + Studio entrypoint
  llm/                # OpenAI backend with schema enforcement
  models/             # Typed contracts and state definitions
  providers/          # Live signal providers (NewsAPI, AlphaVantage, FRED, GDELT)
  scoring/            # Fragility and asymmetry heuristics
  synthesis/          # Report builder
  utils/              # Config, env, logging
tests/                # Full test suite (33 tests, no API keys required)
notebooks/            # Operator notebook
```

---

## 🧪 Development

```bash
pip install -e '.[dev]'
pre-commit install      # lint + format on every commit
pytest -q               # run the full test suite
```

The CI pipeline runs on every push and PR to `main`: lint (`ruff`) → format check → tests.

---

## 🚫 Intentionally Out of Scope

Faultline is a **research and intelligence tool**, not a trading system:

- ❌ No real-time execution or order routing
- ❌ No portfolio management
- ❌ No backtesting framework
- ❌ No large-scale data engineering

It optimizes for **traceable structural reasoning**, modularity, replayability, and operator-grade unattended research workflows.

---

## 📄 License

MIT
