"""
Simple standalone DiscordKit example.

Run with:
    DISCORD_TOKEN=... python examples/simple_bot.py
"""

import os

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import command
from discordkit.types import Intents

load_dotenv()

config = Config(
    token=os.environ["DISCORD_TOKEN"],
    intents=Intents.DEFAULT,
    debug=True,
)

bot = Client(config)


@command(name="ping", description="Classic ping command")
async def ping(ctx):
    await ctx.respond("Pong! 🏓")


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Logged in as {bot.user}")


# Example of component registration (uncomment + send a message with the button)
# @bot.component("demo_btn")
# async def demo_btn(ctx):
#     await ctx.respond("Button clicked via @bot.component!", ephemeral=True)


if __name__ == "__main__":
    bot.run()
