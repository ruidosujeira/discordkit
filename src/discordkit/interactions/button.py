"""
discordkit.interactions.button
==============================

Declarative button component with strong typing.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from ..types import ButtonStyle, ComponentType


@dataclass(slots=True)
class Button:
    """A button component you can attach to messages.

    Example:
        button = Button(
            label="Click me",
            style=ButtonStyle.PRIMARY,
            custom_id="my_button_1",
            on_click=my_handler,
        )

        await ctx.respond("Press the button!", components=[button.to_dict()])
    """

    label: str
    style: ButtonStyle = ButtonStyle.PRIMARY
    custom_id: str | None = None
    url: str | None = None
    emoji: str | None = None
    disabled: bool = False

    # Optional direct callback (advanced usage)
    on_click: Callable[[Any], Awaitable[None]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": ComponentType.BUTTON,
            "style": int(self.style),
            "label": self.label,
            "disabled": self.disabled,
        }
        if self.custom_id:
            data["custom_id"] = self.custom_id
        if self.url:
            data["url"] = self.url
            data["style"] = int(ButtonStyle.LINK)
        if self.emoji:
            data["emoji"] = {"name": self.emoji}
        return data

    def __repr__(self) -> str:
        return f"<Button label={self.label!r} style={self.style.name}>"


__all__ = ["Button"]
