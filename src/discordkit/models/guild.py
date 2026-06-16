"""
discordkit.models.guild
=======================
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..types import Permissions
from .base import DiscordModel
from .user import Member, User


class Guild(DiscordModel):
    """Represents a Discord guild (server)."""

    name: str
    icon: str | None = None
    owner_id: int | None = Field(default=None, alias="owner_id")
    owner: bool | None = None
    permissions: Permissions | None = None
    region: str | None = None  # deprecated but still present sometimes
    afk_channel_id: int | None = Field(default=None, alias="afk_channel_id")
    afk_timeout: int | None = Field(default=None, alias="afk_timeout")
    verification_level: int | None = Field(default=None, alias="verification_level")
    default_message_notifications: int | None = None
    explicit_content_filter: int | None = None
    roles: list[dict[str, Any]] = Field(default_factory=list)
    emojis: list[dict[str, Any]] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    mfa_level: int | None = None
    system_channel_id: int | None = None
    rules_channel_id: int | None = None
    max_presences: int | None = None
    max_members: int | None = None
    description: str | None = None
    premium_tier: int | None = None
    premium_subscription_count: int | None = None
    preferred_locale: str | None = None
    nsfw_level: int | None = None

    # Populated in certain events
    members: list[Member] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)  # forward ref

    @property
    def icon_url(self) -> str | None:
        if not self.icon or not self.id:
            return None
        return f"https://cdn.discordapp.com/icons/{self.id}/{self.icon}.png"

    def __str__(self) -> str:
        return self.name


class Channel(DiscordModel):
    """Represents a channel (text, voice, thread, category, etc.)."""

    type: int
    guild_id: int | None = Field(default=None, alias="guild_id")
    position: int | None = None
    permission_overwrites: list[dict[str, Any]] = Field(default_factory=list)
    name: str | None = None
    topic: str | None = None
    nsfw: bool = False
    last_message_id: int | None = None
    bitrate: int | None = None
    user_limit: int | None = None
    rate_limit_per_user: int | None = None
    recipients: list[User] = Field(default_factory=list)
    icon: str | None = None
    owner_id: int | None = None
    parent_id: int | None = None
    last_pin_timestamp: str | None = None
    rtc_region: str | None = None
    video_quality_mode: int | None = None
    message_count: int | None = None
    member_count: int | None = None
    thread_metadata: dict[str, Any] | None = None

    @property
    def mention(self) -> str:
        if self.id:
            return f"<#{self.id}>"
        return "#unknown-channel"

    def __str__(self) -> str:
        return self.name or f"Channel({self.id})"


# Resolve forward references
Guild.model_rebuild()
Channel.model_rebuild()

__all__ = ["Channel", "Guild"]
