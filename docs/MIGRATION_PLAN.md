# Faultline Migration Plan

## Purpose

This repository currently implements a narrow "empire vs disruptor" fragility engine. The target system is a broader analytical agent that:

- ingests live news and market signals
- maps them into a reusable system-first analytical framework
- retrieves similar prior situations from memory
- predicts likely actor moves, narratives, and repricing paths
- produces actionable outputs for market operators
- tracks outcomes automatically from follow-up news and market data

The old architecture should be treated as disposable where it creates drag. Preserve only components that still reduce implementation cost.

## Implementation Progress

- [x] Slice 0: plan baseline committed.
- [x] Slice 1: shared ontology + state migration landed.
- [x] Slice 2-3: mechanism/stage config and system-first workflow landed.
- [x] Slice 4: local memory retrieval integrated into execution path.
- [x] Slice 5: prediction persistence + follow-up outcome scoring landed.
- [~] Slice 6: operator storytelling underway.
- [x] Added portfolio/watchlist-aware actioning and endangered-symbol reporting.
- [~] Added scenario-tree prediction layer with stage-transition warnings and confidence-band boundaries (current branch).
- [~] Added configurable operator decision policy with timing-window "leave-before-too-late" actions (current branch).
- [~] Added automatic follow-up rescoring loop over stored windows, with calibration refresh from new outcomes (current branch).
- [~] Upgraded report storytelling with action-to-evidence traceability and explicit confidence-boundary sections (current branch).
- [x] Removed disconnected legacy `agents`/`scoring` pipelines and obsolete archetype-scoring configs from the main codebase.

## Operating Rules

- Prefer replacement over incremental stretching when old abstractions are misaligned.
- Keep tests fully local. Never require real network calls or live provider credentials in tests.
- Implement in self-contained slices that can be validated independently.
- Preserve runnable entrypoints where practical, but route them to the new architecture as soon as a compatible slice exists.
- Default to structured state and structured memory first. Use semantic retrieval only as an enrichment layer.

## Target Product Behavior

For each clustered situation, the system should output:

- situation summary
- why it matters now
- key actors
- forces
- relations
- active mechanisms
- current stage
- likely next moves
- scenario tree
- market implications
- actions now
- exit signals
- evidence and references
- confidence and open uncertainties

The first target market actions are:

- watch
- enter
- trim
- exit
- avoid

The system must distinguish:

- asymmetric opportunities: non-obvious, convex, indirect, lower-consensus
- high-confidence opportunities: stronger evidence, clearer path, usually lower convexity

## Architecture Decision Summary

### Keep

- provider ingestion and normalization utilities where reusable
- structured LLM wrapper in `src/faultline/llm/backend.py`
- persistence helpers where reusable
- CLI and LangGraph entrypoints, if cheaply adapted

### Replace

- current narrow ontology in `src/faultline/models/contracts.py`
- current workflow state in `src/faultline/models/state.py`
- current prompt roles in `configs/prompts.yaml`
- current graph in `src/faultline/graph/workflow.py`
- current report shape tied to fragility/archetype/opportunity-only reasoning

### Add

- new shared ontology for system-first analysis
- mechanism and stage configuration
- memory layer with structured store plus semantic retrieval
- prediction tracking and outcome scoring
- richer analyst-style report synthesis

## Target Ontology

Create a new shared ontology centered on situation analysis rather than only topology labels.

### Core Models

- `SituationSnapshot`
- `Actor`
- `Force`
- `Relation`
- `Mechanism`
- `StageAssessment`
- `Prediction`
- `ScenarioPath`
- `MarketImplication`
- `ActionRecommendation`
- `ExitSignal`
- `OutcomeRecord`
- `EvidenceItem`
- `RelatedSituation`
- `AnalystReport`

### Minimum Shared Fields

Every situation analysis should support:

- `situation`
- `key_actors`
- `forces`
- `relations`
- `mechanisms`
- `stage`
- `next_moves`
- `scenarios`
- `opportunities`
- `risks`
- `exit_signals`
- `confidence`
- `evidence`

### Default Force Types

- power
- constraints
- alliances
- resources
- timing

### Default Relation Types

- alliance
- dependency
- competition
- containment
- leverage
- narrative_alignment
- capital_exposure

### Default Mechanism Set

- indirect_strategy
- overextension
- coalition_drift
- legitimacy_erosion
- chokepoint_pressure
- platform_bypass
- regulatory_lag
- reputation_spiral
- resource_exhaustion
- timing_mismatch

### Default Stage Ladder

- latent_tension
- signal_emergence
- pattern_formation
- strategic_positioning
- open_contestation
- repricing
- exhaustion_or_reversal

## Memory Design

Use a two-layer memory design.

### Structured Store

Persist:

- normalized signals
- event clusters
- situation snapshots
- predictions
- analyst reports
- outcome records
- follow-up observations

This can remain SQLite-backed in the first version.

### Semantic Retrieval

Use LangGraph's in-memory store with embeddings for similar-situation retrieval during execution.

First implementation target:

- `langgraph.store.memory.InMemoryStore`

Use it to store:

- situation summaries
- mechanism summaries
- scenario snapshots
- analyst report summaries

Do not use semantic retrieval as the primary source of truth. It is only an enrichment layer for:

- similar prior situations
- related mechanisms
- prior forecast examples

## Prediction and Learning Loop

The system must generate predictions and later score them automatically.

### Prediction Types

- likely actor move
- likely next narrative
- likely asset repricing
- likely timing window

### Outcome Evaluation Inputs

- follow-up news items
- follow-up market price signals
- subsequent cluster updates

### Outcome Evaluation Outputs

- prediction hit or miss
- partial match status
- realized timing vs expected timing
- confidence calibration notes
- mechanism usefulness notes

## Repo Refactor Plan

Implement in the following slices.

### Slice 0: Planning Baseline

Deliverables:

- this migration document
- new branch
- commit containing plan only

Acceptance:

- branch created with `codex/` prefix
- migration plan committed independently

### Slice 1: New Ontology and State

Goal:

Introduce the new shared analysis schema without yet requiring full live memory or prediction scoring.

Deliverables:

- new contracts replacing the narrow `AbstractPattern`-centric model
- new `FaultlineState` aligned to the new pipeline
- updated model exports
- compatibility-safe initial report model

Planned state keys:

- `scenario_id`
- `run_mode`
- `window_start`
- `window_end`
- `raw_signals`
- `normalized_events`
- `event_clusters`
- `selected_cluster`
- `related_situations`
- `situation_snapshot`
- `market_implications`
- `action_recommendations`
- `exit_signals`
- `predictions`
- `outcome_records`
- `final_report`
- `diagnostics`
- `provenance`
- `provider_health`

Acceptance:

- models validate
- tests cover new schema objects
- old narrow models are removed or clearly isolated from active paths

### Slice 2: Configuration Rewrite

Goal:

Replace archetype-centric configuration with mechanism and stage-centric configuration.

Deliverables:

- `configs/mechanisms.yaml`
- `configs/stages.yaml`
- rewritten `configs/prompts.yaml`

Prompt roles should cover:

- situation mapper
- mechanism analyst
- stage assessor
- prediction engine
- market strategist
- outcome critic
- report synthesizer

Acceptance:

- config loaders validate
- prompt text references new ontology only

### Slice 3: Workflow Rebuild

Goal:

Replace the existing graph with a system-first reasoning flow.

Target node sequence:

1. ingest signals
2. normalize events
3. cluster related events
4. retrieve related situations
5. map situation
6. infer mechanisms
7. assess stage
8. predict next moves
9. map market implications
10. generate actions
11. evaluate exits
12. synthesize report

Notes:

- clustering may initially reuse existing normalizer output if sufficient
- graph entrypoint name can remain stable for Studio and CLI compatibility
- remove nodes that are now semantically wrong rather than renaming them cosmetically

Acceptance:

- demo scenarios run end-to-end
- final state and report use only new ontology

### Slice 4: Memory Layer

Goal:

Add related-situation retrieval using LangGraph-compatible in-memory semantic storage.

Deliverables:

- memory service abstraction
- in-memory semantic store adapter
- storage format for situation summaries and mechanism snapshots
- retrieval integrated into graph execution

Acceptance:

- retrieval is testable with local fake embeddings
- no external service required in tests
- related situations are visible in state and final report

### Slice 5: Prediction Outcome Tracking

Goal:

Score previous predictions using later follow-up signals.

Deliverables:

- outcome evaluation models
- persistence for prediction records and outcome records
- automatic follow-up comparison logic

Acceptance:

- tests simulate initial prediction plus later follow-up data
- hit or miss scoring works locally

### Slice 6: Operator Surface and Storytelling

Goal:

Upgrade final outputs from a sparse structural summary to an analyst memo.

Deliverables:

- redesigned markdown report renderer
- stronger evidence and references section
- action-oriented sections for watch, enter, trim, exit, avoid

Acceptance:

- report reads as a coherent analyst memo
- references and reasoning are traceable back to evidence

### Slice 7: Legacy Removal

Goal:

Delete dead code and configs once the new path is stable.

Candidates for removal:

- old archetype configs
- old fragility-only scoring modules
- old opportunity generation path
- old report builder assumptions

Acceptance:

- no unused legacy workflow path remains in the main execution route
- tests pass after cleanup

## File-Level Migration Map

### Replace or rewrite

- `src/faultline/models/contracts.py`
- `src/faultline/models/state.py`
- `src/faultline/models/__init__.py`
- `src/faultline/graph/workflow.py`
- `configs/prompts.yaml`
- `src/faultline/synthesis/report_builder.py`

### Likely keep with adaptation

- `src/faultline/llm/backend.py`
- `src/faultline/providers/live.py`
- `src/faultline/providers/sample.py`
- `src/faultline/persistence/store.py`
- `src/faultline/graph/runner.py`
- `src/faultline/graph/studio.py`
- `src/faultline/__main__.py`

### Likely add

- `src/faultline/analysis/`
- `src/faultline/memory/`
- `src/faultline/prediction/`
- `configs/mechanisms.yaml`
- `configs/stages.yaml`
- new tests for ontology, memory, prediction scoring, report synthesis

## Testing Strategy

### General Rules

- no real network calls in tests
- no dependency on live provider credentials
- no embedding API calls in tests
- no web search calls in tests

### Test Types

#### Unit

- new model validation
- mechanism selection
- stage selection
- prediction generation fallbacks
- action classification
- exit signal logic

#### Integration

- demo scenario end-to-end graph execution
- memory retrieval using local deterministic embeddings or a fake embedder
- outcome scoring from synthetic follow-up signals

#### Regression

- CLI demo run
- Studio graph import
- markdown report rendering

### Fixtures

Add local fixtures for:

- initial cluster data
- follow-up news
- follow-up market moves
- prior situation memory entries

## Implementation Guidance For Coding Agents

- Do not mix schema replacement, workflow rewrite, and legacy cleanup in one patch when avoidable.
- Land the new ontology before changing every consumer.
- Prefer adapter functions during transition if that reduces churn for one slice.
- If a module becomes semantically misleading, replace it rather than preserving the old name and behavior mismatch.
- Keep each step runnable and testable.

## First Execution Sequence

1. create branch `codex/system-first-migration`
2. commit this plan by itself
3. implement Slice 1
4. add or rewrite tests for Slice 1
5. run tests
6. implement Slice 2 and Slice 3 together if prompt and workflow changes are tightly coupled
7. run tests
8. implement Slice 4
9. run tests
10. implement Slice 5
11. run tests
12. implement Slice 6
13. run tests
14. implement Slice 7
15. run full test suite

## Definition Of Done

The migration is complete when:

- the main graph uses the new shared ontology
- memory retrieval is integrated and locally testable
- predictions and follow-up scoring exist
- final reports include reasoning, evidence, references, and actions
- market outputs support watch, enter, trim, exit, avoid
- no tests depend on external services
- legacy architecture is removed from the main path
