from __future__ import annotations

import argparse
import json

from strategic_swarm_agent.graph.runner import StrategicSwarmRunner
from strategic_swarm_agent.providers.sample import SampleScenarioRepository
from strategic_swarm_agent.utils.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Strategic Swarm Agent CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_demo = subparsers.add_parser("run-demo", help="Run one sample scenario")
    run_demo.add_argument("--scenario", required=True)
    run_demo.add_argument("--output-dir", default=None)

    run_all = subparsers.add_parser("run-all-demos", help="Run all sample scenarios")
    run_all.add_argument("--output-dir", default=None)

    evaluate = subparsers.add_parser("evaluate", help="Run one scenario and score the output")
    evaluate.add_argument("--scenario", required=True)
    evaluate.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args()
    runner = StrategicSwarmRunner(output_dir=args.output_dir)
    repository = SampleScenarioRepository()

    if args.command == "run-demo":
        result = runner.run(args.scenario)
        print(json.dumps({"run_id": result["run_id"], "run_dir": result["run_dir"]}, indent=2))
        return

    if args.command == "run-all-demos":
        results = runner.run_all(repository.scenario_ids())
        summary = [
            {
                "scenario_id": item["scenario_id"],
                "run_id": item["run_id"],
                "run_dir": item["run_dir"],
                "evaluation": item["evaluation"],
            }
            for item in results
        ]
        print(json.dumps(summary, indent=2))
        return

    if args.command == "evaluate":
        result = runner.evaluate(args.scenario)
        print(json.dumps(result["evaluation"], indent=2))


if __name__ == "__main__":
    main()
