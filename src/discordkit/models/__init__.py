"""
discordkit.models
=================

Pydantic v2 models for all major Discord objects.

All models are:
- Strongly validated
- Frozen / immutable where appropriate
- Designed to be pleasant to work with in commands and events
"""

from __future__ import annotations

from .base import DiscordModel, TimestampedModel
from .guild import Channel, Guild
from .message import Attachment, Message
from .role import Role
from .user import Member, User

__all__ = [
    "DiscordModel",
    "TimestampedModel",
    "User",
    "Member",
    "Guild",
    "Channel",
    "Message",
    "Attachment",
    "Role",
]
