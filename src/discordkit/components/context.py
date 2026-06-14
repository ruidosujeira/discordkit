"""
discordkit.components.context
=============================

Specialized context objects for interactive components (buttons, selects, modals).

All inherit from the core InteractionContext, so they share the exact same
beautiful response API: respond, defer, followup, edit_response, edit_message.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..core.context import InteractionContext
from ..models import Guild, Member, Message, User
from ..types import ComponentType, InteractionType


@dataclass(slots=True)
class ComponentContext(InteractionContext):
    """Base context for MESSAGE_COMPONENT interactions (buttons and selects).

    Attributes:
        custom_id: The custom_id that was attached to the component.
        component_type: The type of component (BUTTON, STRING_SELECT, etc.).
        values: List of selected values (only for select menus).
        raw_interaction: The full raw interaction payload from Discord (for advanced use).
    """

    custom_id: str = ""
    component_type: int = 0
    values: list[str] = field(default_factory=list)
    raw_interaction: dict[str, Any] = field(default_factory=dict)

    @property
    def is_button(self) -> bool:
        return self.component_type == ComponentType.BUTTON

    @property
    def is_select(self) -> bool:
        return self.component_type in (
            ComponentType.STRING_SELECT,
            ComponentType.USER_SELECT,
            ComponentType.ROLE_SELECT,
            ComponentType.MENTIONABLE_SELECT,
            ComponentType.CHANNEL_SELECT,
        )

    def __repr__(self) -> str:
        kind = "Button" if self.is_button else "Select"
        return f"{kind}Context(custom_id={self.custom_id!r}, user={self.user})"


@dataclass(slots=True)
class ButtonContext(ComponentContext):
    """Context specifically for button interactions.

    You can also just use ComponentContext — this is provided for clarity and
    possible future button-specific helpers.
    """

    def __repr__(self) -> str:
        return f"ButtonContext(custom_id={self.custom_id!r}, user={self.user})"


@dataclass(slots=True)
class SelectContext(ComponentContext):
    """Context for any select menu interaction (string, user, role, etc.)."""

    def __repr__(self) -> str:
        return (
            f"SelectContext(custom_id={self.custom_id!r}, "
            f"values={self.values}, user={self.user})"
        )


@dataclass(slots=True)
class ModalContext(InteractionContext):
    """Context passed to modal submit handlers.

    Access submitted values via:
        - ctx.get_value("field_custom_id")
        - ctx.fields["field_custom_id"]
    """

    custom_id: str = ""
    fields: dict[str, str] = field(default_factory=dict)
    raw_interaction: dict[str, Any] = field(default_factory=dict)

    def get_value(self, field_custom_id: str, default: str | None = None) -> str | None:
        """Convenience method to get a text input value from the modal."""
        return self.fields.get(field_custom_id, default)

    def __repr__(self) -> str:
        return f"ModalContext(custom_id={self.custom_id!r}, fields={list(self.fields.keys())})"


def build_component_context(
    client: "Client",
    interaction: dict[str, Any],
) -> ComponentContext | ModalContext:
    """Factory that builds the right context object from a raw INTERACTION_CREATE payload.

    This is internal but can be useful for testing or advanced dispatch.
    """
    data = interaction.get("data", {})
    custom_id = data.get("custom_id", "")
    interaction_id = interaction.get("id")
    token = interaction.get("token")

    # Resolve user / member
    user_data = interaction.get("user") or interaction.get("member", {}).get("user")
    user = User.model_validate(user_data) if user_data else None

    member_data = interaction.get("member")
    member = Member.model_validate(member_data) if member_data else None

    guild_id = interaction.get("guild_id")
    # We don't fetch full guild here for performance; user can do it if needed

    channel_id = interaction.get("channel_id")
    message_data = interaction.get("message")
    message = Message.model_validate(message_data) if message_data else None

    interaction_type = interaction.get("type")

    if interaction_type == InteractionType.MODAL_SUBMIT:
        # Parse modal fields
        fields: dict[str, str] = {}
        for row in data.get("components", []):
            for comp in row.get("components", []):
                if comp.get("type") == ComponentType.TEXT_INPUT:
                    fields[comp.get("custom_id", "")] = comp.get("value", "")

        return ModalContext(
            client=client,
            interaction_id=int(interaction_id) if interaction_id else None,
            interaction_token=token,
            user=user,
            member=member,
            guild=None,  # can be enriched later
            channel_id=int(channel_id) if channel_id else None,
            message=message,
            custom_id=custom_id,
            fields=fields,
            raw_interaction=interaction,
        )

    # MESSAGE_COMPONENT
    component_type = data.get("component_type", 0)
    values = data.get("values", []) or []

    base = ComponentContext(
        client=client,
        interaction_id=int(interaction_id) if interaction_id else None,
        interaction_token=token,
        user=user,
        member=member,
        guild=None,
        channel_id=int(channel_id) if channel_id else None,
        message=message,
        custom_id=custom_id,
        component_type=component_type,
        values=values,
        raw_interaction=interaction,
    )

    if component_type == ComponentType.BUTTON:
        return ButtonContext(**base.__dict__)  # type: ignore[arg-type]
    if component_type in (
        ComponentType.STRING_SELECT,
        ComponentType.USER_SELECT,
        ComponentType.ROLE_SELECT,
        ComponentType.MENTIONABLE_SELECT,
        ComponentType.CHANNEL_SELECT,
    ):
        return SelectContext(**base.__dict__)  # type: ignore[arg-type]

    return base


__all__ = [
    "InteractionContext",
    "ComponentContext",
    "ButtonContext",
    "SelectContext",
    "ModalContext",
    "build_component_context",
]
