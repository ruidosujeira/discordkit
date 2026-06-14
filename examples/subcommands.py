"""
Professional example of Subcommands and Command Groups in DiscordKit.

This demonstrates:
- Root groups
- Subcommands with full Option support (including complex types)
- Nested groups (group inside group)
- Clean hierarchical routing and option resolution
- How groups appear in Discord (as folders with subcommands)

Run:
    DISCORD_TOKEN=... python examples/subcommands.py
"""
import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command, group
from discordkit.core.context import CommandContext
from discordkit.models import User
from discordkit.types import Intents

load_dotenv()

config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT, debug=True)
bot = Client(config)


# ------------------------------------------------------------------
# Example 1: Simple group with subcommands
# ------------------------------------------------------------------

@group(name="config", description="Manage server configuration")
async def config_group(ctx: CommandContext):
    """This handler runs only if someone somehow invokes the bare group (rare)."""
    await ctx.respond("Please use one of the subcommands: `set`, `get`, or `reset`.")


@config_group.command(name="set", description="Set a configuration value")
async def config_set(
    ctx: CommandContext,
    key: Annotated[str, Option("Configuration key", min_length=2, max_length=30)],
    value: Annotated[str, Option("New value", max_length=100)],
):
    await ctx.respond(f"✅ Set `{key}` = `{value}` (demo)")


@config_group.command(name="get", description="Get current value of a key")
async def config_get(
    ctx: CommandContext,
    key: Annotated[str, Option("Configuration key")],
):
    await ctx.respond(f"Current value for `{key}`: `example-value` (demo)")


# ------------------------------------------------------------------
# Example 2: Nested groups (group inside a group)
# ------------------------------------------------------------------

@config_group.group(name="advanced", description="Advanced / dangerous configuration options")
async def advanced_group(ctx: CommandContext):
    await ctx.respond("Use a subcommand under `advanced`.")


@advanced_group.command(name="reset", description="Reset a specific advanced setting to default")
async def advanced_reset(
    ctx: CommandContext,
    setting: Annotated[str, Option("Advanced setting name")],
    confirm: Annotated[bool, Option("Type true to confirm")] = False,
):
    if not confirm:
        await ctx.respond("⚠️ You must set `confirm: true` to reset advanced settings.", ephemeral=True)
        return
    await ctx.respond(f"🔄 Advanced setting `{setting}` has been reset to defaults (demo).")


# ------------------------------------------------------------------
# Example 3: Top-level group with complex options in subcommand
# ------------------------------------------------------------------

@group(name="admin", description="Administrative actions")
async def admin_group(ctx: CommandContext):
    pass


@admin_group.command(name="ban", description="Ban a user from the server")
async def admin_ban(
    ctx: CommandContext,
    user: Annotated[User, Option("The user to ban")],
    reason: Annotated[str, Option("Reason for the ban", min_length=5, max_length=400)],
    delete_days: Annotated[int, Option("Delete messages from the last N days", min_value=0, max_value=7)] = 0,
):
    await ctx.respond(
        f"🚫 Banned {user.mention} for **{reason}** (would delete last {delete_days} days of messages in a real implementation)."
    )


# Register everything (root groups are sufficient; children travel with them)
bot.add_command(config_group)
bot.add_command(admin_group)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Subcommands demo ready as {bot.user}")
    print("   - /config set ...")
    print("   - /config get ...")
    print("   - /config advanced reset ...")
    print("   - /admin ban ...")
    print("   Groups and subcommands should now appear correctly in Discord after the next sync.")


if __name__ == "__main__":
    bot.run()
