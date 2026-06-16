"""
discordkit.core.config
======================

Strongly typed configuration for the DiscordKit client using Pydantic v2.

This is the single source of truth for how your bot connects and behaves.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, SecretStr, field_validator

from ..types import Intents


class Config(BaseModel):
    """Bot configuration with strong validation.

    All sensitive values (like the token) are stored as `pydantic.SecretStr`
    so they are not accidentally logged or printed.

    Example:
        from discordkit import Config
        from discordkit.types import Intents

        config = Config(
            token="your_bot_token_here",
            intents=Intents.DEFAULT | Intents.GUILD_MEMBERS,
            prefix="!",
            debug=True,
        )
    """

    # Authentication
    token: SecretStr = Field(
        ...,
        description="Your Discord bot token (from the Developer Portal). Never commit this.",
        repr=False,
    )

    # Gateway
    intents: Intents = Field(
        default=Intents.DEFAULT,
        description="Gateway intents your bot requires. Use the Intents flag enum.",
    )

    # Development
    debug: bool = Field(
        default=False,
        description="Enable verbose logging and extra validation checks.",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level for the framework and your bot.",
    )

    # Command behavior
    prefix: str | None = Field(
        default=None,
        description="Legacy prefix for text commands (optional). Slash commands are preferred.",
        min_length=1,
        max_length=5,
    )

    # Connection / resilience
    shard_count: int | None = Field(
        default=None,
        description="Number of shards. Leave None for automatic (recommended).",
        ge=1,
    )
    max_retries: int = Field(
        default=5,
        description="Maximum reconnection attempts on gateway failure.",
        ge=1,
        le=20,
    )
    reconnect_base_delay: float = Field(
        default=1.0,
        description="Base delay (seconds) for exponential backoff reconnection.",
        gt=0,
    )

    # HTTP client tuning
    http_timeout: float = Field(
        default=15.0,
        description="Default timeout in seconds for REST requests.",
    )
    user_agent: str = Field(
        default="DiscordKit (https://github.com/discordkit/discordkit)",
        description="User-Agent sent with all HTTP requests.",
    )

    # Feature flags (for future extensibility without magic)
    enable_hot_reload: bool = Field(
        default=False,
        description="Whether the client should support hot reload (used by CLI run command).",
    )

    @field_validator("token")
    @classmethod
    def validate_token(cls, v: SecretStr) -> SecretStr:
        """Basic sanity check on the token format."""
        token = v.get_secret_value()
        if not token or len(token) < 30:
            raise ValueError("Discord bot token looks invalid (too short).")
        if "." not in token:
            raise ValueError("Discord bot token should contain dots (standard format).")
        return v

    model_config = {
        "frozen": True,  # Config is immutable after creation (safer)
        "extra": "forbid",  # Catch typos early
        "validate_assignment": True,
        "str_strip_whitespace": True,
    }


__all__ = ["Config"]
