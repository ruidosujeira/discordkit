"""
A functional (demo) ticket system using DiscordKit.

Features shown:
- Button interactions to open tickets
- Modal for ticket reason
- Subcommands for staff to manage tickets (close, etc.)
- Use of cache (optional)
- Clean separation of concerns
"""

import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command
from discordkit.components import ButtonContext, ModalContext
from discordkit.core.context import CommandContext
from discordkit.interactions import Button, Modal
from discordkit.types import ButtonStyle, Intents

load_dotenv()

config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT)
bot = Client(config)

# In a real system you would persist this (DB, etc.)
OPEN_TICKETS: dict[int, dict] = {}  # channel_id -> ticket info


@command(name="ticket", description="Open a support ticket")
async def ticket_cmd(ctx: CommandContext):
    """Slash command that sends a button to open a ticket."""
    btn = Button(
        label="Open Ticket",
        style=ButtonStyle.PRIMARY,
        custom_id="open_ticket",
    )

    await ctx.respond(
        "Need help? Click the button below to create a private ticket.",
        components=[{"type": 1, "components": [btn.to_dict()]}],
    )


@bot.component("open_ticket")
async def open_ticket_button(ctx: ButtonContext):
    """Button that opens a modal to collect ticket reason."""
    modal = Modal(title="Create Support Ticket", custom_id="ticket_modal")
    modal.add_text_input(
        label="What is your issue?",
        custom_id="issue",
        style=2,  # paragraph
        placeholder="Describe your problem...",
        required=True,
        max_length=1500,
    )

    # Respond with the modal
    await ctx.http.create_interaction_response(
        ctx.interaction_id,
        ctx.interaction_token,
        payload={
            "type": 9,  # MODAL
            "data": modal.to_dict(),
        },
    )


@bot.modal("ticket_modal")
async def handle_ticket_modal(ctx: ModalContext):
    """Modal submit -> creates a 'ticket' (in this demo just responds)."""
    issue = ctx.get_value("issue") or "No description"

    # In real bot: create a private thread/channel and store it
    ticket_id = hash(ctx.user.id if ctx.user else 0) % 100000

    OPEN_TICKETS[ticket_id] = {
        "user_id": getattr(ctx.user, "id", None),
        "issue": issue,
    }

    await ctx.respond(
        f"✅ Ticket #{ticket_id} created!\n"
        f"**Issue:** {issue}\n"
        "A staff member will assist you shortly.",
        ephemeral=True,
    )


@command(name="close-ticket", description="Close a ticket (staff only)")
async def close_ticket(
    ctx: CommandContext,
    ticket_id: Annotated[int, Option("Ticket ID to close")],
):
    if ticket_id in OPEN_TICKETS:
        del OPEN_TICKETS[ticket_id]
        await ctx.respond(f"Ticket #{ticket_id} has been closed.", ephemeral=True)
    else:
        await ctx.respond("Ticket not found.", ephemeral=True)


bot.add_command(ticket_cmd)
bot.add_command(close_ticket)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Ticket system demo ready as {bot.user}")


if __name__ == "__main__":
    bot.run()
