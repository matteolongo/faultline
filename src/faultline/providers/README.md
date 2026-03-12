# Providers Package

This package handles signal ingestion and the first-stage transformation into normalized events and clusters.

## Workflow Responsibilities

- `ingest_signals` pulls raw inputs from sample or live providers.
- `normalize_events` deduplicates, tags, groups, and scores those inputs into `SignalEvent` and `EventCluster` objects.

## Main Files

- `base.py` defines the provider interface and shared HTTP behavior.
- `live.py` contains the external data providers and web-search enrichment logic.
- `sample.py` loads scenario fixtures used for demo and goldset runs.
- `registry.py` builds the default live provider list.
- `normalizer.py` contains `SignalNormalizer`, which deduplicates, derives story keys, extracts entities, assigns regions, and builds ranked clusters.

## What It Is For

- Isolating upstream data-source behavior from the rest of the graph.
- Converting messy heterogeneous signals into a stable internal event format.
- Supporting both deterministic sample scenarios and live ingestion windows.

## Use This Package When

- You are adding a new upstream data source.
- You need to change dedupe, clustering, tagging, region inference, or provider weighting.
- You are debugging why a run did or did not produce a strong selected cluster.
