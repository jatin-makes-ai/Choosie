"""
VibeDiff — Battle-test your prompts. Ship the best one.

Usage:
    from vibediff import Competitor, Arena

    c1 = Competitor(provider="openai", model="gpt-4o", prompt="Explain {topic}")
    c2 = Competitor(provider="anthropic", model="claude-3-sonnet", prompt="Describe {topic}")

    arena = Arena(competitors=[c1, c2])
    arena.battle(mode=1, variables={"topic": "quantum computing"})
"""

from vibediff.core.competitor import Competitor
from vibediff.core.arena import Arena
from vibediff.core.battle import BattleMode
from vibediff.storage.csv_store import CSVStore

__all__ = ["Competitor", "Arena", "BattleMode", "CSVStore"]
__version__ = "0.1.0"
