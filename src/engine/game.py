"""Main game engine for Werewolf."""

import asyncio
import random
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

from ..agents.player import Player
from ..communication.channels import ChannelManager, Visibility
from ..communication.markdown_logger import MarkdownLogger
from ..llm.openrouter import OpenRouterClient
from .phases import GamePhase, PhaseManager
from .roles import Role, ROLES, get_role


@dataclass
class GameConfig:
    """Configuration for a game."""
    player_count: int = 6
    discussion_rounds: int = 3
    role_distribution: dict[str, int] = field(default_factory=lambda: {
        "Werewolf": 2,
        "Seer": 1,
        "Doctor": 1,
        "Villager": 2,
    })


@dataclass
class NightResult:
    """Results from a night phase."""
    werewolf_target: Optional[str] = None
    protected_player: Optional[str] = None
    witch_saved: Optional[str] = None
    witch_poisoned: Optional[str] = None
    deaths: list[str] = field(default_factory=list)
    death_causes: dict[str, str] = field(default_factory=dict)


class Game:
    """The main Werewolf game engine.

    This engine only enforces rules - all intelligence comes from the LLMs.
    """

    def __init__(
        self,
        config: GameConfig,
        llm_client: OpenRouterClient,
        logger: Optional[MarkdownLogger] = None,
    ):
        """Initialize the game.

        Args:
            config: Game configuration.
            llm_client: OpenRouter client for LLM calls.
            logger: Optional markdown logger.
        """
        self.config = config
        self.llm_client = llm_client
        self.logger = logger or MarkdownLogger()
        self.phase_manager = PhaseManager(discussion_rounds=config.discussion_rounds)
        self.channels = ChannelManager()

        self.players: list[Player] = []
        self.winner: Optional[str] = None  # "village" or "werewolf"

    def setup_players(
        self,
        player_configs: list[dict],
    ) -> None:
        """Set up players with roles.

        Args:
            player_configs: List of player configurations with name, model.
        """
        # Create role pool
        role_pool: list[Role] = []
        for role_name, count in self.config.role_distribution.items():
            role = get_role(role_name)
            role_pool.extend([role] * count)

        if len(role_pool) != len(player_configs):
            raise ValueError(
                f"Role count ({len(role_pool)}) doesn't match "
                f"player count ({len(player_configs)})"
            )

        # Shuffle and assign
        random.shuffle(role_pool)

        self.players = []
        for i, pconfig in enumerate(player_configs):
            player = Player(
                name=pconfig["name"],
                role=role_pool[i],
                model=pconfig.get("model", "anthropic/claude-sonnet-4"),
                llm_client=self.llm_client,
            )
            self.players.append(player)

        # Set up werewolf knowledge
        werewolves = [p for p in self.players if p.role.team == "werewolf"]
        werewolf_names = [p.name for p in werewolves]
        self.channels.setup_werewolf_channel(werewolf_names)

        # Initialize all players
        for player in self.players:
            if player.role.team == "werewolf":
                other_wolves = [n for n in werewolf_names if n != player.name]
                player.initialize(other_werewolves=other_wolves)
            else:
                player.initialize()

        # Log setup
        self.logger.log_setup(
            players=[{
                "name": p.name,
                "model": p.model,
                "personality": p.personality_traits,
            } for p in self.players],
            role_assignments={p.name: p.role.name for p in self.players},
        )

    @property
    def alive_players(self) -> list[Player]:
        """Get all alive players."""
        return [p for p in self.players if p.alive]

    @property
    def alive_player_names(self) -> list[str]:
        """Get names of all alive players."""
        return [p.name for p in self.alive_players]

    @property
    def alive_werewolves(self) -> list[Player]:
        """Get all alive werewolves."""
        return [p for p in self.alive_players if p.role.team == "werewolf"]

    @property
    def alive_villagers(self) -> list[Player]:
        """Get all alive village team members."""
        return [p for p in self.alive_players if p.role.team == "village"]

    def check_win_condition(self) -> Optional[str]:
        """Check if game has ended.

        Returns:
            "village" if village wins, "werewolf" if werewolves win, None if ongoing.
        """
        werewolf_count = len(self.alive_werewolves)
        villager_count = len(self.alive_villagers)

        if werewolf_count == 0:
            return "village"
        if werewolf_count >= villager_count:
            return "werewolf"
        return None

    async def run_night_phase(self) -> NightResult:
        """Execute the night phase.

        Returns:
            Results of the night.
        """
        phase_name = self.phase_manager.state.phase_name
        self.logger.log_phase_start(phase_name)

        result = NightResult()

        # Announce night
        self.channels.broadcast_system_event(
            f"Night {self.phase_manager.state.round_number} falls. The village sleeps...",
            phase_name,
            self.players,
        )

        # Get non-werewolf targets
        non_werewolf_names = [p.name for p in self.alive_players if p.role.team != "werewolf"]

        # --- Werewolf discussion and kill ---
        werewolves = self.alive_werewolves
        if werewolves:
            # Werewolf discussion
            for wolf in werewolves:
                response = await wolf.werewolf_discuss(
                    phase_name,
                    self.alive_player_names,
                    non_werewolf_names,
                )
                self.channels.werewolf.broadcast(
                    wolf.name,
                    response,
                    phase_name,
                    self.players,
                    Visibility.WEREWOLF,
                )

            # Werewolf vote (take majority or first wolf's choice)
            wolf_votes = []
            for wolf in werewolves:
                vote = await wolf.werewolf_vote(
                    phase_name,
                    self.alive_player_names,
                    non_werewolf_names,
                )
                wolf_votes.append(vote)

            # Majority vote
            vote_counts = Counter(wolf_votes)
            result.werewolf_target = vote_counts.most_common(1)[0][0]

            self.logger.log_night_action(
                phase_name, "Werewolf", "Pack", "kill", result.werewolf_target
            )
            self.logger.log_werewolf_discussion(
                phase_name,
                self.channels.werewolf.get_messages(phase_name),
            )

        # --- Seer investigation ---
        seer = next((p for p in self.alive_players if p.role.name == "Seer"), None)
        if seer:
            others = [n for n in self.alive_player_names if n != seer.name]
            target = await seer.seer_investigate(phase_name, self.alive_player_names, others)

            # Get result
            target_player = next((p for p in self.players if p.name == target), None)
            if target_player:
                is_werewolf = target_player.role.team == "werewolf"
                result_text = "WEREWOLF" if is_werewolf else "NOT a werewolf"
                seer.receive_private_knowledge(
                    f"Night {self.phase_manager.state.round_number} investigation",
                    f"{target} is {result_text}",
                )
                self.logger.log_night_action(
                    phase_name, "Seer", seer.name, "investigate", target, result_text
                )

        # --- Doctor protection ---
        doctor = next((p for p in self.alive_players if p.role.name == "Doctor"), None)
        if doctor:
            # Can't protect same player twice in a row
            valid_targets = [
                n for n in self.alive_player_names
                if n != doctor.last_protected
            ]
            target = await doctor.doctor_protect(phase_name, self.alive_player_names, valid_targets)
            result.protected_player = target
            self.logger.log_night_action(phase_name, "Doctor", doctor.name, "protect", target)

        # --- Witch actions ---
        witch = next((p for p in self.alive_players if p.role.name == "Witch"), None)
        if witch:
            others = [n for n in self.alive_player_names if n != witch.name]
            save_target, poison_target = await witch.witch_action(
                phase_name,
                self.alive_player_names,
                result.werewolf_target,
                others,
            )
            if save_target:
                result.witch_saved = save_target
                self.logger.log_night_action(phase_name, "Witch", witch.name, "save", save_target)
            if poison_target:
                result.witch_poisoned = poison_target
                self.logger.log_night_action(
                    phase_name, "Witch", witch.name, "poison", poison_target
                )

        # --- Resolve deaths ---
        # Werewolf kill (unless protected or witch saved)
        if result.werewolf_target:
            protected = (
                result.werewolf_target == result.protected_player or
                result.werewolf_target == result.witch_saved
            )
            if not protected:
                result.deaths.append(result.werewolf_target)
                result.death_causes[result.werewolf_target] = "werewolf attack"

        # Witch poison
        if result.witch_poisoned and result.witch_poisoned not in result.deaths:
            result.deaths.append(result.witch_poisoned)
            result.death_causes[result.witch_poisoned] = "mysterious poisoning"

        return result

    async def run_day_announcement(self, night_result: NightResult) -> Optional[str]:
        """Announce night deaths and handle Hunter.

        Args:
            night_result: Results from the night.

        Returns:
            Hunter's revenge target if applicable.
        """
        phase_name = self.phase_manager.state.phase_name

        if night_result.deaths:
            for name in night_result.deaths:
                player = next(p for p in self.players if p.name == name)
                player.kill()
                cause = night_result.death_causes.get(name, "unknown causes")

                # Announce death
                self.channels.broadcast_system_event(
                    f"{name} was found dead this morning ({cause}). "
                    f"They were a {player.role.name}.",
                    phase_name,
                    self.players,
                )
                self.logger.log_death(name, cause, phase_name, player.role.name)

                # Handle Hunter revenge
                if player.role.name == "Hunter":
                    targets = [n for n in self.alive_player_names if n != name]
                    if targets:
                        revenge_target = await player.hunter_revenge(
                            phase_name,
                            self.alive_player_names,
                            targets,
                        )
                        revenge_player = next(p for p in self.players if p.name == revenge_target)
                        revenge_player.kill()
                        self.channels.broadcast_system_event(
                            f"The Hunter takes {revenge_target} with them! "
                            f"{revenge_target} was a {revenge_player.role.name}.",
                            phase_name,
                            self.players,
                        )
                        self.logger.log_death(
                            revenge_target, "Hunter's revenge", phase_name, revenge_player.role.name
                        )
                        return revenge_target
        else:
            self.channels.broadcast_system_event(
                "The village wakes to find everyone alive. The night was peaceful.",
                phase_name,
                self.players,
            )

        return None

    async def run_day_discussion(self) -> None:
        """Run the day discussion phase."""
        phase_name = self.phase_manager.state.phase_name
        self.logger.log_phase_start(phase_name)

        # Announce discussion
        round_num = self.phase_manager.state.discussion_round
        self.channels.broadcast_system_event(
            f"Discussion round {round_num} begins.",
            phase_name,
            self.players,
        )

        # Each alive player speaks once
        for player in self.alive_players:
            response = await player.speak(phase_name, self.alive_player_names)
            self.channels.public.broadcast(
                player.name,
                response,
                phase_name,
                self.players,
            )

        # Log the discussion
        self.logger.log_discussion(phase_name, self.channels.public.get_messages(phase_name))

    async def run_day_vote(self) -> Optional[str]:
        """Run the day voting phase.

        Returns:
            Name of eliminated player, or None for tie.
        """
        phase_name = self.phase_manager.state.phase_name
        self.logger.log_phase_start(phase_name)

        # Announce vote
        self.channels.broadcast_system_event(
            "Time to vote! Who should be eliminated?",
            phase_name,
            self.players,
        )

        # Collect votes
        candidates = self.alive_player_names
        votes: dict[str, str] = {}

        for player in self.alive_players:
            # Can't vote for yourself
            valid_candidates = [n for n in candidates if n != player.name]
            vote = await player.vote(phase_name, self.alive_player_names, valid_candidates)
            votes[player.name] = vote

            # Announce vote publicly
            self.channels.public.broadcast(
                player.name,
                f"I vote for {vote}.",
                phase_name,
                self.players,
            )

        # Count votes
        vote_counts = Counter(votes.values())
        top_votes = vote_counts.most_common(2)

        eliminated = None
        if len(top_votes) == 1 or (len(top_votes) > 1 and top_votes[0][1] > top_votes[1][1]):
            # Clear winner
            eliminated = top_votes[0][0]
            player = next(p for p in self.players if p.name == eliminated)
            player.kill()

            # Announce
            self.channels.broadcast_system_event(
                f"The village has decided. {eliminated} is eliminated. "
                f"They were a {player.role.name}.",
                phase_name,
                self.players,
            )
            self.logger.log_death(eliminated, "village vote", phase_name, player.role.name)

            # Handle Hunter
            if player.role.name == "Hunter":
                targets = [n for n in self.alive_player_names if n != eliminated]
                if targets:
                    revenge = await player.hunter_revenge(
                        phase_name,
                        self.alive_player_names,
                        targets,
                    )
                    revenge_player = next(p for p in self.players if p.name == revenge)
                    revenge_player.kill()
                    self.channels.broadcast_system_event(
                        f"The Hunter takes {revenge} with them! "
                        f"{revenge} was a {revenge_player.role.name}.",
                        phase_name,
                        self.players,
                    )
                    self.logger.log_death(
                        revenge, "Hunter's revenge", phase_name, revenge_player.role.name
                    )
        else:
            # Tie - no elimination
            self.channels.broadcast_system_event(
                "The vote is tied. No one is eliminated today.",
                phase_name,
                self.players,
            )

        self.logger.log_vote(phase_name, votes, eliminated)
        return eliminated

    async def run(self) -> str:
        """Run the complete game.

        Returns:
            The winning team ("village" or "werewolf").
        """
        # Start logging
        self.logger.start_game()

        # Start game
        self.phase_manager.start_game()

        while True:
            phase = self.phase_manager.state.phase

            if phase == GamePhase.NIGHT:
                night_result = await self.run_night_phase()
                self.phase_manager.next_phase()

                # Day announcement
                await self.run_day_announcement(night_result)

                # Check win condition
                winner = self.check_win_condition()
                if winner:
                    self.winner = winner
                    break

                self.phase_manager.next_phase()

            elif phase == GamePhase.DAY_DISCUSSION:
                await self.run_day_discussion()

                # Check if more discussion rounds
                if self.phase_manager.state.discussion_round < self.config.discussion_rounds:
                    self.phase_manager.next_phase()
                else:
                    self.phase_manager.next_phase()

            elif phase == GamePhase.DAY_VOTE:
                await self.run_day_vote()

                # Check win condition
                winner = self.check_win_condition()
                if winner:
                    self.winner = winner
                    break

                self.phase_manager.next_phase()

            else:
                # Should not reach here
                break

        # Log game end
        self.phase_manager.end_game()
        self.logger.log_game_end(
            winner=self.winner,
            surviving_players=[{
                "name": p.name,
                "role": p.role.name,
            } for p in self.alive_players],
            all_players=[{
                "name": p.name,
                "role": p.role.name,
                "team": p.role.team,
                "alive": p.alive,
            } for p in self.players],
        )

        return self.winner
