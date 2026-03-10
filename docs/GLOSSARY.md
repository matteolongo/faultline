# Faultline — Domain Glossary

This glossary defines the core domain concepts used throughout the codebase. When in doubt about what a term means or where it lives in code, start here.

---

## Core Topology Concepts

### Empire
The **centralized defensive order** in a structural conflict. The Empire is the incumbent: the entity with a large, expensive surface to defend, high fixed costs, and concentrated nodes. It is structurally fragile because its defense scales faster than the attacker's offense.

**Examples:** NATO's undersea cable infrastructure, a proprietary AI platform, a sovereign debt structure  
**Code:** `archetype.empire_type` in `configs/archetypes.yaml`; `AbstractPattern.empire_nodes` in `models/contracts.py`

### Disruptor
The **distributed adaptive challenger**. The Disruptor exploits structural fragility in the Empire using cheap, scalable, or parallel means. The Disruptor wins by making the Empire spend more to defend than the Disruptor spends to probe.

**Examples:** A bypass cable network, an open-weight AI model, a drone swarm  
**Code:** `archetype.disruptor_type` in `configs/archetypes.yaml`; `AbstractPattern.disruptor_nodes`

### Archetype
A **named structural conflict topology** — a pattern of Empire vs. Disruptor dynamics that recurs across different historical and contemporary scenarios.

Three archetypes are currently defined:
- **`empire_vs_swarm`**: Centralized defense vs. distributed swarm probes
- **`chokepoint_vs_bypass`**: Control of a narrow route vs. low-cost rerouting
- **`monolith_vs_protocol`**: Proprietary integrated system vs. open protocol adoption

**Code:** `configs/archetypes.yaml`; loaded by `utils/config.py`; matched in `graph/workflow.py::detect_scenario`

### Asymmetry
The **ratio of disruption cost to defense cost**. High asymmetry means the Disruptor can probe cheaply while the Empire spends heavily to defend each node. This is the core signal — high asymmetry = structural fragility = potential opportunity.

**Code:** `AbstractPattern.asymmetry_score` (float 0–1); `scoring/fragility.py`

### Cheap Weapon
A **low-cost disruption vector** that exploits the Empire's expensive defense surface. The Cheap Weapon is the mechanism through which asymmetry is realized.

**Examples:** An open-source model release collapsing pricing power; a software-defined routing layer bypassing a physical chokepoint; a drone strike against a high-value but lightly defended node  
**Code:** `archetype.cheap_weapon_examples` in `configs/archetypes.yaml`

---

## Signal & Data Concepts

### RawSignal
An **unprocessed data point** as fetched from a provider. Contains source, timestamp, headline/title, URL, and raw metadata.  
**Code:** `models/contracts.py::RawSignal`

### SignalEvent
A **normalized, deduplicated signal** with salience score, tags, and structural metadata attached. This is the primary unit processed through the pipeline.  
**Code:** `models/contracts.py::SignalEvent`

### EventCluster
A **group of `SignalEvent`s** that share a structural story — the same archetype trigger, geography, or entity.  
**Code:** `models/contracts.py::EventCluster`

### AbstractPattern
The **structural interpretation** of a cluster: which nodes are Empire, which are Disruptor, what the asymmetry score is, and what the cheap weapon is.  
**Code:** `models/contracts.py::AbstractPattern`

---

## Scoring Concepts

### Fragility Score
A **composite 0–1 measure** of structural weakness at a node or cluster level. Combines six weighted factors:

| Factor | Weight | What it measures |
|--------|--------|-----------------|
| `hubris_index` | 0.18 | Incumbent overconfidence — ignoring or dismissing the disruption |
| `energy_defense_ratio` | 0.22 | Cost asymmetry — how expensive is defense vs. disruption? |
| `kinetic_ripple` | 0.16 | Physical or kinetic pressure creating cascade potential |
| `centralization_score` | 0.20 | Single points of failure — how concentrated is the Empire node? |
| `redundancy_penalty` | 0.12 | Lack of fallback paths (negative = more fragile) |
| `antifragility_attraction` | 0.12 | Whether the Disruptor benefits from stress and disorder |

**Code:** `configs/scoring.yaml` (weights); `scoring/fragility.py::FragilityScorer`

### Fragility Assessment
The **output of fragility scoring** for a single node: the score, dominant factor, contributing signals, and confidence level.  
**Code:** `models/contracts.py::FragilityAssessment`

### High Fragility Threshold
Nodes scoring above **0.72** are classified as "high fragility" — eligible for opportunity generation.  
**Code:** `configs/scoring.yaml::thresholds.high_fragility`

---

## Opportunity Concepts

### EquityOpportunity
A **structured opportunity idea** surfaced from a fragile node: the thesis, target entity, long/short direction, invalidation conditions, time horizon, and conviction score.  
**Code:** `models/contracts.py::EquityOpportunity`

### Invalidation Logic
**Explicit conditions under which an opportunity thesis fails.** Every `EquityOpportunity` must have at least one invalidation condition. This prevents vague or unfalsifiable ideas.  
**Code:** `EquityOpportunity.invalidation_conditions` (list of strings)

### Monitor-Only
A flag (`EquityOpportunity.monitor_only = True`) indicating the idea has **structural merit but insufficient evidence** to act. It should be tracked, not traded.  
**Code:** `models/contracts.py::EquityOpportunity.monitor_only`; gated in `agents/execution_critic.py`

### Convexity
A measure of the **asymmetric payoff profile** of an opportunity. High convexity = limited downside, large potential upside. The system targets only high-convexity ideas.

---

## Pipeline Concepts

### Run Mode
How signals are sourced for a pipeline run:
- `demo` — loads deterministic fixture signals from `data/samples/`
- `live` — fetches signals for a specified `window_start`/`window_end`
- `latest` — fetches signals for the last N minutes (default 60)
- `replay` — rebuilds a report from previously stored raw signals

**Code:** `FaultlineState.run_mode`; `graph/runner.py`

### Ripple Scenario
A **projected second-order cascade effect** from a fragility event. Ripple scenarios map what breaks next if the primary node fails.  
**Code:** `models/contracts.py::RippleScenario`; generated by `agents/ripple_architect.py`

### Dead Letter
A **failed provider fetch** that is logged to persistence rather than crashing the pipeline. Allows partial ingestion to proceed.  
**Code:** `persistence/store.py::log_dead_letter()`

### Trace
A **node-by-node state snapshot** written to `outputs/{scenario}/{run_id}/trace.json`. Each entry is one state snapshot per node — enables replay and debugging of any run step by step.  
**Code:** `graph/runner.py`; `utils/io.py`

---

## LLM Concepts

### StructuredReasoner
The **base class for all LLM-backed agent nodes**. Wraps OpenAI's structured output API with schema enforcement. All four LLM agents extend this.  
**Code:** `llm/backend.py::StructuredReasoner`

### Schema Enforcement
OpenAI's strict structured output mode requires `additionalProperties: false` on every object in the schema **and** all properties listed in `required`. Pydantic doesn't generate this by default — `_enforce_additional_properties()` in `backend.py` patches schemas before every call.  
**Code:** `llm/backend.py::_enforce_additional_properties()`

---

## Provider Concepts

### BaseProvider
The **interface all signal providers implement**. One method: `fetch_window(start_at, end_at) -> list[RawSignal]`.  
**Code:** `providers/base.py::BaseProvider`

### Provider Health
A **connectivity check** for all registered providers. Returns status per provider without failing the pipeline.  
**Code:** `faultline provider-health` CLI; `providers/registry.py`
