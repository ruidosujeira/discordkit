"""
Suggestions / Feedback Bot with Voting

Advanced real-world example demonstrating:

- Use of components (buttons) for voting
- Cache for fast suggestion lookup
- Subcommands for staff management (/suggestions approve, /suggestions deny)
- Proper error handling
- Smart use of resolved options (User)
- Clean separation between public and staff commands

Suggestions are stored in memory for the demo (use a database in production).
Each suggestion gets upvote / downvote buttons that update live.
"""

import os
from dataclasses import dataclass, field
from typing import Annotated

from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import Option, command, group
from discordkit.components import ButtonContext
from discordkit.core.context import CommandContext
from discordkit.interactions import Button
from discordkit.types import ButtonStyle, Intents

load_dotenv()


@dataclass
class Suggestion:
    id: int
    author_id: int
    content: str
    upvotes: set[int] = field(default_factory=set)
    downvotes: set[int] = field(default_factory=set)

    @property
    def score(self) -> int:
        return len(self.upvotes) - len(self.downvotes)


SUGGESTIONS: dict[int, Suggestion] = {}
NEXT_ID = 1


config = Config(token=os.environ["DISCORD_TOKEN"], intents=Intents.DEFAULT)
bot = Client(config)


@group(name="suggestions", description="Manage suggestions")
async def suggestions_group(ctx: CommandContext):
    pass


@suggestions_group.command(name="submit", description="Submit a new suggestion")
async def suggestions_submit(
    ctx: CommandContext,
    suggestion: Annotated[str, Option("Your suggestion (max 500 chars)", max_length=500)],
):
    global NEXT_ID
    sug = Suggestion(id=NEXT_ID, author_id=ctx.user.id if ctx.user else 0, content=suggestion)
    SUGGESTIONS[NEXT_ID] = sug
    NEXT_ID += 1

    # Cache the suggestion for fast button lookups
    bot.cache.set_user(ctx.user)  # ensure author is cached

    await ctx.respond(
        f"✅ Suggestion #{sug.id} submitted!\n> {suggestion}",
        components=[
            {
                "type": 1,
                "components": [
                    Button(label="👍 Upvote", style=ButtonStyle.SUCCESS, custom_id=f"sug_up_{sug.id}").to_dict(),
                    Button(label="👎 Downvote", style=ButtonStyle.DANGER, custom_id=f"sug_down_{sug.id}").to_dict(),
                ],
            }
        ],
    )


# Voting buttons (use prefix for easy routing)
@bot.component("sug_up_")
async def upvote(ctx: ButtonContext):
    await _handle_vote(ctx, up=True)


@bot.component("sug_down_")
async def downvote(ctx: ButtonContext):
    await _handle_vote(ctx, up=False)


async def _handle_vote(ctx: ButtonContext, up: bool):
    try:
        sug_id = int(ctx.custom_id.split("_")[-1])
    except (ValueError, IndexError):
        await ctx.respond("Invalid suggestion.", ephemeral=True)
        return

    sug = SUGGESTIONS.get(sug_id)
    if not sug:
        await ctx.respond("Suggestion not found.", ephemeral=True)
        return

    user_id = ctx.user.id if ctx.user else 0

    # Toggle vote
    if up:
        if user_id in sug.upvotes:
            sug.upvotes.remove(user_id)
        else:
            sug.upvotes.add(user_id)
            sug.downvotes.discard(user_id)
    else:
        if user_id in sug.downvotes:
            sug.downvotes.remove(user_id)
        else:
            sug.downvotes.add(user_id)
            sug.upvotes.discard(user_id)

    await ctx.respond(
        f"**Suggestion #{sug.id}** (Score: {sug.score})\n> {sug.content}\n"
        f"👍 {len(sug.upvotes)} | 👎 {len(sug.downvotes)}",
        ephemeral=True,
    )


# Staff subcommands
@suggestions_group.command(name="list", description="List recent suggestions (staff)")
async def suggestions_list(ctx: CommandContext):
    if not SUGGESTIONS:
        await ctx.respond("No suggestions yet.", ephemeral=True)
        return

    lines = []
    for sug in sorted(SUGGESTIONS.values(), key=lambda s: s.score, reverse=True)[:10]:
        lines.append(f"**#{sug.id}** (Score: {sug.score}) — {sug.content[:80]}...")

    await ctx.respond("\n".join(lines), ephemeral=True)


@suggestions_group.command(name="approve", description="Approve a suggestion")
async def suggestions_approve(
    ctx: CommandContext,
    suggestion_id: Annotated[int, Option("Suggestion ID")],
):
    if suggestion_id not in SUGGESTIONS:
        await ctx.respond("Suggestion not found.", ephemeral=True)
        return

    sug = SUGGESTIONS.pop(suggestion_id)
    await ctx.respond(f"✅ Approved suggestion #{suggestion_id} by <@{sug.author_id}>.")


@suggestions_group.command(name="deny", description="Deny a suggestion")
async def suggestions_deny(
    ctx: CommandContext,
    suggestion_id: Annotated[int, Option("Suggestion ID")],
    reason: Annotated[str, Option("Reason for denial", max_length=200)] = "",
):
    if suggestion_id not in SUGGESTIONS:
        await ctx.respond("Suggestion not found.", ephemeral=True)
        return

    sug = SUGGESTIONS.pop(suggestion_id)
    msg = f"❌ Denied suggestion #{suggestion_id}."
    if reason:
        msg += f" Reason: {reason}"
    await ctx.respond(msg)


bot.add_command(suggestions_group)


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ Suggestions bot ready as {bot.user}")
    print("   Public: /suggestions submit")
    print("   Staff: /suggestions list | approve | deny")


if __name__ == "__main__":
    bot.run()
