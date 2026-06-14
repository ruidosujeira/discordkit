"""
discordkit.components
=====================

Runtime component and modal registration + context objects.

This is the recommended way to handle buttons, selects and modals with callbacks.

See `ComponentRouter`, `ButtonContext` / `SelectContext`, `ModalContext`.
"""

from __future__ import annotations

from .context import (
    ButtonContext,
    ComponentContext,
    ModalContext,
    SelectContext,
    build_component_context,
    InteractionContext,  # re-export for convenience
)
from .router import ComponentRouter

__all__ = [
    "ComponentRouter",
    "ComponentContext",
    "ButtonContext",
    "SelectContext",
    "ModalContext",
    "build_component_context",
    "InteractionContext",
]
