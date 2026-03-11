from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

from faultline.graph.runner import StrategicSwarmRunner
from faultline.presentation.operator_surface import (
    available_demo_scenarios,
    list_recent_runs,
    load_report_markdown,
    parse_operator_datetime,
    run_and_summarize,
)
from faultline.utils.env import bootstrap_env


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - dependency-gated runtime
        raise SystemExit("Install operator extras first: pip install -e '.[operator]'") from exc

    bootstrap_env()
    st.set_page_config(page_title="Faultline Operator", layout="wide")
    st.title("Faultline Operator")
    st.caption("Manual research runs over the existing StrategicSwarmRunner.")

    output_dir = st.sidebar.text_input("Output directory", value=os.getenv("FAULTLINE_OUTPUT_DIR", "outputs"))
    runner = StrategicSwarmRunner(output_dir=output_dir)

    st.sidebar.subheader("Provider Health")
    st.sidebar.dataframe(runner.provider_health(), use_container_width=True)

    mode = st.sidebar.selectbox("Mode", ["demo", "latest", "live", "replay"])
    scenario = None
    start_at = None
    end_at = None
    lookback_minutes = None
    run_id = None

    if mode == "demo":
        scenario = st.sidebar.selectbox("Scenario", available_demo_scenarios(), index=0)
    elif mode == "latest":
        lookback_minutes = int(st.sidebar.number_input("Lookback minutes", min_value=15, value=60, step=15))
    elif mode == "live":
        default_end = datetime.now(UTC).replace(microsecond=0, second=0)
        default_start = default_end - timedelta(minutes=60)
        start_raw = st.sidebar.text_input("Start (ISO8601)", value=default_start.isoformat())
        end_raw = st.sidebar.text_input("End (ISO8601)", value=default_end.isoformat())
        start_at = parse_operator_datetime(start_raw)
        end_at = parse_operator_datetime(end_raw)
    elif mode == "replay":
        run_id = st.sidebar.text_input("Run ID", value="")
        st.sidebar.caption("Leave empty to replay a stored time window instead.")
        start_raw = st.sidebar.text_input("Replay start (optional ISO8601)", value="")
        end_raw = st.sidebar.text_input("Replay end (optional ISO8601)", value="")
        start_at = parse_operator_datetime(start_raw)
        end_at = parse_operator_datetime(end_raw)

    if st.sidebar.button("Run", type="primary"):
        payload = run_and_summarize(
            runner,
            mode=mode,
            scenario=scenario,
            start_at=start_at,
            end_at=end_at,
            lookback_minutes=lookback_minutes,
            run_id=run_id or None,
        )
        summary = payload["summary"]
        report_json = payload["report_json"] or {}

        left, right = st.columns([1, 2])
        with left:
            st.subheader("Run Summary")
            st.json(summary)
            st.subheader("Latest Runs")
            st.dataframe(list_recent_runs(output_dir), use_container_width=True)
        with right:
            st.subheader(report_json.get("publication_status", "unknown"))
            st.markdown(report_json.get("executive_summary", "No report generated."))
            if report_json.get("monitor_only_reason"):
                st.warning(report_json["monitor_only_reason"])
            if report_json.get("market_implications"):
                st.markdown("### Market Implications")
                for item in report_json["market_implications"]:
                    st.markdown(f"- {item}")
            st.markdown("### Provenance")
            for item in report_json.get("provenance", []):
                st.markdown(f"- {item}")
            markdown_report = payload["report_markdown"] or load_report_markdown(summary["run_dir"])
            if markdown_report:
                st.markdown("### Full Report")
                st.markdown(markdown_report)
    else:
        st.subheader("Latest Runs")
        st.dataframe(list_recent_runs(output_dir), use_container_width=True)


if __name__ == "__main__":  # pragma: no cover - streamlit entrypoint
    main()
