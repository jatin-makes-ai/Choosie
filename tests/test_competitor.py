"""Tests for the Competitor class."""
import pytest
from unittest.mock import MagicMock, patch
from vibediff.core.competitor import Competitor, CompetitorResult


def make_competitor(**kwargs):
    defaults = dict(provider="openai", model="gpt-4o", prompt="Say hello to {name}")
    defaults.update(kwargs)
    return Competitor(**defaults)


class TestCompetitorInit:
    def test_auto_name_with_provider(self):
        c = make_competitor()
        assert c.name == "openai/gpt-4o"

    def test_auto_name_without_provider(self):
        c = Competitor(provider="", model="gpt-4o", prompt="Hello")
        assert c.name == "gpt-4o"

    def test_custom_name(self):
        c = make_competitor(name="My GPT")
        assert c.name == "My GPT"

    def test_invalid_prompt_template(self):
        with pytest.raises(ValueError, match="Invalid prompt template"):
            Competitor(provider="openai", model="gpt-4o", prompt="Hello {unclosed")

    def test_unique_ids(self):
        c1 = make_competitor()
        c2 = make_competitor()
        assert c1.id != c2.id


class TestPromptRendering:
    def test_render_with_variables(self):
        c = make_competitor()
        rendered = c.render_prompt({"name": "Alice"})
        assert rendered == "Say hello to Alice"

    def test_render_no_variables(self):
        c = Competitor(provider="openai", model="gpt-4o", prompt="Hello world")
        assert c.render_prompt() == "Hello world"

    def test_render_missing_variable_raises(self):
        c = make_competitor()
        with pytest.raises(Exception):  # StrictUndefined raises UndefinedError
            c.render_prompt({})

    def test_render_extra_variables_ignored(self):
        c = make_competitor()
        rendered = c.render_prompt({"name": "Bob", "extra": "ignored"})
        assert rendered == "Say hello to Bob"


class TestCompetitorRun:
    @patch("vibediff.core.competitor.litellm_completion")
    def test_run_returns_result(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Hello, Alice!"
        mock_completion.return_value = mock_response

        c = make_competitor()
        result = c.run({"name": "Alice"})

        assert isinstance(result, CompetitorResult)
        assert result.response == "Hello, Alice!"
        assert result.rendered_prompt == "Say hello to Alice"
        assert result.competitor is c

    @patch("vibediff.core.competitor.litellm_completion")
    def test_run_uses_correct_model_string(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hi"
        mock_completion.return_value = mock_response

        c = Competitor(provider="anthropic", model="claude-3-5-sonnet-20241022", prompt="Hi")
        c.run()

        call_kwargs = mock_completion.call_args
        assert call_kwargs[1]["model"] == "anthropic/claude-3-5-sonnet-20241022"

    @patch("vibediff.core.competitor.litellm_completion")
    def test_run_without_provider_prefix(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "hi"
        mock_completion.return_value = mock_response

        c = Competitor(provider="", model="gpt-4o", prompt="Hi")
        c.run()

        call_kwargs = mock_completion.call_args
        assert call_kwargs[1]["model"] == "gpt-4o"
