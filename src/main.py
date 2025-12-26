"""Main entry point for Agentic Werewolf."""

import asyncio
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich import print as rprint

from .engine.game import Game, GameConfig
from .llm.openrouter import OpenRouterClient
from .communication.markdown_logger import MarkdownLogger


# Load environment variables
load_dotenv()

console = Console()


def load_config(config_path: str = "config/game.yaml") -> dict:
    """Load game configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        console.print(f"[red]Config file not found: {config_path}[/red]")
        sys.exit(1)

    with open(path) as f:
        return yaml.safe_load(f)


def display_welcome():
    """Display welcome message."""
    console.print(Panel.fit(
        "[bold red]WEREWOLF[/bold red]\n"
        "[dim]An AI-powered game of deception[/dim]",
        border_style="red",
    ))
    console.print()


def display_players(players: list[dict], roles: dict[str, str]):
    """Display player information."""
    table = Table(title="Players", show_header=True, header_style="bold magenta")
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Role", style="red")

    for player in players:
        role = roles.get(player["name"], "?")
        # Hide role for suspense (or show it for debugging)
        table.add_row(
            player["name"],
            player["model"],
            f"[dim]{role}[/dim]",  # Dimmed to indicate it's secret
        )

    console.print(table)
    console.print()


async def run_game_with_progress(game: Game) -> str:
    """Run the game with progress display."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Game in progress...", total=None)

        # Patch the game to show progress
        original_run_night = game.run_night_phase
        original_run_discussion = game.run_day_discussion
        original_run_vote = game.run_day_vote

        async def wrapped_night():
            progress.update(task, description=f"[red]Night {game.phase_manager.state.round_number}...[/red]")
            return await original_run_night()

        async def wrapped_discussion():
            round_num = game.phase_manager.state.discussion_round
            progress.update(
                task,
                description=f"[yellow]Day {game.phase_manager.state.round_number} - Discussion round {round_num}...[/yellow]"
            )
            return await original_run_discussion()

        async def wrapped_vote():
            progress.update(
                task,
                description=f"[blue]Day {game.phase_manager.state.round_number} - Voting...[/blue]"
            )
            return await original_run_vote()

        game.run_night_phase = wrapped_night
        game.run_day_discussion = wrapped_discussion
        game.run_day_vote = wrapped_vote

        winner = await game.run()

    return winner


def display_results(game: Game, winner: str):
    """Display game results."""
    console.print()

    # Winner announcement
    if winner == "village":
        console.print(Panel(
            "[bold green]THE VILLAGE WINS![/bold green]\n"
            "All werewolves have been eliminated.",
            border_style="green",
        ))
    else:
        console.print(Panel(
            "[bold red]THE WEREWOLVES WIN![/bold red]\n"
            "The werewolves have taken over the village.",
            border_style="red",
        ))

    console.print()

    # Final standings
    table = Table(title="Final Standings", show_header=True, header_style="bold")
    table.add_column("Player", style="cyan")
    table.add_column("Role", style="magenta")
    table.add_column("Team", style="blue")
    table.add_column("Status", style="green")

    for player in game.players:
        status = "[green]Survived[/green]" if player.alive else "[red]Dead[/red]"
        team_color = "red" if player.role.team == "werewolf" else "green"
        table.add_row(
            player.name,
            player.role.name,
            f"[{team_color}]{player.role.team}[/{team_color}]",
            status,
        )

    console.print(table)
    console.print()

    # Log location
    if game.logger.game_dir:
        console.print(f"[dim]Game log saved to: {game.logger.game_dir}[/dim]")


async def main():
    """Main entry point."""
    display_welcome()

    # Check for API key
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        console.print("[red]Error: OPENROUTER_API_KEY not set![/red]")
        console.print("Please set your OpenRouter API key in .env file or environment variable.")
        sys.exit(1)

    # Load configuration
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/game.yaml"
    console.print(f"[dim]Loading config from: {config_path}[/dim]")
    config_data = load_config(config_path)

    # Create game config
    game_config = GameConfig(
        player_count=config_data["game"]["player_count"],
        discussion_rounds=config_data["game"]["discussion_rounds"],
        role_distribution=config_data["roles"],
    )

    # Initialize clients
    llm_client = OpenRouterClient(api_key=api_key)
    logger = MarkdownLogger(base_dir="games")

    # Create game
    game = Game(config=game_config, llm_client=llm_client, logger=logger)

    # Set up players
    player_configs = config_data["players"][:game_config.player_count]
    console.print(f"[cyan]Setting up {len(player_configs)} players...[/cyan]")

    game.setup_players(player_configs)

    # Display players (with hidden roles)
    display_players(
        [{"name": p.name, "model": p.model} for p in game.players],
        {p.name: p.role.name for p in game.players},
    )

    # Confirm start
    console.print("[yellow]Press Enter to start the game...[/yellow]")
    input()

    # Run game
    console.print("[bold]Game starting![/bold]")
    console.print()

    try:
        winner = await run_game_with_progress(game)
        display_results(game, winner)
    except KeyboardInterrupt:
        console.print("\n[yellow]Game interrupted by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]Error during game: {e}[/red]")
        raise


def run():
    """Entry point for the CLI."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
