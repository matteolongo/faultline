# Persistence Package

This package stores the durable record of Faultline runs and provider diagnostics.

## Main Module

- `store.py` contains `SignalStore` plus helpers such as `make_dead_letter`.

## What It Persists

- Raw signals
- Normalized events and event clusters
- Situation snapshots
- Calibration and outcome signals
- Run artifacts, reports, and operator workspace state
- Dead letters and provider-health diagnostics

## Workflow Responsibilities

- Supports dedupe checks and prior story counts during normalization.
- Supplies calibration signals before prediction and market mapping.
- Saves snapshots after the workflow finishes.
- Records provider failures so live ingestion can degrade without crashing the whole run.

## Use This Package When

- You need to add or change durable storage for a workflow artifact.
- You are working on replay, follow-up scoring, provider health, or dead-letter behavior.
- You need data access that survives process restarts rather than in-memory execution only.
