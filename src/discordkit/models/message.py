"""
discordkit.models.message
=========================
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import DiscordModel
from .user import Member, User


class Attachment(DiscordModel):
    filename: str
    size: int
    url: str
    proxy_url: str
    height: int | None = None
    width: int | None = None
    content_type: str | None = None
    ephemeral: bool = False


class Message(DiscordModel):
    """Represents a message received from Discord."""

    channel_id: int = Field(alias="channel_id")
    author: User
    content: str = ""
    timestamp: str | None = None
    edited_timestamp: str | None = None
    tts: bool = False
    mention_everyone: bool = False
    mentions: list[User] = Field(default_factory=list)
    mention_roles: list[int] = Field(default_factory=list)
    mention_channels: list[dict[str, Any]] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    embeds: list[dict[str, Any]] = Field(default_factory=list)
    reactions: list[dict[str, Any]] = Field(default_factory=list)
    pinned: bool = False
    webhook_id: int | None = None
    type: int = 0
    flags: int = 0
    referenced_message: Message | None = None
    interaction: dict[str, Any] | None = None
    thread: dict[str, Any] | None = None
    components: list[dict[str, Any]] = Field(default_factory=list)
    sticker_items: list[dict[str, Any]] = Field(default_factory=list)
    position: int | None = None
    role_subscription_data: dict[str, Any] | None = None
    guild_id: int | None = Field(default=None, alias="guild_id")

    # Sometimes included in certain events
    member: Member | None = None

    @property
    def jump_url(self) -> str:
        if self.guild_id and self.channel_id and self.id:
            return f"https://discord.com/channels/{self.guild_id}/{self.channel_id}/{self.id}"
        if self.channel_id and self.id:
            return f"https://discord.com/channels/@me/{self.channel_id}/{self.id}"
        return ""

    def __str__(self) -> str:
        return self.content or "[no content]"


__all__ = ["Attachment", "Message"]
