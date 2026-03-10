# Faultline — Agent Context

> Read this file before making any changes. It covers architecture, conventions, domain concepts, and how to run things.

## What This Project Does

Faultline is a **geopolitical structural fragility reasoning engine** built on [LangGraph](https://github.com/langchain-ai/langgraph). It ingests live signals from news, markets, and macro data, then reasons about structural stress and asymmetric disruption using an "Empire vs. Disruptor" topology.

**It does NOT**: summarize headlines, execute trades, manage portfolios, or backtest strategies.

**It DOES**: map fragility, score asymmetry, project ripple cascades, and surface high-convexity opportunity theses with explicit invalidation logic.

## Repository Layout

```
src/faultline/
  agents/          # LLM-backed reasoning nodes (PatternMatcher, SignalAlchemist, etc.)
  evaluation/      # Scoring rubrics and goldset evaluation harness
  graph/           # LangGraph workflow (workflow.py) + Studio entrypoint (studio.py)
  llm/             # OpenAI backend with schema enforcement (backend.py)
  models/          # Typed Pydantic contracts (contracts.py) and graph state (state.py)
  providers/       # Live signal providers: NewsAPI, Alpha Vantage, FRED, GDELT
  scoring/         # Heuristic fragility scoring (fragility.py)
  synthesis/       # Final report builder (report_builder.py)
  utils/           # Config loader, env, logging, IO helpers

configs/
  archetypes.yaml  # Known geopolitical conflict archetypes (Empire vs. Disruptor topologies)
  prompts.yaml     # LLM system and user prompts for each agent node
  scoring.yaml     # Fragility scoring weights and thresholds
  providers.yaml   # Live provider defaults (query terms, limits, timeouts)

tests/             # 33 tests — run without any API keys
data/samples/      # Fixture signals for demo and test runs
```

## The 12-Node Pipeline

All pipeline logic lives in `src/faultline/graph/workflow.py`. Nodes run in sequence:

1. `ingest_signals` — Fetch raw signals from providers
2. `normalize_signals` — Dedupe, score salience, enrich metadata
3. `detect_scenario` — Match against archetypes in `configs/archetypes.yaml`
4. `cluster_events` — Group signals into structural stories
5. `enrich_clusters` — Live web search per cluster (requires `OPENAI_API_KEY`)
6. `match_patterns` — LLM-backed archetype and fragility pattern identification
7. `run_signal_alchemist` — Convert structural patterns into quantified signals
8. `abstract_topology` — Build Empire–Disruptor graph with asymmetry mapping
9. `score_fragility` — Weighted multi-factor fragility scoring
10. `architect_ripples` — Project cascade scenarios and second-order effects
11. `generate_opportunities` — Surface high-convexity opportunity ideas
12. `synthesize_report` — Build final report with provenance and invalidation logic

## Key Patterns

### Adding a new LangGraph node
1. Define a function in `workflow.py` with signature `def my_node(state: FaultlineState) -> dict:`
2. Return only the keys you want to update in state (LangGraph merges dicts)
3. Add it to the graph with `workflow.add_node("my_node", my_node)`
4. Wire edges with `workflow.add_edge()`

### Adding a new provider
1. Create `src/faultline/providers/myprovider.py` implementing `BaseProvider`
2. The key method: `fetch_window(start_at: datetime, end_at: datetime) -> list[RawSignal]`
3. Register it in `src/faultline/providers/registry.py`
4. Add config defaults to `configs/providers.yaml`

### LLM structured output
All LLM calls go through `src/faultline/llm/backend.py` → `StructuredReasoner.call()`.
The `_enforce_additional_properties()` function in `backend.py` is critical — it patches Pydantic-generated schemas to comply with OpenAI's strict structured output requirements (`additionalProperties: false`, all fields in `required`). Do not bypass this.

### State
`FaultlineState` (in `models/state.py`) is the full 22-field TypedDict passed between nodes.
`FaultlineInputSchema` is the 4-field subset shown in LangGraph Studio's input panel — do not add internal pipeline fields to it.

### Models
All data contracts are Pydantic `BaseModel` in `src/faultline/models/contracts.py`.
Never use plain dicts for inter-node data — always use typed models.

## Domain Vocabulary

See `docs/GLOSSARY.md` for full definitions. Quick reference:

| Term | Meaning |
|------|---------|
| **Empire** | Centralized defensive order (incumbent, utility, closed system) |
| **Disruptor** | Distributed adaptive network (protocol, open-source, bypass) |
| **Archetype** | Named structural conflict topology (e.g., "Chokepoint vs. Bypass") |
| **Fragility score** | Composite 0–1 weakness measure across 6 weighted factors |
| **Cheap weapon** | Low-cost disruption vector (e.g., open model, rerouting, drone swarm) |
| **Ripple** | Second-order cascade scenario projected from a fragility node |
| **Asymmetry** | Ratio of disruption cost to defense cost — the core alpha signal |
| **Monitor-only** | Flag on an opportunity that needs more evidence before acting |

## Running Things

```bash
# Install
pip install -e .[dev]

# Tests (no API keys needed)
pytest -q
pytest tests/test_models.py  # fast unit tests only

# Lint + format
ruff check src/ tests/
ruff format src/ tests/

# Demo run
faultline run-demo --scenario arctic_cable_bypass

# All demos
faultline run-all-demos

# LangGraph Studio
langgraph dev  # then open https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024

# Make targets
make test
make lint
make demo
make studio
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `FAULTLINE_OUTPUT_DIR` | `outputs/` | Report and trace output |
| `FAULTLINE_DATABASE_URL` | `outputs/faultline_runs.sqlite` | Persistence backend |
| `FAULTLINE_LOG_LEVEL` | `INFO` | Log verbosity |
| `OPENAI_API_KEY` | — | Optional; enables LLM nodes + web enrichment |
| `NEWSAPI_API_KEY` | — | Live news ingestion |
| `ALPHAVANTAGE_API_KEY` | — | Market data ingestion |
| `FRED_API_KEY` | — | Macro data ingestion |

## Testing Conventions

- Tests live in `tests/` and use `pytest`
- Fixture signals are in `tests/fixtures/` and `data/samples/`
- Tests must **not** require API keys — use `data/samples/` fixtures for live-mode tests
- `run_mode="demo"` loads deterministic fixtures; use this for new tests
- CI runs on every push/PR to `main` via `.github/workflows/ci.yml`

## What to Avoid

- Do not add fields to `FaultlineInputSchema` (it controls the Studio UI — keep it to 4 fields)
- Do not bypass `_enforce_additional_properties()` when making OpenAI structured output calls
- Do not import directly from sub-modules in tests — import from the package root or `faultline.models`
- Do not add `TODO`/`FIXME` markers — resolve issues in the same PR
