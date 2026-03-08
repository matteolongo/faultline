from strategic_swarm_agent.agents.pattern_matcher import PatternMatcher
from strategic_swarm_agent.agents.signal_alchemist import SignalAlchemist
from strategic_swarm_agent.providers.normalizer import SignalNormalizer
from strategic_swarm_agent.providers.sample import NewsSignalProvider, MarketContextProvider, DarkSignalProvider
from strategic_swarm_agent.scoring.fragility import FragilityScorer


def test_fragility_scoring_produces_explanations() -> None:
    scenario_id = "debt_defense_spiral"
    raw = NewsSignalProvider().fetch(scenario_id) + MarketContextProvider().fetch(scenario_id) + DarkSignalProvider().fetch(scenario_id)
    events = SignalNormalizer().normalize(raw)
    patterns = PatternMatcher().match(events)
    bundles = SignalAlchemist().enrich(events, scenario_id)
    assessment = FragilityScorer().score(events, patterns, bundles)[0]

    assert assessment.fragility_score.value > 0.5
    assert "Composite score" in assessment.fragility_score.explanation
    assert assessment.fragile_nodes
    assert assessment.antifragile_nodes
