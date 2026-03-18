"""Tests for CSV storage."""
import os
import pytest
import tempfile
from unittest.mock import MagicMock
from choosie.storage.csv_store import CSVStore
from choosie.core.battle import BattleMode, BattleResult
from choosie.core.competitor import Competitor, CompetitorResult


def make_competitor(name="A"):
    return Competitor(provider="openai", model="gpt-4o", prompt="Hi", name=name)


def make_result(competitor, response="Hello", won=False, vote=None):
    r = CompetitorResult(
        competitor=competitor,
        rendered_prompt="Hi",
        response=response,
        raw_response=MagicMock(),
    )
    r.won = won
    r.vote = vote
    return r


@pytest.fixture
def tmp_csv(tmp_path):
    return str(tmp_path / "test_results.csv")


class TestCSVStore:
    def test_creates_file_on_init(self, tmp_csv):
        store = CSVStore(tmp_csv)
        assert os.path.exists(tmp_csv)

    def test_save_creates_rows(self, tmp_csv):
        store = CSVStore(tmp_csv)
        c1, c2 = make_competitor("A"), make_competitor("B")
        r1 = make_result(c1, won=True)
        r2 = make_result(c2, won=False)
        battle = BattleResult(
            mode=BattleMode.PICK_BEST, results=[r1, r2], winner=r1,
        )
        store.save(battle, user_query="Test query", user_comment="Good!")

        rows = store.load_dicts()
        assert len(rows) == 2
        assert rows[0]["competitor_name"] == "A"
        assert rows[0]["is_winner"] == "True"
        assert rows[0]["user_query"] == "Test query"
        assert rows[0]["user_comment"] == "Good!"
        assert rows[1]["is_winner"] == "False"
        assert rows[1]["user_comment"] == ""

    def test_num_battles(self, tmp_csv):
        store = CSVStore(tmp_csv)
        c1 = make_competitor("A")

        for _ in range(3):
            r = make_result(c1)
            b = BattleResult(mode=BattleMode.THUMBS, results=[r])
            store.save(b)

        assert store.num_battles == 3

    def test_load_empty(self, tmp_csv):
        store = CSVStore(tmp_csv)
        rows = store.load_dicts()
        assert rows == []

    def test_multiple_saves_append(self, tmp_csv):
        store = CSVStore(tmp_csv)
        c1 = make_competitor("A")

        r1 = make_result(c1)
        b1 = BattleResult(mode=BattleMode.THUMBS, results=[r1])
        store.save(b1)

        r2 = make_result(c1)
        b2 = BattleResult(mode=BattleMode.THUMBS, results=[r2])
        store.save(b2)

        rows = store.load_dicts()
        assert len(rows) == 2
