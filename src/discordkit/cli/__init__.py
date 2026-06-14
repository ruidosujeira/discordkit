"""
discordkit.cli
==============

Modern CLI for DiscordKit using Typer.

Available commands (initial):
- new <name>     Create a new DiscordKit bot project
- run            Run a bot with hot reload (future)
- sync           Sync slash commands manually (future)
"""

from __future__ import annotations

from .main import app, main

__all__ = ["app", "main"]
