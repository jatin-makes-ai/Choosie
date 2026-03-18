# ⚔️ Choosie

> **Battle-test your prompts. Ship the best one.**

Choosie is an open-source Python library for comparing LLM prompts and models head-to-head. Define competitors, launch an arena, and let a beautiful evaluation UI (or your own logic) pick the winner — with a live ELO leaderboard tracking performance across every battle.

[![PyPI - Python Version](https://img.shields.io/badge/python-3.10%2B-blue)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)]()
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange)]()

---

## ✨ Features

- **LLM-agnostic** — supports OpenAI, Anthropic, Groq, Cohere, Mistral, and 100+ providers via [LiteLLM](https://github.com/BerriAI/litellm)
- **Prompt templating** — write prompts with `{variable}` placeholders, inject values at battle time
- **Two battle modes** out of the box:
  - `PICK_BEST` — side-by-side cards, you pick the winner
  - `THUMBS` — rate each response 👍 / 👎 independently
- **ELO leaderboard** — competitors gain/lose rating after every battle; track who's winning over time
- **Parallel execution** — all competitors run concurrently to minimize wall-clock time
- **Beautiful Gradio UI** — dark-mode battleground UI launches automatically in your browser

---

## 🚀 Quickstart

### Install

```bash
pip install choosie
```

### Run a battle

```python
from choosie import Competitor, Arena, BattleMode

c1 = Competitor(
    provider="openai",
    model="gpt-4o-mini",
    prompt="Explain {topic} simply.",
    name="GPT-4o-mini"
)

c2 = Competitor(
    provider="anthropic",
    model="claude-3-5-sonnet-20241022",
    prompt="Give a detailed breakdown of {topic}.",
    name="Claude 3.5"
)

arena = Arena(competitors=[c1, c2])

# Mode 1: pick the best response side-by-side
result = arena.battle(mode=1, variables={"topic": "transformer attention"})

# Mode 2: thumbs up/down on each response
result = arena.battle(mode=2, variables={"topic": "RAG vs fine-tuning"})

# View leaderboard
arena.leaderboard().display()
```

The Gradio UI will open in your browser automatically. Once you submit your judgement, the battle result is returned and the leaderboard is updated.

---

## 🧩 API Reference

### `Competitor`

```python
Competitor(
    provider: str,           # LiteLLM provider, e.g. "openai", "anthropic", "groq"
    model: str,              # Model name, e.g. "gpt-4o", "claude-3-5-sonnet-20241022"
    prompt: str,             # Prompt string with optional {variable} placeholders
    name: str = "",          # Display name (auto-generated if omitted)
    temperature: float = 0.7,
    max_tokens: int = 1024,
    extra_params: dict = {}  # Forwarded to LiteLLM
)
```

### `Arena`

```python
Arena(
    competitors: list[Competitor],
    parallel: bool = True,      # Run competitors concurrently
    on_result: callable = None, # Callback(BattleResult) after each battle
)

arena.battle(
    mode: int | BattleMode,   # 1 = PICK_BEST, 2 = THUMBS
    variables: dict = {},     # Template variable substitutions
    launch_ui: bool = True,   # Set False for headless/CI use
)

arena.leaderboard()  # Returns Leaderboard object
arena.history        # List of all BattleResult objects
```

### `Leaderboard`

```python
lb = arena.leaderboard()
lb.display()        # Pretty-print to stdout
lb.to_dict()        # List of dicts
lb.to_dataframe()   # pandas DataFrame (requires: pip install choosie[analytics])
```

---

## 🔑 API Keys

Choosie uses LiteLLM, which reads API keys from environment variables:

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:ANTHROPIC_API_KEY = "sk-ant-..."
$env:GROQ_API_KEY = "gsk_..."
```

---

## 🛣️ Roadmap

| Version | Features |
|---------|---------|
| **v0.1** (now) | Core library, PICK_BEST + THUMBS modes, ELO leaderboard, Gradio UI |
| **v0.2** | Rubric-based scoring, regression/golden-baseline mode, result persistence (SQLite) |
| **v1.0** | Stable API, pytest plugin, CI integration |
| **v2.0** | Agentic evaluation (LLM-as-judge), auto-prompt optimization |

---

## 🤝 Contributing

PRs and issues welcome! See `CONTRIBUTING.md` (coming soon).

---

## 📄 License

MIT
