"""
Battle modes and result structures for Choosie.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from choosie.core.competitor import CompetitorResult


class BattleMode(IntEnum):
    """
    Available battle evaluation modes.

    PICK_BEST  (1): User sees all responses side-by-side and picks the winner.
    THUMBS     (2): User sees each response individually and votes thumbs up/down.
    """

    PICK_BEST = 1
    THUMBS = 2

    @classmethod
    def from_value(cls, value: int | str) -> "BattleMode":
        """Accept int (1, 2) or string ('pick_best', 'thumbs') inputs."""
        if isinstance(value, int):
            return cls(value)
        normalized = value.upper().replace("-", "_")
        try:
            return cls[normalized]
        except KeyError:
            raise ValueError(
                f"Unknown battle mode: {value!r}. "
                f"Valid options: {[m.name for m in cls]}"
            )


@dataclass
class BattleResult:
    """
    Captures the full outcome of a single arena battle session.

    Attributes:
        id:          Unique battle ID for leaderboard tracking.
        mode:        The BattleMode used.
        variables:   Template variables used in this battle.
        results:     CompetitorResult list, one per competitor.
        winner:      The winning CompetitorResult (None if no clear winner / draw).
        timestamp:   When the battle occurred (UTC).
        metadata:    Optional dict for any extra user-defined context.
    """

    mode: BattleMode
    results: list["CompetitorResult"]
    variables: dict = field(default_factory=dict)
    winner: "CompetitorResult | None" = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict = field(default_factory=dict)

    @property
    def competitor_names(self) -> list[str]:
        return [r.competitor.name for r in self.results]

    def summary(self) -> str:
        winner_name = self.winner.competitor.name if self.winner else "No winner"
        return (
            f"Battle [{self.id[:8]}] | Mode: {self.mode.name} | "
            f"Winner: {winner_name} | Competitors: {self.competitor_names}"
        )
