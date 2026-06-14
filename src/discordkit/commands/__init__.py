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

from .command import Command, CommandContext
from .decorators import command, group
from .option import Option
from .registry import CommandRegistry
from .resolver import resolve_options

# Advanced (mostly internal but useful for testing / power users)
from .option import build_option_dict, build_options_from_signature

__all__ = [
    "Command",
    "CommandContext",
    "command",
    "group",
    "CommandRegistry",
    "Option",
    "resolve_options",
    "build_options_from_signature",
    "build_option_dict",
]
