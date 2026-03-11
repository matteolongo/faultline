# Faultline Glossary

## Situation Modeling

### Situation Snapshot
Structured representation of the current system under pressure, including actors, forces, relations, mechanisms, stage, risks, and supporting evidence.  
Code: `models/contracts.py::SituationSnapshot`

### Actor
Entity participating in the situation with objectives, constraints, resources, influence, and adaptability attributes.  
Code: `models/contracts.py::Actor`

### Force
Directional pressure shaping the situation outcome (default classes: power, constraints, alliances, resources, timing).  
Code: `models/contracts.py::Force`

### Relation
Typed relationship between actors (for example competition, alliance, leverage, dependency).  
Code: `models/contracts.py::Relation`

### Mechanism
Reusable causal pattern explaining how visible signals translate into strategic pressure.  
Code: `models/contracts.py::Mechanism`; config in `configs/mechanisms.yaml`

### Stage Assessment
Current phase on the stage ladder (for example `strategic_positioning`, `open_contestation`, `repricing`).  
Code: `models/contracts.py::StageAssessment`; config in `configs/stages.yaml`

## Prediction Layer

### Prediction
Explicit forecast unit with type, time horizon, confidence, banding, and prior evidence.  
Prediction types: `actor_move`, `narrative`, `asset_repricing`, `timing_window`.  
Code: `models/contracts.py::Prediction`

### Scenario Path
One branch in the scenario tree (base/upside/downside style branch with probability and confidence band).  
Code: `models/contracts.py::ScenarioPath`

### Stage Transition Warning
Warning that stage progression or reversal is likely within a lead-time window, including probability and trigger.  
Code: `models/contracts.py::StageTransitionWarning`

### Confidence Bands
Shared interpretation layer used in prediction/reporting:
- `high_confidence`: stronger evidence and tighter execution bias
- `asymmetric`: meaningful edge with non-trivial uncertainty
- `speculative`: monitor-first posture

## Market & Action Layer

### Market Implication
Translation from structural mechanism to directional market pressure on an asset/theme/sector target.  
Code: `models/contracts.py::MarketImplication`

### Action Recommendation
Operator-facing recommendation. Core actions:
- `watch`
- `enter`
- `trim`
- `exit`
- `avoid`
Code: `models/contracts.py::ActionRecommendation`

### Endangered Symbol
Held symbol flagged as vulnerable under current calibrated downside implications.  
Code path: `analysis/system_first.py::ActionEngine`

### Operator Policy Config
Configurable threshold set controlling action gating, conflict resolution, and timing-window behavior.  
Code: `models/contracts.py::OperatorPolicyConfig`

### Leave-Before-Too-Late Logic
Timing-window policy behavior that escalates from watch/trim to exit when timing pressure and stage warnings cross configured thresholds.  
Code path: `analysis/system_first.py::ActionEngine._timing_actions`

## Learning Loop

### Outcome Record
Follow-up evaluation record for a prediction, including status (`confirmed`, `partial`, `unconfirmed`) and confidence delta.  
Code: `models/contracts.py::OutcomeRecord`

### Calibration Signal
Aggregated historical prediction performance by prediction type; used to nudge confidence and rationale framing.  
Code: `models/contracts.py::CalibrationSignal`; loaded via `persistence/store.py`

### Automatic Follow-Up Scoring
Batch rescoring flow that applies a follow-up signal window to eligible prior runs and refreshes calibration inputs.  
Code: `graph/runner.py::auto_score_followups`; CLI `auto-followup`

## Reporting & Traceability

### Final Report
Structured analyst memo payload containing situation map, scenario tree, implications, actions, confidence boundaries, traceability, evidence, and references.  
Code: `models/contracts.py::FinalReport`

### Action Traceability
Section linking each action to supporting prediction(s), stage warnings, and evidence references.  
Code path: `synthesis/report_builder.py`

### Monitor-Only
Publication status for low-confidence or weak-agreement situations where full actioning is not justified.  
Code path: `synthesis/report_builder.py`
