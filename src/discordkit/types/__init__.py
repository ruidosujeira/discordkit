"""
discordkit.types
================

Strongly typed primitives, enums, flags and constants used across the framework.

All public types here should be safe for end-users to import and use in annotations.
"""

from __future__ import annotations

from enum import IntEnum, IntFlag
from typing import Literal

# =============================================================================
# Gateway Intents (bitfield)
# =============================================================================


class Intents(IntFlag):
    """Discord Gateway Intents.

    Strongly typed IntFlag so you can combine them naturally:

        intents = Intents.GUILDS | Intents.GUILD_MESSAGES | Intents.MESSAGE_CONTENT
    """

    NONE = 0

    GUILDS = 1 << 0
    GUILD_MEMBERS = 1 << 1
    GUILD_BANS = 1 << 2
    GUILD_EMOJIS_AND_STICKERS = 1 << 3
    GUILD_INTEGRATIONS = 1 << 4
    GUILD_WEBHOOKS = 1 << 5
    GUILD_INVITES = 1 << 6
    GUILD_VOICE_STATES = 1 << 7
    GUILD_PRESENCES = 1 << 8
    GUILD_MESSAGES = 1 << 9
    GUILD_MESSAGE_REACTIONS = 1 << 10
    GUILD_MESSAGE_TYPING = 1 << 11
    DIRECT_MESSAGES = 1 << 12
    DIRECT_MESSAGE_REACTIONS = 1 << 13
    DIRECT_MESSAGE_TYPING = 1 << 14
    MESSAGE_CONTENT = 1 << 15
    GUILD_SCHEDULED_EVENTS = 1 << 16
    AUTO_MODERATION_CONFIGURATION = 1 << 20
    AUTO_MODERATION_EXECUTION = 1 << 21

    # Common useful presets
    DEFAULT = GUILDS | GUILD_MESSAGES | GUILD_MESSAGE_REACTIONS | DIRECT_MESSAGES
    ALL = (
        GUILDS
        | GUILD_MEMBERS
        | GUILD_BANS
        | GUILD_EMOJIS_AND_STICKERS
        | GUILD_INTEGRATIONS
        | GUILD_WEBHOOKS
        | GUILD_INVITES
        | GUILD_VOICE_STATES
        | GUILD_PRESENCES
        | GUILD_MESSAGES
        | GUILD_MESSAGE_REACTIONS
        | GUILD_MESSAGE_TYPING
        | DIRECT_MESSAGES
        | DIRECT_MESSAGE_REACTIONS
        | DIRECT_MESSAGE_TYPING
        | MESSAGE_CONTENT
        | GUILD_SCHEDULED_EVENTS
        | AUTO_MODERATION_CONFIGURATION
        | AUTO_MODERATION_EXECUTION
    )


# =============================================================================
# Permissions (bitfield)
# =============================================================================


class Permissions(IntFlag):
    """Discord permission flags (bitfield)."""

    NONE = 0

    CREATE_INSTANT_INVITE = 1 << 0
    KICK_MEMBERS = 1 << 1
    BAN_MEMBERS = 1 << 2
    ADMINISTRATOR = 1 << 3
    MANAGE_CHANNELS = 1 << 4
    MANAGE_GUILD = 1 << 5
    ADD_REACTIONS = 1 << 6
    VIEW_AUDIT_LOG = 1 << 7
    PRIORITY_SPEAKER = 1 << 8
    STREAM = 1 << 9
    VIEW_CHANNEL = 1 << 10
    SEND_MESSAGES = 1 << 11
    SEND_TTS_MESSAGES = 1 << 12
    MANAGE_MESSAGES = 1 << 13
    EMBED_LINKS = 1 << 14
    ATTACH_FILES = 1 << 15
    READ_MESSAGE_HISTORY = 1 << 16
    MENTION_EVERYONE = 1 << 17
    USE_EXTERNAL_EMOJIS = 1 << 18
    VIEW_GUILD_INSIGHTS = 1 << 19
    CONNECT = 1 << 20
    SPEAK = 1 << 21
    MUTE_MEMBERS = 1 << 22
    DEAFEN_MEMBERS = 1 << 23
    MOVE_MEMBERS = 1 << 24
    USE_VAD = 1 << 25
    CHANGE_NICKNAME = 1 << 26
    MANAGE_NICKNAMES = 1 << 27
    MANAGE_ROLES = 1 << 28
    MANAGE_WEBHOOKS = 1 << 29
    MANAGE_GUILD_EXPRESSIONS = 1 << 30
    USE_APPLICATION_COMMANDS = 1 << 31
    REQUEST_TO_SPEAK = 1 << 32
    MANAGE_EVENTS = 1 << 33
    MANAGE_THREADS = 1 << 34
    CREATE_PUBLIC_THREADS = 1 << 35
    CREATE_PRIVATE_THREADS = 1 << 36
    USE_EXTERNAL_STICKERS = 1 << 37
    SEND_MESSAGES_IN_THREADS = 1 << 38
    USE_EMBEDDED_ACTIVITIES = 1 << 39
    MODERATE_MEMBERS = 1 << 40
    VIEW_CREATOR_MONETIZATION_ANALYTICS = 1 << 41
    USE_SOUNDBOARD = 1 << 42
    USE_EXTERNAL_SOUNDS = 1 << 45
    SEND_VOICE_MESSAGES = 1 << 46

    # Useful combined sets
    ALL = (1 << 47) - 1  # All current permissions


# =============================================================================
# Application Command Types
# =============================================================================


class ApplicationCommandType(IntEnum):
    """Types of application commands (slash, user, message)."""

    CHAT_INPUT = 1
    USER = 2
    MESSAGE = 3


class ApplicationCommandOptionType(IntEnum):
    """Option types for slash command parameters."""

    SUB_COMMAND = 1
    SUB_COMMAND_GROUP = 2
    STRING = 3
    INTEGER = 4
    BOOLEAN = 5
    USER = 6
    CHANNEL = 7
    ROLE = 8
    MENTIONABLE = 9
    NUMBER = 10
    ATTACHMENT = 11


# =============================================================================
# Component Types (for buttons, modals, etc.)
# =============================================================================


class ComponentType(IntEnum):
    """Message component types."""

    ACTION_ROW = 1
    BUTTON = 2
    STRING_SELECT = 3
    TEXT_INPUT = 4
    USER_SELECT = 5
    ROLE_SELECT = 6
    MENTIONABLE_SELECT = 7
    CHANNEL_SELECT = 8


class ButtonStyle(IntEnum):
    """Styles for button components."""

    PRIMARY = 1
    SECONDARY = 2
    SUCCESS = 3
    DANGER = 4
    LINK = 5


# =============================================================================
# Interaction Types
# =============================================================================


class InteractionType(IntEnum):
    """Types of incoming interactions from Discord."""

    PING = 1
    APPLICATION_COMMAND = 2
    MESSAGE_COMPONENT = 3
    APPLICATION_COMMAND_AUTOCOMPLETE = 4
    MODAL_SUBMIT = 5


class InteractionResponseType(IntEnum):
    """Response types you can send back to an interaction."""

    PONG = 1
    CHANNEL_MESSAGE_WITH_SOURCE = 4
    DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE = 5
    DEFERRED_UPDATE_MESSAGE = 6
    UPDATE_MESSAGE = 7
    APPLICATION_COMMAND_AUTOCOMPLETE_RESULT = 8
    MODAL = 9


# =============================================================================
# Literals for common values
# =============================================================================

ChannelType = Literal[0, 1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15]
MessageType = Literal[
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
    11,
    12,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
]

__all__ = [
    "ApplicationCommandOptionType",
    "ApplicationCommandType",
    "ButtonStyle",
    "ChannelType",
    "ComponentType",
    "Intents",
    "InteractionResponseType",
    "InteractionType",
    "MessageType",
    "Permissions",
]
