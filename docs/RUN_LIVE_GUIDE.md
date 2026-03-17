# Using `run-live` on a 48-Hour Live News Window

This guide reflects the current implementation in:

- `src/faultline/__main__.py`
- `src/faultline/graph/runner.py`
- `src/faultline/graph/workflow.py`
- `configs/providers.yaml`

## Current State Review

The live path in the repository is no longer the older 10-node path shown in some top-level docs. The current production workflow is a 14-node graph:

1. `plan_retrieval`
2. `ingest_signals`
3. `normalize_events`
4. `extract_evidence_claims`
5. `retrieve_related_situations`
6. `retrieve_calibration`
7. `map_situation`
8. `build_consequence_graph`
9. `generate_predictions`
10. `map_market_implications`
11. `generate_actions`
12. `collect_run_metrics`
13. `synthesize_report`
14. `remember_situation`

Important current-state facts before you use `run-live`:

- `run-live` is a CLI wrapper around `StrategicSwarmRunner.run_live(...)`.
- A run persists artifacts to disk and to the SQLite/Postgres store.
- The current live provider set is `newsapi`, `alphavantage`, `fred`, and `gdelt`.
- `openai-websearch` exists, but it is currently used in `topic_chat`, not in the normal `run-live` path.
- The workflow builds one report per run around `selected_cluster`, even if the normalization stage produced multiple clusters.
- Live mode deduplicates against previously seen raw signals, so repeated windows can look thinner than the first run.

## Exact 48-Hour Window

At `2026-03-17T22:14:37Z`, the strict last-48-hours window is:

- `start=2026-03-15T22:14:37Z`
- `end=2026-03-17T22:14:37Z`

If you want to generate that window dynamically:

macOS:

```bash
START=$(date -u -v-48H +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

Linux:

```bash
START=$(date -u -d '48 hours ago' +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
```

## Live Themes Worth Watching In This Window

The current provider queries are biased toward chokepoints, protocols, stablecoins, payment rails, refinancing stress, and open-model competition. Within the March 15-17, 2026 window, the most relevant live themes are:

- Stablecoin and payment-rail consolidation:
  [Axios: Mastercard expands crypto effort, buying BVNK](https://www.axios.com/2026/03/17/mastercard-crypto-bvnk)
- Energy and shipping chokepoint stress:
  [WSJ live coverage: Hormuz crossings paralyzed, but China-bound ships keep moving](https://www.wsj.com/livecoverage/stock-market-today-dow-sp-500-nasdaq-03-17-2026/card/hormuz-crossings-paralysed-but-china-bound-ships-keep-moving-tJLyPHyGeYfpJXflVNtw)
- Oil and gas repricing pressure from the same conflict cluster:
  [The Guardian: Oil and gas prices rise again after Iran attacks production facilities](https://www.theguardian.com/business/2026/mar/17/oil-gas-prices-rise-iran-us-israel-war-brent-crude-uae-strikes)
- Stablecoin infrastructure M&A from a market-facing outlet:
  [Barron's: Mastercard to buy stablecoin startup BVNK for $1.8 billion](https://www.barrons.com/articles/mastercard-bvnk-stablecoin-crypto-bb8fe3ad)

Those themes line up well with the repository's configured live retrieval focus.

## Preflight

First check which providers are actually configured in your environment:

```bash
faultline provider-health
```

Expected behavior:

- `gdelt` can run without an API key.
- `newsapi` requires `NEWSAPI_API_KEY`.
- `alphavantage` requires `ALPHAVANTAGE_API_KEY`.
- `fred` requires `FRED_API_KEY`.

Relevant environment variables:

- `FAULTLINE_OUTPUT_DIR`
- `FAULTLINE_DATABASE_URL`
- `FAULTLINE_DEFAULT_LOOKBACK_MINUTES`
- `NEWSAPI_API_KEY`
- `ALPHAVANTAGE_API_KEY`
- `FRED_API_KEY`

## Minimal 48-Hour Run

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z
```

That is enough to:

- fetch live signals from the configured providers
- normalize and deduplicate them
- select the strongest cluster
- generate situation mapping, predictions, market implications, and actions
- write artifacts into the output directory

The CLI prints:

```json
{
  "run_id": "...",
  "run_dir": "..."
}
```

## All `run-live` Features

### 1. Raw window control

Required flags:

- `--start`
- `--end`

Both must be ISO-8601 timestamps. UTC with `Z` is the safest choice.

### 2. Portfolio-aware execution

Simple symbol-only form:

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --positions XLE,QQQ \
  --watchlist NVDA,COIN,GLD
```

Use this only when you need symbol names and nothing else.

### 3. Structured positions JSON

Use `--positions-json` when you want:

- `direction`
- `quantity`
- `cost_basis`
- `tags`
- `notes`

Example file:

- `docs/examples/run_live_positions_48h.json`

Run:

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --positions-json docs/examples/run_live_positions_48h.json
```

### 4. Structured watchlist JSON

Use `--watchlist-json` when you want:

- `bias`
- `tags`
- `notes`

Example file:

- `docs/examples/run_live_watchlist_48h.json`

Run:

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --watchlist-json docs/examples/run_live_watchlist_48h.json
```

### 5. Operator policy overrides

Use `--policy-json` to change action thresholds.

Example file:

- `docs/examples/run_live_policy_48h.json`

Useful when you want:

- later or earlier trim/exit behavior
- tighter watchlist enter/avoid thresholds
- more aggressive timing-window behavior
- higher urgency thresholds
- conflict preservation via `allow_conflicting_actions`

Run:

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --policy-json docs/examples/run_live_policy_48h.json
```

### 6. Automatic follow-up scoring

`run-live` can immediately trigger follow-up scoring after the run finishes.

Flags:

- `--auto-followup`
- `--followup-min-age-minutes`
- `--followup-limit-runs`
- `--followup-include-demo`
- `--followup-rescore-existing`

Example:

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --auto-followup \
  --followup-min-age-minutes 180 \
  --followup-limit-runs 10
```

What it does:

- loads raw signals from the same follow-up window
- finds eligible older runs
- scores prior predictions against those signals
- writes `outcomes.json` and `outcomes.md` into each affected run directory

### 7. Include demo runs in follow-up scoring

Add:

```bash
--followup-include-demo
```

Use this if you want old sample runs to be rescored alongside real live runs.

### 8. Rescore already scored runs

Add:

```bash
--followup-rescore-existing
```

Use this only when you explicitly want to overwrite or refresh prior follow-up judgments.

### 9. Custom output location

Use:

```bash
--output-dir /path/to/output/root
```

If omitted, Faultline uses `FAULTLINE_OUTPUT_DIR` or `outputs/`.

## Recommended Full Command For The Current 48-Hour Window

```bash
faultline run-live \
  --start 2026-03-15T22:14:37Z \
  --end 2026-03-17T22:14:37Z \
  --positions-json docs/examples/run_live_positions_48h.json \
  --watchlist-json docs/examples/run_live_watchlist_48h.json \
  --policy-json docs/examples/run_live_policy_48h.json \
  --auto-followup \
  --followup-min-age-minutes 180 \
  --followup-limit-runs 10 \
  --output-dir outputs
```

## Python API Equivalent

```python
from datetime import UTC, datetime

from faultline.graph.runner import StrategicSwarmRunner

runner = StrategicSwarmRunner(output_dir="outputs")

result = runner.run_live(
    start_at=datetime(2026, 3, 15, 22, 14, 37, tzinfo=UTC),
    end_at=datetime(2026, 3, 17, 22, 14, 37, tzinfo=UTC),
    portfolio_positions=[
        {"symbol": "XLE", "direction": "long", "quantity": 15, "tags": ["energy", "oil", "shipping"]},
        {"symbol": "QQQ", "direction": "long", "quantity": 12, "tags": ["ai", "platforms", "semis"]},
    ],
    watchlist=[
        {"symbol": "NVDA", "tags": ["enablers", "ai", "compute"]},
        {"symbol": "COIN", "tags": ["stablecoin", "payment-rails", "crypto"]},
        {"symbol": "GLD", "tags": ["safe-haven", "macro"]},
    ],
    operator_policy_config={
        "portfolio_trim_threshold": 0.58,
        "portfolio_exit_threshold": 0.75,
        "watchlist_enter_threshold": 0.70,
        "timing_trim_threshold": 0.55,
        "timing_exit_threshold": 0.72,
        "high_urgency_threshold": 0.78,
    },
    auto_followup=True,
    followup_min_run_age_minutes=180,
    followup_limit_runs=10,
)

print(result["run_id"])
print(result["run_dir"])
```

## What The Run Produces

For each `run-live` invocation, Faultline writes a run directory that typically contains:

- `report.md`
- `report.json`
- `state.json`
- `trace.json`

If follow-up scoring runs later, it also writes:

- `outcomes.json`
- `outcomes.md`

What to inspect first:

- `report.md`: operator-facing narrative output
- `report.json`: structured report payload
- `state.json`: full final state, including predictions, implications, actions, diagnostics, and run metrics
- `trace.json`: node-by-node review trace and snapshots

## What To Inspect Inside `state.json`

The highest-signal fields for live debugging are:

- `event_clusters`
- `selected_cluster`
- `evidence_claims`
- `transmission_paths`
- `market_exposures`
- `predictions`
- `market_implications`
- `action_recommendations`
- `exit_signals`
- `endangered_symbols`
- `diagnostics`
- `run_metrics`

Useful diagnostics keys include:

- `source_counts`
- `provider_coverage`
- `duplicates_removed`
- `selected_cluster_reason`
- `detected_scenario`
- `equity_opportunity_count`

Useful `run_metrics` keys include:

- `query_plan`
- `provider_coverage`
- `node_timings_ms`
- `dropped_signal_reasons`
- `provider_errors`
- `included_signal_count`
- `excluded_signal_count`
- `implication_specificity`
- `evidence_coverage_ratio`
- `independent_source_ratio`
- `symbol_hit_rate`
- `followup_confirmation_rate`

## Recommended Inspection Commands After The Run

```bash
faultline list-signals --limit 50
```

```bash
python - <<'PY'
import json
from pathlib import Path

run_dir = Path("outputs/live")  # replace with the printed run_dir if different
latest = sorted(run_dir.iterdir())[-1]
state = json.loads((latest / "state.json").read_text())
print("selected_cluster:", state.get("selected_cluster", {}).get("canonical_title"))
print("implications:", len(state.get("market_implications", [])))
print("actions:", len(state.get("action_recommendations", [])))
print("provider_coverage:", list(state.get("run_metrics", {}).get("provider_coverage", {}).keys()))
PY
```

## Known Limitations On A 48-Hour Window

This is the most important section for real usage.

### One run equals one selected cluster

If the last 48 hours contain:

- a Hormuz shipping story
- a stablecoin/payments story
- an AI/open-model story

`run-live` will still build the final report around only one `selected_cluster`. The other clusters are persisted, but they do not become separate reports in the same run.

### Provider caps can compress broad windows

The configured providers have bounded result collection:

- NewsAPI uses paged pulls with finite page count and page size.
- AlphaVantage news is explicitly limited.
- GDELT uses `maxrecords`.

For a volatile 48-hour window, you are getting a strategic slice, not guaranteed exhaustive coverage.

### Re-running the same live window is not the same as replaying it

Live mode checks previously seen dedupe hashes and drops already-seen raw signals. If you want to re-run exactly the same collected material, use:

```bash
faultline replay --run-id <previous-run-id>
```

or replay by exact time window after signals have already been stored.

## Best Practice For The Last 48 Hours

If your goal is "one sharp memo on the strongest live story," use one 48-hour `run-live`.

If your goal is "cover the last 48 hours with better story separation," do this instead:

1. Use `backfill` over the same 48-hour span with `--step-minutes 60`.
2. Review which hourly windows produced the strongest clusters.
3. Re-run narrower windows with `run-live` or `replay`.
4. Use `--auto-followup` only after you have a run cadence you actually want to calibrate.

## Example JSON Payloads Included In The Repo

- `docs/examples/run_live_positions_48h.json`
- `docs/examples/run_live_watchlist_48h.json`
- `docs/examples/run_live_policy_48h.json`

They are designed around the March 15-17, 2026 live themes described above.
