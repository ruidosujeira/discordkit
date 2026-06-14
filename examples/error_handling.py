"""
Production-oriented Error Handling Patterns with DiscordKit.

This example shows:
- Global error handler registration
- Graceful degradation (user never sees raw tracebacks)
- Structured logging context
- Per-command recovery when possible
- How the framework protects your 24/7 bot

In real projects you would send `context` + error to Sentry, a Discord logging channel,
or your observability stack.
"""
import logging
import os
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command
from discordkit.core.context import CommandContext
from discordkit.types import Intents

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("mybot")

config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT, debug=False)
bot = Client(config)


# ------------------------------------------------------------------
# Global error handler (highly recommended for production)
# ------------------------------------------------------------------

@bot.error_handler
async def global_error_handler(error: Exception, context: dict):
    cmd = context.get("command", "unknown")
    user = context.get("user_id")
    guild = context.get("guild_id")

    logger.error(
        "Command failed | cmd=%s | user=%s | guild=%s | error=%s",
        cmd, user, guild, error,
        exc_info=True,  # full traceback in logs
    )

    # Example: send to a private logging channel in production
    # log_channel = bot.get_channel(123456789)
    # if log_channel:
    #     await log_channel.send(f"Error in `{cmd}` by <@{user}>: ```{error}```")


# ------------------------------------------------------------------
# Commands that demonstrate different error scenarios
# ------------------------------------------------------------------

@command(name="divide", description="Divide two numbers (can fail)")
async def divide(
    ctx: CommandContext,
    a: Annotated[int, Option("First number")],
    b: Annotated[int, Option("Second number (non-zero)")],
):
    # This will raise ZeroDivisionError if b == 0
    result = a / b
    await ctx.respond(f"{a} / {b} = {result}")


@command(name="risky", description="Command that can raise arbitrary errors")
async def risky(ctx: CommandContext, action: Annotated[str, Option("What to do", choices=["crash", "slow", "ok"])]):
    if action == "crash":
        raise RuntimeError("Something went very wrong on purpose")
    if action == "slow":
        import asyncio
        await asyncio.sleep(10)  # simulate long work without defer (bad practice)
        await ctx.respond("Finished slow work")
    else:
        await ctx.respond("Everything is fine.")


@command(name="safe", description="Command with internal recovery")
async def safe(ctx: CommandContext):
    try:
        # Simulate something that might fail
        raise ValueError("Temporary glitch")
    except Exception as e:
        # Local recovery + still report upward if you want
        logger.warning("Recovered locally from: %s", e)
        await ctx.respond("I handled a small internal error gracefully.", ephemeral=True)
        # Optionally still notify global handlers:
        # raise  # re-raise if you want it logged globally too


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Error handling demo ready as {bot.user}")
    print("   Try /divide 10 0, /risky crash, /safe")
    print("   All errors are caught. Your bot stays alive.")


if __name__ == "__main__":
    bot.run()
