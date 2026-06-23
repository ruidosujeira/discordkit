"""
discordkit.core.context
=======================

Context objects passed to command handlers and interaction callbacks.

These are the main objects users interact with inside their code.
They are designed to be intuitive and powerful while remaining explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..models import Guild, Member, Message, User
from ..types import InteractionResponseType

if TYPE_CHECKING:
    from .client import Client
    from .http import DiscordHTTPClient


# =============================================================================
# Base Interaction Context (shared by slash commands, buttons, modals, selects)
# =============================================================================


@dataclass(slots=True)
class InteractionContext:
    """Base class containing all common interaction response helpers.

    Both CommandContext (for slash commands) and the various component contexts
    inherit from this so the DX for .respond(), .defer(), .followup() etc. is
    identical everywhere.
    """

    client: Client
    interaction_id: int | None = None
    interaction_token: str | None = None
    user: User | None = None
    member: Member | None = None
    guild: Guild | None = None
    channel_id: int | None = None
    message: Message | None = None

    # Internal
    _responded: bool = field(default=False, init=False, repr=False)
    _deferred: bool = field(default=False, init=False, repr=False)

    @property
    def http(self) -> DiscordHTTPClient:
        return self.client.http

    @property
    def is_interaction(self) -> bool:
        return self.interaction_id is not None

    async def respond(
        self,
        content: str | None = None,
        *,
        embed: dict[str, Any] | None = None,
        embeds: list[dict[str, Any]] | None = None,
        ephemeral: bool = False,
        components: list[dict[str, Any]] | None = None,
    ) -> None:
        """Send a response to the interaction (or regular message for non-interactions)."""
        if self.is_interaction and not self._responded:
            payload: dict[str, Any] = {
                "type": InteractionResponseType.CHANNEL_MESSAGE_WITH_SOURCE,
                "data": {
                    "content": content,
                    "embeds": [embed] if embed else (embeds or []),
                    "flags": 64 if ephemeral else 0,
                    "components": components or [],
                },
            }
            await self.http.create_interaction_response(
                self.interaction_id,  # type: ignore[arg-type]
                self.interaction_token,  # type: ignore[arg-type]
                payload=payload,
            )
            self._responded = True
        else:
            if self.channel_id:
                body: dict[str, Any] = {"content": content or ""}
                if embed:
                    body["embeds"] = [embed]
                if embeds:
                    body["embeds"] = embeds
                if components:
                    body["components"] = components
                await self.http.request(
                    "POST",
                    f"/channels/{self.channel_id}/messages",
                    json=body,
                )

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        """Acknowledge the interaction. Use thinking=True for a visible 'Bot is thinking...' state."""
        if not self.is_interaction or self._responded:
            return

        # For components we can also use DEFERRED_UPDATE_MESSAGE if we want to edit original
        response_type = InteractionResponseType.DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE
        payload = {
            "type": response_type,
            "data": {"flags": 64 if ephemeral else 0},
        }
        await self.http.create_interaction_response(
            self.interaction_id,  # type: ignore[arg-type]
            self.interaction_token,  # type: ignore[arg-type]
            payload=payload,
        )
        self._deferred = True
        self._responded = True

    async def followup(
        self,
        content: str | None = None,
        *,
        embed: dict[str, Any] | None = None,
        ephemeral: bool = False,
    ) -> dict[str, Any]:
        """Send a followup message (works after respond or defer)."""
        if not self.interaction_token:
            if self.channel_id:
                return await self.http.request(  # type: ignore[no-any-return]
                    "POST",
                    f"/channels/{self.channel_id}/messages",
                    json={"content": content},
                )
            return {}

        body: dict[str, Any] = {"content": content or ""}
        if embed:
            body["embeds"] = [embed]
        if ephemeral:
            body["flags"] = 64

        return await self.http.request(  # type: ignore[no-any-return]
            "POST",
            f"/webhooks/{self.client.application_id}/{self.interaction_token}",
            json=body,
        )

    async def edit_response(
        self,
        content: str | None = None,
        *,
        embed: dict[str, Any] | None = None,
        components: list[dict[str, Any]] | None = None,
    ) -> None:
        """Edit the original interaction response."""
        if not self.interaction_token:
            return
        body: dict[str, Any] = {}
        if content is not None:
            body["content"] = content
        if embed:
            body["embeds"] = [embed]
        if components is not None:
            body["components"] = components

        await self.http.request(
            "PATCH",
            f"/webhooks/{self.client.application_id}/{self.interaction_token}/messages/@original",
            json=body,
        )

    async def edit_message(
        self,
        *,
        content: str | None = None,
        embed: dict[str, Any] | None = None,
        components: list[dict[str, Any]] | None = None,
    ) -> None:
        """Edit the message that triggered this component interaction (useful for buttons)."""
        if not self.interaction_token or not self.message:
            # Fallback to regular message edit if we have channel + message id
            if self.channel_id and self.message and self.message.id:
                body: dict[str, Any] = {}
                if content is not None:
                    body["content"] = content
                if embed:
                    body["embeds"] = [embed]
                if components is not None:
                    body["components"] = components
                await self.http.request(
                    "PATCH",
                    f"/channels/{self.channel_id}/messages/{self.message.id}",
                    json=body,
                )
            return

        body: dict[str, Any] = {}  # type: ignore[no-redef]
        if content is not None:
            body["content"] = content
        if embed:
            body["embeds"] = [embed]
        if components is not None:
            body["components"] = components

        await self.http.request(
            "PATCH",
            f"/webhooks/{self.client.application_id}/{self.interaction_token}/messages/@original",
            json=body,
        )


@dataclass(slots=True)
class Context:
    """Generic context available in events and some commands.

    Contains references to the client, the raw event data, and
    convenience helpers.
    """

    client: Client
    event_name: str
    raw_data: dict[str, Any]

    @property
    def http(self) -> DiscordHTTPClient:
        return self.client.http

    async def fetch_channel(self, channel_id: int) -> dict[str, Any]:
        """Low-level channel fetch (expand with proper model later)."""
        result: Any = await self.http.request("GET", f"/channels/{channel_id}")
        return result  # type: ignore[no-any-return]


@dataclass(slots=True)
class CommandContext(InteractionContext):
    """Context passed to slash / prefix command handlers.

    Inherits all the powerful response methods from InteractionContext
    (.respond, .defer, .followup, .edit_response, .edit_message).
    """

    command_name: str = ""
    # Slash command options (parsed)
    options: dict[str, Any] = field(default_factory=dict)

    def __repr__(self) -> str:
        return (
            f"CommandContext(command={self.command_name!r}, user={self.user}, guild={self.guild})"
        )


@dataclass(slots=True)
class AutocompleteContext(InteractionContext):
    """Context passed to autocomplete handlers.

    The handler should return (or the framework will use) a list of suggestion dicts:
        [{"name": "Display name", "value": "actual_value"}, ...]
    """

    command_name: str = ""
    option_name: str = ""
    value: str = ""  # The current partial text the user has typed

    async def respond(self, choices: list[dict[str, Any]]) -> None:  # type: ignore[override]
        """Send autocomplete suggestions back to Discord.

        choices: list of {"name": str, "value": str | int | float}
        """
        if not self.interaction_id or not self.interaction_token:
            return

        payload = {
            "type": 8,  # APPLICATION_COMMAND_AUTOCOMPLETE_RESULT
            "data": {"choices": choices[:25]},  # Discord max 25
        }
        await self.http.create_interaction_response(
            self.interaction_id,
            self.interaction_token,
            payload=payload,
        )
        self._responded = True


__all__ = [
    "AutocompleteContext",
    "CommandContext",
    "Context",
    "InteractionContext",
]
