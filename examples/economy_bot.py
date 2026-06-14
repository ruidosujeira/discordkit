"""
Advanced Economy / Levels Bot Example

Demonstrates excellent use of:
- Deep command hierarchy with subcommands (/economy balance, /economy give, /levels rank)
- Smart use of the built-in cache for user data
- Proper Option usage with validation
- Error handling patterns
- Caching resolved users automatically via the resolver

This is a self-contained demo. In production you would persist data (DB/JSON).
"""

import os
from dataclasses import dataclass, field
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command, group
from discordkit.core.context import CommandContext
from discordkit.models import User
from discordkit.types import Intents

load_dotenv()


@dataclass
class UserEconomy:
    balance: int = 100
    xp: int = 0
    level: int = 1


# In-memory store for the demo (use real DB in production)
ECONOMY_DATA: dict[int, UserEconomy] = {}


def get_economy(user_id: int) -> UserEconomy:
    if user_id not in ECONOMY_DATA:
        ECONOMY_DATA[user_id] = UserEconomy()
    return ECONOMY_DATA[user_id]


config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT)
bot = Client(config)


# --- Economy Group with subcommands ---

@group(name="economy", description="Economy and currency commands")
async def economy_group(ctx: CommandContext):
    pass


@economy_group.command(name="balance", description="Check your or someone else's balance")
async def economy_balance(
    ctx: CommandContext,
    user: Annotated[User | None, Option("User to check (defaults to you)")] = None,
):
    target = user or ctx.user
    if not target or not target.id:
        await ctx.respond("Could not determine user.", ephemeral=True)
        return

    # Cache is automatically populated when the option resolver runs
    cached = bot.cache.get_user(target.id)
    if cached:
        print(f"[CACHE] Hit for user {target.id}")

    eco = get_economy(target.id)
    await ctx.respond(f"**{target.display_name}** has **{eco.balance}** coins (Level {eco.level}).")


@economy_group.command(name="give", description="Give coins to another user")
async def economy_give(
    ctx: CommandContext,
    user: Annotated[User, Option("User to give coins to")],
    amount: Annotated[int, Option("Amount of coins", min_value=1, max_value=10000)],
):
    if not ctx.user or not ctx.user.id:
        return

    if user.id == ctx.user.id:
        await ctx.respond("You cannot give coins to yourself.", ephemeral=True)
        return

    sender = get_economy(ctx.user.id)
    receiver = get_economy(user.id)

    if sender.balance < amount:
        await ctx.respond("You don't have enough coins.", ephemeral=True)
        return

    sender.balance -= amount
    receiver.balance += amount

    await ctx.respond(f"Gave **{amount}** coins to {user.mention}.")


# --- Levels Group ---

@group(name="levels", description="XP and leveling system")
async def levels_group(ctx: CommandContext):
    pass


@levels_group.command(name="rank", description="Show your current level and XP")
async def levels_rank(ctx: CommandContext):
    if not ctx.user or not ctx.user.id:
        return
    eco = get_economy(ctx.user.id)
    await ctx.respond(f"**{ctx.user.display_name}** — Level **{eco.level}** | XP: **{eco.xp}**")


@levels_group.command(name="add-xp", description="Add XP to a user (admin only in real bots)")
async def levels_add_xp(
    ctx: CommandContext,
    user: Annotated[User, Option("User to give XP")],
    amount: Annotated[int, Option("XP amount", min_value=1, max_value=5000)],
):
    eco = get_economy(user.id)
    eco.xp += amount
    # Simple level up logic
    new_level = 1 + (eco.xp // 100)
    if new_level > eco.level:
        eco.level = new_level
        await ctx.respond(f"{user.mention} leveled up to **Level {eco.level}**!")
    else:
        await ctx.respond(f"Added **{amount}** XP to {user.mention}.")


# Register groups
bot.add_command(economy_group)
bot.add_command(levels_group)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Economy/Levels bot ready as {bot.user}")
    print("   Try /economy balance, /economy give, /levels rank, /levels add-xp")


if __name__ == "__main__":
    bot.run()
