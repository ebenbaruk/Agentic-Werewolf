"""OpenRouter API client for LLM access."""

import os
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel


class Message(BaseModel):
    """A chat message."""
    role: str
    content: str


class OpenRouterClient:
    """Client for OpenRouter API (OpenAI-compatible)."""

    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the OpenRouter client.

        Args:
            api_key: OpenRouter API key. If not provided, reads from OPENROUTER_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenRouter API key required. Set OPENROUTER_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = AsyncOpenAI(
            base_url=self.OPENROUTER_BASE_URL,
            api_key=self.api_key,
        )

    async def chat(
        self,
        messages: list[Message],
        model: str = "anthropic/claude-sonnet-4",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Send a chat completion request.

        Args:
            messages: List of chat messages.
            model: Model identifier (e.g., "anthropic/claude-sonnet-4", "openai/gpt-4o").
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens in response.

        Returns:
            The assistant's response text.
        """
        response = await self.client.chat.completions.create(
            model=model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content or ""

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = "anthropic/claude-sonnet-4",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Generate a response with system and user prompts.

        Args:
            system_prompt: System instructions.
            user_prompt: User message.
            model: Model identifier.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens in response.

        Returns:
            The assistant's response text.
        """
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_prompt),
        ]
        return await self.chat(messages, model, temperature, max_tokens)
