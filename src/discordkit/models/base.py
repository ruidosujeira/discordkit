"""
discordkit.models.base
======================

Base Pydantic model for all Discord API objects.

We use Pydantic v2 with strict configuration:
- extra = "ignore" (Discord often adds new fields)
- populate_by_name (support both snake_case and Discord's camelCase where useful)
- frozen where it makes sense for value objects
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DiscordModel(BaseModel):
    """Base class for all Discord data models.

    Provides consistent behavior across User, Guild, Message, etc.
    """

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        from_attributes=True,
        validate_default=True,
        str_strip_whitespace=True,
        # Use modern Pydantic v2 style
        revalidate_instances="always",
    )

    # Common helper: many Discord objects have an id
    id: int | None = Field(default=None, description="Discord snowflake ID")


class TimestampedModel(DiscordModel):
    """Mixin for objects that carry created_at / updated_at style fields."""

    created_at: datetime | None = None


__all__ = ["DiscordModel", "TimestampedModel"]
