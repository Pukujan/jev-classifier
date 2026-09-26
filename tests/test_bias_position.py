"""Position-bias harness: permute option order, measure label invariance (#32).

Pure Python, no self-report: asking JEV "are you order-biased?" would be
metacognitive nonsense, so the harness flips the order of the same options and
watches whether the label follows the position or the meaning. It belongs here,
not in ``packs.py`` — it is a measurement harness, not a question.
"""

from __future__ import annotations

CRITERIA = {"alpha": "first option text", "beta": "second option text"}


def permuted(criteria: dict[str, str]) -> dict[str, str]:
    return {key: criteria[key] for key in reversed(list(criteria))}


class PositionBiasedModel:
    """Always picks whichever option is listed first."""

    def __call__(self, criteria: dict[str, str]) -> dict:
        return {"type": "choice", "choice": next(iter(criteria))}


class MeaningStableModel:
    """Always picks the option it actually prefers, whatever the order."""

    def __call__(self, criteria: dict[str, str]) -> dict:
        return {"type": "choice", "choice": "beta"}


def measure_position_bias(decide, criteria: dict[str, str]) -> dict:
    forward = decide(criteria)["choice"]
    backward = decide(permuted(criteria))["choice"]
    return {"forward": forward, "backward": backward, "stable": forward == backward}


def test_option_order_is_actually_reversed() -> None:
    assert list(permuted(CRITERIA)) == ["beta", "alpha"]


def test_position_biased_model_is_detected() -> None:
    result = measure_position_bias(PositionBiasedModel(), CRITERIA)
    assert result["forward"] == "alpha"
    assert result["backward"] == "beta"
    assert result["stable"] is False


def test_meaning_stable_model_is_not_flagged() -> None:
    result = measure_position_bias(MeaningStableModel(), CRITERIA)
    assert result["forward"] == "beta"
    assert result["backward"] == "beta"
    assert result["stable"] is True


def test_harness_holds_the_option_text_constant() -> None:
    seen: list[dict[str, str]] = []

    def decide(criteria: dict[str, str]) -> dict:
        seen.append(dict(criteria))
        return {"choice": "alpha"}

    measure_position_bias(decide, CRITERIA)
    assert len(seen) == 2
    assert set(seen[0].items()) == set(seen[1].items())
    assert list(seen[0]) != list(seen[1])


def test_position_bias_is_not_a_pack_question() -> None:
    from jev_classifier.bias import get_pack

    pack = get_pack()
    for q in pack.questions:
        assert "position" not in q.id
        assert "order" not in q.instructions.lower()
