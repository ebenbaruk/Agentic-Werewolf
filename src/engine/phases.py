"""Game phase definitions and transitions."""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional


class GamePhase(Enum):
    """Phases of the werewolf game."""
    SETUP = auto()           # Initial setup, role assignment
    NIGHT = auto()           # Werewolves hunt, special roles act
    DAY_ANNOUNCEMENT = auto()  # Announce night deaths
    DAY_DISCUSSION = auto()  # Players discuss
    DAY_VOTE = auto()        # Players vote to eliminate
    GAME_OVER = auto()       # Game has ended


@dataclass
class PhaseState:
    """Current state within a phase."""
    phase: GamePhase
    round_number: int = 1  # Day/Night number (1, 2, 3...)
    discussion_round: int = 0  # Which discussion round within a day
    current_speaker_index: int = 0  # Whose turn to speak

    @property
    def phase_name(self) -> str:
        """Get a human-readable phase name with round number."""
        if self.phase == GamePhase.NIGHT:
            return f"night_{self.round_number}"
        elif self.phase == GamePhase.DAY_DISCUSSION:
            return f"day_{self.round_number}_discussion"
        elif self.phase == GamePhase.DAY_VOTE:
            return f"day_{self.round_number}_vote"
        elif self.phase == GamePhase.DAY_ANNOUNCEMENT:
            return f"day_{self.round_number}_announcement"
        return self.phase.name.lower()


class PhaseManager:
    """Manages phase transitions and state."""

    def __init__(self, discussion_rounds: int = 3):
        """Initialize the phase manager.

        Args:
            discussion_rounds: Number of discussion rounds per day.
        """
        self.discussion_rounds = discussion_rounds
        self.state = PhaseState(phase=GamePhase.SETUP, round_number=0)

    def start_game(self) -> PhaseState:
        """Start the game - transition to first night."""
        self.state = PhaseState(phase=GamePhase.NIGHT, round_number=1)
        return self.state

    def next_phase(self) -> PhaseState:
        """Advance to the next phase.

        Returns:
            The new phase state.
        """
        current = self.state.phase

        if current == GamePhase.SETUP:
            # Start with first night
            self.state = PhaseState(phase=GamePhase.NIGHT, round_number=1)

        elif current == GamePhase.NIGHT:
            # Night -> Day Announcement
            self.state = PhaseState(
                phase=GamePhase.DAY_ANNOUNCEMENT,
                round_number=self.state.round_number,
            )

        elif current == GamePhase.DAY_ANNOUNCEMENT:
            # Announcement -> Discussion
            self.state = PhaseState(
                phase=GamePhase.DAY_DISCUSSION,
                round_number=self.state.round_number,
                discussion_round=1,
            )

        elif current == GamePhase.DAY_DISCUSSION:
            # Check if more discussion rounds
            if self.state.discussion_round < self.discussion_rounds:
                self.state = PhaseState(
                    phase=GamePhase.DAY_DISCUSSION,
                    round_number=self.state.round_number,
                    discussion_round=self.state.discussion_round + 1,
                )
            else:
                # Move to voting
                self.state = PhaseState(
                    phase=GamePhase.DAY_VOTE,
                    round_number=self.state.round_number,
                )

        elif current == GamePhase.DAY_VOTE:
            # Vote -> Next Night
            self.state = PhaseState(
                phase=GamePhase.NIGHT,
                round_number=self.state.round_number + 1,
            )

        elif current == GamePhase.GAME_OVER:
            # Stay in game over
            pass

        return self.state

    def end_game(self) -> PhaseState:
        """End the game."""
        self.state = PhaseState(
            phase=GamePhase.GAME_OVER,
            round_number=self.state.round_number,
        )
        return self.state

    def advance_speaker(self, num_speakers: int) -> bool:
        """Advance to next speaker in discussion.

        Args:
            num_speakers: Total number of speakers.

        Returns:
            True if there are more speakers, False if round is complete.
        """
        self.state.current_speaker_index += 1
        if self.state.current_speaker_index >= num_speakers:
            self.state.current_speaker_index = 0
            return False
        return True

    def reset_speaker_index(self) -> None:
        """Reset speaker index for new discussion round."""
        self.state.current_speaker_index = 0
