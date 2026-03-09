"""LangGraph Studio entrypoint.

Exposes the Strategic Swarm graph for use in LangGraph Studio / LangGraph Cloud.

Usage in langgraph.json:
    "graphs": { "strategic_swarm": "strategic_swarm_agent.graph.studio:graph" }

Default input (override in Studio's "Input" panel):
    {
        "run_mode": "demo",
        "scenario_id": "arctic_cable_bypass"
    }

Available demo scenario_ids:
    - arctic_cable_bypass
    - debt_defense_spiral
    - open_model_breakout

For live mode set:
    {
        "run_mode": "live"
    }
And ensure OPENAI_API_KEY (and optionally NEWSAPI_KEY, ALPHAVANTAGE_KEY, FRED_API_KEY)
are present in your .env file or the Studio environment.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Auto-load .env from project root (works both locally and in Studio)
load_dotenv(Path(__file__).resolve().parents[4] / ".env", override=False)

from strategic_swarm_agent.graph.workflow import StrategicSwarmWorkflow  # noqa: E402
from strategic_swarm_agent.models import SwarmInputSchema  # noqa: E402
from strategic_swarm_agent.persistence.store import SignalStore  # noqa: E402

_output_dir = Path(os.getenv("SWARM_OUTPUT_DIR", "outputs"))
_output_dir.mkdir(parents=True, exist_ok=True)

_store = SignalStore(str(_output_dir / "runs.sqlite"))
_workflow = StrategicSwarmWorkflow(store=_store)

# `graph` is the symbol LangGraph Studio expects.
# _input_schema=SwarmInputSchema restricts the Studio Input panel to the 4 user-facing fields
# (scenario_id, run_mode, window_start, window_end) without affecting programmatic invocations.
graph = _workflow.build(_input_schema=SwarmInputSchema)
