"""Markdown logger for game conversations and events."""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .channels import Message, Visibility


class MarkdownLogger:
    """Writes game events and conversations to markdown files."""

    def __init__(self, base_dir: str = "games"):
        """Initialize the logger.

        Args:
            base_dir: Base directory for game logs.
        """
        self.base_dir = Path(base_dir)
        self.game_dir: Optional[Path] = None
        self.game_id: Optional[str] = None

    def start_game(self, game_id: Optional[str] = None) -> Path:
        """Start logging a new game.

        Args:
            game_id: Optional game identifier. If not provided, uses timestamp.

        Returns:
            Path to the game directory.
        """
        if game_id is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            game_id = f"game_{timestamp}"

        self.game_id = game_id
        self.game_dir = self.base_dir / game_id
        self.game_dir.mkdir(parents=True, exist_ok=True)

        # Create initial game state file
        self._write_game_header()

        return self.game_dir

    def _write_game_header(self) -> None:
        """Write the initial game state file header."""
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "w") as f:
            f.write(f"# Werewolf Game - {self.game_id}\n\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("---\n\n")

    def log_setup(
        self,
        players: list[dict],
        role_assignments: dict[str, str],
    ) -> None:
        """Log game setup information.

        Args:
            players: List of player info dicts (name, model, personality).
            role_assignments: Mapping of player names to roles.
        """
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write("## Players\n\n")
            f.write("| Player | Model | Personality | Role (Hidden) |\n")
            f.write("|--------|-------|-------------|---------------|\n")
            for p in players:
                role = role_assignments.get(p["name"], "Unknown")
                personality = ", ".join(p.get("personality", []))
                f.write(f"| {p['name']} | {p['model']} | {personality} | {role} |\n")
            f.write("\n---\n\n")

    def log_phase_start(self, phase: str) -> None:
        """Log the start of a game phase.

        Args:
            phase: Phase name (e.g., "night_1", "day_1_discussion").
        """
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write(f"## {phase.replace('_', ' ').title()}\n\n")

    def log_discussion(
        self,
        phase: str,
        messages: list[Message],
    ) -> None:
        """Log a discussion to its own markdown file.

        Args:
            phase: Phase name.
            messages: List of messages from the discussion.
        """
        filename = f"{phase}.md"
        filepath = self.game_dir / filename

        with open(filepath, "w") as f:
            f.write(f"# {phase.replace('_', ' ').title()}\n\n")

            current_round = 1
            for i, msg in enumerate(messages):
                if msg.speaker == "SYSTEM":
                    f.write(f"\n*{msg.content}*\n\n")
                else:
                    f.write(f"**{msg.speaker}**:\n")
                    f.write(f"> {msg.content}\n\n")

        # Also append summary to game state
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write(f"*See [{filename}](./{filename}) for full discussion*\n\n")

    def log_werewolf_discussion(
        self,
        phase: str,
        messages: list[Message],
    ) -> None:
        """Log werewolf night discussion.

        Args:
            phase: Phase name (e.g., "night_1").
            messages: Messages from werewolf chat.
        """
        filename = f"{phase}_werewolves.md"
        filepath = self.game_dir / filename

        with open(filepath, "w") as f:
            f.write(f"# Werewolf Night Chat - {phase.replace('_', ' ').title()}\n\n")
            f.write("*This conversation is secret - only werewolves can see it*\n\n")
            f.write("---\n\n")

            for msg in messages:
                f.write(f"**{msg.speaker}**:\n")
                f.write(f"> {msg.content}\n\n")

    def log_vote(
        self,
        phase: str,
        votes: dict[str, str],
        eliminated: Optional[str],
    ) -> None:
        """Log voting results.

        Args:
            phase: Phase name.
            votes: Mapping of voter to voted-for.
            eliminated: Name of eliminated player, or None for tie.
        """
        # Create votes directory if needed
        votes_dir = self.game_dir / "votes"
        votes_dir.mkdir(exist_ok=True)

        filename = f"{phase}.md"
        filepath = votes_dir / filename

        # Count votes
        vote_counts: dict[str, list[str]] = {}
        for voter, target in votes.items():
            if target not in vote_counts:
                vote_counts[target] = []
            vote_counts[target].append(voter)

        with open(filepath, "w") as f:
            f.write(f"# Voting - {phase.replace('_', ' ').title()}\n\n")

            f.write("## Individual Votes\n\n")
            f.write("| Voter | Voted For |\n")
            f.write("|-------|----------|\n")
            for voter, target in sorted(votes.items()):
                f.write(f"| {voter} | {target} |\n")

            f.write("\n## Vote Totals\n\n")
            for target, voters in sorted(vote_counts.items(), key=lambda x: -len(x[1])):
                f.write(f"- **{target}**: {len(voters)} votes ({', '.join(voters)})\n")

            f.write(f"\n## Result\n\n")
            if eliminated:
                f.write(f"**{eliminated}** was eliminated by the village.\n")
            else:
                f.write("*No elimination - vote was tied.*\n")

        # Append to game state
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write(f"### Vote Result\n\n")
            if eliminated:
                f.write(f"**{eliminated}** was eliminated.\n\n")
            else:
                f.write("*Vote tied - no elimination*\n\n")

    def log_death(
        self,
        player_name: str,
        cause: str,
        phase: str,
        role_revealed: Optional[str] = None,
    ) -> None:
        """Log a player death.

        Args:
            player_name: Who died.
            cause: How they died.
            phase: When they died.
            role_revealed: Their role (revealed on death).
        """
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write(f"### Death\n\n")
            f.write(f"**{player_name}** died ({cause}).\n")
            if role_revealed:
                f.write(f"*They were a {role_revealed}.*\n")
            f.write("\n")

    def log_night_action(
        self,
        phase: str,
        role: str,
        player: str,
        action: str,
        target: Optional[str] = None,
        result: Optional[str] = None,
    ) -> None:
        """Log a night action (for game review - not visible to players).

        Args:
            phase: Night phase.
            role: Role that took action.
            player: Player who took action.
            action: What action.
            target: Target of action.
            result: Result of action.
        """
        filename = f"{phase}_actions.md"
        filepath = self.game_dir / filename

        # Append to file
        mode = "a" if filepath.exists() else "w"
        with open(filepath, mode) as f:
            if mode == "w":
                f.write(f"# Night Actions - {phase.replace('_', ' ').title()}\n\n")
                f.write("*This file records all night actions for game review*\n\n")
                f.write("---\n\n")

            f.write(f"**{player}** ({role}): {action}")
            if target:
                f.write(f" -> {target}")
            if result:
                f.write(f" [{result}]")
            f.write("\n\n")

    def log_game_end(
        self,
        winner: str,
        surviving_players: list[dict],
        all_players: list[dict],
    ) -> None:
        """Log the game ending.

        Args:
            winner: Winning team ("village" or "werewolf").
            surviving_players: Players still alive.
            all_players: All players with roles revealed.
        """
        game_file = self.game_dir / "game_state.md"
        with open(game_file, "a") as f:
            f.write("---\n\n")
            f.write("# GAME OVER\n\n")
            f.write(f"## Winner: {winner.upper()} TEAM\n\n")

            f.write("## Survivors\n\n")
            if surviving_players:
                for p in surviving_players:
                    f.write(f"- {p['name']} ({p['role']})\n")
            else:
                f.write("*No survivors*\n")

            f.write("\n## All Players\n\n")
            f.write("| Player | Role | Team | Survived |\n")
            f.write("|--------|------|------|----------|\n")
            for p in all_players:
                survived = "Yes" if p.get("alive", False) else "No"
                f.write(f"| {p['name']} | {p['role']} | {p['team']} | {survived} |\n")

            f.write(f"\n\nEnded: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
