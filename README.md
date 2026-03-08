# Strategic Swarm Agent

Strategic Swarm Agent is an MVP reasoning engine for structural fragility analysis. It takes a small cluster of heterogeneous signals, abstracts them into an `Empire vs Disruptor` topology, scores fragility and asymmetry, builds ripple scenarios, and surfaces only higher-convexity opportunity ideas with explicit invalidation logic.

The design goal is not headline summarization. The system is built to answer:

- What is the structural topology of the conflict?
- Where is the cheap weapon versus the expensive defense surface?
- Which nodes are fragile?
- Which systems become antifragile?
- Is there an indirect, nonlinear execution thesis worth surfacing?

## MVP capabilities

- Modular provider layer with three demo providers: news, market context, and dark signals
- Typed contracts with `pydantic`
- Versioned archetype knowledge base in YAML
- Deterministic fragility and convexity heuristics
- Four sub-agent style nodes orchestrated in `langgraph`
- Explainable final report with provenance and invalidation logic
- Three end-to-end demo scenarios
- JSON and Markdown output export
- SQLite persistence for replay and debugging

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

## Environment

Environment variables are intentionally minimal for the MVP:

- `SWARM_OUTPUT_DIR`: output folder for reports and traces. Defaults to `outputs/`.
- `SWARM_RUN_DB`: SQLite path for persisted runs. Defaults to `outputs/swarm_runs.sqlite`.
- `SWARM_LOG_LEVEL`: logging level. Defaults to `INFO`.
- `OPENAI_API_KEY`: optional and unused by default. Reserved for future LLM-backed node upgrades.

See [.env.example](/Users/matteo.longo/projects/streategic_swarm_agent/.env.example).

## CLI usage

```bash
python3 -m strategic_swarm_agent run-demo --scenario debt_defense_spiral
python3 -m strategic_swarm_agent run-demo --scenario regional_microgrid_shock --output-dir outputs/custom
python3 -m strategic_swarm_agent run-all-demos
python3 -m strategic_swarm_agent evaluate --scenario arctic_cable_bypass
```

## What is intentionally excluded

- Live internet ingestion
- Real-time trading or execution
- Portfolio management
- Backtesting
- Large-scale data engineering
- Broad external integrations

The MVP optimizes for traceable structural reasoning, modularity, and replayability.
