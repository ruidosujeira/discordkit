"""
discordkit.components.router
============================

Clean, explicit component (button/select) and modal routing system.

Usage:

    bot = Client(config)

    @bot.component("confirm_delete")
    async def on_confirm(ctx: ButtonContext):
        await ctx.edit_message(content="Deleted!", components=[])

    @bot.component("language:")
    async def on_language(ctx: SelectContext):
        choice = ctx.values[0] if ctx.values else None
        await ctx.respond(f"You chose {choice}")

    @bot.modal("feedback_modal")
    async def on_feedback(ctx: ModalContext):
        text = ctx.get_value("feedback_text")
        await ctx.respond(f"Thanks for your feedback: {text}", ephemeral=True)

The router supports:
- Exact custom_id matching
- Prefix matching (register with trailing ":" e.g. "ticket:")
- Clean separation of component vs modal handlers
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from .context import (
    ComponentContext,
    ModalContext,
    build_component_context,
)

if TYPE_CHECKING:
    from ..core.client import Client

logger = logging.getLogger(__name__)

ComponentHandler = Callable[[ComponentContext], Awaitable[Any]]
ModalHandler = Callable[[ModalContext], Awaitable[Any]]


class ComponentRouter:
    """Holds registered component and modal handlers and dispatches to them."""

    def __init__(self, client: Client) -> None:
        self.client = client
        # exact or prefix registrations
        self._component_handlers: dict[str, ComponentHandler] = {}
        self._modal_handlers: dict[str, ModalHandler] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def component(self, custom_id: str) -> Callable[[ComponentHandler], ComponentHandler]:
        """Decorator to register a handler for button or select interactions.

        Supports prefix matching: register "vote:" to match "vote:up", "vote:down", etc.
        """

        def decorator(handler: ComponentHandler) -> ComponentHandler:
            if not custom_id:
                raise ValueError("custom_id cannot be empty when registering a component handler")
            self._component_handlers[custom_id] = handler
            logger.debug("Registered component handler for %r", custom_id)
            return handler

        return decorator

    def modal(self, custom_id: str) -> Callable[[ModalHandler], ModalHandler]:
        """Decorator to register a handler for modal submissions."""

        def decorator(handler: ModalHandler) -> ModalHandler:
            if not custom_id:
                raise ValueError("custom_id cannot be empty when registering a modal handler")
            self._modal_handlers[custom_id] = handler
            logger.debug("Registered modal handler for %r", custom_id)
            return handler

        return decorator

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _find_handler(self, custom_id: str, registry: dict[str, Any]) -> tuple[str, Any] | None:
        """Find the best matching handler.

        Priority:
        1. Exact match
        2. Longest prefix match (keys that end with ':' and custom_id starts with them)
        """
        if custom_id in registry:
            return custom_id, registry[custom_id]

        # Prefix matching (keys registered with trailing ":")
        candidates = [
            (key, handler)
            for key, handler in registry.items()
            if key.endswith(":") and custom_id.startswith(key)
        ]
        if candidates:
            # Choose the most specific (longest) prefix
            candidates.sort(key=lambda x: len(x[0]), reverse=True)
            return candidates[0]

        return None

    async def dispatch(self, interaction: dict[str, Any]) -> bool:
        """Attempt to route an INTERACTION_CREATE payload to a component or modal handler.

        Returns True if a handler was found and invoked, False otherwise.
        """
        itype = interaction.get("type")
        data = interaction.get("data", {})
        custom_id: str = data.get("custom_id", "")

        if not custom_id:
            return False

        if itype == 3:  # MESSAGE_COMPONENT
            match = self._find_handler(custom_id, self._component_handlers)
            if not match:
                return False

            registered_id, handler = match
            ctx = build_component_context(self.client, interaction)

            logger.debug(
                "Dispatching component custom_id=%r (matched %r) to %s",
                custom_id,
                registered_id,
                handler.__name__,
            )
            try:
                result = handler(ctx)
                if result is not None:
                    await result
            except Exception as exc:
                logger.exception("Error in component handler %r: %s", handler.__name__, exc)
                # Best effort: tell the user something went wrong
                try:
                    if not ctx._responded:
                        await ctx.respond(
                            "Something went wrong while handling this interaction.", ephemeral=True
                        )
                except Exception:
                    pass
            return True

        elif itype == 5:  # MODAL_SUBMIT
            match = self._find_handler(custom_id, self._modal_handlers)
            if not match:
                return False

            registered_id, handler = match
            ctx = build_component_context(self.client, interaction)

            logger.debug(
                "Dispatching modal custom_id=%r (matched %r) to %s",
                custom_id,
                registered_id,
                handler.__name__,
            )
            try:
                result = handler(ctx)
                if result is not None:
                    await result
            except Exception as exc:
                logger.exception("Error in modal handler %r: %s", handler.__name__, exc)
                try:
                    if not ctx._responded:
                        await ctx.respond(
                            "Something went wrong while processing the form.", ephemeral=True
                        )
                except Exception:
                    pass
            return True

        return False

    def __repr__(self) -> str:
        return (
            f"<ComponentRouter components={len(self._component_handlers)} "
            f"modals={len(self._modal_handlers)}>"
        )


__all__ = ["ComponentContext", "ComponentRouter", "ModalContext"]
