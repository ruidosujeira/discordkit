"""
discordkit.commands.registry
============================

Central registry for all commands (slash + future prefix).

The Client owns one CommandRegistry.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from .command import Command

if TYPE_CHECKING:
    from ..core.client import Client

logger = logging.getLogger(__name__)


class CommandRegistry:
    """Holds and manages all registered commands for a Client."""

    def __init__(self, client: Client) -> None:
        self.client = client
        self._commands: dict[str, Command] = {}
        self._guild_commands: dict[int, dict[str, Command]] = {}

    def register(self, command: Command | Callable[..., Any]) -> Command:
        """Register a Command (or group). Children are registered recursively via the tree.

        Only top-level commands (those without a parent) are stored directly for lookup/sync.
        """
        if not isinstance(command, Command):
            if hasattr(command, "_discordkit_command"):
                extracted = command._discordkit_command
                if isinstance(extracted, Command):
                    command = extracted
                else:
                    raise TypeError(
                        f"Object {command} is not a Command and was not created with @command"
                    )
            else:
                raise TypeError(
                    f"Object {command} is not a Command and was not created with @command"
                )

        # mypy narrowing: after the above, command is guaranteed to be Command
        cmd: Command = command  # type narrowed by the isinstance + extraction above

        # Attach any children that were added via .command() before registration
        # (they are already linked via parent/children)

        if cmd.parent is None:
            # Top-level (either a flat command or a root group)
            if cmd.guild_ids:
                for gid in cmd.guild_ids:
                    self._guild_commands.setdefault(gid, {})[cmd.name] = cmd
            else:
                self._commands[cmd.name] = cmd
        else:
            # Child commands/groups are carried inside their parent's tree.
            # We still log for visibility.
            logger.debug(
                "Registered child command/group: %s (under %s)",
                cmd.name,
                cmd.parent.name if cmd.parent else "?",
            )

        # Recursively ensure any children are "known" (mostly for logging/debug)
        for child in cmd.children:
            self._ensure_child_registered(child)

        logger.debug("Registered command: %s", cmd)
        return cmd

    def _ensure_child_registered(self, command: Command) -> None:
        """Internal: walk children for logging / future use."""
        for child in command.children:
            logger.debug("  - child: %s", child.name)
            self._ensure_child_registered(child)

    def command_decorator(self, **kwargs: Any) -> Callable[[Callable[..., Any]], Command]:
        """Used by Client.command() to allow @bot.command() sugar."""
        from .decorators import command as _command

        def decorator(func: Callable[..., Any]) -> Command:
            cmd = _command(**kwargs)(func)
            return self.register(cmd)

        return decorator

    def get(self, name: str, guild_id: int | None = None) -> Command | None:
        if guild_id and guild_id in self._guild_commands:
            return self._guild_commands[guild_id].get(name)
        return self._commands.get(name)

    def resolve_command_from_interaction(
        self, data: dict[str, Any]
    ) -> tuple[Command | None, list[dict[str, Any]], str]:
        """Given the 'data' portion of an APPLICATION_COMMAND interaction, walk the
        nested options to find the leaf Command handler, its raw options, and the full path.

        Returns (leaf_command_or_none, leaf_options_list, full_command_path_string)
        """
        root_name = (data.get("name") or "").lower()
        current: Command | None = self.get(root_name)

        options: list[dict[str, Any]] = data.get("options") or []
        path_parts = [root_name]

        # Traverse subcommand / sub-group nesting
        while options:
            first = options[0]
            sub_name = (first.get("name") or "").lower()
            sub_type = first.get("type")

            if sub_type in (1, 2):  # SUB_COMMAND or SUB_COMMAND_GROUP
                path_parts.append(sub_name)
                if current and current.children:
                    for ch in current.children:
                        if ch.name.lower() == sub_name:
                            current = ch
                            break
                options = first.get("options") or []
            else:
                # We reached the parameters of the leaf
                break

        full_path = " ".join(p for p in path_parts if p)

        # At this point 'options' should be the parameter options for the leaf
        return current, options, full_path

    def all_global(self) -> list[Command]:
        return list(self._commands.values())

    def _has_global_commands(self) -> bool:
        return bool(self._commands)

    async def sync_global_commands(self, application_id: int) -> None:
        """Push all global commands to Discord.

        This is called automatically on READY when global commands exist.
        """
        if not self._commands:
            return

        logger.info("Syncing %d global slash command(s)...", len(self._commands))
        payload = [cmd.to_discord_payload() for cmd in self._commands.values()]

        try:
            result = await self.client.http.bulk_overwrite_global_commands(application_id, payload)
            logger.info("Successfully synced %d global command(s)", len(result))
        except Exception as exc:
            logger.exception("Failed to sync global commands: %s", exc)

    # Future: sync_guild_commands, remove_command, etc.

    def __len__(self) -> int:
        return len(self._commands) + sum(len(v) for v in self._guild_commands.values())

    def __repr__(self) -> str:
        return f"<CommandRegistry global={len(self._commands)} guild_scoped={len(self._guild_commands)}>"


__all__ = ["CommandRegistry"]
