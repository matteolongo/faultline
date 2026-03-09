from __future__ import annotations

import os

from strategic_swarm_agent.utils.env import bootstrap_env


def test_bootstrap_env_loads_dotenv_files(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("NEWSAPI_API_KEY", raising=False)
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)

    (tmp_path / ".env").write_text(
        "NEWSAPI_API_KEY=base-key\nALPHAVANTAGE_API_KEY=base-av\n"
    )
    (tmp_path / ".env.local").write_text("NEWSAPI_API_KEY=override-key\n")

    original_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        bootstrap_env()
    finally:
        os.chdir(original_cwd)

    assert os.getenv("NEWSAPI_API_KEY") == "override-key"
    assert os.getenv("ALPHAVANTAGE_API_KEY") == "base-av"
