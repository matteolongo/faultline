# Memory Package

This package manages similarity-based retrieval of prior situations for analog and calibration context.

## Workflow Responsibilities

- `retrieve_related_situations` searches memory for similar prior clusters.
- `remember_situation` stores the new `SituationSnapshot` after report synthesis.

## Main Module

- `store.py` contains `SituationMemory` and the local `HashingEmbedder`.

## What It Does

- Builds a deterministic embedding-like representation for local semantic search.
- Stores compact situation records in an in-memory LangGraph store.
- Returns `RelatedSituation` objects that the mapper and report builder can cite.

## Use This Package When

- You want to retrieve earlier analogous situations without depending on an external vector database.
- You want to change how similar situations are indexed or matched.
- You need traceable prior-situation context for mapping and reporting.
