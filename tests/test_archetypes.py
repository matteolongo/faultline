from faultline.utils.config import load_mechanisms, load_stages


def test_mechanism_library_contains_core_mechanisms() -> None:
    payload = load_mechanisms()
    names = {item["name"] for item in payload["mechanisms"]}
    assert {
        "Indirect Strategy",
        "Platform Bypass",
        "Coalition Drift",
        "Timing Mismatch",
    }.issubset(names)


def test_stage_ladder_contains_repricing() -> None:
    payload = load_stages()
    stage_ids = {item["id"] for item in payload["stages"]}
    assert "repricing" in stage_ids
    assert "strategic_positioning" in stage_ids
