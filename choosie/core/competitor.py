"""
Competitor: a single (model, prompt) combination that participates in a battle.

Supports Jinja2-style prompt templates:
    Competitor(
        provider="openai",
        model="gpt-4o",
        prompt="Explain {topic} to a {audience}",
        name="GPT-4o Simple"
    )
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from jinja2 import BaseLoader, Environment, TemplateSyntaxError

# LiteLLM is the universal LLM gateway — supports 100+ providers transparently.
try:
    import litellm
    from litellm import completion as litellm_completion
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "LiteLLM is required. Install it with: pip install litellm"
    ) from exc


from jinja2 import StrictUndefined

# Use StrictUndefined so missing variables raise clear errors at render time.
# Use {var} syntax instead of Jinja's default {{var}} to match common prompt conventions.
_JINJA_ENV = Environment(
    loader=BaseLoader(),
    variable_start_string="{",
    variable_end_string="}",
    undefined=StrictUndefined,
)


@dataclass
class Competitor:
    """
    Represents one contestant in a Choosie arena.

    Args:
        provider:    LiteLLM provider prefix, e.g. "openai", "anthropic", "groq".
                     Pass "" to let LiteLLM auto-detect from the model name.
        model:       Model identifier, e.g. "gpt-4o", "claude-3-5-sonnet-20241022".
        prompt:      The system/user prompt. Supports {variable} placeholders.
        name:        Human-readable label shown in the UI. Auto-generated if omitted.
        temperature: Sampling temperature (default 0.7).
        max_tokens:  Max tokens to generate (default 1024).
        extra_params: Any additional kwargs forwarded to the LiteLLM completion call.
        id:          Stable unique ID for tracking across battles (auto-generated).
    """

    provider: str
    model: str
    prompt: str
    name: str = ""
    temperature: float = 0.7
    max_tokens: int = 1024
    extra_params: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    def __post_init__(self) -> None:
        if not self.name:
            prefix = f"{self.provider}/" if self.provider else ""
            self.name = f"{prefix}{self.model}"

        # Validate that the prompt template parses correctly at construction time.
        try:
            _JINJA_ENV.from_string(self.prompt)
        except TemplateSyntaxError as exc:
            raise ValueError(f"Invalid prompt template syntax: {exc}") from exc

    def render_prompt(self, variables: dict[str, Any] | None = None) -> str:
        """Render the prompt template with the provided variables."""
        template = _JINJA_ENV.from_string(self.prompt)
        return template.render(**(variables or {}))

    def run(self, variables: dict[str, Any] | None = None) -> "CompetitorResult":
        """
        Execute this competitor against the LLM and return a CompetitorResult.

        Args:
            variables: Dict of values to substitute into the prompt template.

        Returns:
            CompetitorResult with the rendered prompt and model response.
        """
        rendered = self.render_prompt(variables)

        # Build the fully-qualified model string LiteLLM expects, e.g. "openai/gpt-4o"
        llm_model = f"{self.provider}/{self.model}" if self.provider else self.model

        response = litellm_completion(
            model=llm_model,
            messages=[{"role": "user", "content": rendered}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.extra_params,
        )

        return CompetitorResult(
            competitor=self,
            rendered_prompt=rendered,
            response=response.choices[0].message.content or "",
            raw_response=response,
        )

    def __repr__(self) -> str:
        return f"Competitor(name={self.name!r}, model={self.model!r})"


@dataclass
class CompetitorResult:
    """
    The output produced by a single Competitor during a battle.

    Attributes:
        competitor:      The Competitor that produced this result.
        rendered_prompt: The final prompt string after template substitution.
        response:        The model's text response.
        raw_response:    The raw LiteLLM response object (for advanced use).
        score:           Numeric score assigned during evaluation (None until judged).
        vote:            Human/LLM vote: 1 (thumbs up), -1 (thumbs down), 0 (skip).
        won:             Whether this competitor was selected as the winner.
    """

    competitor: Competitor
    rendered_prompt: str
    response: str
    raw_response: Any
    score: float | None = None
    vote: int | None = None  # 1, -1, or 0
    won: bool = False
