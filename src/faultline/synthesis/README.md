# Synthesis Package

This package turns the workflow artifacts into the final operator-facing report.

## Workflow Responsibility

- `synthesize_report` uses `ReportBuilder` to combine the mapped situation, related analogs, calibration notes, predictions, scenario branches, implications, actions, exits, and provenance into a `FinalReport`.

## Main Module

- `report_builder.py` contains `ReportBuilder` plus markdown renderers for reports and outcome summaries.

## What It Produces

- Publication status and monitor-only reasoning
- Executive summary and why-now framing
- System, mechanism, scenario, and action sections
- Traceability lines, evidence lists, references, and calibration notes
- Markdown output suitable for persisted artifacts and operator review

## Use This Package When

- You need to change report structure or wording.
- You are adding a new report field that should stay traceable to evidence or predictions.
- You want to alter publish-vs-monitor decision logic.
