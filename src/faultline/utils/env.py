from __future__ import annotations

from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at import time during partial installs
    load_dotenv = None


def bootstrap_env(search_from: str | Path | None = None) -> None:
    if load_dotenv is None:
        return

    start = Path(search_from or Path.cwd()).resolve()
    candidates = [start, *start.parents]

    for directory in candidates:
        env_path = directory / ".env"
        env_local_path = directory / ".env.local"
        if env_path.exists():
            load_dotenv(env_path, override=False)
        if env_local_path.exists():
            load_dotenv(env_local_path, override=True)
