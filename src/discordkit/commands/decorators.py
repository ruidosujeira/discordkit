"""
discordkit.commands.decorators
==============================

@command and @group decorators. These are the primary developer-facing API.
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from ..types import ApplicationCommandType
from .command import Command

F = TypeVar("F", bound=Callable[..., Any])


def command(
    name: str | None = None,
    *,
    description: str | None = None,
    guild_ids: list[int] | None = None,
    default_member_permissions: int | None = None,
    nsfw: bool = False,
) -> Callable[[F], Command]:
    """Decorator that turns an async function into a registered slash command.

    Example:
        @command(name="ping", description="Check if the bot is alive")
        async def ping(ctx):
            await ctx.respond("Pong!")

        # or let it infer the name
        @command()
        async def hello(ctx, name: str):
            await ctx.respond(f"Hello {name}")
    """

    def decorator(func: F) -> Command:
        cmd_name = name or func.__name__
        cmd_desc = description or (func.__doc__ or f"{cmd_name} command").strip()

        cmd = Command(
            name=cmd_name,
            description=cmd_desc,
            callback=func,
            guild_ids=guild_ids,
            default_member_permissions=default_member_permissions,
            nsfw=nsfw,
        )
        # Attach the command object to the function for discoverability
        func._discordkit_command = cmd  # type: ignore[attr-defined]
        return cmd

    return decorator


def group(
    name: str | None = None,
    *,
    description: str | None = None,
    guild_ids: list[int] | None = None,
) -> Callable[[F], Command]:
    """Decorator for creating a command group (container for subcommands and sub-groups).

    Full hierarchical support is provided. Use the returned group's `.command()` method
    (or nested @group) to attach subcommands.

    Example:
        @group(name="config", description="Server configuration commands")
        async def config(ctx):
            # This handler is optional for groups; subcommands are preferred.
            await ctx.respond("Use a subcommand like /config set ...")

        @config.command(name="set", description="Set a configuration value")
        async def set_config(ctx, key: Annotated[str, Option("Key")], value: str):
            ...

        # You can even nest groups
        @config.group(name="advanced", description="Advanced settings")
        async def advanced_group(ctx): ...

        @advanced_group.command(name="reset", description="Reset advanced settings")
        async def reset(ctx):
            ...
    """
    def decorator(func: F) -> Command:
        gname = name or func.__name__
        gdesc = description or (func.__doc__ or f"{gname} group").strip()

        grp = Command(
            name=gname,
            description=gdesc,
            callback=func,
            guild_ids=guild_ids,
            command_type=ApplicationCommandType.CHAT_INPUT,
        )
        func._discordkit_command = grp  # type: ignore[attr-defined]
        return grp

    return decorator


__all__ = ["command", "group"]
