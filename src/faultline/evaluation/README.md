# Evaluation Package

This package contains lightweight quality scoring for generated reports.

## Main Module

- `rubric.py` computes a simple scorecard over situation quality, mechanism coverage, prediction depth, action coverage, and explainability.

## What It Is For

- Quick regression checks on report structure.
- Demo and goldset evaluation flows where you want a numeric summary of output quality.
- Comparing output completeness across runs without building a full benchmarking system.

## Use This Package When

- You want a fast heuristic score for a `FinalReport`.
- You are building tests or scripts that need a coarse quality signal.

It is not the main prediction-calibration system. Follow-up confirmation scoring lives in `prediction/`.
