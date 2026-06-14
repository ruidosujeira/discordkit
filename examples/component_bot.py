"""
Example demonstrating the new component + modal routing system.

Run with a valid token:
    DISCORD_TOKEN=... python examples/component_bot.py
"""
import os
from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import command
from discordkit.components import ButtonContext, ModalContext, SelectContext
from discordkit.interactions import Button, Modal, SelectMenu
from discordkit.types import ButtonStyle, Intents

load_dotenv()

config = Config(
    token=os.environ["DISCORD_TOKEN"],
    intents=Intents.DEFAULT,
    debug=True,
)

bot = Client(config)


# ------------------------------------------------------------------
# Slash command that sends interactive components
# ------------------------------------------------------------------

@command(name="demo", description="Show interactive components demo")
async def demo(ctx):
    # Buttons
    confirm = Button(label="Confirm", style=ButtonStyle.SUCCESS, custom_id="confirm_action")
    cancel = Button(label="Cancel", style=ButtonStyle.DANGER, custom_id="cancel_action")

    # Select
    color_select = SelectMenu(
        custom_id="favorite_color",
        placeholder="Pick your favorite color",
        options=[
            {"label": "Red", "value": "red"},
            {"label": "Blue", "value": "blue"},
            {"label": "Green", "value": "green"},
        ],
    )

    await ctx.respond(
        "Try the buttons and the select menu below!",
        components=[
            {"type": 1, "components": [confirm.to_dict(), cancel.to_dict()]},
            {"type": 1, "components": [color_select.to_dict()]},
            # A button that opens a modal
            {
                "type": 1,
                "components": [
                    Button(
                        label="Give feedback",
                        style=ButtonStyle.SECONDARY,
                        custom_id="open_feedback_modal",
                    ).to_dict()
                ],
            },
        ],
    )


# ------------------------------------------------------------------
# Component handlers using the new @bot.component decorator
# ------------------------------------------------------------------

@bot.component("confirm_action")
async def on_confirm(ctx: ButtonContext):
    await ctx.edit_message(content="✅ Confirmed! Thank you.", components=[])


@bot.component("cancel_action")
async def on_cancel(ctx: ButtonContext):
    await ctx.edit_message(content="❌ Cancelled.", components=[])


@bot.component("favorite_color")
async def on_color_select(ctx: SelectContext):
    value = ctx.values[0] if ctx.values else "nothing"
    await ctx.respond(f"You selected **{value}**!", ephemeral=True)


@bot.component("open_feedback_modal")
async def on_open_modal(ctx: ButtonContext):
    # We respond with a modal (using the raw payload for now;
    # a nicer Modal builder integration can be added later)
    modal_payload = {
        "type": 9,  # MODAL
        "data": {
            "custom_id": "feedback_modal",
            "title": "Send Feedback",
            "components": [
                {
                    "type": 1,
                    "components": [
                        {
                            "type": 4,
                            "custom_id": "feedback_text",
                            "label": "What do you think?",
                            "style": 2,
                            "required": True,
                            "placeholder": "Your thoughts...",
                            "max_length": 500,
                        }
                    ],
                }
            ],
        },
    }
    # Because this is a component interaction, we must respond with the modal directly
    # using the low-level interaction response for now.
    await ctx.http.create_interaction_response(
        ctx.interaction_id,  # type: ignore
        ctx.interaction_token,  # type: ignore
        payload=modal_payload,
    )


# ------------------------------------------------------------------
# Modal handler
# ------------------------------------------------------------------

@bot.modal("feedback_modal")
async def on_feedback(ctx: ModalContext):
    text = ctx.get_value("feedback_text") or ""
    await ctx.respond(f"🎉 Thanks for the feedback!\n> {text}", ephemeral=True)


# ------------------------------------------------------------------
# Ready
# ------------------------------------------------------------------

@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Component demo bot ready as {bot.user}")
    print("   Use /demo in a channel where the bot is present.")


if __name__ == "__main__":
    bot.run()
