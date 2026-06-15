"""
discordkit.core.client
======================

The main Client class - the heart of every DiscordKit bot.

Design philosophy:
- Explicit over magic: you see how things are wired
- Strong separation of concerns (http, gateway, commands, interactions)
- Pydantic-validated configuration
- Great ergonomics for both simple scripts and large bots
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from typing import Any, Callable, TypeVar

from pydantic import SecretStr

from .cache import CacheBackend, MemoryCache
from ..commands.registry import CommandRegistry
from ..commands.resolver import resolve_options
from ..components.router import ComponentRouter
from ..models import Channel, Guild, Member, User
from ..types import Intents, InteractionType
from .config import Config
from .context import AutocompleteContext, CommandContext, Context
from .gateway import Gateway, GatewayEvent
from .http import DiscordHTTPClient

logger = logging.getLogger(__name__)

EventHandler = Callable[[Context], Any]
T = TypeVar("T")


class Client:
    """Main entry point for DiscordKit bots.

    Example usage:
        from discordkit import Client, Config
        from discordkit.commands import command
        from discordkit.types import Intents

        config = Config(token=os.getenv("DISCORD_TOKEN"), intents=Intents.DEFAULT)
        bot = Client(config)

        @command()
        async def ping(ctx: CommandContext):
            await ctx.respond("Pong! 🏓")

        bot.add_command(ping)

        @bot.event("ready")
        async def on_ready(ctx: Context):
            print(f"Logged in as {bot.user}")

        bot.run()
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._token = config.token.get_secret_value()

        # Core subsystems
        self.http = DiscordHTTPClient(
            token=self._token,
            timeout=config.http_timeout,
            user_agent=config.user_agent,
        )

        self.gateway = Gateway(
            token=self._token,
            intents=config.intents,
            on_event=self._dispatch_gateway_event,
            on_ready=self._handle_ready,
        )

        self.commands = CommandRegistry(client=self)
        self.components = ComponentRouter(client=self)
        self.cache: CacheBackend = MemoryCache(
            default_ttl=300.0,
            max_size=10_000,
            touch_on_read=True,
        )

        # Auto-populate cache from resolved slash-command options
        self._auto_cache_enabled = True

        # Autocomplete handlers: (command_name, option_name) -> async callable
        self._autocomplete_handlers: dict[tuple[str, str], Any] = {}

        # Global error handlers (can be registered by user for production logging/alerting)
        self._error_handlers: list[Callable[[Exception, dict[str, Any]], Any]] = []

        # Runtime state
        self.user: User | None = None
        self.application_id: int | None = None
        self._guilds: dict[int, Guild] = {}
        self._event_handlers: dict[str, list[EventHandler]] = {}
        self._running = False

        # Setup basic logging according to config
        self._configure_logging()

    def _configure_logging(self) -> None:
        level = getattr(logging, self.config.log_level)
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
        if self.config.debug:
            logging.getLogger("discordkit").setLevel(logging.DEBUG)

    # ------------------------------------------------------------------
    # Public API - Events
    # ------------------------------------------------------------------

    def event(self, name: str) -> Callable[[EventHandler], EventHandler]:
        """Decorator to register an event handler.

        Available core events: ready, message_create, interaction_create, etc.
        """

        def decorator(func: EventHandler) -> EventHandler:
            self._event_handlers.setdefault(name.lower(), []).append(func)
            return func

        return decorator

    def on(self, name: str, handler: EventHandler) -> None:
        """Programmatic alternative to the @event decorator."""
        self._event_handlers.setdefault(name.lower(), []).append(handler)

    async def _dispatch(self, name: str, ctx: Context) -> None:
        handlers = self._event_handlers.get(name.lower(), [])
        for handler in handlers:
            try:
                result = handler(ctx)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                logger.exception("Error in event handler %r: %s", name, exc)

    async def _dispatch_gateway_event(self, event: GatewayEvent) -> None:
        """Internal: turn raw gateway events into nice Context objects."""
        if not event.t:
            return

        event_name = event.t.lower()

        ctx = Context(
            client=self,
            event_name=event.t,
            raw_data=event.d or {},
        )

        # Special handling for some high-value events
        if event.t == "READY":
            pass
        elif event.t == "MESSAGE_CREATE":
            # TODO: build full Message model and attach to ctx
            pass
        elif event.t == "INTERACTION_CREATE":
            # Component / modal routing happens here (slash commands are handled via REST)
            interaction_data = event.d or {}
            handled = await self._handle_interaction(interaction_data)
            if handled:
                # Still allow generic listeners if someone wants raw access
                pass

        await self._dispatch(event_name, ctx)
        # Also dispatch the generic "event" for power users
        await self._dispatch("event", ctx)

    async def _handle_ready(self, ready_data: dict[str, Any]) -> None:
        """Process the READY payload and populate client state."""
        self.user = User.model_validate(ready_data["user"])
        self.application_id = ready_data["application"]["id"]

        if self._auto_cache_enabled:
            self.cache.set_user(self.user)

        logger.info("Logged in as %s (id=%s)", self.user, self.user.id)

        # Register slash commands if any were added
        if self.commands._has_global_commands():
            await self.commands.sync_global_commands(self.application_id)

        # Mark ready
        ready_ctx = Context(client=self, event_name="READY", raw_data=ready_data)
        await self._dispatch("ready", ready_ctx)

    async def _handle_interaction(self, interaction: dict[str, Any]) -> bool:
        """Route all supported interaction types.

        Returns whether a handler was invoked (for components/modals/slash/autocomplete).
        """
        itype = interaction.get("type")

        try:
            if itype == InteractionType.APPLICATION_COMMAND:
                await self._handle_application_command(interaction)
                return True

            if itype == InteractionType.APPLICATION_COMMAND_AUTOCOMPLETE:
                await self._handle_autocomplete(interaction)
                return True

            if itype in (InteractionType.MESSAGE_COMPONENT, InteractionType.MODAL_SUBMIT):
                try:
                    routed = await self.components.dispatch(interaction)
                    if routed:
                        logger.debug("Interaction %s routed successfully", itype)
                    return routed
                except Exception as exc:
                    # Build minimal context for error reporting
                    ctx_info = {
                        "type": "component",
                        "custom_id": (interaction.get("data") or {}).get("custom_id"),
                        "user_id": (interaction.get("user") or (interaction.get("member") or {}).get("user") or {}).get("id"),
                    }
                    await self._report_generic_error(exc, ctx_info)
                    return False

            return False
        except Exception as exc:
            logger.exception("Error while routing interaction type %s: %s", itype, exc)
            return False

    async def _handle_application_command(self, interaction: dict[str, Any]) -> None:
        """Handle incoming slash command (APPLICATION_COMMAND), including full subcommand/group hierarchy."""
        data = interaction.get("data", {}) or {}
        root_name = (data.get("name") or "").lower()

        # Use the registry's resolver to walk the hierarchy and find the actual leaf handler
        leaf_cmd, leaf_raw_options, full_path = self.commands.resolve_command_from_interaction(data)

        if leaf_cmd is None:
            logger.warning("Received unknown slash command path: %s", full_path or root_name)
            return

        # Build a temporary interaction "view" for the resolver that contains only the leaf options
        # (the resolver expects 'data.options' to be the parameters for the target command)
        leaf_interaction_view = {
            **interaction,
            "data": {
                **data,
                "name": leaf_cmd.name,  # leaf name for any logging inside resolver
                "options": leaf_raw_options,
            },
        }

        # Resolve options using the *leaf* command's signature (critical for correct type hints)
        try:
            resolved_opts = resolve_options(leaf_cmd, leaf_interaction_view, cache=self.cache)
        except Exception as exc:
            logger.exception("Failed to resolve options for %s: %s", full_path, exc)
            resolved_opts = {}

        # Build context using the full path for logging / clarity
        ctx = self._build_command_context(interaction, full_path, resolved_opts)

        logger.info(
            "Dispatching slash command '%s' (leaf: %s) with resolved options: %s",
            full_path,
            leaf_cmd.name,
            list(resolved_opts.keys()),
        )

        try:
            await leaf_cmd.invoke(ctx)
        except Exception as exc:
            await self._handle_command_error(exc, ctx, command_path=full_path)

    def _build_command_context(
        self, interaction: dict[str, Any], command_name: str, options: dict[str, Any]
    ) -> CommandContext:
        """Construct a CommandContext from raw interaction + resolved options."""
        data = interaction.get("data", {}) or {}

        # User / member resolution (same as components)
        user_data = interaction.get("user") or interaction.get("member", {}).get("user")
        user = User.model_validate(user_data) if user_data else None

        member_data = interaction.get("member")
        member = Member.model_validate({**member_data, "user": user_data}) if member_data and user_data else None

        guild_id = interaction.get("guild_id")
        channel_id = interaction.get("channel_id")
        message = None  # slash commands don't usually have a triggering message

        return CommandContext(
            client=self,
            command_name=command_name,
            interaction_id=int(interaction.get("id")) if interaction.get("id") else None,
            interaction_token=interaction.get("token"),
            user=user,
            member=member,
            guild=None,  # can be enriched on demand
            channel_id=int(channel_id) if channel_id else None,
            message=message,
            options=options,
        )

    async def _handle_autocomplete(self, interaction: dict[str, Any]) -> None:
        """Handle APPLICATION_COMMAND_AUTOCOMPLETE and call the registered handler."""
        data = interaction.get("data", {}) or {}
        command_name = (data.get("name") or "").lower()

        # Find the focused option
        focused_option: dict[str, Any] | None = None
        for opt in data.get("options", []) or []:
            if opt.get("focused"):
                focused_option = opt
                break

        if not focused_option:
            # Fallback: take first option
            opts = data.get("options", []) or []
            focused_option = opts[0] if opts else {}

        option_name = (focused_option.get("name") or "").lower()
        current_value = str(focused_option.get("value", ""))

        key = (command_name, option_name)
        handler = self._autocomplete_handlers.get(key)

        if handler is None:
            logger.debug("No autocomplete handler for %s.%s", command_name, option_name)
            # Send empty response so Discord doesn't error
            await self._send_autocomplete_response(interaction, [])
            return

        # Build autocomplete context
        ctx = self._build_autocomplete_context(interaction, command_name, option_name, current_value)

        try:
            result = handler(ctx)
            if inspect.iscoroutine(result):
                result = await result

            choices: list[dict[str, Any]] = []
            if isinstance(result, list):
                choices = result
            # If the handler already called ctx.respond, it returned None or we ignore

            # If handler didn't respond yet and we have choices, respond
            if choices and not getattr(ctx, "_responded", False):
                await ctx.respond(choices)

        except Exception as exc:
            ctx_info = {
                "type": "autocomplete",
                "command": command_name,
                "option": option_name,
                "value": current_value,
                "user_id": (interaction.get("user") or {}).get("id"),
            }
            await self._report_generic_error(exc, ctx_info)
            await self._send_autocomplete_response(interaction, [])

    def _build_autocomplete_context(
        self, interaction: dict[str, Any], command_name: str, option_name: str, value: str
    ) -> AutocompleteContext:
        user_data = interaction.get("user") or interaction.get("member", {}).get("user")
        user = User.model_validate(user_data) if user_data else None

        member_data = interaction.get("member")
        member = Member.model_validate(member_data) if member_data else None

        channel_id = interaction.get("channel_id")

        return AutocompleteContext(
            client=self,
            interaction_id=int(interaction.get("id")) if interaction.get("id") else None,
            interaction_token=interaction.get("token"),
            user=user,
            member=member,
            channel_id=int(channel_id) if channel_id else None,
            command_name=command_name,
            option_name=option_name,
            value=value,
        )

    async def _send_autocomplete_response(self, interaction: dict[str, Any], choices: list[dict[str, Any]]) -> None:
        """Low-level helper to send autocomplete choices when handler doesn't use the context."""
        iid = interaction.get("id")
        token = interaction.get("token")
        if not iid or not token:
            return
        payload = {
            "type": 8,  # APPLICATION_COMMAND_AUTOCOMPLETE_RESULT
            "data": {"choices": choices[:25]},
        }
        await self.http.create_interaction_response(int(iid), token, payload=payload)

    # ------------------------------------------------------------------
    # Public API - Commands
    # ------------------------------------------------------------------

    def add_command(self, command: Any) -> None:
        """Register a command object (usually created via @command decorator)."""
        self.commands.register(command)

    def command(self, **kwargs: Any) -> Callable[[Callable[..., Any]], Any]:
        """Decorator shortcut for registering slash/prefix commands.

        Example:
            @bot.command(name="ping", description="Replies with pong")
            async def ping(ctx):
                await ctx.respond("Pong")
        """
        return self.commands.command_decorator(**kwargs)

    def group(self, **kwargs: Any) -> Callable[[Callable[..., Any]], Any]:
        """Decorator shortcut for creating command groups (with subcommands).

        Example:
            @bot.group(name="admin", description="Admin tools")
            async def admin(ctx): ...

            @admin.command(name="kick")
            async def kick(ctx, user: User): ...
        """
        from ..commands.decorators import group as _group

        def decorator(func: Callable[..., Any]) -> Any:
            grp = _group(**kwargs)(func)
            return self.commands.register(grp)

        return decorator

    # ------------------------------------------------------------------
    # Public API - Components & Modals (interactive routing)
    # ------------------------------------------------------------------

    def component(self, custom_id: str) -> Callable[[Callable[..., Any]], Any]:
        """Decorator to register a handler for button or select menu interactions.

        Supports prefix matching by ending the id with ":".

        Example:
            @bot.component("delete")
            async def on_delete(ctx: ComponentContext):
                await ctx.edit_message(content="Deleted", components=[])

            @bot.component("color:")
            async def on_color(ctx: SelectContext):
                await ctx.respond(f"Selected: {ctx.values}")
        """
        return self.components.component(custom_id)

    def modal(self, custom_id: str) -> Callable[[Callable[..., Any]], Any]:
        """Decorator to register a handler for modal form submissions.

        Example:
            @bot.modal("feedback")
            async def on_feedback(ctx: ModalContext):
                reason = ctx.get_value("reason")
                await ctx.respond("Thank you!", ephemeral=True)
        """
        return self.components.modal(custom_id)

    # ------------------------------------------------------------------
    # Public API - Autocomplete (for slash command options)
    # ------------------------------------------------------------------

    def autocomplete(
        self, command: str, option: str
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator to register an autocomplete handler for a specific option of a command.

        Example:
            @bot.autocomplete("configure", "template")
            async def template_autocomplete(ctx: AutocompleteContext):
                # ctx.value contains what the user typed so far
                suggestions = [
                    {"name": "Default", "value": "default"},
                    {"name": "Advanced", "value": "advanced"},
                ]
                await ctx.respond(suggestions)
                # or return the list and framework will call respond
        """
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            key = (command.lower(), option.lower())
            self._autocomplete_handlers[key] = func
            return func

        return decorator

    def error_handler(
        self, func: Callable[[Exception, dict[str, Any]], Any] | None = None
    ) -> Callable[[Callable[[Exception, dict[str, Any]], Any]], Callable[[Exception, dict[str, Any]], Any]]:
        """Register a global error handler.

        Can be used as decorator or method:

            @bot.error_handler
            async def on_error(error, context):
                logger.error("Command failed", exc_info=error)
                # context contains: 'command', 'user_id', 'guild_id', 'type' (command/component/etc)

            # or
            bot.error_handler(my_error_handler)
        """
        def register(f: Callable[[Exception, dict[str, Any]], Any]):
            self._error_handlers.append(f)
            return f

        if func is not None:
            return register(func)
        return register

    async def _handle_command_error(
        self, error: Exception, ctx: CommandContext, *, command_path: str | None = None
    ) -> None:
        """Centralized error handling for slash commands (and reusable for others)."""
        context = {
            "type": "command",
            "command": command_path or getattr(ctx, "command_name", "unknown"),
            "user_id": getattr(ctx.user, "id", None),
            "guild_id": getattr(ctx, "guild", None) and getattr(ctx.guild, "id", None),
            "channel_id": ctx.channel_id,
        }
        logger.exception("Error in command '%s': %s", context.get("command"), error, extra={"context": context})

        # Best effort user-facing response
        try:
            if not getattr(ctx, "_responded", False):
                await ctx.respond(
                    "❌ An unexpected error occurred while processing your command. The developers have been notified.",
                    ephemeral=True,
                )
        except Exception:
            pass

        await self._notify_error_handlers(error, context)

    async def _report_generic_error(self, error: Exception, context: dict[str, Any]) -> None:
        """Generic error path used by component/autocomplete/etc. dispatchers."""
        logger.exception("Unhandled interaction error: %s | context=%s", error, context)
        await self._notify_error_handlers(error, context)

    async def _notify_error_handlers(self, error: Exception, context: dict[str, Any]) -> None:
        """Call all registered user error handlers."""
        for handler in self._error_handlers:
            try:
                result = handler(error, context)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as handler_exc:
                logger.exception("Error handler itself raised an exception: %s", handler_exc)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to the gateway and run until closed. Does not block forever by itself."""
        self._running = True
        logger.info("Starting DiscordKit client (intents=%s)...", self.config.intents)
        await self.gateway.connect()

        # Keep the client alive
        try:
            while self._running:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            await self.close()

    def run(self) -> None:
        """Blocking helper that runs the bot until interrupted.

        This is the method most users will call at the bottom of their script.
        """
        try:
            asyncio.run(self.start())
        except KeyboardInterrupt:
            logger.info("Received KeyboardInterrupt, shutting down...")

    async def close(self) -> None:
        """Cleanly shut down HTTP + Gateway connections."""
        self._running = False
        logger.info("Shutting down DiscordKit client...")
        await self.gateway.close()
        await self.http.close()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    async def fetch_me(self) -> User:
        """Fetch the current bot user (useful for testing)."""
        data = await self.http.get_current_user()
        self.user = User.model_validate(data)
        return self.user

    def get_guild(self, guild_id: int) -> Guild | None:
        return self._guilds.get(guild_id)

    # ------------------------------------------------------------------
    # Cache integration
    # ------------------------------------------------------------------

    def configure_cache(
        self,
        *,
        default_ttl: float | None = None,
        max_size: int | None = None,
        touch_on_read: bool | None = None,
        ttl_by_type: dict[str, float] | None = None,
        backend: CacheBackend | None = None,
        persistent: bool = False,
        cache_path: str | None = None,
    ) -> None:
        """Configure or replace the client cache.

        Pass a custom ``backend`` to use Redis or another ``CacheBackend``
        implementation. When ``backend`` is omitted, a new :class:`MemoryCache`
        (or :class:`PersistentCache` when ``persistent=True``) is built from
        the provided options.

        Example::

            bot.configure_cache(
                default_ttl=600,
                max_size=20_000,
                touch_on_read=True,
                ttl_by_type={"member": 120, "guild": 1800},
            )

            # Survive restarts with SQLite persistence:
            bot.configure_cache(persistent=True, cache_path=".data/bot_cache.db")
        """
        if backend is not None:
            self.cache = backend
            return

        from .cache import EvictionPolicy

        kwargs: dict[str, Any] = {
            "eviction_policy": EvictionPolicy.LRU,
            "touch_on_read": touch_on_read if touch_on_read is not None else True,
        }
        if default_ttl is not None:
            kwargs["default_ttl"] = default_ttl
        if max_size is not None:
            kwargs["max_size"] = max_size
        if ttl_by_type is not None:
            kwargs["ttl_by_type"] = ttl_by_type

        if persistent:
            from .cache_persistent import PersistentCache

            path = cache_path or ".discordkit_cache.db"
            self.cache = PersistentCache(path=path, **kwargs)
        else:
            self.cache = MemoryCache(**kwargs)

    @property
    def auto_cache(self) -> bool:
        """Whether resolved slash-command options are stored automatically."""
        return self._auto_cache_enabled

    @auto_cache.setter
    def auto_cache(self, enabled: bool) -> None:
        self._auto_cache_enabled = enabled

    def get_cached_user(self, user_id: int) -> User | None:
        """Return a cached :class:`~discordkit.models.User`, if present."""
        return self.cache.get_user(user_id)

    def get_cached_member(self, guild_id: int, user_id: int) -> Member | None:
        """Return a cached :class:`~discordkit.models.Member`, if present."""
        return self.cache.get_member(guild_id, user_id)

    def get_cached_guild(self, guild_id: int) -> Guild | None:
        """Return a cached :class:`~discordkit.models.Guild`, if present."""
        return self.cache.get_guild(guild_id)

    def get_cached_channel(self, channel_id: int) -> Channel | None:
        """Return a cached :class:`~discordkit.models.Channel`, if present."""
        return self.cache.get_channel(channel_id)

    async def fetch_user_cached(
        self,
        user_id: int,
        fetcher: Callable[[], User | None | Any],
        *,
        ttl: float | None = None,
    ) -> User | None:
        """Cache-aside helper: return cached user or call ``fetcher`` on miss."""
        return await self.cache.get_or_fetch_user(user_id, fetcher, ttl=ttl)

    async def fetch_member_cached(
        self,
        guild_id: int,
        user_id: int,
        fetcher: Callable[[], Member | None | Any],
        *,
        ttl: float | None = None,
    ) -> Member | None:
        """Cache-aside helper: return cached member or call ``fetcher`` on miss."""
        return await self.cache.get_or_fetch_member(guild_id, user_id, fetcher, ttl=ttl)

    def invalidate_guild_cache(self, guild_id: int) -> int:
        """Invalidate all cached members for a guild."""
        return self.cache.invalidate_by_guild(guild_id)

    def cache_stats(self):
        """Return a snapshot of cache hit/miss/eviction statistics."""
        return self.cache.stats()

    @property
    def is_ready(self) -> bool:
        return self.user is not None and self.application_id is not None


__all__ = ["Client"]
