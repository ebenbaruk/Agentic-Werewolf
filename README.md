# Agentic Werewolf

A multi-agent simulation where large language models play the classic social deduction game Werewolf against each other.

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/LLM-OpenRouter-orange.svg" alt="OpenRouter">
</p>

## Overview

Instead of humans, AI language models play Werewolf autonomously. Each AI acts as an independent player with a hidden role, communicating through natural language to deceive, deduce, and vote—just like humans would.

The system uses a minimal game engine that only enforces rules. All intelligence, strategy, and social behavior emerge entirely from the language models.

## Key Features

- **Multi-Model Support** — Mix different LLMs in the same game (GPT, Claude, Gemini, Grok, Mistral, Llama)
- **Minimal Engine** — Rules-only enforcement; all strategy comes from the AI
- **Natural Conversations** — Players discuss, accuse, defend, and lie using language
- **Complete Logging** — Every conversation saved to Markdown for analysis
- **Extended Roles** — Villager, Werewolf, Seer, Doctor, Hunter, Witch
- **Personality System** — Randomized traits create diverse player behaviors

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                        GAME ENGINE                          │
│  • Assigns roles            • Manages phases                │
│  • Enforces rules           • Determines winners            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      AI PLAYERS (LLMs)                      │
│                                                             │
│   Claude ←→ GPT ←→ Gemini ←→ Grok ←→ Mistral ←→ Llama     │
│                                                             │
│  • Receive limited information (role, visible messages)     │
│  • Reason and strategize independently                      │
│  • Communicate through natural language                     │
│  • Vote based on their own judgment                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     MARKDOWN LOGS                           │
│  • Public discussions       • Werewolf night chat           │
│  • Voting records           • Game state timeline           │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Clone the repository
git clone https://github.com/ebenbaruk/Agentic-Werewolf.git
cd Agentic-Werewolf

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure API key
cp .env.example .env
# Edit .env and add your OpenRouter API key
```

Get your OpenRouter API key at [openrouter.ai/keys](https://openrouter.ai/keys)

## Usage

```bash
# Run a game with default configuration
python -m src.main

# Run with custom config
python -m src.main config/custom_game.yaml
```

## Configuration

Edit `config/game.yaml` to customize your game:

```yaml
game:
  player_count: 6
  discussion_rounds: 3
  voting: public

roles:
  Werewolf: 2
  Seer: 1
  Doctor: 1
  Villager: 2

players:
  - name: Claude
    model: anthropic/claude-sonnet-4.5
  - name: GPT
    model: openai/gpt-5.2
  - name: Gemini
    model: google/gemini-3-flash-preview
  - name: Grok
    model: x-ai/grok-4.1-fast
  - name: Mistral
    model: mistralai/mistral-large-2512
  - name: Llama
    model: meta-llama/llama-4-maverick
```

## Game Rules

### Teams
| Team | Win Condition |
|------|---------------|
| Village | Eliminate all werewolves |
| Werewolf | Equal or outnumber villagers |

### Roles

| Role | Team | Ability |
|------|------|---------|
| Villager | Village | No special ability — use deduction to find werewolves |
| Werewolf | Werewolf | Kill one villager each night (coordinated with pack) |
| Seer | Village | Investigate one player each night to learn their alignment |
| Doctor | Village | Protect one player from death each night |
| Hunter | Village | When killed, take one player down with you |
| Witch | Village | One-time healing potion and one-time poison potion |

### Game Flow

```
┌─────────┐     ┌──────────────┐     ┌──────────┐     ┌─────────┐
│  NIGHT  │ ──▶ │  DAY DISCUSS │ ──▶ │ DAY VOTE │ ──▶ │  NIGHT  │
└─────────┘     └──────────────┘     └──────────┘     └─────────┘
     │                                      │
     │ • Werewolves kill                    │ • Players vote to eliminate
     │ • Seer investigates                  │ • Majority wins
     │ • Doctor protects                    │ • Ties = no elimination
     │ • Witch uses potions                 │
     ▼                                      ▼
   Deaths                              Check winner
  announced                            ───▶ Loop or End
```

## Project Structure

```
Agentic-Werewolf/
├── src/
│   ├── main.py                 # CLI entry point
│   ├── engine/
│   │   ├── game.py             # Game state machine
│   │   ├── phases.py           # Phase transitions
│   │   └── roles.py            # Role definitions
│   ├── agents/
│   │   ├── player.py           # AI player agent
│   │   ├── prompts.py          # System prompts
│   │   └── memory.py           # Context management
│   ├── communication/
│   │   ├── channels.py         # Message routing
│   │   └── markdown_logger.py  # Conversation logging
│   └── llm/
│       └── openrouter.py       # OpenRouter API client
├── config/
│   └── game.yaml               # Game configuration
├── games/                      # Generated game logs
├── requirements.txt
└── pyproject.toml
```

## Game Logs

After each game, detailed logs are saved to `games/`:

```
games/game_2024-12-26_143052/
├── game_state.md           # Complete game timeline
├── day_1_discussion.md     # Public conversations
├── night_1_werewolves.md   # Secret werewolf chat
├── night_1_actions.md      # All night actions (for review)
└── votes/
    └── day_1_vote.md       # Voting breakdown
```

## Supported Models

Any model available on [OpenRouter](https://openrouter.ai/models) can be used:

| Provider | Example Models |
|----------|----------------|
| Anthropic | `anthropic/claude-sonnet-4.5`, `anthropic/claude-opus-4` |
| OpenAI | `openai/gpt-5.2`, `openai/gpt-4o` |
| Google | `google/gemini-3-flash-preview`, `google/gemini-2.5-pro` |
| xAI | `x-ai/grok-4.1-fast` |
| Mistral | `mistralai/mistral-large-2512` |
| Meta | `meta-llama/llama-4-maverick` |

## Why This Project?

This simulation serves as a testbed for studying:

- **Multi-agent communication** — How LLMs interact and coordinate
- **Emergent deception** — Whether AI can learn to lie convincingly
- **Theory of mind** — Can models reason about others' beliefs?
- **Strategic behavior** — Decision-making under uncertainty
- **Model comparison** — How different LLMs approach the same social game


---

<p align="center">
  <i>Watch AI agents lie, deceive, and vote each other out.</i>
</p>
