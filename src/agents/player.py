"""AI Player agent for the Werewolf game."""

from dataclasses import dataclass, field
from typing import Optional

from ..engine.roles import Role
from ..llm.openrouter import OpenRouterClient, Message
from .memory import PlayerMemory
from .prompts import (
    build_system_prompt,
    generate_personality,
    DISCUSSION_PROMPT,
    VOTE_PROMPT,
    NIGHT_WEREWOLF_DISCUSSION_PROMPT,
    NIGHT_WEREWOLF_VOTE_PROMPT,
    NIGHT_SEER_PROMPT,
    NIGHT_DOCTOR_PROMPT,
    NIGHT_WITCH_PROMPT,
    HUNTER_REVENGE_PROMPT,
)


@dataclass
class Player:
    """An AI player in the Werewolf game."""

    name: str
    role: Role
    model: str
    llm_client: OpenRouterClient
    alive: bool = True
    personality_traits: list[str] = field(default_factory=list)
    memory: PlayerMemory = field(default=None)
    system_prompt: str = ""

    # Witch-specific state
    has_healing_potion: bool = True
    has_poison_potion: bool = True

    # Doctor-specific state
    last_protected: Optional[str] = None

    def __post_init__(self):
        """Initialize memory and system prompt after creation."""
        if not self.personality_traits:
            self.personality_traits = generate_personality()

        if self.memory is None:
            self.memory = PlayerMemory(
                role_name=self.role.name,
                team=self.role.team,
            )

    def set_werewolf_teammates(self, teammates: list[str]) -> None:
        """Set werewolf team info and rebuild system prompt."""
        self.system_prompt = build_system_prompt(
            player_name=self.name,
            role=self.role,
            personality_traits=self.personality_traits,
            other_werewolves=teammates,
        )

    def initialize(self, other_werewolves: Optional[list[str]] = None) -> None:
        """Initialize the player for a new game."""
        self.system_prompt = build_system_prompt(
            player_name=self.name,
            role=self.role,
            personality_traits=self.personality_traits,
            other_werewolves=other_werewolves,
        )

    async def _generate(
        self,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
    ) -> str:
        """Generate a response using the LLM."""
        return await self.llm_client.generate(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            model=self.model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def speak(self, current_phase: str, alive_players: list[str]) -> str:
        """Generate a statement for day discussion.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.

        Returns:
            The player's statement.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = DISCUSSION_PROMPT.format(context=context)
        return await self._generate(prompt, temperature=0.8)

    async def vote(
        self,
        current_phase: str,
        alive_players: list[str],
        candidates: list[str],
    ) -> str:
        """Vote for a player to eliminate.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            candidates: List of players that can be voted for.

        Returns:
            Name of the player being voted for.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = VOTE_PROMPT.format(
            context=context,
            candidates=", ".join(candidates),
        )
        response = await self._generate(prompt, temperature=0.3, max_tokens=50)
        # Extract just the name from the response
        return self._extract_name(response, candidates)

    async def werewolf_discuss(
        self,
        current_phase: str,
        alive_players: list[str],
        targets: list[str],
    ) -> str:
        """Discuss with werewolf pack during night.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            targets: List of potential victims.

        Returns:
            Discussion contribution.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = NIGHT_WEREWOLF_DISCUSSION_PROMPT.format(
            context=context,
            targets=", ".join(targets),
        )
        return await self._generate(prompt, temperature=0.8)

    async def werewolf_vote(
        self,
        current_phase: str,
        alive_players: list[str],
        targets: list[str],
    ) -> str:
        """Vote for werewolf kill target.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            targets: List of potential victims.

        Returns:
            Name of the chosen victim.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = NIGHT_WEREWOLF_VOTE_PROMPT.format(
            context=context,
            targets=", ".join(targets),
        )
        response = await self._generate(prompt, temperature=0.3, max_tokens=50)
        return self._extract_name(response, targets)

    async def seer_investigate(
        self,
        current_phase: str,
        alive_players: list[str],
        targets: list[str],
    ) -> str:
        """Choose a player to investigate.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            targets: List of players that can be investigated.

        Returns:
            Name of the player to investigate.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = NIGHT_SEER_PROMPT.format(
            context=context,
            targets=", ".join(targets),
        )
        response = await self._generate(prompt, temperature=0.3, max_tokens=50)
        return self._extract_name(response, targets)

    async def doctor_protect(
        self,
        current_phase: str,
        alive_players: list[str],
        targets: list[str],
    ) -> str:
        """Choose a player to protect.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            targets: List of players that can be protected.

        Returns:
            Name of the player to protect.
        """
        context = self.memory.get_context(current_phase, alive_players)
        restriction = ""
        if self.last_protected:
            restriction = f"(You cannot protect {self.last_protected} - you protected them last night)"

        prompt = NIGHT_DOCTOR_PROMPT.format(
            context=context,
            targets=", ".join(targets),
            restriction=restriction,
        )
        response = await self._generate(prompt, temperature=0.3, max_tokens=50)
        chosen = self._extract_name(response, targets)
        self.last_protected = chosen
        return chosen

    async def witch_action(
        self,
        current_phase: str,
        alive_players: list[str],
        victim: Optional[str],
        targets: list[str],
    ) -> tuple[Optional[str], Optional[str]]:
        """Decide on witch action.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            victim: Tonight's werewolf victim (if any).
            targets: List of players that can be poisoned.

        Returns:
            Tuple of (save_target, poison_target) - both can be None.
        """
        context = self.memory.get_context(current_phase, alive_players)

        potion_status = []
        if self.has_healing_potion:
            potion_status.append("Healing potion: AVAILABLE")
        else:
            potion_status.append("Healing potion: USED")
        if self.has_poison_potion:
            potion_status.append("Poison potion: AVAILABLE")
        else:
            potion_status.append("Poison potion: USED")

        victim_info = ""
        if victim and self.has_healing_potion:
            victim_info = f"Tonight's victim: {victim} (you can save them with healing potion)"

        actions = []
        if victim and self.has_healing_potion:
            actions.append('"save" - use healing potion to save the victim')
        if self.has_poison_potion:
            actions.append('"poison [name]" - use poison potion to kill someone')
        actions.append('"pass" - do nothing')

        prompt = NIGHT_WITCH_PROMPT.format(
            context=context,
            potion_status="\n".join(potion_status),
            victim_info=victim_info,
            actions="\n".join(actions),
        )
        response = await self._generate(prompt, temperature=0.5, max_tokens=100)
        response = response.lower().strip()

        save_target = None
        poison_target = None

        if "save" in response and self.has_healing_potion and victim:
            save_target = victim
            self.has_healing_potion = False
        elif "poison" in response and self.has_poison_potion:
            # Extract poison target
            for target in targets:
                if target.lower() in response:
                    poison_target = target
                    self.has_poison_potion = False
                    break

        return save_target, poison_target

    async def hunter_revenge(
        self,
        current_phase: str,
        alive_players: list[str],
        targets: list[str],
    ) -> str:
        """Choose a player to take down upon death.

        Args:
            current_phase: Current game phase.
            alive_players: List of alive player names.
            targets: List of players that can be shot.

        Returns:
            Name of the player to shoot.
        """
        context = self.memory.get_context(current_phase, alive_players)
        prompt = HUNTER_REVENGE_PROMPT.format(
            context=context,
            targets=", ".join(targets),
        )
        response = await self._generate(prompt, temperature=0.3, max_tokens=50)
        return self._extract_name(response, targets)

    def _extract_name(self, response: str, valid_names: list[str]) -> str:
        """Extract a player name from LLM response.

        Args:
            response: The LLM's response.
            valid_names: List of valid player names.

        Returns:
            The extracted name, or the first valid name if extraction fails.
        """
        response_lower = response.lower().strip()

        # Try exact match first
        for name in valid_names:
            if name.lower() == response_lower:
                return name

        # Try if response contains the name
        for name in valid_names:
            if name.lower() in response_lower:
                return name

        # Fallback to first valid name
        return valid_names[0] if valid_names else ""

    def receive_message(self, phase: str, speaker: str, content: str, visibility: str) -> None:
        """Add a message to this player's memory.

        Args:
            phase: Current game phase.
            speaker: Who said it.
            content: What was said.
            visibility: "public", "werewolf", or "private".
        """
        if visibility == "public":
            self.memory.add_public_message(phase, speaker, content)
        elif visibility == "werewolf" and self.role.team == "werewolf":
            self.memory.add_werewolf_message(phase, speaker, content)

    def receive_system_event(self, phase: str, content: str) -> None:
        """Add a system event to this player's memory."""
        self.memory.add_system_event(phase, content)

    def receive_private_knowledge(self, key: str, value: str) -> None:
        """Add private knowledge (e.g., seer result)."""
        self.memory.add_private_knowledge(key, value)

    def kill(self) -> None:
        """Mark the player as dead."""
        self.alive = False
