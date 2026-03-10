# Contributing to Faultline

Thank you for contributing! Faultline is a geopolitical structural fragility reasoning engine — contributions that improve signal quality, reasoning depth, or developer experience are especially welcome.

## Getting Started

```bash
git clone <repo>
cd faultline
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pre-commit install        # installs ruff lint/format hooks on every commit
```

Verify your setup:

```bash
pytest -q                 # all 33 tests should pass, no API keys needed
faultline run-demo --scenario arctic_cable_bypass
```

## Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-name>` | `feature/perplexity-provider` |
| Bug fix | `fix/<short-name>` | `fix/openai-schema-error` |
| Docs | `docs/<short-name>` | `docs/glossary` |
| Refactor | `refactor/<short-name>` | `refactor/fragility-scorer` |

## Pull Request Checklist

Before opening a PR, confirm:

- [ ] `pytest -q` passes with no failures
- [ ] `ruff check src/ tests/` reports no errors
- [ ] `ruff format --check src/ tests/` reports no changes needed
- [ ] New behavior has test coverage
- [ ] No `TODO`/`FIXME` markers left in code
- [ ] `CLAUDE.md` updated if you changed key architecture/patterns

## How to Add a New Provider

Providers ingest raw signals from external data sources.

1. Create `src/faultline/providers/myprovider.py`:

```python
from faultline.providers.base import BaseProvider
from faultline.models.contracts import RawSignal

class MyProvider(BaseProvider):
    name = "myprovider"

    def fetch_window(self, start_at: datetime, end_at: datetime) -> list[RawSignal]:
        ...
```

2. Register it in `src/faultline/providers/registry.py`
3. Add config defaults to `configs/providers.yaml`
4. Add a test in `tests/test_providers.py` using fixtures (no real API calls)

## How to Add a New LangGraph Node

Nodes are pure functions that receive and return state.

1. Add your function to `src/faultline/graph/workflow.py`:

```python
def my_node(state: FaultlineState) -> dict:
    """Brief description of what this node does."""
    # do work
    return {"my_field": result}  # return only updated keys
```

2. Register it: `workflow.add_node("my_node", my_node)`
3. Wire edges: `workflow.add_edge("previous_node", "my_node")`
4. Add the output field to `FaultlineState` in `models/state.py` if needed
5. Write a test in `tests/test_scenario_nodes.py`

## How to Add a New Archetype

Archetypes are named structural conflict topologies the system reasons about.

1. Add an entry to `configs/archetypes.yaml` following the existing schema:

```yaml
- id: my_archetype
  name: My Archetype Name
  empire_type: Description of the incumbent/defender
  disruptor_type: Description of the challenger/disruptor
  asymmetry_type: What makes the disruption cheap vs. the defense expensive
  trigger_tags:
    - relevant-tag
  cheap_weapon_examples:
    - example cheap weapon
  analog_refs:
    - historical_analog
```

2. No code changes required — archetypes are loaded dynamically from YAML.

## Code Standards

- **Type annotations** on all function signatures (no bare `Any` unless unavoidable)
- **Pydantic `BaseModel`** for all inter-node data contracts
- **Docstrings** on all public classes and non-trivial functions
- **No raw OpenAI calls** — use `StructuredReasoner` from `llm/backend.py`
- **No API keys in tests** — use `data/samples/` fixture data

## Commit Messages

Use conventional commits:

```
feat: add Perplexity news provider
fix: handle missing window_start gracefully in ingest_signals
docs: add ripple scenario examples to glossary
refactor: extract fragility weights into config loader
test: add coverage for cluster deduplication
```

## Questions?

Open an issue with the `question` label. For architecture discussions, open a `discussion` if GitHub Discussions is enabled.
