"""Communication channels for message routing between players."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from enum import Enum

if TYPE_CHECKING:
    from ..agents.player import Player


class Visibility(Enum):
    """Message visibility levels."""
    PUBLIC = "public"  # All players see
    WEREWOLF = "werewolf"  # Only werewolves see
    PRIVATE = "private"  # Only specific player sees


@dataclass
class Message:
    """A message in a channel."""
    speaker: str
    content: str
    phase: str
    visibility: Visibility


@dataclass
class Channel:
    """Base class for communication channels."""

    name: str
    messages: list[Message] = field(default_factory=list)

    def add_message(
        self,
        speaker: str,
        content: str,
        phase: str,
        visibility: Visibility = Visibility.PUBLIC,
    ) -> Message:
        """Add a message to the channel."""
        msg = Message(
            speaker=speaker,
            content=content,
            phase=phase,
            visibility=visibility,
        )
        self.messages.append(msg)
        return msg

    def get_messages(self, phase: Optional[str] = None) -> list[Message]:
        """Get messages, optionally filtered by phase."""
        if phase is None:
            return self.messages
        return [m for m in self.messages if m.phase == phase]

    def clear(self) -> None:
        """Clear all messages."""
        self.messages.clear()


@dataclass
class PublicChannel(Channel):
    """Channel for public day discussions - all players can see."""

    def __post_init__(self):
        self.name = "public"

    def broadcast(
        self,
        speaker: str,
        content: str,
        phase: str,
        players: list["Player"],
    ) -> None:
        """Broadcast a message to all players.

        Args:
            speaker: Who is speaking.
            content: What they said.
            phase: Current game phase.
            players: All players to receive the message.
        """
        msg = self.add_message(speaker, content, phase, Visibility.PUBLIC)
        for player in players:
            if player.alive:
                player.receive_message(phase, speaker, content, "public")


@dataclass
class PrivateChannel(Channel):
    """Channel for private communication - werewolf night chat, etc."""

    allowed_players: list[str] = field(default_factory=list)

    def broadcast(
        self,
        speaker: str,
        content: str,
        phase: str,
        players: list["Player"],
        visibility: Visibility = Visibility.WEREWOLF,
    ) -> None:
        """Broadcast a message to allowed players only.

        Args:
            speaker: Who is speaking.
            content: What they said.
            phase: Current game phase.
            players: All players (will filter to allowed ones).
            visibility: Message visibility level.
        """
        msg = self.add_message(speaker, content, phase, visibility)
        for player in players:
            if player.alive and player.name in self.allowed_players:
                player.receive_message(phase, speaker, content, visibility.value)


class ChannelManager:
    """Manages all communication channels for a game."""

    def __init__(self):
        self.public = PublicChannel(name="public")
        self.werewolf = PrivateChannel(name="werewolf", allowed_players=[])
        self._private_channels: dict[str, PrivateChannel] = {}

    def setup_werewolf_channel(self, werewolf_names: list[str]) -> None:
        """Configure the werewolf private channel."""
        self.werewolf.allowed_players = werewolf_names

    def get_private_channel(self, player_name: str) -> PrivateChannel:
        """Get or create a private channel for a specific player."""
        if player_name not in self._private_channels:
            self._private_channels[player_name] = PrivateChannel(
                name=f"private_{player_name}",
                allowed_players=[player_name],
            )
        return self._private_channels[player_name]

    def broadcast_system_event(
        self,
        content: str,
        phase: str,
        players: list["Player"],
    ) -> None:
        """Broadcast a system event to all players.

        Args:
            content: Event description.
            phase: Current game phase.
            players: All players.
        """
        self.public.add_message("SYSTEM", content, phase, Visibility.PUBLIC)
        for player in players:
            player.receive_system_event(phase, content)

    def clear_all(self) -> None:
        """Clear all channels."""
        self.public.clear()
        self.werewolf.clear()
        for channel in self._private_channels.values():
            channel.clear()
