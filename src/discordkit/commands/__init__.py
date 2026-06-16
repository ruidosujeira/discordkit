"""
discordkit.commands
===================

Modern command system focused on slash commands first, with clean support
for future prefix commands and hybrid commands.

Core ideas:
- Commands are first-class objects (not just decorated functions)
- Strong typing of options via function signatures + Pydantic (future)
- Very explicit registration
- Easy to extend (groups, checks, cooldowns, permissions)
"""

from __future__ import annotations

# CommandContext lives in core to avoid import cycles with the Command dataclass;
# we re-export it here for the public commands API.
from ..core.context import CommandContext
from .command import Command
from .decorators import command, group

# Advanced (mostly internal but useful for testing / power users)
from .option import Option, build_option_dict, build_options_from_signature
from .registry import CommandRegistry
from .resolver import resolve_options

__all__ = [
    "Command",
    "CommandContext",
    "CommandRegistry",
    "Option",
    "build_option_dict",
    "build_options_from_signature",
    "command",
    "group",
    "resolve_options",
]
