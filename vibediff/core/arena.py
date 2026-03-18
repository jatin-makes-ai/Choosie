"""
Arena: the orchestrator that runs competitors against each other.

arena = Arena(competitors=[c1, c2, c3])
arena.battle(mode=1, variables={"topic": "quantum computing"})
arena.battle(mode=BattleMode.THUMBS, variables={"topic": "neural nets"})
"""

from __future__ import annotations

import concurrent.futures
import logging
from typing import Any

from vibediff.core.battle import BattleMode, BattleResult
from vibediff.core.competitor import Competitor, CompetitorResult

logger = logging.getLogger(__name__)


class Arena:
    """
    Orchestrates battles between multiple Competitor instances.

    Args:
        competitors:  List of Competitor objects. Minimum 2 required.
        parallel:     If True (default), runs all competitors concurrently.
        max_workers:  Thread pool size for parallel execution (default: len(competitors)).
        on_result:    Optional callback(BattleResult) called after each battle completes.
        csv_path:     Path to save battle results to CSV (default: "vibediff_results.csv").

    Example:
        arena = Arena(competitors=[c1, c2])
        arena.battle(mode=1, variables={"topic": "LLMs"})
    """

    def __init__(
        self,
        competitors: list[Competitor],
        parallel: bool = True,
        max_workers: int | None = None,
        on_result: Any = None,
        csv_path: str = "vibediff_results.csv",
    ) -> None:
        if len(competitors) < 1:
            raise ValueError("Arena requires at least one competitor.")
        self.competitors = competitors
        self.parallel = parallel
        self.max_workers = max_workers or len(competitors)
        self.on_result = on_result
        self.csv_path = csv_path
        self._history: list[BattleResult] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def battle(
        self,
        mode: int | str | BattleMode = 1,
        variables: dict[str, Any] | None = None,
        launch_ui: bool = True,
        description: str = "",
        share: bool = False,
        **kwargs: Any,
    ) -> BattleResult | None:
        """
        Run a battle and (optionally) launch the Gradio evaluation UI.

        When launch_ui=True (default), opens the interactive Battleground UI
        which runs in a continuous loop (generate → evaluate → save → repeat).
        The UI handles its own CSV persistence and leaderboard.

        When launch_ui=False, runs all competitors once and returns a
        BattleResult without evaluation (headless / CI mode).

        Args:
            mode:        Battle mode — 1 (PICK_BEST) or 2 (THUMBS).
            variables:   Template variables substituted into each competitor's prompt.
            launch_ui:   If True (default), opens the Gradio Battleground UI.
            description: Custom description shown at the top of the UI.
            share:       If True, creates a public Gradio share link.
            **kwargs:    Forwarded to the UI launcher.

        Returns:
            BattleResult (headless mode) or None (UI mode — results saved to CSV).
        """
        battle_mode = BattleMode.from_value(mode)
        variables = variables or {}

        logger.info(
            "Starting battle | mode=%s | competitors=%d | variables=%s",
            battle_mode.name,
            len(self.competitors),
            list(variables.keys()),
        )

        # ── Interactive UI mode ──────────────────────────────────────────
        if launch_ui:
            from vibediff.ui.app import launch_arena_ui

            launch_arena_ui(
                competitors=self.competitors,
                mode=battle_mode.value,
                csv_path=self.csv_path,
                share=share,
                description=description,
                **kwargs,
            )
            return None

        # ── Headless mode ────────────────────────────────────────────────
        results = self._run_competitors(variables)
        battle = BattleResult(mode=battle_mode, results=results, variables=variables)

        self._history.append(battle)
        if self.on_result:
            try:
                self.on_result(battle)
            except Exception:
                logger.exception("on_result callback raised an exception.")

        logger.info(battle.summary())
        return battle

    @property
    def history(self) -> list[BattleResult]:
        """All past BattleResult objects for this Arena instance."""
        return list(self._history)

    def leaderboard(self):
        """Return a live Leaderboard computed from this Arena's battle history."""
        from vibediff.analytics.leaderboard import Leaderboard

        return Leaderboard.from_history(self._history)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_competitors(self, variables: dict[str, Any]) -> list[CompetitorResult]:
        """Execute all competitors, returning results in the original order."""
        if self.parallel and len(self.competitors) > 1:
            return self._run_parallel(variables)
        return self._run_sequential(variables)

    def _run_sequential(self, variables: dict[str, Any]) -> list[CompetitorResult]:
        results = []
        for competitor in self.competitors:
            logger.debug("Running competitor: %s", competitor.name)
            result = competitor.run(variables)
            results.append(result)
        return results

    def _run_parallel(self, variables: dict[str, Any]) -> list[CompetitorResult]:
        results: list[CompetitorResult | None] = [None] * len(self.competitors)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as executor:
            futures = {
                executor.submit(c.run, variables): idx
                for idx, c in enumerate(self.competitors)
            }
            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]
                try:
                    results[idx] = future.result()
                except Exception:
                    logger.exception(
                        "Competitor %s raised an exception.",
                        self.competitors[idx].name,
                    )
                    raise
        return results  # type: ignore[return-value]

    def __repr__(self) -> str:
        names = [c.name for c in self.competitors]
        return f"Arena(competitors={names})"
