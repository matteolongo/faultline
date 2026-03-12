from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import NodeReviewSession
from faultline.presentation.operator_surface import (
    available_demo_scenarios,
    current_review_step,
    list_recent_runs,
    load_report_markdown,
    parse_operator_datetime,
    review_toc_rows,
    summarize_final_state,
)
from faultline.utils.env import bootstrap_env
from faultline.utils.io import serialize_model


def _parse_symbol_csv(value: str) -> list[dict[str, str]]:
    return [{"symbol": token.strip()} for token in value.split(",") if token.strip()]


def _store_review_session(st: Any, session: NodeReviewSession) -> None:
    st.session_state["review_session"] = session.model_dump(mode="json")


def _load_review_session(st: Any) -> NodeReviewSession | None:
    raw = st.session_state.get("review_session")
    if not raw:
        return None
    return NodeReviewSession.model_validate(raw)


def _clear_review_session(st: Any) -> None:
    st.session_state["review_session"] = None


def _render_completed_run(st: Any, session: NodeReviewSession, output_dir: str) -> None:
    final_state = serialize_model(session.final_state)
    summary = summarize_final_state(final_state)
    summary["run_id"] = session.selected_run_id
    summary["run_dir"] = session.selected_run_dir
    report_markdown = load_report_markdown(session.selected_run_dir) if session.selected_run_dir else None

    left, right = st.columns([1, 2])
    with left:
        st.subheader("Run Summary")
        st.json(summary)
        st.subheader("Latest Runs")
        st.dataframe(list_recent_runs(output_dir), use_container_width=True)
    with right:
        report_json = final_state.get("final_report", {})
        st.subheader(report_json.get("publication_status", "completed"))
        st.markdown(report_json.get("executive_summary", "No report generated."))
        if report_json.get("topic_prompt"):
            st.markdown(f"**Topic**: {report_json['topic_prompt']}")
        if report_json.get("deep_dive_objective"):
            st.markdown(f"**Deep-Dive Objective**: {report_json['deep_dive_objective']}")
        if report_json.get("monitor_only_reason"):
            st.warning(report_json["monitor_only_reason"])
        if report_markdown:
            st.markdown("### Full Report")
            st.markdown(report_markdown)


def _render_delta_summary(st: Any, step: dict[str, Any]) -> None:
    if not step.get("changed_keys"):
        st.caption("No state keys changed for this node.")
        return
    rows = [{"key": key, "summary": step["delta_summary"].get(key, "")} for key in step["changed_keys"]]
    st.dataframe(rows, use_container_width=True)


def _render_preview(st: Any, step: dict[str, Any], session: NodeReviewSession) -> None:
    payload = step.get("preview_payload", {})
    node_id = step["node_id"]
    if node_id == "ingest_signals":
        st.dataframe(payload.get("signals", []), use_container_width=True)
        st.json(payload.get("source_counts", {}))
        return
    if node_id == "normalize_events":
        st.markdown(f"**Selected Cluster**: `{payload.get('selected_cluster_id') or 'none'}`")
        st.markdown(f"**Included Signals**: {len(payload.get('included_signal_ids', []))}")
        st.markdown(f"**Excluded Signals**: {len(payload.get('excluded_signal_ids', []))}")
        st.dataframe(payload.get("normalized_events", []), use_container_width=True)
        st.dataframe(payload.get("candidate_clusters", []), use_container_width=True)
        return
    if node_id == "retrieve_related_situations":
        for item in payload.get("related_situations", []):
            with st.expander(item.get("title", "Related situation"), expanded=False):
                st.markdown(item.get("summary", ""))
                st.markdown(f"Similarity: `{item.get('similarity_score', 0)}`")
                if item.get("mechanisms"):
                    st.markdown(f"Mechanisms: {', '.join(item['mechanisms'])}")
        return
    if node_id == "retrieve_calibration":
        st.markdown(f"**Calibration Signals**: {payload.get('count', 0)}")
        st.dataframe(payload.get("calibration_signals", []), use_container_width=True)
        return
    if node_id == "map_situation":
        snapshot = payload.get("situation_snapshot", {})
        st.json(
            {
                "title": snapshot.get("title"),
                "stage": snapshot.get("stage", {}).get("stage"),
                "system_under_pressure": snapshot.get("system_under_pressure"),
                "actors": payload.get("actors", []),
                "mechanisms": payload.get("mechanisms", []),
            }
        )
        return
    if node_id == "generate_predictions":
        st.dataframe(payload.get("predictions", []), use_container_width=True)
        st.dataframe(payload.get("scenario_tree", []), use_container_width=True)
        st.dataframe(payload.get("stage_transition_warnings", []), use_container_width=True)
        return
    if node_id == "map_market_implications":
        st.dataframe(payload.get("market_implications", []), use_container_width=True)
        return
    if node_id == "generate_actions":
        st.dataframe(payload.get("action_recommendations", []), use_container_width=True)
        st.dataframe(payload.get("exit_signals", []), use_container_width=True)
        if payload.get("endangered_symbols"):
            st.markdown(f"**Endangered symbols**: {', '.join(payload['endangered_symbols'])}")
        return
    if node_id == "synthesize_report":
        st.markdown(f"**Headline**: {payload.get('headline', '')}")
        st.markdown(payload.get("executive_summary", ""))
        st.json(
            {
                "publication_status": payload.get("publication_status"),
                "retrieval_questions": payload.get("retrieval_questions", []),
                "market_implications": payload.get("market_implications", []),
            }
        )
        return
    st.success(payload.get("message", "Situation saved."))


def _review_editor(st: Any, step: dict[str, Any], session: NodeReviewSession) -> dict[str, Any]:
    payload = step.get("editable_payload", {})
    node_id = step["node_id"]
    prefix = f"{session.session_id}_{node_id}"
    if node_id == "normalize_events":
        raw_signals = session.state_snapshots[step["pre_state_index"]].get("raw_signals", [])
        options = {item["id"]: f"{item['id']} | {item.get('source')} | {item.get('title')}" for item in raw_signals}
        excluded_ids = st.multiselect(
            "Exclude signals",
            options=list(options.keys()),
            default=payload.get("excluded_signal_ids", []),
            format_func=lambda item: options[item],
            key=f"{prefix}_excluded",
        )
        clusters = payload.get("candidate_clusters") or step.get("preview_payload", {}).get("candidate_clusters", [])
        cluster_options = {item["cluster_id"]: f"{item['cluster_id']} | {item['title']}" for item in clusters}
        selected_cluster_id = st.selectbox(
            "Primary cluster",
            options=list(cluster_options.keys()) or [""],
            index=(
                list(cluster_options.keys()).index(payload.get("selected_cluster_id"))
                if payload.get("selected_cluster_id") in cluster_options
                else 0
            ),
            format_func=lambda item: cluster_options.get(item, "No clusters available"),
            key=f"{prefix}_cluster",
        )
        return {
            "excluded_signal_ids": excluded_ids,
            "selected_cluster_id": selected_cluster_id or None,
        }
    if node_id == "map_situation":
        return {
            "title": st.text_input("Situation title", value=payload.get("title", ""), key=f"{prefix}_title"),
            "summary": st.text_area(
                "Situation summary",
                value=payload.get("summary", ""),
                height=140,
                key=f"{prefix}_summary",
            ),
            "system_under_pressure": st.text_input(
                "System under pressure",
                value=payload.get("system_under_pressure", ""),
                key=f"{prefix}_system",
            ),
        }
    if node_id == "map_market_implications":
        return {
            "market_implications": st.data_editor(
                payload.get("market_implications", []),
                num_rows="dynamic",
                key=f"{prefix}_implications",
            )
        }
    if node_id == "generate_actions":
        return {
            "action_recommendations": st.data_editor(
                payload.get("action_recommendations", []),
                num_rows="dynamic",
                key=f"{prefix}_actions",
            ),
            "exit_signals": st.data_editor(
                payload.get("exit_signals", []),
                num_rows="dynamic",
                key=f"{prefix}_exits",
            ),
        }
    if node_id == "synthesize_report":
        return {
            "headline": st.text_input("Headline", value=payload.get("headline", ""), key=f"{prefix}_headline"),
            "executive_summary": st.text_area(
                "Executive summary",
                value=payload.get("executive_summary", ""),
                height=160,
                key=f"{prefix}_executive_summary",
            ),
        }
    return {}


def _render_review_actions(
    st: Any, runner: StrategicSwarmRunner, session: NodeReviewSession, step: dict[str, Any]
) -> None:
    editable = bool(step.get("editable_payload"))
    edits = _review_editor(st, step, session) if editable else {}
    cols = st.columns(2 if editable else 1)
    if editable and cols[0].button("Apply Changes", key=f"{session.session_id}_{step['node_id']}_apply"):
        session = runner.apply_review_edits(session, edits=edits)
        _store_review_session(st, session)
        st.rerun()
    if cols[-1].button("Approve And Continue", key=f"{session.session_id}_{step['node_id']}_approve"):
        if editable:
            session = runner.apply_review_edits(session, edits=edits)
        session = runner.approve_review_step(session)
        _store_review_session(st, session)
        st.rerun()


def _render_review_session(st: Any, runner: StrategicSwarmRunner, session: NodeReviewSession, output_dir: str) -> None:
    session = runner.load_review_session(session)
    _store_review_session(st, session)
    toc_rows = review_toc_rows(session.model_dump(mode="json"))
    current_step = current_review_step(session.model_dump(mode="json"))

    if session.status == "completed":
        _render_completed_run(st, session, output_dir)

    left, right = st.columns([1, 3])
    with left:
        st.subheader("Node TOC")
        st.dataframe(toc_rows, use_container_width=True)
        if current_step:
            st.caption(f"Paused at `{current_step['node_id']}`")
        elif session.selected_run_id:
            st.caption(f"Completed run `{session.selected_run_id}`")
        if st.button("Reset Review Session"):
            _clear_review_session(st)
            st.rerun()

    with right:
        for step in session.steps:
            step_payload = step.model_dump(mode="json")
            expanded = step.status == "paused"
            label = (
                f"{step.title} | {step.status} | "
                f"{len(step.changed_keys)} changed keys | {step.artifact_summary or 'no artifact summary'}"
            )
            with st.expander(label, expanded=expanded):
                st.markdown("### What Changed")
                _render_delta_summary(st, step_payload)
                st.markdown("### Preview")
                _render_preview(st, step_payload, session)
                if step.status == "paused":
                    st.markdown("### Review Action")
                    _render_review_actions(st, runner, session, step_payload)


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - dependency-gated runtime
        raise SystemExit("Install operator extras first: pip install -e '.[operator]'") from exc

    bootstrap_env()
    st.set_page_config(page_title="Faultline Operator", layout="wide")
    st.title("Faultline Operator")
    st.caption("Human-in-the-loop review over the native LangGraph workflow.")
    st.session_state.setdefault("topic_chat_session", None)
    st.session_state.setdefault("review_session", None)

    output_dir = st.sidebar.text_input("Output directory", value=os.getenv("FAULTLINE_OUTPUT_DIR", "outputs"))
    runner = StrategicSwarmRunner(output_dir=output_dir)

    st.sidebar.subheader("Provider Health")
    st.sidebar.dataframe(runner.provider_health(), use_container_width=True)
    mode = st.sidebar.selectbox("Mode", ["topic_chat", "demo", "latest", "live", "replay"])

    review_session = _load_review_session(st)
    if review_session is not None:
        _render_review_session(st, runner, review_session, output_dir)
        return

    scenario = None
    start_at = None
    end_at = None
    lookback_minutes = None
    run_id = None

    if mode == "topic_chat":
        topic = st.sidebar.text_area("Topic or thesis", value=st.session_state.get("topic_chat_topic", ""), height=100)
        thesis = st.sidebar.text_input("Optional thesis", value=st.session_state.get("topic_chat_thesis", ""))
        positions_raw = st.sidebar.text_input(
            "Positions (optional)",
            value=st.session_state.get("topic_chat_positions", ""),
        )
        watchlist_raw = st.sidebar.text_input(
            "Watchlist (optional)",
            value=st.session_state.get("topic_chat_watchlist", ""),
        )
        st.session_state["topic_chat_topic"] = topic
        st.session_state["topic_chat_thesis"] = thesis
        st.session_state["topic_chat_positions"] = positions_raw
        st.session_state["topic_chat_watchlist"] = watchlist_raw

        if st.sidebar.button("Start Topic Chat", type="primary"):
            session = runner.prepare_topic_chat(
                topic,
                thesis=thesis or None,
                portfolio_positions=_parse_symbol_csv(positions_raw),
                watchlist=_parse_symbol_csv(watchlist_raw),
            )
            st.session_state["topic_chat_session"] = session.model_dump(mode="json")
        if st.sidebar.button("Reset Topic Chat"):
            st.session_state["topic_chat_session"] = None

        topic_session = st.session_state.get("topic_chat_session")
        if not topic_session:
            st.subheader("Latest Runs")
            st.dataframe(list_recent_runs(output_dir), use_container_width=True)
            return

        st.subheader("Topic Chat")
        st.markdown(f"**Original Topic**: {topic_session['topic_prompt']['topic']}")
        st.markdown(f"**Current Interpretation**: {topic_session['interpretation']}")
        st.markdown(f"**Status**: `{topic_session['status']}`")
        st.json(topic_session["brief"])
        if topic_session.get("turns"):
            st.markdown("### Intake Transcript")
            for turn in topic_session["turns"]:
                st.markdown(f"**System**: {turn['system_question']}")
                st.markdown(f"**User**: {turn['user_answer']}")
        if topic_session.get("current_question"):
            answer = st.text_input("Next answer", key="topic_chat_answer")
            if st.button("Submit Answer"):
                updated = runner.continue_topic_chat(topic_session, answer)
                st.session_state["topic_chat_session"] = updated.model_dump(mode="json")
                st.rerun()
            return
        if st.button("Start Review Session", type="primary"):
            review = runner.start_review_session(
                mode="topic_chat",
                topic_session=topic_session,
            )
            _store_review_session(st, review)
            st.rerun()
        return

    if mode == "demo":
        scenario = st.sidebar.selectbox("Scenario", available_demo_scenarios(), index=0)
    elif mode == "latest":
        lookback_minutes = int(st.sidebar.number_input("Lookback minutes", min_value=15, value=60, step=15))
    elif mode == "live":
        default_end = datetime.now(UTC).replace(microsecond=0, second=0)
        default_start = default_end - timedelta(minutes=60)
        start_at = parse_operator_datetime(st.sidebar.text_input("Start (ISO8601)", value=default_start.isoformat()))
        end_at = parse_operator_datetime(st.sidebar.text_input("End (ISO8601)", value=default_end.isoformat()))
    elif mode == "replay":
        run_id = st.sidebar.text_input("Run ID", value="")
        st.sidebar.caption("Leave empty to replay a stored time window instead.")
        start_at = parse_operator_datetime(st.sidebar.text_input("Replay start (optional ISO8601)", value=""))
        end_at = parse_operator_datetime(st.sidebar.text_input("Replay end (optional ISO8601)", value=""))

    if st.sidebar.button("Start Review Session", type="primary"):
        review = runner.start_review_session(
            mode=mode,
            scenario=scenario,
            start_at=start_at,
            end_at=end_at,
            lookback_minutes=lookback_minutes,
            run_id=run_id or None,
        )
        _store_review_session(st, review)
        st.rerun()

    st.subheader("Latest Runs")
    st.dataframe(list_recent_runs(output_dir), use_container_width=True)


if __name__ == "__main__":  # pragma: no cover - streamlit entrypoint
    main()
