# Contributing to Faultline

Thanks for contributing.

Faultline is a system-first strategic analysis engine. High-value contributions usually improve one of:

- signal quality and normalization reliability
- mechanism/stage reasoning quality
- prediction calibration and follow-up scoring
- operator action quality and traceability

## Setup

```bash
git clone <repo>
cd faultline
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Branch Naming

Use `codex/` prefix for automation branches and one of these patterns for manual work:

- `feature/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `refactor/<short-name>`

## Required Checks

Before opening a PR:

- `ruff check .`
- `ruff format --check src/ tests/ docs/`
- `pytest -q`

## Testing Rules

- Tests must not make real external API calls.
- Use deterministic fixtures (`data/samples/`, `tests/fixtures/`) or synthetic `RawSignal` payloads.
- New behavior should include focused unit/integration tests.

## Adding a Provider

1. Implement a provider in `src/faultline/providers/`.
2. Register it in `src/faultline/providers/registry.py`.
3. Add defaults/config in `configs/providers.yaml`.
4. Add tests in `tests/test_providers.py` with mocked responses/fixtures.

## Adding/Changing Workflow Nodes

1. Update `src/faultline/graph/workflow.py`.
2. Keep state updates explicit and typed (`models/state.py`).
3. Keep contracts in `models/contracts.py` coherent with report/render layers.
4. Add or update regression tests for:
   - graph e2e
   - operator surface
   - report rendering (when applicable)

## Config Changes

Mechanism and stage behavior is config-driven:

- `configs/mechanisms.yaml`
- `configs/stages.yaml`
- `configs/prompts.yaml` (when prompt logic is involved)

When changing these, also update tests and docs (`README.md`, `docs/GLOSSARY.md`, `CLAUDE.md`) if terminology or behavior changes.

## Commit Style

Use concise imperative messages, for example:

- `Add automatic follow-up scoring loop`
- `Improve report traceability and confidence storytelling`
- `Finalize system-first report contract cleanup`
