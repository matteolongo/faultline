# Faultline — GitHub Copilot Workspace Instructions

## Project Overview

**Faultline** is a geopolitical structural fragility reasoning engine built with LangGraph and Python 3.11. It ingests live signals (news, markets, macro), maps structural conflict topologies ("Empire vs. Disruptor"), and surfaces asymmetric opportunity theses with explicit invalidation logic.

This is a **research and intelligence tool** — not a trading system, portfolio manager, or backtester.

## Architecture

12-node LangGraph pipeline. All nodes are in `src/faultline/graph/workflow.py`.

```
ingest → normalize → detect_scenario → cluster → enrich → match_patterns
→ signal_alchemist → abstract_topology → score_fragility
→ architect_ripples → generate_opportunities → synthesize_report
```

Each node: `def node_name(state: FaultlineState) -> dict` — returns only updated state keys.

## Key Files

| File | Purpose |
|------|---------|
| `src/faultline/graph/workflow.py` | Entire pipeline — all 12 nodes + graph wiring |
| `src/faultline/models/contracts.py` | All Pydantic data contracts |
| `src/faultline/models/state.py` | `FaultlineState` (full) + `FaultlineInputSchema` (Studio input) |
| `src/faultline/llm/backend.py` | OpenAI structured output caller — **always use this, never raw openai calls** |
| `src/faultline/providers/base.py` | `BaseProvider` interface all providers implement |
| `configs/archetypes.yaml` | Known conflict topologies |
| `configs/scoring.yaml` | Fragility scoring weights |

## Coding Conventions

- **Python 3.11+**, full type annotations on all functions
- **Pydantic `BaseModel`** for all inter-node data (no raw dicts)
- **TypedDict** for graph state (`FaultlineState`)
- **ruff** for linting and formatting (`line-length = 120`)
- All LLM calls through `StructuredReasoner` in `llm/backend.py`
- Schema patching via `_enforce_additional_properties()` is **required** for OpenAI strict mode

## Domain Terms

| Term | Meaning |
|------|---------|
| Empire | Centralized defensive incumbent |
| Disruptor | Distributed adaptive challenger |
| Archetype | Named conflict topology (e.g., "Chokepoint vs. Bypass") |
| Fragility score | 0–1 composite weakness measure |
| Cheap weapon | Low-cost disruption vector |
| Ripple | Projected second-order cascade effect |
| Monitor-only | Opportunity flag: needs more evidence |

## Running Tests

```bash
pip install -e .[dev]
pytest -q                    # full suite, no API keys needed
pytest tests/test_models.py  # fast unit tests
ruff check src/ tests/       # lint check
```

## How to Add Things

**New LangGraph node**: add function to `workflow.py`, wire with `add_node()` + `add_edge()`.  
**New provider**: implement `BaseProvider` in `providers/`, register in `providers/registry.py`.  
**New data model**: add Pydantic `BaseModel` to `models/contracts.py`, export from `models/__init__.py`.  
**New archetype**: add entry to `configs/archetypes.yaml` following existing schema.

## Critical Rules

1. Never add fields to `FaultlineInputSchema` — it controls the LangGraph Studio UI (4 fields only)
2. Never call OpenAI directly — always go through `StructuredReasoner.call()`
3. Never bypass `_enforce_additional_properties()` — OpenAI strict mode requires it
4. Tests must not require API keys — use `data/samples/` fixtures
