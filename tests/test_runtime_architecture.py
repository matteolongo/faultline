from pathlib import Path


def test_workflow_module_has_no_local_graph_fallback() -> None:
    source = Path("src/faultline/graph/workflow.py").read_text()

    assert "class _CompiledGraph" not in source
    assert "class StateGraph" not in source
    assert "from langgraph.graph import END, START, StateGraph" in source


def test_llm_backend_avoids_raw_httpx_posts() -> None:
    source = Path("src/faultline/llm/backend.py").read_text()

    assert "ChatOpenAI" in source
    assert "httpx.post(" not in source
