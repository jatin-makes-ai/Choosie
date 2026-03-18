"""
ELO-based Leaderboard for tracking competitor performance across battles.

- Competitors gain/lose ELO points after every Pick-Best battle (winner vs losers).
- Thumbs battles contribute positive/negative vote counts.
- Results can be exported to a pandas DataFrame or dict.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from choosie.core.battle import BattleMode, BattleResult

_DEFAULT_ELO = 1000
_K_FACTOR = 32  # Standard ELO K-factor; tune higher for faster convergence


@dataclass
class CompetitorStats:
    """Accumulated statistics for a single competitor across all battles."""

    name: str
    competitor_id: str
    elo: float = _DEFAULT_ELO
    wins: int = 0
    losses: int = 0
    draws: int = 0
    thumbs_up: int = 0
    thumbs_down: int = 0
    battles_played: int = 0

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses + self.draws
        return self.wins / total if total > 0 else 0.0

    @property
    def thumb_score(self) -> float:
        total = self.thumbs_up + self.thumbs_down
        return self.thumbs_up / total if total > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "elo": round(self.elo, 1),
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": f"{self.win_rate:.1%}",
            "thumbs_up": self.thumbs_up,
            "thumbs_down": self.thumbs_down,
            "thumb_score": f"{self.thumb_score:.1%}",
            "battles": self.battles_played,
        }


class Leaderboard:
    """
    Tracks and ranks competitors using ELO ratings and vote counts.

    Usage:
        lb = arena.leaderboard()
        lb.display()          # Pretty-prints to stdout
        df = lb.to_dataframe()  # Returns a pandas DataFrame
        data = lb.to_dict()   # Returns list of dicts
    """

    def __init__(self) -> None:
        self._stats: dict[str, CompetitorStats] = {}

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_history(cls, history: list["BattleResult"]) -> "Leaderboard":
        """Build a leaderboard from a list of completed BattleResult objects."""
        lb = cls()
        for battle in history:
            lb.record(battle)
        return lb

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record(self, battle: "BattleResult") -> None:
        """Ingest a completed BattleResult and update internal stats."""
        from choosie.core.battle import BattleMode

        for r in battle.results:
            self._ensure(r.competitor)

        if battle.mode == BattleMode.PICK_BEST:
            self._record_pick_best(battle)
        elif battle.mode == BattleMode.THUMBS:
            self._record_thumbs(battle)

    def _ensure(self, competitor) -> CompetitorStats:
        cid = competitor.id
        if cid not in self._stats:
            self._stats[cid] = CompetitorStats(
                name=competitor.name, competitor_id=cid
            )
        return self._stats[cid]

    def _record_pick_best(self, battle: "BattleResult") -> None:
        """Winner beats every other competitor in pairwise ELO updates."""
        if not battle.winner:
            # No winner selected → draw between all pairs
            results = battle.results
            for i, r in enumerate(results):
                stats = self._stats[r.competitor.id]
                stats.battles_played += 1
                stats.draws += 1
            return

        winner_stats = self._stats[battle.winner.competitor.id]
        winner_stats.wins += 1
        winner_stats.battles_played += 1
        winner_stats.won = True if hasattr(winner_stats, "won") else None

        for r in battle.results:
            if r is battle.winner:
                continue
            loser_stats = self._stats[r.competitor.id]
            loser_stats.losses += 1
            loser_stats.battles_played += 1

            # ELO update: winner vs loser
            w_new, l_new = _elo_update(winner_stats.elo, loser_stats.elo)
            winner_stats.elo = w_new
            loser_stats.elo = l_new

    def _record_thumbs(self, battle: "BattleResult") -> None:
        """Record individual thumbs votes; no head-to-head ELO update."""
        for r in battle.results:
            stats = self._stats[r.competitor.id]
            stats.battles_played += 1
            if r.vote == 1:
                stats.thumbs_up += 1
            elif r.vote == -1:
                stats.thumbs_down += 1

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def ranked(self) -> list[CompetitorStats]:
        """Return competitors sorted by ELO descending."""
        return sorted(self._stats.values(), key=lambda s: s.elo, reverse=True)

    def to_dict(self) -> list[dict]:
        return [s.to_dict() for s in self.ranked()]

    def to_dataframe(self):
        """Return a pandas DataFrame. Requires pandas to be installed."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Install pandas for DataFrame export: pip install pandas"
            ) from exc
        return pd.DataFrame(self.to_dict())

    def display(self) -> None:
        """Pretty-print the leaderboard to stdout."""
        rows = self.ranked()
        if not rows:
            print("No battles recorded yet.")
            return

        header = f"{'Rank':<5} {'Name':<30} {'ELO':>6} {'W':>4} {'L':>4} {'D':>4} {'Win%':>7} {'👍':>5} {'👎':>5}"
        print("\n" + "=" * len(header))
        print("  Choosie Leaderboard")
        print("=" * len(header))
        print(header)
        print("-" * len(header))
        for rank, stats in enumerate(rows, 1):
            print(
                f"{rank:<5} {stats.name:<30} {stats.elo:>6.1f} "
                f"{stats.wins:>4} {stats.losses:>4} {stats.draws:>4} "
                f"{stats.win_rate:>7.1%} {stats.thumbs_up:>5} {stats.thumbs_down:>5}"
            )
        print("=" * len(header) + "\n")


# ------------------------------------------------------------------
# ELO math
# ------------------------------------------------------------------

def _expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))


def _elo_update(
    winner_elo: float, loser_elo: float, k: float = _K_FACTOR
) -> tuple[float, float]:
    """Return (new_winner_elo, new_loser_elo)."""
    exp_w = _expected_score(winner_elo, loser_elo)
    exp_l = _expected_score(loser_elo, winner_elo)
    return winner_elo + k * (1 - exp_w), loser_elo + k * (0 - exp_l)
