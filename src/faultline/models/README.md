# Models Package

This package defines the typed contracts for the entire Faultline system.

## Main Files

- `contracts.py` contains the Pydantic models for signals, clusters, situations, predictions, implications, actions, reports, checkpoints, and operator surfaces.
- `state.py` contains `FaultlineInputSchema` and `FaultlineState`, which define the graph input and state payloads.

## What It Is For

- Keeping every stage explicit and typed.
- Giving the graph, storage layer, and report synthesis a shared vocabulary.
- Making LLM, operator, and persistence boundaries validate cleanly.

## Use This Package When

- You add a new workflow field or remove an old one.
- You need a new contract for a report section, checkpoint, provider output, or action surface.
- You want to understand what each node is allowed to read or write.

If you change the graph nodes or report sections, update these models in the same change.
