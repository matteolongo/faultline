from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from strategic_swarm_agent.graph.runner import StrategicSwarmRunner, default_goldset
from strategic_swarm_agent.providers.sample import SampleScenarioRepository
from strategic_swarm_agent.utils.env import bootstrap_env
from strategic_swarm_agent.utils.logging import configure_logging


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategic Swarm Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_demo = subparsers.add_parser("run-demo", help="Run one sample scenario")
    run_demo.add_argument("--scenario", required=True)
    run_demo.add_argument("--output-dir", default=None)

    run_all = subparsers.add_parser("run-all-demos", help="Run all sample scenarios")
    run_all.add_argument("--output-dir", default=None)

    evaluate = subparsers.add_parser(
        "evaluate", help="Run one scenario and score the output"
    )
    evaluate.add_argument("--scenario", required=True)
    evaluate.add_argument("--output-dir", default=None)

    ingest = subparsers.add_parser(
        "ingest-window", help="Fetch and process a live time window"
    )
    ingest.add_argument("--start", required=True)
    ingest.add_argument("--end", required=True)
    ingest.add_argument("--output-dir", default=None)

    run_latest = subparsers.add_parser(
        "run-latest", help="Run the latest live lookback window"
    )
    run_latest.add_argument("--lookback-minutes", type=int, default=None)
    run_latest.add_argument("--output-dir", default=None)

    run_live = subparsers.add_parser("run-live", help="Run a specific live time window")
    run_live.add_argument("--start", required=True)
    run_live.add_argument("--end", required=True)
    run_live.add_argument("--output-dir", default=None)

    backfill = subparsers.add_parser("backfill", help="Backfill live windows")
    backfill.add_argument("--start", required=True)
    backfill.add_argument("--end", required=True)
    backfill.add_argument("--step-minutes", type=int, default=60)
    backfill.add_argument("--output-dir", default=None)

    replay = subparsers.add_parser(
        "replay", help="Replay a previous run or stored time window"
    )
    replay.add_argument("--run-id", default=None)
    replay.add_argument("--start", default=None)
    replay.add_argument("--end", default=None)
    replay.add_argument("--output-dir", default=None)

    signals = subparsers.add_parser("list-signals", help="List persisted raw signals")
    signals.add_argument("--limit", type=int, default=25)
    signals.add_argument("--provider", default=None)
    signals.add_argument("--output-dir", default=None)

    health = subparsers.add_parser(
        "provider-health", help="Show provider configuration and recent status"
    )
    health.add_argument("--output-dir", default=None)

    goldset = subparsers.add_parser(
        "evaluate-goldset", help="Evaluate all sample scenarios"
    )
    goldset.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    bootstrap_env()
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    runner = StrategicSwarmRunner(output_dir=getattr(args, "output_dir", None))
    repository = SampleScenarioRepository()

    if args.command == "run-demo":
        result = runner.run_demo(args.scenario)
        print(
            json.dumps(
                {"run_id": result["run_id"], "run_dir": result["run_dir"]}, indent=2
            )
        )
        return

    if args.command == "run-all-demos":
        results = runner.evaluate_goldset(repository.scenario_ids())
        print(
            json.dumps(
                [
                    {
                        "scenario_id": item["scenario_id"],
                        "run_id": item["run_id"],
                        "run_dir": item["run_dir"],
                        "evaluation": item["evaluation"],
                    }
                    for item in results
                ],
                indent=2,
            )
        )
        return

    if args.command == "evaluate":
        result = runner.evaluate(args.scenario)
        print(json.dumps(result["evaluation"], indent=2))
        return

    if args.command == "ingest-window":
        result = runner.ingest_window(
            start_at=_parse_datetime(args.start), end_at=_parse_datetime(args.end)
        )
        print(json.dumps(result, indent=2))
        return

    if args.command == "run-live":
        result = runner.run_live(
            start_at=_parse_datetime(args.start), end_at=_parse_datetime(args.end)
        )
        print(
            json.dumps(
                {"run_id": result["run_id"], "run_dir": result["run_dir"]}, indent=2
            )
        )
        return

    if args.command == "run-latest":
        result = runner.run_latest(lookback_minutes=args.lookback_minutes)
        print(
            json.dumps(
                {"run_id": result["run_id"], "run_dir": result["run_dir"]}, indent=2
            )
        )
        return

    if args.command == "backfill":
        results = runner.backfill(
            start_at=_parse_datetime(args.start),
            end_at=_parse_datetime(args.end),
            step_minutes=args.step_minutes,
        )
        print(
            json.dumps(
                [
                    {"run_id": item["run_id"], "run_dir": item["run_dir"]}
                    for item in results
                ],
                indent=2,
            )
        )
        return

    if args.command == "replay":
        result = runner.replay(
            run_id=args.run_id,
            start_at=_parse_datetime(args.start) if args.start else None,
            end_at=_parse_datetime(args.end) if args.end else None,
        )
        print(
            json.dumps(
                {"run_id": result["run_id"], "run_dir": result["run_dir"]}, indent=2
            )
        )
        return

    if args.command == "list-signals":
        print(
            json.dumps(
                runner.list_signals(limit=args.limit, provider_name=args.provider),
                indent=2,
            )
        )
        return

    if args.command == "provider-health":
        print(json.dumps(runner.provider_health(), indent=2))
        return

    if args.command == "evaluate-goldset":
        results = runner.evaluate_goldset(default_goldset())
        print(json.dumps([item["evaluation"] for item in results], indent=2))


if __name__ == "__main__":
    main()
