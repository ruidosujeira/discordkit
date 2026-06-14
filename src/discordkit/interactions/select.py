"""
discordkit.interactions.select
==============================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..types import ComponentType


@dataclass(slots=True)
class SelectMenu:
    """String select (dropdown) component."""

    custom_id: str
    placeholder: str | None = None
    min_values: int = 1
    max_values: int = 1
    disabled: bool = False
    options: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "type": ComponentType.STRING_SELECT,
            "custom_id": self.custom_id,
            "min_values": self.min_values,
            "max_values": self.max_values,
            "disabled": self.disabled,
        }
        if self.placeholder:
            data["placeholder"] = self.placeholder
        if self.options:
            data["options"] = self.options
        return data


__all__ = ["SelectMenu"]
