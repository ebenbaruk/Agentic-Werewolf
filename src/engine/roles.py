"""Role definitions for the Werewolf game."""

from dataclasses import dataclass
from typing import Literal, Optional


@dataclass(frozen=True)
class Role:
    """A role in the Werewolf game."""

    name: str
    team: Literal["village", "werewolf"]
    night_action: Optional[str] = None
    description: str = ""

    def __str__(self) -> str:
        return self.name


# All available roles
ROLES = {
    "Villager": Role(
        name="Villager",
        team="village",
        night_action=None,
        description="A regular villager with no special abilities. Use your wits to identify the werewolves."
    ),
    "Werewolf": Role(
        name="Werewolf",
        team="werewolf",
        night_action="kill",
        description="A werewolf who hunts villagers at night. Coordinate with your pack to eliminate the village."
    ),
    "Seer": Role(
        name="Seer",
        team="village",
        night_action="investigate",
        description="A villager with the ability to see the true nature of one player each night."
    ),
    "Doctor": Role(
        name="Doctor",
        team="village",
        night_action="protect",
        description="A villager who can protect one player from death each night."
    ),
    "Hunter": Role(
        name="Hunter",
        team="village",
        night_action="revenge_kill",
        description="When killed, the Hunter can take one other player with them."
    ),
    "Witch": Role(
        name="Witch",
        team="village",
        night_action="save_or_poison",
        description="Has one healing potion and one poison potion to use throughout the game."
    ),
}


def get_role(name: str) -> Role:
    """Get a role by name."""
    if name not in ROLES:
        raise ValueError(f"Unknown role: {name}. Available: {list(ROLES.keys())}")
    return ROLES[name]


def get_werewolf_roles() -> list[Role]:
    """Get all roles on the werewolf team."""
    return [role for role in ROLES.values() if role.team == "werewolf"]


def get_village_roles() -> list[Role]:
    """Get all roles on the village team."""
    return [role for role in ROLES.values() if role.team == "village"]
