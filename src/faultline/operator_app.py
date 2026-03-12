from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

from faultline.graph.runner import StrategicSwarmRunner
from faultline.models import (
    EvidenceCheckpoint,
    ImplicationsCheckpoint,
    OperatorWorkspaceSession,
    ReportCheckpoint,
    ResearchBrief,
    SituationCheckpoint,
)
from faultline.presentation.operator_surface import (
    available_demo_scenarios,
    list_recent_runs,
    load_report_markdown,
    parse_operator_datetime,
    run_and_summarize,
    workspace_checkpoint_rows,
)
from faultline.utils.env import bootstrap_env


def _parse_symbol_csv(value: str) -> list[dict[str, str]]:
    return [{"symbol": token.strip()} for token in value.split(",") if token.strip()]


def _split_lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _store_workspace(st: Any, workspace: OperatorWorkspaceSession) -> None:
    st.session_state["operator_workspace"] = workspace.model_dump(mode="json")


def _load_workspace(st: Any) -> OperatorWorkspaceSession | None:
    raw = st.session_state.get("operator_workspace")
    if not raw:
        return None
    return OperatorWorkspaceSession.model_validate(raw)


def _effective_brief(workspace: OperatorWorkspaceSession) -> ResearchBrief | None:
    return workspace.brief_checkpoint.approved_brief or workspace.brief_checkpoint.computed_brief


def _reset_downstream(workspace: OperatorWorkspaceSession, stage: str) -> OperatorWorkspaceSession:
    if stage == "brief":
        workspace.evidence_checkpoint = EvidenceCheckpoint()
        workspace.situation_checkpoint = SituationCheckpoint()
        workspace.implications_checkpoint = ImplicationsCheckpoint()
        workspace.report_checkpoint = ReportCheckpoint()
    elif stage == "evidence":
        workspace.situation_checkpoint = SituationCheckpoint()
        workspace.implications_checkpoint = ImplicationsCheckpoint()
        workspace.report_checkpoint = ReportCheckpoint()
    elif stage == "situation":
        workspace.implications_checkpoint = ImplicationsCheckpoint()
        workspace.report_checkpoint = ReportCheckpoint()
    elif stage == "implications":
        workspace.report_checkpoint = ReportCheckpoint()
    workspace.selected_run_id = None
    workspace.selected_run_dir = None
    return workspace


def _approve_stage(workspace: OperatorWorkspaceSession, stage: str) -> OperatorWorkspaceSession:
    if stage == "brief" and workspace.brief_checkpoint.computed_brief is not None:
        workspace.brief_checkpoint.approved_brief = workspace.brief_checkpoint.computed_brief.model_copy(deep=True)
        workspace.brief_checkpoint.status = "approved"
    elif stage == "evidence":
        workspace.evidence_checkpoint.approved_cluster_id = workspace.evidence_checkpoint.selected_cluster_id
        workspace.evidence_checkpoint.status = "approved"
    elif stage == "situation":
        workspace.situation_checkpoint.status = "approved"
    elif stage == "implications":
        workspace.implications_checkpoint.status = "approved"
    elif stage == "report" and workspace.report_checkpoint.final_report is not None:
        workspace.report_checkpoint.status = "approved"
    return workspace


def _render_payload(st: Any, payload: dict[str, Any], output_dir: str) -> None:
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
        if report_json.get("topic_prompt"):
            st.markdown(f"**Topic**: {report_json['topic_prompt']}")
        if report_json.get("deep_dive_objective"):
            st.markdown(f"**Deep-Dive Objective**: {report_json['deep_dive_objective']}")
        if report_json.get("monitor_only_reason"):
            st.warning(report_json["monitor_only_reason"])
        if report_json.get("market_implications"):
            st.markdown("### Market Implications")
            for item in report_json["market_implications"]:
                st.markdown(f"- {item}")
        if report_json.get("retrieval_questions"):
            st.markdown("### Retrieval Questions")
            for item in report_json["retrieval_questions"]:
                st.markdown(f"- {item}")
        st.markdown("### Provenance")
        for item in report_json.get("provenance", []):
            st.markdown(f"- {item}")
        markdown_report = payload["report_markdown"] or load_report_markdown(summary["run_dir"])
        if markdown_report:
            st.markdown("### Full Report")
            st.markdown(markdown_report)


def _render_brief_stage(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession) -> None:
    brief = _effective_brief(workspace) or ResearchBrief(original_topic=workspace.brief_checkpoint.topic_prompt.topic if workspace.brief_checkpoint.topic_prompt else "")
    prefix = f"{workspace.workspace_id}_brief"
    st.markdown(f"**Status**: `{workspace.brief_checkpoint.status}`")
    st.markdown(f"**Interpretation**: {workspace.brief_checkpoint.chat_intake_session.interpretation if workspace.brief_checkpoint.chat_intake_session else ''}")
    normalized_topic = st.text_input("Normalized topic", value=brief.normalized_topic, key=f"{prefix}_normalized_topic")
    system_under_study = st.text_input("System under study", value=brief.system_under_study, key=f"{prefix}_system_under_study")
    analysis_goal = st.text_input("Analysis goal", value=brief.analysis_goal, key=f"{prefix}_analysis_goal")
    geographic_scope = st.text_input("Geographic scope", value=brief.geographic_scope, key=f"{prefix}_geographic_scope")
    time_horizon = st.text_input("Time horizon", value=brief.time_horizon, key=f"{prefix}_time_horizon")
    target_universe = st.text_input("Target universe", value=brief.target_universe, key=f"{prefix}_target_universe")
    positions_raw = st.text_input(
        "Positions",
        value=",".join(item.symbol for item in brief.positions),
        key=f"{prefix}_positions",
    )
    watchlist_raw = st.text_input(
        "Watchlist",
        value=",".join(item.symbol for item in brief.watchlist),
        key=f"{prefix}_watchlist",
    )
    columns = st.columns(5)
    if columns[0].button("Save Brief Changes", key=f"{prefix}_save"):
        updated = ResearchBrief.model_validate(
            {
                **brief.model_dump(mode="json"),
                "normalized_topic": normalized_topic,
                "system_under_study": system_under_study,
                "analysis_goal": analysis_goal,
                "geographic_scope": geographic_scope,
                "time_horizon": time_horizon,
                "target_universe": target_universe,
                "positions": _parse_symbol_csv(positions_raw),
                "watchlist": _parse_symbol_csv(watchlist_raw),
            }
        )
        workspace = runner.apply_brief_edits(workspace, updated)
        _store_workspace(st, workspace)
        st.rerun()
    if columns[1].button("Approve Brief", key=f"{prefix}_approve"):
        workspace = _approve_stage(workspace, "brief")
        _store_workspace(st, workspace)
        st.rerun()
    if columns[2].button("Generate Evidence", key=f"{prefix}_generate", disabled=workspace.brief_checkpoint.status != "approved"):
        workspace = runner.build_evidence_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if columns[3].button("Rerun from Here", key=f"{prefix}_rerun", disabled=workspace.brief_checkpoint.status != "approved"):
        workspace = runner.rerun_from_checkpoint(workspace, "brief")
        _store_workspace(st, workspace)
        st.rerun()
    if columns[4].button("Reset Downstream", key=f"{prefix}_reset"):
        workspace = _reset_downstream(workspace, "brief")
        _store_workspace(st, workspace)
        st.rerun()
    st.markdown("### Intake Transcript")
    if workspace.brief_checkpoint.chat_intake_session and workspace.brief_checkpoint.chat_intake_session.turns:
        for turn in workspace.brief_checkpoint.chat_intake_session.turns:
            st.markdown(f"**System**: {turn.system_question}")
            st.markdown(f"**User**: {turn.user_answer}")
    else:
        st.caption("No follow-up turns were recorded.")


def _render_evidence_stage(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession) -> None:
    checkpoint = workspace.evidence_checkpoint
    prefix = f"{workspace.workspace_id}_evidence"
    st.markdown(f"**Status**: `{checkpoint.status}`")
    retrieval_text = st.text_area(
        "Retrieval questions",
        value="\n".join(checkpoint.retrieval_questions),
        height=140,
        key=f"{prefix}_questions",
    )
    signal_options = {item.id: f"{item.id} | {item.source} | {item.title}" for item in checkpoint.raw_signals}
    excluded_ids = st.multiselect(
        "Exclude signals",
        options=list(signal_options.keys()),
        default=checkpoint.excluded_signal_ids,
        format_func=lambda item: signal_options[item],
        key=f"{prefix}_excluded",
    )
    cluster_options = {item.cluster_id: f"{item.cluster_id} | {item.canonical_title}" for item in checkpoint.candidate_clusters}
    selected_cluster_id = st.selectbox(
        "Primary cluster",
        options=list(cluster_options.keys()) or [""],
        index=(list(cluster_options.keys()).index(checkpoint.selected_cluster_id) if checkpoint.selected_cluster_id in cluster_options else 0),
        format_func=lambda item: cluster_options.get(item, "No clusters yet"),
        key=f"{prefix}_cluster",
    )
    cols = st.columns(6)
    if cols[0].button("Save Evidence Changes", key=f"{prefix}_save"):
        workspace = runner.apply_evidence_edits(
            workspace,
            retrieval_questions=_split_lines(retrieval_text),
            excluded_signal_ids=excluded_ids,
            selected_cluster_id=selected_cluster_id or None,
        )
        _store_workspace(st, workspace)
        st.rerun()
    if cols[1].button("Generate Evidence", key=f"{prefix}_generate"):
        workspace = runner.build_evidence_checkpoint(
            workspace,
            retrieval_questions=_split_lines(retrieval_text),
            excluded_signal_ids=excluded_ids,
            selected_cluster_id=selected_cluster_id or None,
        )
        _store_workspace(st, workspace)
        st.rerun()
    if cols[2].button("Approve Evidence", key=f"{prefix}_approve", disabled=checkpoint.status == "not_started"):
        workspace.evidence_checkpoint.selected_cluster_id = selected_cluster_id or None
        workspace = _approve_stage(workspace, "evidence")
        _store_workspace(st, workspace)
        st.rerun()
    if cols[3].button("Generate Situation", key=f"{prefix}_next", disabled=workspace.evidence_checkpoint.status != "approved"):
        workspace = runner.build_situation_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[4].button("Rerun from Here", key=f"{prefix}_rerun", disabled=workspace.evidence_checkpoint.status != "approved"):
        workspace = runner.rerun_from_checkpoint(workspace, "evidence")
        _store_workspace(st, workspace)
        st.rerun()
    if cols[5].button("Reset Downstream", key=f"{prefix}_reset"):
        workspace = _reset_downstream(workspace, "evidence")
        _store_workspace(st, workspace)
        st.rerun()
    if checkpoint.raw_signals:
        st.markdown("### Signals")
        st.dataframe(
            [
                {
                    "id": item.id,
                    "source": item.source,
                    "timestamp": item.timestamp,
                    "region": item.region,
                    "confidence": item.confidence,
                    "title": item.title,
                }
                for item in checkpoint.raw_signals
            ],
            use_container_width=True,
        )
    if checkpoint.candidate_clusters:
        st.markdown("### Candidate Clusters")
        st.dataframe(
            [
                {
                    "cluster_id": item.cluster_id,
                    "title": item.canonical_title,
                    "agreement": item.agreement_score,
                    "strength": item.cluster_strength,
                }
                for item in checkpoint.candidate_clusters
            ],
            use_container_width=True,
        )


def _render_situation_stage(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession) -> None:
    checkpoint = workspace.situation_checkpoint
    prefix = f"{workspace.workspace_id}_situation"
    st.markdown(f"**Status**: `{checkpoint.status}`")
    snapshot = checkpoint.situation_snapshot
    title = st.text_input("Situation title", value=snapshot.title if snapshot else "", key=f"{prefix}_title")
    summary = st.text_area("Situation summary", value=snapshot.summary if snapshot else "", height=120, key=f"{prefix}_summary")
    system_under_pressure = st.text_input(
        "System under pressure",
        value=snapshot.system_under_pressure if snapshot else "",
        key=f"{prefix}_system",
    )
    cols = st.columns(5)
    if cols[0].button("Generate Situation", key=f"{prefix}_generate", disabled=workspace.evidence_checkpoint.status != "approved"):
        workspace = runner.build_situation_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[1].button("Save Situation Changes", key=f"{prefix}_save", disabled=snapshot is None):
        workspace = runner.apply_situation_edits(
            workspace,
            title=title,
            summary=summary,
            system_under_pressure=system_under_pressure,
        )
        _store_workspace(st, workspace)
        st.rerun()
    if cols[2].button("Approve Situation", key=f"{prefix}_approve", disabled=snapshot is None):
        workspace = _approve_stage(workspace, "situation")
        _store_workspace(st, workspace)
        st.rerun()
    if cols[3].button("Generate Implications", key=f"{prefix}_next", disabled=workspace.situation_checkpoint.status != "approved"):
        workspace = runner.build_implications_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[4].button("Reset Downstream", key=f"{prefix}_reset"):
        workspace = _reset_downstream(workspace, "situation")
        _store_workspace(st, workspace)
        st.rerun()
    if snapshot is not None:
        st.markdown("### Situation Snapshot")
        st.json(snapshot.model_dump(mode="json"))
        st.markdown("### Predictions")
        st.dataframe(
            [
                {
                    "type": item.prediction_type,
                    "description": item.description,
                    "horizon": item.time_horizon,
                    "confidence": item.confidence,
                }
                for item in checkpoint.predictions
            ],
            use_container_width=True,
        )


def _render_implications_stage(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession) -> None:
    checkpoint = workspace.implications_checkpoint
    prefix = f"{workspace.workspace_id}_implications"
    st.markdown(f"**Status**: `{checkpoint.status}`")
    implication_rows = [item.model_dump(mode="json") for item in checkpoint.market_implications]
    action_rows = [item.model_dump(mode="json") for item in checkpoint.action_recommendations]
    edited_implications = st.data_editor(implication_rows, num_rows="dynamic", key=f"{prefix}_implications")
    edited_actions = st.data_editor(action_rows, num_rows="dynamic", key=f"{prefix}_actions")
    cols = st.columns(5)
    if cols[0].button("Generate Implications", key=f"{prefix}_generate", disabled=workspace.situation_checkpoint.status != "approved"):
        workspace = runner.build_implications_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[1].button("Save Implication Changes", key=f"{prefix}_save", disabled=checkpoint.status == "not_started"):
        workspace = runner.apply_implication_edits(workspace, implications=edited_implications, actions=edited_actions)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[2].button("Approve Implications", key=f"{prefix}_approve", disabled=checkpoint.status == "not_started"):
        workspace = _approve_stage(workspace, "implications")
        _store_workspace(st, workspace)
        st.rerun()
    if cols[3].button("Generate Report", key=f"{prefix}_next", disabled=workspace.implications_checkpoint.status != "approved"):
        workspace = runner.build_report_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[4].button("Reset Downstream", key=f"{prefix}_reset"):
        workspace = _reset_downstream(workspace, "implications")
        _store_workspace(st, workspace)
        st.rerun()
    if checkpoint.endangered_symbols:
        st.markdown(f"**Endangered symbols**: {', '.join(checkpoint.endangered_symbols)}")


def _render_report_stage(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession) -> None:
    checkpoint = workspace.report_checkpoint
    prefix = f"{workspace.workspace_id}_report"
    st.markdown(f"**Status**: `{checkpoint.status}`")
    report = checkpoint.final_report
    headline = st.text_input("Headline", value=report.headline if report else "", key=f"{prefix}_headline")
    executive_summary = st.text_area(
        "Executive summary",
        value=report.executive_summary if report else "",
        height=120,
        key=f"{prefix}_summary",
    )
    cols = st.columns(4)
    if cols[0].button("Generate Report", key=f"{prefix}_generate", disabled=workspace.implications_checkpoint.status != "approved"):
        workspace = runner.build_report_checkpoint(workspace)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[1].button("Save Report Changes", key=f"{prefix}_save", disabled=report is None):
        workspace = runner.apply_report_edits(workspace, headline=headline, executive_summary=executive_summary)
        _store_workspace(st, workspace)
        st.rerun()
    if cols[2].button("Approve Report", key=f"{prefix}_approve", disabled=report is None):
        workspace = _approve_stage(workspace, "report")
        _store_workspace(st, workspace)
        st.rerun()
    if cols[3].button("Rerun from Here", key=f"{prefix}_rerun", disabled=workspace.implications_checkpoint.status == "not_started"):
        workspace = runner.rerun_from_checkpoint(workspace, "report")
        _store_workspace(st, workspace)
        st.rerun()
    if report is not None:
        if checkpoint.run_id:
            st.markdown(f"**Run ID**: `{checkpoint.run_id}`")
        st.markdown("### Markdown Preview")
        st.markdown(checkpoint.report_markdown)


def _render_workspace(st: Any, runner: StrategicSwarmRunner, workspace: OperatorWorkspaceSession, output_dir: str) -> None:
    left, right = st.columns([1, 3])
    with left:
        st.subheader("Stepper")
        rows = workspace_checkpoint_rows(workspace.model_dump(mode="json"))
        labels = [f"{row['stage'].title()} [{row['status']}]" for row in rows]
        current_index = next(
            (index for index, row in enumerate(rows) if row["stage"] == workspace.current_stage),
            0,
        )
        selected = st.radio("Checkpoint", options=labels, index=current_index, key=f"{workspace.workspace_id}_stepper")
        workspace.current_stage = rows[labels.index(selected)]["stage"]
        _store_workspace(st, workspace)
        if workspace.selected_run_id:
            st.caption(f"Selected run: {workspace.selected_run_id}")
        if workspace.rerun_lineage:
            st.markdown("### Reruns")
            for item in workspace.rerun_lineage:
                st.markdown(f"- {item}")
    with right:
        stage = workspace.current_stage
        if stage == "brief":
            _render_brief_stage(st, runner, workspace)
        elif stage == "evidence":
            _render_evidence_stage(st, runner, workspace)
        elif stage == "situation":
            _render_situation_stage(st, runner, workspace)
        elif stage == "implications":
            _render_implications_stage(st, runner, workspace)
        else:
            _render_report_stage(st, runner, workspace)
        if workspace.selected_run_id:
            st.markdown("---")
            st.markdown(f"**Persisted run**: `{workspace.selected_run_id}`")
            st.dataframe(list_recent_runs(output_dir), use_container_width=True)


def main() -> None:
    try:
        import streamlit as st
    except ImportError as exc:  # pragma: no cover - dependency-gated runtime
        raise SystemExit("Install operator extras first: pip install -e '.[operator]'") from exc

    bootstrap_env()
    st.set_page_config(page_title="Faultline Operator", layout="wide")
    st.title("Faultline Operator")
    st.caption("Manual research runs over the existing StrategicSwarmRunner.")
    st.session_state.setdefault("topic_chat_session", None)
    st.session_state.setdefault("operator_workspace", None)

    output_dir = st.sidebar.text_input("Output directory", value=os.getenv("FAULTLINE_OUTPUT_DIR", "outputs"))
    runner = StrategicSwarmRunner(output_dir=output_dir)

    st.sidebar.subheader("Provider Health")
    st.sidebar.dataframe(runner.provider_health(), use_container_width=True)

    mode = st.sidebar.selectbox("Mode", ["topic_chat", "demo", "latest", "live", "replay"])
    scenario = None
    start_at = None
    end_at = None
    lookback_minutes = None
    run_id = None
    payload = None

    if mode == "topic_chat":
        topic = st.sidebar.text_area("Topic or thesis", value=st.session_state.get("topic_chat_topic", ""), height=100)
        thesis = st.sidebar.text_input("Optional thesis", value=st.session_state.get("topic_chat_thesis", ""))
        positions_raw = st.sidebar.text_input("Positions (optional)", value=st.session_state.get("topic_chat_positions", ""))
        watchlist_raw = st.sidebar.text_input("Watchlist (optional)", value=st.session_state.get("topic_chat_watchlist", ""))
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
            st.session_state["operator_workspace"] = None
        if st.sidebar.button("Reset Topic Chat"):
            st.session_state["topic_chat_session"] = None
            st.session_state["operator_workspace"] = None
    elif mode == "demo":
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

    if mode == "topic_chat":
        session_raw = st.session_state.get("topic_chat_session")
        workspace = _load_workspace(st)
        if workspace is not None:
            _render_workspace(st, runner, workspace, output_dir)
            return
        if session_raw:
            session = session_raw
            st.subheader("Topic Chat")
            st.markdown(f"**Original Topic**: {session['topic_prompt']['topic']}")
            st.markdown(f"**Current Interpretation**: {session['interpretation']}")
            st.markdown(f"**Status**: `{session['status']}`")
            st.json(session["brief"])
            if session.get("turns"):
                st.markdown("### Intake Transcript")
                for turn in session["turns"]:
                    st.markdown(f"**System**: {turn['system_question']}")
                    st.markdown(f"**User**: {turn['user_answer']}")
            if session.get("current_question"):
                answer = st.text_input("Next answer", key="topic_chat_answer")
                if st.button("Submit Answer"):
                    updated = runner.continue_topic_chat(session, answer)
                    st.session_state["topic_chat_session"] = updated.model_dump(mode="json")
                    st.rerun()
            else:
                if st.button("Open Stepper Workspace", type="primary"):
                    workspace = runner.initialize_workspace(session)
                    _store_workspace(st, workspace)
                    st.rerun()
        else:
            st.subheader("Latest Runs")
            st.dataframe(list_recent_runs(output_dir), use_container_width=True)
        return

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
        _render_payload(st, payload, output_dir)
    else:
        st.subheader("Latest Runs")
        st.dataframe(list_recent_runs(output_dir), use_container_width=True)


if __name__ == "__main__":  # pragma: no cover - streamlit entrypoint
    main()
