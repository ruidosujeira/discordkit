"""
Advanced Command Options Example for DiscordKit.

This demonstrates the powerful Annotated + Option system.

Features shown:
- Basic types with constraints (min/max length, min/max value)
- choices (both simple and (name, value) form)
- Discord entity types: User, Member, Role, Channel, Attachment
- Optional parameters (using default = None + type | None)
- Autocomplete flag (structure for future full support)
- channel_types filtering

Run (after registering the command via the bot):
    DISCORD_TOKEN=... python examples/advanced_commands.py
"""
from __future__ import annotations

import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command
from discordkit.models import Attachment, Channel, Member, Role, User
from discordkit.types import Intents

load_dotenv()

# Guarded so the module can be imported for payload inspection without a token
_token = os.environ.get("DISCORD_TOKEN")
if _token:
    config = Config(
        token=_token,
        intents=Intents.DEFAULT,
        debug=True,
    )
    bot = Client(config)
else:
    bot = None  # type: ignore[assignment]


@command(
    name="configure",
    description="Advanced configuration command showcasing the Option system",
)
async def configure(
    ctx,
    # --- Basic constrained string ---
    name: Annotated[
        str,
        Option(
            "Display name for the configuration",
            min_length=3,
            max_length=32,
        ),
    ],
    # --- Integer with range + choices ---
    level: Annotated[
        int,
        Option(
            "Power level (1-100)",
            min_value=1,
            max_value=100,
            choices=[("Beginner", 1), ("Intermediate", 25), ("Expert", 75), ("God", 100)],
        ),
    ],
    # --- Float / Number ---
    multiplier: Annotated[
        float,
        Option("Multiplier (0.5x - 5.0x)", min_value=0.5, max_value=5.0),
    ] = 1.0,
    # --- Boolean flag ---
    verbose: Annotated[
        bool,
        Option("Enable verbose output / logging"),
    ] = False,
    # --- Discord User (resolves to User object at runtime in the future) ---
    # --- Optional User ---
    target_user: Annotated[
        User | None,
        Option("The user this configuration applies to (optional)"),
    ] = None,
    # --- Optional Role ---
    role: Annotated[
        Role | None,
        Option("Role to assign (optional)"),
    ] = None,
    # --- Channel with filtering (only text + announcement channels) ---
    target_channel: Annotated[
        Channel | None,
        Option(
            "Channel where the result will be posted (optional)",
            channel_types=[0, 5],
        ),
    ] = None,
    # --- Attachment (for uploading files, images, etc) ---
    reference_file: Annotated[
        Attachment | None,
        Option("Optional reference file / image"),
    ] = None,
    # --- Example of autocomplete (structure ready) ---
    template: Annotated[
        str,
        Option(
            "Template to use (supports autocomplete in the future)",
            autocomplete=True,
        ),
    ] = "default",
):
    """Demonstrates many different Option features at once."""

    parts = [
        f"**Name:** {name}",
        f"**Level:** {level}",
        f"**Multiplier:** {multiplier}x",
        f"**Verbose:** {verbose}",
    ]

    if target_user:
        parts.append(f"**Target:** {target_user.mention} ({target_user.display_name})")

    if role:
        parts.append(f"**Role:** {role.mention}")

    if target_channel:
        parts.append(f"**Channel:** {target_channel.mention}")

    if reference_file:
        parts.append(f"**Attachment:** {reference_file.filename} ({reference_file.size} bytes)")

    parts.append(f"**Template:** {template}")

    await ctx.respond("\n".join(parts))


# Simpler individual examples -------------------------------------------------

@command(name="ban", description="Ban a user with reason and duration")
async def ban(
    ctx,
    user: Annotated[User, Option("User to ban")],
    reason: Annotated[
        str,
        Option("Reason for the ban", min_length=5, max_length=400),
    ],
    delete_messages_days: Annotated[
        int,
        Option("How many days of messages to delete", min_value=0, max_value=7),
    ] = 0,
    notify_user: Annotated[
        bool,
        Option("DM the user about the ban?"),
    ] = True,
):
    await ctx.respond(
        f"Banning {user.mention} for '{reason}'. "
        f"Delete messages: {delete_messages_days}d. Notify: {notify_user}"
    )


@command(name="poll", description="Create a quick poll with choices")
async def poll(
    ctx,
    question: Annotated[str, Option("The poll question", max_length=100)],
    option_a: Annotated[str, Option("First option")],
    option_b: Annotated[str, Option("Second option")],
    duration_minutes: Annotated[
        int,
        Option("How long the poll runs", min_value=1, max_value=1440, choices=[("5 min", 5), ("1 hour", 60), ("1 day", 1440)]),
    ] = 60,
):
    await ctx.respond(
        f"**Poll:** {question}\n"
        f"• {option_a}\n"
        f"• {option_b}\n"
        f"Duration: {duration_minutes} minutes"
    )


# Register the commands with the bot (required for sync + payload demo)
if bot is not None:
    bot.add_command(configure)
    bot.add_command(ban)
    bot.add_command(poll)


if bot is not None:
    @bot.event("ready")
    async def on_ready(ctx):
        print(f"✅ Advanced options demo ready as {bot.user}")
        print("   Use /configure, /ban or /poll (after the commands are synced).")

        # Demo: show what the payload looks like (very useful for debugging)
        print("\n--- Example generated payload for /configure ---")
        import json

        configure_cmd = getattr(configure, "_discordkit_command", configure)
        if hasattr(configure_cmd, "to_discord_payload"):
            payload = configure_cmd.to_discord_payload()
            print(json.dumps(payload.get("options", []), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    if bot is None:
        print("Set DISCORD_TOKEN to run the example.")
    else:
        bot.run()
