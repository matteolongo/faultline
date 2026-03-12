# Presentation Package

This package contains UI-facing helpers for summarizing and displaying Faultline output.

## Main Module

- `operator_surface.py` provides helpers for date parsing, run summaries, workspace checkpoint tables, loading saved artifacts, listing recent runs, and running the system with a view-friendly summary payload.

## What It Is For

- Supporting the Streamlit operator app.
- Translating raw workflow output into dashboard-ready summaries.
- Reading persisted markdown and JSON artifacts back into the UI.

## Use This Package When

- You are changing what the operator surface shows.
- You need reusable presentation helpers that should not live inside the core workflow.
- You want to expose more persisted run data without touching the analytical logic.
