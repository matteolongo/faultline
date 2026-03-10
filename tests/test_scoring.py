from faultline.agents.pattern_matcher import PatternMatcher
from faultline.agents.signal_alchemist import SignalAlchemist
from faultline.providers.normalizer import SignalNormalizer
from faultline.providers.sample import (
    DarkSignalProvider,
    MarketContextProvider,
    NewsSignalProvider,
)
from faultline.scoring.fragility import FragilityScorer


def test_fragility_scoring_produces_explanations() -> None:
    scenario_id = "debt_defense_spiral"
    raw = (
        NewsSignalProvider().fetch(scenario_id)
        + MarketContextProvider().fetch(scenario_id)
        + DarkSignalProvider().fetch(scenario_id)
    )
    events, clusters, _ = SignalNormalizer().normalize(raw)
    cluster = clusters[0]
    cluster_events = [event for event in events if event.cluster_id == cluster.cluster_id]
    patterns, _ = PatternMatcher().match(cluster_events, cluster)
    bundles, _ = SignalAlchemist().enrich(cluster_events, cluster)
    assessment = FragilityScorer().score(cluster_events, cluster, patterns, bundles)[0]

    assert assessment.fragility_score.value > 0.5
    assert "Composite score" in assessment.fragility_score.explanation
    assert assessment.fragile_nodes
    assert assessment.antifragile_nodes
