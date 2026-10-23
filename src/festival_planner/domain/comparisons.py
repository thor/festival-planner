"""Turning Comparisons into weights with a Bradley–Terry model."""

import math
from collections import Counter, defaultdict
from collections.abc import Iterable

from .planning import Comparison
from .programme import ProgrammeEntryId

ITERATIONS = 1000
TOLERANCE = 1e-12


def comparison_bonuses(
    comparisons: Iterable[Comparison], weight: float
) -> dict[ProgrammeEntryId, float]:
    """Weight bonuses for the compared Programme Entries.

    Fits Bradley–Terry strengths by minorisation–maximisation. A weak prior,
    one win and one loss against a virtual entry of strength 1, keeps the
    strengths finite for unbeaten entries. The bonus is `weight` times the
    log-strength, centred so the bonuses sum to zero. Entries are processed in
    sorted order, so the result does not depend on input order.
    """
    comparisons = tuple(comparisons)
    games: defaultdict[ProgrammeEntryId, Counter[ProgrammeEntryId]] = defaultdict(
        Counter
    )
    wins: Counter[ProgrammeEntryId] = Counter()
    for c in comparisons:
        games[c.preferred][c.other] += 1
        games[c.other][c.preferred] += 1
        wins[c.preferred] += 1
    entries = sorted(games)
    if not entries:
        return {}
    strength = dict.fromkeys(entries, 1.0)
    for _ in range(ITERATIONS):
        updated = {
            i: (wins[i] + 1)
            / (
                2 / (strength[i] + 1.0)
                + sum(
                    n / (strength[i] + strength[j]) for j, n in sorted(games[i].items())
                )
            )
            for i in entries
        }
        change = max(abs(updated[i] - strength[i]) for i in entries)
        strength = updated
        if change < TOLERANCE:
            break
    logs = {i: math.log(strength[i]) for i in entries}
    mean = sum(logs.values()) / len(logs)
    return {i: weight * (logs[i] - mean) for i in entries}
