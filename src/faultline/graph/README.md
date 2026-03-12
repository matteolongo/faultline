# Graph Package

This package defines and runs the production Faultline workflow.

## Main Files

- `workflow.py` defines the active node graph:
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
- `runner.py` provides high-level run modes, checkpoint workflows, replay, persistence integration, and follow-up scoring.
- `studio.py` exposes the compiled graph for LangGraph Studio or LangGraph Cloud.

## What This Package Does

- Wires the packages together in the correct order.
- Owns state transitions through `FaultlineState`.
- Separates low-level node logic from higher-level run management and operator workflows.

## Use This Package When

- You need to add, remove, or reorder production nodes.
- You need to change run modes such as demo, live, replay, topic-chat, or checkpoint reruns.
- You are integrating Faultline with LangGraph tooling or a higher-level application shell.

If you change node structure, update `models/state.py` with the matching state contract changes.
