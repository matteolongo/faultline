.PHONY: install install-full test lint format check demo demo-all studio clean

# ── Setup ──────────────────────────────────────────────────────────────────
install:
	pip install -e '.[dev]'

install-full:
	pip install -e '.[dev,operator]'
	pre-commit install

# ── Quality ────────────────────────────────────────────────────────────────
test:
	pytest -q --tb=short

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

check: lint
	ruff format --check src/ tests/

# ── Run ────────────────────────────────────────────────────────────────────
demo:
	faultline run-demo --scenario arctic_cable_bypass

demo-all:
	faultline run-all-demos

studio:
	langgraph dev

health:
	faultline provider-health

# ── Cleanup ────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .ruff_cache .pytest_cache
