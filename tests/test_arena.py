"""Tests for the Arena class."""
import pytest
from unittest.mock import MagicMock, patch
from choosie.core.arena import Arena
from choosie.core.battle import BattleMode, BattleResult
from choosie.core.competitor import Competitor, CompetitorResult


def make_mock_result(competitor, response="mock response"):
    return CompetitorResult(
        competitor=competitor,
        rendered_prompt="mock prompt",
        response=response,
        raw_response=MagicMock(),
    )


def make_competitor(name="Test", provider="openai", model="gpt-4o"):
    return Competitor(provider=provider, model=model, prompt="Hello {name}", name=name)


class TestArenaInit:
    def test_requires_at_least_one_competitor(self):
        with pytest.raises(ValueError):
            Arena(competitors=[])

    def test_single_competitor_allowed(self):
        c = make_competitor()
        arena = Arena(competitors=[c])
        assert len(arena.competitors) == 1

    def test_csv_path_default(self):
        c = make_competitor()
        arena = Arena(competitors=[c])
        assert arena.csv_path == "choosie_results.csv"

    def test_csv_path_custom(self):
        c = make_competitor()
        arena = Arena(competitors=[c], csv_path="custom.csv")
        assert arena.csv_path == "custom.csv"


class TestArenaBattle:
    def test_headless_skips_ui(self):
        c1 = make_competitor("A")
        r1 = make_mock_result(c1)

        with patch.object(c1, "run", return_value=r1):
            arena = Arena(competitors=[c1])
            result = arena.battle(mode=1, variables={"name": "test"}, launch_ui=False)

        assert isinstance(result, BattleResult)

    def test_headless_history_accumulates(self):
        c1 = make_competitor("A")
        r1 = make_mock_result(c1)

        with patch.object(c1, "run", return_value=r1):
            arena = Arena(competitors=[c1])
            arena.battle(mode=1, variables={"name": "x"}, launch_ui=False)
            arena.battle(mode=1, variables={"name": "y"}, launch_ui=False)

        assert len(arena.history) == 2

    def test_on_result_callback_fires(self):
        c1 = make_competitor("A")
        r1 = make_mock_result(c1)
        callback = MagicMock()

        with patch.object(c1, "run", return_value=r1):
            arena = Arena(competitors=[c1], on_result=callback)
            arena.battle(mode=1, variables={"name": "x"}, launch_ui=False)

        callback.assert_called_once()

    @patch("choosie.ui.app.launch_arena_ui")
    def test_ui_mode_calls_launch(self, mock_ui):
        c1, c2 = make_competitor("A"), make_competitor("B")
        arena = Arena(competitors=[c1, c2])
        result = arena.battle(mode=1, launch_ui=True)

        mock_ui.assert_called_once()
        assert result is None  # UI mode returns None

    @patch("choosie.ui.app.launch_arena_ui")
    def test_ui_mode_passes_csv_path(self, mock_ui):
        c1 = make_competitor("A")
        arena = Arena(competitors=[c1], csv_path="my_results.csv")
        arena.battle(mode=1, launch_ui=True)

        call_kwargs = mock_ui.call_args
        assert call_kwargs[1]["csv_path"] == "my_results.csv"
