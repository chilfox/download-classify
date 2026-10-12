"""Fixed topic decision policy shared by monitoring and model acceptance."""
from collections.abc import Mapping

MIN_SCORE = 0.80
MIN_GAP = 0.20


def decide_topic(scores: Mapping[str, float]) -> tuple[str, float | None, bool]:
    """Return top topic, top-two gap, and movement eligibility for validated scores.

    Callers supply a nonempty mapping of finite [0, 1] scores for every
    configured category. Ties rank by name; a single topic still needs 0.80.
    """
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    gap = ranked[0][1] - ranked[1][1] if len(ranked) > 1 else None
    clear = ranked[0][1] >= MIN_SCORE and (gap is None or gap >= MIN_GAP)
    return ranked[0][0], gap, clear
