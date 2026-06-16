"""
discordkit.commands.command
===========================

The Command object model.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from inspect import signature
from typing import TYPE_CHECKING, Any, TypeVar

from ..types import ApplicationCommandType
from .option import build_options_from_signature  # new powerful system

if TYPE_CHECKING:
    from ..core.context import CommandContext

    F = TypeVar("F", bound=Callable[..., Any])


@dataclass(slots=True)
class Command:
    """Represents a slash command (or future prefix/hybrid command).

    This is the canonical in-memory representation. It knows how to:
    - Convert itself into the Discord API payload
    - Invoke the user callback with a properly built CommandContext
    """

    name: str
    description: str
    callback: Callable[..., Awaitable[Any]]
    guild_ids: list[int] | None = None  # None = global command
    default_member_permissions: int | None = None
    nsfw: bool = False

    # Parsed metadata
    options: list[dict[str, Any]] = field(default_factory=list)
    command_type: ApplicationCommandType = ApplicationCommandType.CHAT_INPUT

    # Hierarchical support for groups and subcommands
    parent: Command | None = None
    children: list[Command] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Pre-build options using the modern Annotated + Option system (if not already provided).

        This allows validation to happen at decoration/registration time.
        """
        if not self.options and not self.children:
            try:
                built = build_options_from_signature(self.callback)
                if built:
                    object.__setattr__(self, "options", built)
            except Exception:
                pass

    def add_child(self, child: Command) -> None:
        """Attach a subcommand or sub-group to this command/group."""
        child.parent = self
        if child not in self.children:
            self.children.append(child)
        # Clear any pre-built options on the parent so payload is rebuilt from children
        if self.children:
            object.__setattr__(self, "options", [])

    def command(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        guild_ids: list[int] | None = None,
        default_member_permissions: int | None = None,
        nsfw: bool = False,
    ) -> Callable[[F], Command]:
        """Decorator to register a subcommand under this group or sub-group.

        Example:
            @admin.command(name="ban", description="Ban a user")
            async def ban(ctx, user: User):
                ...
        """
        from .decorators import command as _create_command

        def decorator(func: F) -> Command:
            sub = _create_command(
                name=name,
                description=description,
                guild_ids=guild_ids,
                default_member_permissions=default_member_permissions,
                nsfw=nsfw,
            )(func)
            self.add_child(sub)
            return sub

        return decorator

    def group(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        guild_ids: list[int] | None = None,
    ) -> Callable[[F], Command]:
        """Create and attach a nested sub-group under this group."""
        from .decorators import group as _create_group

        def decorator(func: F) -> Command:
            sub_group = _create_group(name=name, description=description, guild_ids=guild_ids)(func)
            self.add_child(sub_group)
            return sub_group

        return decorator

    def _as_option(self) -> dict[str, Any]:
        """Return the representation of this command as it should appear inside a parent's 'options' array."""
        if self.children:
            # This is a sub-group
            sub_opts = [child._as_option() for child in self.children]
            return {
                "name": self.name,
                "description": self.description,
                "type": 2,  # SUB_COMMAND_GROUP
                "options": sub_opts,
            }
        else:
            # Leaf subcommand: include its parameter options
            param_options = self.options or build_options_from_signature(self.callback)
            return {
                "name": self.name,
                "description": self.description,
                "type": 1,  # SUB_COMMAND
                "options": param_options,
            }

    def to_discord_payload(self) -> dict[str, Any]:
        """Convert to the exact shape Discord expects.

        For groups, this embeds children as nested options (SUB_COMMAND / SUB_COMMAND_GROUP).
        """
        if self.children:
            # Group or sub-group: build nested structure from children
            options = [child._as_option() for child in self.children]
        else:
            options = self.options or build_options_from_signature(self.callback)

        payload: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "type": int(self.command_type),
            "options": options,
            "default_member_permissions": (
                str(self.default_member_permissions)
                if self.default_member_permissions is not None
                else None
            ),
            "nsfw": self.nsfw,
        }
        if self.guild_ids:
            pass
        return {k: v for k, v in payload.items() if v is not None}

    async def invoke(self, ctx: CommandContext, **kwargs: Any) -> Any:
        """Call the user-provided callback with a CommandContext + parsed options."""
        # Merge stored options + runtime kwargs
        call_kwargs = {**ctx.options, **kwargs}

        # Always inject ctx as first positional or kwarg if the function accepts it

        sig = signature(self.callback)
        params = list(sig.parameters.keys())

        if "ctx" in params or "context" in params:
            # User wants the context
            if "ctx" in params:
                return await self.callback(ctx, **call_kwargs)
            else:
                return await self.callback(context=ctx, **call_kwargs)
        else:
            return await self.callback(**call_kwargs)

    def __repr__(self) -> str:
        scope = "guild" if self.guild_ids else "global"
        return f"<Command name={self.name!r} scope={scope}>"


__all__ = ["Command", "CommandContext"]
