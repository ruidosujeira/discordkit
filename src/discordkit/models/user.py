"""
discordkit.models.user
======================

Strongly typed User and Member models.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import ConfigDict, Field

from .base import DiscordModel


class User(DiscordModel):
    """Represents a Discord user (not necessarily a guild member)."""

    username: str
    discriminator: str = "0"  # "0" for new usernames
    global_name: str | None = Field(default=None, alias="global_name")
    avatar: str | None = None
    bot: bool = False
    system: bool = False
    verified: bool | None = None
    email: str | None = Field(default=None, repr=False)
    flags: int = 0
    premium_type: int | None = None
    public_flags: int | None = None

    @property
    def display_name(self) -> str:
        """Best human-friendly name available."""
        return self.global_name or self.username

    @property
    def mention(self) -> str:
        return f"<@{self.id}>"

    def __str__(self) -> str:
        return self.display_name

    model_config: ClassVar[ConfigDict] = {
        **DiscordModel.model_config,
        "frozen": True,
    }


class Member(DiscordModel):
    """Represents a guild member (user + guild-specific data)."""

    user: User | None = None
    nick: str | None = None
    avatar: str | None = None
    roles: list[int] = Field(default_factory=list)
    joined_at: str | None = None  # ISO string for now (can be parsed later)
    premium_since: str | None = None
    deaf: bool = False
    mute: bool = False
    pending: bool = False
    permissions: str | None = None  # Permission bit string

    @property
    def display_name(self) -> str:
        if self.nick:
            return self.nick
        if self.user:
            return self.user.display_name
        return "Unknown Member"

    @property
    def mention(self) -> str:
        if self.user and self.user.id:
            return f"<@{self.user.id}>"
        return "<@0>"

    def __str__(self) -> str:
        return self.display_name


__all__ = ["Member", "User"]
