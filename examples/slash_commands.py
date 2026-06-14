"""
Full Slash Command Example with resolved options + autocomplete.

Demonstrates:
- Complex option resolution (User, Role, Channel, Attachment)
- Primitives with constraints
- Basic autocomplete on one option
- Clean handler that receives real model instances in ctx.options or via **kwargs

Usage:
    DISCORD_TOKEN=... python examples/slash_commands.py
"""
import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command, resolve_options
from discordkit.core.context import AutocompleteContext, CommandContext
from discordkit.models import Attachment, Channel, Role, User
from discordkit.types import Intents

load_dotenv()

config = Config(
    token=os.environ["DISCORD_TOKEN"],
    intents=Intents.DEFAULT,
    debug=True,
)

bot = Client(config)


# ------------------------------------------------------------------
# Main example command with rich resolved options
# ------------------------------------------------------------------

@command(name="userinfo", description="Show information about a user (with resolution demo)")
async def userinfo(
    ctx: CommandContext,
    user: Annotated[User, Option("The user to inspect")],
    include_roles: Annotated[bool, Option("Include top roles?")] = False,
    reason: Annotated[str | None, Option("Internal note", max_length=100)] = None,
):
    """Handler receives real User object thanks to automatic resolution."""
    lines = [
        f"**User:** {user.mention} ({user.display_name})",
        f"**ID:** {user.id}",
        f"**Bot:** {user.bot}",
    ]

    if include_roles:
        lines.append("_Roles would be fetched here in a real bot_")

    if reason:
        lines.append(f"**Note:** {reason}")

    # You can also access via ctx.options
    # resolved_user = ctx.options.get("user")

    await ctx.respond("\n".join(lines))


@command(name="configure", description="Demo command with many resolved option types + autocomplete")
async def configure(
    ctx: CommandContext,
    name: Annotated[str, Option("Configuration name", min_length=2, max_length=30)],
    level: Annotated[int, Option("Level", min_value=1, max_value=100)] = 10,
    target_channel: Annotated[Channel | None, Option("Target channel", channel_types=[0, 5])] = None,
    attachment: Annotated[Attachment | None, Option("Reference file")] = None,
    role: Annotated[Role | None, Option("Role to apply")] = None,
    template: Annotated[str, Option("Template to use", autocomplete=True)] = "default",
):
    parts = [f"**Name:** {name}", f"**Level:** {level}"]

    if target_channel:
        parts.append(f"**Channel:** {target_channel.mention} (type={target_channel.type})")

    if attachment:
        parts.append(f"**Attachment:** {attachment.filename} ({attachment.size} bytes)")

    if role:
        parts.append(f"**Role:** {role.name}")

    parts.append(f"**Template:** {template}")

    await ctx.respond("\n".join(parts))


# ------------------------------------------------------------------
# Autocomplete handler (basic but functional)
# ------------------------------------------------------------------

@bot.autocomplete("configure", "template")
async def configure_template_autocomplete(ctx: AutocompleteContext):
    """Simple static + dynamic autocomplete based on what user typed."""
    value = (ctx.value or "").lower()

    suggestions = [
        {"name": "Default Template", "value": "default"},
        {"name": "Advanced Template", "value": "advanced"},
        {"name": "Minimal Template", "value": "minimal"},
        {"name": "Debug Template", "value": "debug"},
    ]

    if value:
        suggestions = [s for s in suggestions if value in s["name"].lower() or value in str(s["value"]).lower()]

    # Handler can either return the list or call respond
    await ctx.respond(suggestions)   # framework will also handle if you just return the list


# ------------------------------------------------------------------
# Registration + ready
# ------------------------------------------------------------------

bot.add_command(userinfo)
bot.add_command(configure)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Slash command demo ready as {bot.user}")
    print("   Try /userinfo, /configure in Discord (commands must be synced by the framework on READY).")
    print("   Autocomplete is registered for the 'template' option of /configure.")


if __name__ == "__main__":
    bot.run()
