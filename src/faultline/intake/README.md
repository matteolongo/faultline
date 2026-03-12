# Intake Package

This package turns a loose operator topic into a structured research brief before retrieval and graph execution start.

## Main Module

- `topic_chat.py` contains `TopicChatIntake`, which starts topic sessions, asks for missing brief fields, applies user answers, describes the resulting brief, and generates retrieval questions.

## What It Produces

- `TopicPrompt`
- `ResearchBrief`
- `ChatIntakeSession`
- Retrieval questions suitable for downstream evidence gathering

## How It Works

- Uses heuristic parsing for topic normalization, geography, time horizon, and target universe.
- Optionally calls `llm.StructuredReasoner` to refine the brief into a typed model.
- Tracks missing fields and the next clarification question required to make the brief actionable.

## Use This Package When

- You want a conversational front door before the main workflow runs.
- You need to derive a concrete evidence-gathering brief from an ambiguous topic.
- You are building topic-chat or operator-workspace flows that must stay typed and reviewable.
