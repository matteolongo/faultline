# LLM Package

This package centralizes structured LLM calls for Faultline.

## Main Module

- `backend.py` contains `StructuredReasoner`, which sends a typed JSON-schema request to the OpenAI Responses API and falls back cleanly when the model is unavailable or the response is invalid.

## What It Does

- Builds strict structured-output schemas from Pydantic models.
- Enforces OpenAI-compatible schema constraints such as `additionalProperties: false`.
- Returns typed models plus diagnostics instead of leaking raw model responses through the rest of the codebase.

## Current Usage

- The intake flow uses it to refine a topic into a `ResearchBrief`.

## Use This Package When

- You need a new structured LLM step and want it to stay consistent with project rules.
- You need graceful fallback behavior when API credentials or live calls are unavailable.

All structured LLM integrations should route through this package instead of making direct API calls elsewhere.
