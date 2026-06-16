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
    InteractionContext,  # re-export for convenience
    ModalContext,
    SelectContext,
    build_component_context,
)
from .router import ComponentRouter

__all__ = [
    "ButtonContext",
    "ComponentContext",
    "ComponentRouter",
    "InteractionContext",
    "ModalContext",
    "SelectContext",
    "build_component_context",
]
