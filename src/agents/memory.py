"""Player memory management for context and history tracking."""

from dataclasses import dataclass, field
from typing import Optional

from pydantic import BaseModel


class MemoryEntry(BaseModel):
    """A single memory entry."""
    phase: str  # e.g., "night_1", "day_1_discussion", "day_1_vote"
    content: str
    visibility: str  # "public", "werewolf", "private"
    speaker: Optional[str] = None


@dataclass
class PlayerMemory:
    """Manages a player's knowledge and context.

    Players only know what they've observed:
    - Their own role
    - Public discussions they've witnessed
    - Private information (werewolf chat if werewolf, seer results if seer, etc.)
    - Death announcements
    - Voting history
    """

    role_name: str
    team: str
    entries: list[MemoryEntry] = field(default_factory=list)
    private_knowledge: dict[str, str] = field(default_factory=dict)
    max_recent_entries: int = 50  # Keep full detail for last N entries

    def add_public_message(self, phase: str, speaker: str, content: str) -> None:
        """Add a public discussion message."""
        self.entries.append(MemoryEntry(
            phase=phase,
            content=content,
            visibility="public",
            speaker=speaker,
        ))

    def add_werewolf_message(self, phase: str, speaker: str, content: str) -> None:
        """Add a werewolf-only message (night coordination)."""
        self.entries.append(MemoryEntry(
            phase=phase,
            content=content,
            visibility="werewolf",
            speaker=speaker,
        ))

    def add_private_knowledge(self, key: str, value: str) -> None:
        """Add private knowledge (e.g., seer investigation result)."""
        self.private_knowledge[key] = value

    def add_system_event(self, phase: str, content: str) -> None:
        """Add a system event (death announcement, phase change, etc.)."""
        self.entries.append(MemoryEntry(
            phase=phase,
            content=content,
            visibility="public",
            speaker=None,
        ))

    def get_context(self, current_phase: str, alive_players: list[str]) -> str:
        """Build context string for the LLM.

        Args:
            current_phase: The current game phase.
            alive_players: List of players still alive.

        Returns:
            Formatted context string.
        """
        lines = []

        # Role and team
        lines.append(f"YOUR ROLE: {self.role_name}")
        lines.append(f"YOUR TEAM: {self.team.upper()}")
        lines.append("")

        # Private knowledge
        if self.private_knowledge:
            lines.append("YOUR PRIVATE KNOWLEDGE:")
            for key, value in self.private_knowledge.items():
                lines.append(f"  - {key}: {value}")
            lines.append("")

        # Alive players
        lines.append(f"PLAYERS STILL ALIVE: {', '.join(alive_players)}")
        lines.append("")

        # Recent history (last N entries in full)
        recent = self.entries[-self.max_recent_entries:]
        if recent:
            lines.append("RECENT EVENTS:")
            current_display_phase = None
            for entry in recent:
                if entry.phase != current_display_phase:
                    lines.append(f"\n--- {entry.phase.upper().replace('_', ' ')} ---")
                    current_display_phase = entry.phase

                if entry.speaker:
                    lines.append(f"[{entry.speaker}]: {entry.content}")
                else:
                    lines.append(f"* {entry.content}")

        lines.append("")
        lines.append(f"CURRENT PHASE: {current_phase.upper().replace('_', ' ')}")

        return "\n".join(lines)

    def clear_old_entries(self, keep_last: int = 100) -> None:
        """Trim old entries to manage context size."""
        if len(self.entries) > keep_last:
            self.entries = self.entries[-keep_last:]
