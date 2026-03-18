"""
Quick example: Launch a blind evaluation battleground.

Set your API keys as environment variables before running:
  $env:OPENAI_API_KEY = "sk-..."
  $env:ANTHROPIC_API_KEY = "sk-ant-..."
  $env:GROQ_API_KEY = "gsk_..."

Then run:
  python examples/quickstart.py
"""

from vibediff import Arena, Competitor

# ── Define your competitors ───────────────────────────────────────────────────
# The user in the UI will NOT see these names or prompts — only "Response A", "Response B", etc.

c1 = Competitor(
    provider="openai",
    model="gpt-4o-mini",
    prompt="{query}",
    name="GPT-4o-mini (Vanilla)",
)

c2 = Competitor(
    provider="openai",
    model="gpt-4o",
    prompt="You are an expert teacher. Answer the following question clearly and concisely:\n\n{query}",
    name="GPT-4o (Teacher Prompt)",
)

# Uncomment for 3-way battle with Anthropic:
# c3 = Competitor(
#     provider="anthropic",
#     model="claude-3-5-sonnet-20241022",
#     prompt="Think step by step. {query}",
#     name="Claude 3.5 (Chain-of-Thought)",
# )

# ── Launch the battleground ──────────────────────────────────────────────────

arena = Arena(
    competitors=[c1, c2],
    csv_path="vibediff_results.csv",  # All results saved here automatically
)

# Mode 1: Pick the Best (side-by-side, blind)
arena.battle(mode=1)

# Or Mode 2: Thumbs Up/Down
# arena.battle(mode=2)
