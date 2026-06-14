"""
A practical moderation bot example using DiscordKit best practices.

Demonstrates:
- Subcommands under an "mod" group
- Rich Option usage with validation
- Automatic option resolution (User)
- Basic error handling
- Clean command structure
"""

import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, group
from discordkit.core.context import CommandContext
from discordkit.models import User
from discordkit.types import Intents

load_dotenv()

config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT)
bot = Client(config)


@group(name="mod", description="Moderation commands")
async def mod_group(ctx: CommandContext):
    """Root group for all moderation actions."""
    pass


@mod_group.command(name="ban", description="Ban a user")
async def mod_ban(
    ctx: CommandContext,
    user: Annotated[User, Option("User to ban")],
    reason: Annotated[str, Option("Reason for ban", min_length=5, max_length=500)],
    delete_days: Annotated[int, Option("Delete recent messages (0-7 days)", min_value=0, max_value=7)] = 0,
):
    # In a real bot you would call the Discord ban endpoint here
    await ctx.respond(
        f"🚫 Banned {user.mention} for: {reason}\n"
        f"(Would delete messages from the last {delete_days} day(s))",
        ephemeral=True,
    )


@mod_group.command(name="kick", description="Kick a user")
async def mod_kick(
    ctx: CommandContext,
    user: Annotated[User, Option("User to kick")],
    reason: Annotated[str, Option("Reason", max_length=300)] = "No reason provided",
):
    await ctx.respond(f"👢 Kicked {user.mention}. Reason: {reason}", ephemeral=True)


@mod_group.command(name="timeout", description="Timeout a user")
async def mod_timeout(
    ctx: CommandContext,
    user: Annotated[User, Option("User to timeout")],
    minutes: Annotated[int, Option("Duration in minutes", min_value=1, max_value=40320)] = 60,
    reason: Annotated[str, Option("Reason", max_length=300)] = "",
):
    await ctx.respond(
        f"⏳ Timed out {user.mention} for {minutes} minute(s). {reason}",
        ephemeral=True,
    )


bot.add_command(mod_group)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Moderation bot ready as {bot.user}")


if __name__ == "__main__":
    bot.run()
