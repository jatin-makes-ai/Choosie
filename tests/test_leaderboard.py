"""Tests for the Leaderboard and ELO system."""
import pytest
from choosie.analytics.leaderboard import Leaderboard, _elo_update
from choosie.core.battle import BattleMode, BattleResult
from choosie.core.competitor import Competitor, CompetitorResult
from unittest.mock import MagicMock


def make_competitor(name="A", cid=None):
    c = Competitor(provider="openai", model="gpt-4o", prompt="Hi", name=name)
    if cid:
        c.id = cid
    return c


def make_result(competitor, vote=None, won=False):
    r = CompetitorResult(
        competitor=competitor,
        rendered_prompt="Hi",
        response="Hello",
        raw_response=MagicMock(),
    )
    r.vote = vote
    r.won = won
    return r


class TestEloMath:
    def test_winner_gains_elo(self):
        w, l = _elo_update(1000, 1000)
        assert w > 1000
        assert l < 1000

    def test_elo_sum_conserved(self):
        w, l = _elo_update(1200, 800)
        assert abs((w + l) - (1200 + 800)) < 0.01

    def test_upset_gives_bigger_gain(self):
        # Weak player (800) beats strong player (1200)
        w_up, _ = _elo_update(800, 1200)
        # Expected win: strong (1200) beats weak (800)
        w_exp, _ = _elo_update(1200, 800)
        assert w_up - 800 > w_exp - 1200


class TestLeaderboard:
    def _make_pick_best_battle(self, winner_comp, losers):
        winner_result = make_result(winner_comp, won=True)
        loser_results = [make_result(l) for l in losers]
        all_results = [winner_result] + loser_results
        return BattleResult(
            mode=BattleMode.PICK_BEST,
            results=all_results,
            winner=winner_result,
        )

    def test_winner_elo_increases(self):
        c1, c2 = make_competitor("A"), make_competitor("B")
        battle = self._make_pick_best_battle(c1, [c2])
        lb = Leaderboard.from_history([battle])

        ranked = lb.ranked()
        assert ranked[0].name == "A"
        assert ranked[0].elo > 1000
        assert ranked[1].elo < 1000

    def test_thumbs_votes_recorded(self):
        c1 = make_competitor("A")
        r1 = make_result(c1, vote=1)
        r2 = make_result(c1, vote=-1)
        b1 = BattleResult(mode=BattleMode.THUMBS, results=[r1])
        b2 = BattleResult(mode=BattleMode.THUMBS, results=[r2])

        lb = Leaderboard.from_history([b1, b2])
        stats = lb.ranked()[0]
        assert stats.thumbs_up == 1
        assert stats.thumbs_down == 1

    def test_empty_leaderboard(self):
        lb = Leaderboard()
        assert lb.ranked() == []
        assert lb.to_dict() == []
