from strategic_swarm_agent.utils.config import load_archetypes


def test_archetype_library_contains_required_topologies() -> None:
    payload = load_archetypes()
    names = {item.name for item in payload["topologies"]}
    assert {
        "Empire vs Swarm",
        "Chokepoint vs Bypass",
        "Monolith vs Protocol",
        "Heavy Capital vs Light Network",
    }.issubset(names)


def test_historical_analog_lookup_is_available() -> None:
    payload = load_archetypes()
    analogs = payload["historical_analogs"]
    assert "linux_vs_proprietary_stacks" in analogs
    assert analogs["linux_vs_proprietary_stacks"].name == "Linux vs proprietary stacks"
