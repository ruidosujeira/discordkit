"""
discordkit.interactions.modal
=============================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Modal:
    """Modal (form) definition.

    Example:
        modal = Modal(title="Feedback", custom_id="feedback_modal")
        modal.add_text_input(label="Your thoughts", custom_id="thoughts", required=True)

        await ctx.respond_modal(modal)   # (to be implemented)
    """

    title: str
    custom_id: str
    components: list[dict[str, Any]] = field(default_factory=list)

    def add_text_input(
        self,
        *,
        label: str,
        custom_id: str,
        style: int = 1,  # 1 = short, 2 = paragraph
        placeholder: str | None = None,
        required: bool = True,
        min_length: int | None = None,
        max_length: int | None = None,
    ) -> None:
        row = {
            "type": 1,  # ACTION_ROW
            "components": [
                {
                    "type": 4,  # TEXT_INPUT
                    "custom_id": custom_id,
                    "label": label,
                    "style": style,
                    "required": required,
                    "placeholder": placeholder,
                    "min_length": min_length,
                    "max_length": max_length,
                }
            ],
        }
        self.components.append(row)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "custom_id": self.custom_id,
            "components": self.components,
        }


__all__ = ["Modal"]
