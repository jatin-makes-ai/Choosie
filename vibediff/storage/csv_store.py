"""
CSV-backed persistence for VibeDiff battle results.

Each battle round is written as one row per competitor to a local CSV file,
capturing the response, vote, winner status, timing, and user comments —
all without revealing model identity in the UI.
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vibediff.core.battle import BattleResult

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "vibediff_results.csv"

_FIELDNAMES = [
    "battle_id",
    "timestamp",
    "battle_mode",
    "user_query",
    "competitor_name",
    "competitor_id",
    "provider",
    "model",
    "rendered_prompt",
    "response",
    "is_winner",
    "vote",
    "user_comment",
]


class CSVStore:
    """
    Append-only CSV writer for battle results.

    Usage:
        store = CSVStore("results.csv")
        store.save(battle_result)
        df = store.load()  # pandas DataFrame (optional)

    Each call to ``save()`` appends N rows (one per competitor).
    The CSV is created automatically if it doesn't exist.
    """

    def __init__(self, path: str | Path = _DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._ensure_header()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        battle: "BattleResult",
        user_query: str = "",
        user_comment: str = "",
    ) -> None:
        """
        Append one battle's results to the CSV.

        Args:
            battle:      A completed BattleResult.
            user_query:  The user's input text that triggered the battle.
            user_comment: Optional comment the user gave after picking.
        """
        rows = []
        for r in battle.results:
            rows.append({
                "battle_id": battle.id[:8],
                "timestamp": battle.timestamp.isoformat(),
                "battle_mode": battle.mode.name,
                "user_query": user_query,
                "competitor_name": r.competitor.name,
                "competitor_id": r.competitor.id,
                "provider": r.competitor.provider,
                "model": r.competitor.model,
                "rendered_prompt": r.rendered_prompt,
                "response": r.response,
                "is_winner": r.won,
                "vote": r.vote if r.vote is not None else "",
                "user_comment": user_comment if r.won else "",
            })

        with open(self.path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
            writer.writerows(rows)

        logger.info("Saved %d rows to %s (battle %s)", len(rows), self.path, battle.id[:8])

    def load(self):
        """
        Load the CSV into a pandas DataFrame.

        Returns:
            pandas.DataFrame with all recorded battles.
        """
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                "Install pandas to load results: pip install pandas"
            ) from exc
        if not self.path.exists():
            return pd.DataFrame(columns=_FIELDNAMES)
        return pd.read_csv(self.path)

    def load_dicts(self) -> list[dict]:
        """Load the CSV as a list of dicts (no pandas required)."""
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)

    @property
    def num_battles(self) -> int:
        """Return the number of unique battles recorded."""
        rows = self.load_dicts()
        return len(set(r["battle_id"] for r in rows))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_header(self) -> None:
        """Write the CSV header if the file doesn't exist yet."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=_FIELDNAMES)
                writer.writeheader()
            logger.info("Created results CSV: %s", self.path)
