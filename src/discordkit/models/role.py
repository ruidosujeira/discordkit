"""
discordkit.models.role
======================

Minimal Role model for use in command options (and future guild features).
"""

from __future__ import annotations

from typing import Any, ClassVar

from pydantic import ConfigDict

from .base import DiscordModel


class Role(DiscordModel):
    """Represents a Discord role."""

    name: str
    color: int = 0
    hoist: bool = False
    position: int = 0
    permissions: str = "0"
    managed: bool = False
    mentionable: bool = False
    tags: dict[str, Any] | None = None
    flags: int = 0

    @property
    def mention(self) -> str:
        if self.id:
            return f"<@&{self.id}>"
        return "@deleted-role"

    def __str__(self) -> str:
        return self.name

    model_config: ClassVar[ConfigDict] = {
        **DiscordModel.model_config,
        "frozen": True,
    }


__all__ = ["Role"]
