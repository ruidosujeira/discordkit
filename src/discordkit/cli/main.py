"""
discordkit.cli.main
===================

Entry point for the `discordkit` command-line interface.

Current commands:
- `discordkit new <project-name>`  → scaffolds a ready-to-run modern bot

Future commands (planned):
- run          (with watchfiles hot reload)
- sync         (force slash command sync)
- add command  (interactive)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich import print
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

# watchfiles is a required dependency of discordkit
from watchfiles import PythonFilter, run_process

app = typer.Typer(
    name="discordkit",
    help="DiscordKit - Modern Python framework for Discord bots",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()


def _kebab_to_snake(name: str) -> str:
    return name.replace("-", "_").replace(" ", "_").lower()


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + "\n", encoding="utf-8")


@app.command()
def new(
    name: Annotated[str, typer.Argument(help="Name of your new bot project (e.g. my-cool-bot)")],
    *,
    minimal: Annotated[
        bool,
        typer.Option("--minimal", "-m", help="Create a minimal single-file bot (no src layout)"),
    ] = False,
    force: Annotated[
        bool, typer.Option("--force", "-f", help="Overwrite existing directory if it exists")
    ] = False,
) -> None:
    """Create a new DiscordKit bot project with best practices.

    This will generate:
    - pyproject.toml (using uv + modern packaging)
    - src layout (or minimal)
    - A working example bot using slash commands
    - .env.example + README with instructions
    """
    project_name = name.strip()
    if not project_name:
        console.print("[red]Project name cannot be empty[/red]")
        raise typer.Exit(1)

    target_dir = Path(project_name).resolve()
    package_name = _kebab_to_snake(project_name)

    if target_dir.exists() and not force:
        if any(target_dir.iterdir()):
            console.print(
                f"[red]Directory '{target_dir}' already exists and is not empty. "
                "Use --force to overwrite.[/red]"
            )
            raise typer.Exit(1)

    if target_dir.exists() and force:
        shutil.rmtree(target_dir)

    target_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(f"[bold cyan]Creating DiscordKit project:[/] [bold]{project_name}[/]", border_style="cyan"))

    # ------------------------------------------------------------------
    # Root files
    # ------------------------------------------------------------------
    _write_file(
        target_dir / "pyproject.toml",
        f"""[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "{package_name}"
version = "0.1.0"
description = "A Discord bot built with DiscordKit"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
    "discordkit>=0.1.0",
    "python-dotenv>=1.0.1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/{package_name}"]

[tool.uv]
dev-dependencies = ["ruff", "mypy"]
""",
    )

    _write_file(
        target_dir / ".gitignore",
        """__pycache__/
*.py[cod]
.venv/
.env
.env.local
dist/
build/
*.egg-info/
.mypy_cache/
.ruff_cache/
""",
    )

    _write_file(
        target_dir / ".env.example",
        """# Copy this file to .env and fill in your values
DISCORD_TOKEN=your_bot_token_here
# DISCORDKIT_DEBUG=true
""",
    )

    _write_file(
        target_dir / "README.md",
        f"""# {project_name}

A Discord bot built with [DiscordKit](https://github.com/discordkit/discordkit).

## Quick start

```bash
# 1. Install uv (recommended) or use pip
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create and activate virtual environment + install deps
uv sync
# or: python -m venv .venv && source .venv/bin/activate && pip install -e .

# 3. Configure your token
cp .env.example .env
# edit .env and put your token

# 4. Run the bot (with hot reload!)
discordkit run
# or for the module layout:
uv run python -m {package_name}
```

## Development with hot reload

While developing, use the built-in CLI:

```bash
discordkit run                  # auto-detects entrypoint
discordkit run src/{package_name}/bot.py
```

It will automatically restart the bot when you save Python files.

## Features demonstrated

- Strongly typed Client + Config with Pydantic v2
- Slash commands + component routing (`@bot.component`, `@bot.modal`)
- Hot reload with `discordkit run`

Happy botting!
""",
    )

    # ------------------------------------------------------------------
    # Source code
    # ------------------------------------------------------------------
    if minimal:
        # Single file bot
        src_file = target_dir / f"{package_name}.py"
        _write_file(
            src_file,
            f'''"""
{package_name} - A DiscordKit bot (minimal single-file version)
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
    debug=os.getenv("DISCORDKIT_DEBUG", "false").lower() == "true",
)

bot = Client(config)


@command(name="ping", description="Responds with Pong!")
async def ping(ctx):
    """Simple ping command."""
    await ctx.respond("Pong! 🏓")


@command(name="hello", description="Say hello to someone")
async def hello(ctx, name: str = "friend"):
    await ctx.respond(f"Hello {{name}}! 👋")


@bot.event("ready")
async def on_ready(ctx):
    print(f"✅ {{bot.user}} is ready and online!")


if __name__ == "__main__":
    bot.run()

# You can also register components:
# @bot.component("my_button")
# async def on_click(ctx):
#     await ctx.respond("Clicked!", ephemeral=True)
''',
        )
    else:
        # Proper src layout
        src_dir = target_dir / "src" / package_name
        src_dir.mkdir(parents=True, exist_ok=True)

        _write_file(
            src_dir / "__init__.py",
            f'''"""
{package_name}
"""
__version__ = "0.1.0"
''',
        )

        _write_file(
            src_dir / "bot.py",
            f'''"""
{package_name}.bot
==================

Main bot entry point.
"""
import os
from dotenv import load_dotenv

from discordkit import Client, Config
from discordkit.commands import command
from discordkit.types import Intents

from .commands import setup_commands

load_dotenv()

config = Config(
    token=os.environ["DISCORD_TOKEN"],
    intents=Intents.DEFAULT,
    debug=os.getenv("DISCORDKIT_DEBUG", "false").lower() == "true",
)

bot = Client(config)


# Register example commands from the commands package
setup_commands(bot)


@bot.event("ready")
async def on_ready(ctx):
    """Fired when the bot has connected and is ready to receive events."""
    print(f"✅ Bot ready! Logged in as {{bot.user}} ({{bot.user.id if bot.user else 'unknown'}})")
    print(f"   Application ID: {{bot.application_id}}")
    print("   Press Ctrl+C to stop.")


def run() -> None:
    """Entry point used by `python -m {package_name}` or console scripts."""
    bot.run()


if __name__ == "__main__":
    run()
''',
        )

        # Commands package
        cmd_dir = src_dir / "commands"
        cmd_dir.mkdir(exist_ok=True)

        _write_file(
            cmd_dir / "__init__.py",
            '''"""
{package_name}.commands
=======================

Organize all your slash commands and groups here.
"""
from __future__ import annotations

from discordkit import Client
from discordkit.commands import command


def setup_commands(bot: Client) -> None:
    """Register all commands with the bot.

    This pattern keeps your main bot.py clean while allowing
    you to split commands across multiple modules as the project grows.
    """
    # Example commands are registered via decorator + add_command below,
    # but you can also do pure registration:
    #
    # from .info import info
    # bot.add_command(info)

    # We import here so the decorators run and attach ._discordkit_command
    from .basic import ping, hello, info

    bot.add_command(ping)
    bot.add_command(hello)
    bot.add_command(info)
''',
        )

        _write_file(
            cmd_dir / "basic.py",
            '''"""
{package_name}.commands.basic
=============================

Simple example commands demonstrating DiscordKit style.
"""
from discordkit.commands import command
from discordkit.core.context import CommandContext


@command(name="ping", description="Check if the bot is alive")
async def ping(ctx: CommandContext) -> None:
    """Classic ping command."""
    await ctx.respond("Pong! 🏓  (Latency will be shown here in a future version)")


@command(name="hello", description="Greet a user")
async def hello(ctx: CommandContext, name: str = "friend") -> None:
    """Greets the user with an optional name parameter."""
    await ctx.respond(f"Hello **{name}**! Nice to see you here 👋")


@command(name="info", description="Show basic bot information")
async def info(ctx: CommandContext) -> None:
    """Displays information about this bot."""
    await ctx.respond(
        "This bot was created with **DiscordKit** — a modern, strongly-typed "
        "Discord framework focused on great developer experience."
    )
''',
        )

        # Add a __main__.py so `python -m package_name` works nicely
        _write_file(
            src_dir / "__main__.py",
            f'''"""
Allows running the package directly:

    python -m {package_name}
"""
from .bot import run

if __name__ == "__main__":
    run()
''',
        )

    # Final touches
    console.print()
    console.print("[bold green]✓[/] Project created successfully!")
    console.print()
    console.print(f"Next steps:")
    console.print(f"  1. [cyan]cd {project_name}[/cyan]")
    console.print(f"  2. Copy [cyan].env.example[/cyan] to [cyan].env[/cyan] and add your bot token")
    console.print(f"  3. Install dependencies (recommended):")
    console.print(f"     [cyan]uv sync[/cyan]")
    console.print(f"  4. Run your bot:")
    if minimal:
        console.print(f"     [cyan]uv run {package_name}.py[/cyan]   (or python {package_name}.py)")
    else:
        console.print(f"     [cyan]uv run python -m {package_name}[/cyan]")

    console.print()
    console.print(
        Panel(
            "Tip: After creating a bot in the [link=https://discord.com/developers/applications]Developer Portal[/link],\n"
            "remember to enable the necessary Privileged Gateway Intents if you use them.",
            title="[bold]Reminder[/bold]",
            border_style="yellow",
        )
    )


# =============================================================================
# Run command with hot reload
# =============================================================================


def _detect_watch_directories(entry: str, cwd: Path) -> list[str]:
    """Smartly decide which directories to watch for a given entry point."""
    dirs: set[str] = {str(cwd)}

    p = Path(entry)
    if p.exists() and p.is_file():
        # Watching the directory containing the file is good
        dirs.add(str(p.parent.resolve()))
    else:
        # Likely a module (mybot or mybot.bot)
        # Try common layouts generated by `discordkit new`
        for candidate in ("src", ".", "app", "bot"):
            cand = cwd / candidate
            if cand.exists() and cand.is_dir():
                dirs.add(str(cand.resolve()))

    # Always watch the project root
    return sorted(dirs)


@app.command()
def run(
    entry: Annotated[
        str,
        typer.Argument(
            help="Entry point for your bot. Can be a file (bot.py) or a module (mybot.bot or mybot)"
        ),
    ] = "bot.py",
    *,
    reload: Annotated[
        bool,
        typer.Option("--reload/--no-reload", help="Enable hot reload (default: on)")
    ] = True,
    watch: Annotated[
        list[str] | None,
        typer.Option(
            "--watch",
            "-w",
            help="Extra directories to watch (can be used multiple times)",
        ),
    ] = None,
) -> None:
    """Run a DiscordKit bot with automatic hot reload on file changes.

    This is the recommended way to develop bots locally.

    Examples:

        # From inside a project generated by `discordkit new`
        discordkit run                  # looks for bot.py or src layout
        discordkit run src/mybot/bot.py
        discordkit run mybot            # runs as module (python -m mybot)

        # Explicit module
        discordkit run my_cool_bot.bot
    """
    cwd = Path.cwd()

    console.print(Panel.fit(f"[bold cyan]DiscordKit Run[/] — entry: [bold]{entry}[/]", border_style="cyan"))

    if not reload:
        # Simple execution without watching (useful for production or debugging reload)
        console.print("[yellow]Hot reload disabled[/yellow]")
        _execute_entry_once(entry, cwd)
        return

    watch_dirs = _detect_watch_directories(entry, cwd)
    if watch:
        watch_dirs.extend(watch)

    watch_dirs = sorted(set(str(Path(d).resolve()) for d in watch_dirs))

    console.print(f"[dim]Watching directories:[/dim] {', '.join(watch_dirs)}")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")

    python_exec = sys.executable

    # Build the command we will run in the child process
    if Path(entry).exists() and Path(entry).is_file():
        target_args: list[str] = [entry]
        kind = "file"
    else:
        # Treat as importable module
        target_args = ["-m", entry]
        kind = "module"

    def _start_bot() -> None:
        """This runs inside the watchfiles child process manager."""
        # We just want to spawn python with the right args
        import subprocess

        cmd = [python_exec, *target_args]
        console.print(f"[green]→ Starting bot[/green] ({kind}): [bold]{' '.join(cmd)}[/bold]")

        env = os.environ.copy()
        # Ensure the project root is on PYTHONPATH so `python -m pkg` works nicely
        env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")

        try:
            subprocess.run(cmd, env=env, cwd=cwd)
        except KeyboardInterrupt:
            pass

    # Use watchfiles' excellent run_process helper.
    # It will spawn the target in a way that we can restart it cleanly.
    try:
        run_process(
            *watch_dirs,
            target=_start_bot,
            watch_filter=PythonFilter(),
            # Debounce a little so rapid saves don't spam restarts
            debounce=400,
        )
    except KeyboardInterrupt:
        console.print("\n[bold red]Stopped.[/bold red]")


def _execute_entry_once(entry: str, cwd: Path) -> None:
    """Run the bot entrypoint a single time (no reload)."""
    import subprocess

    python_exec = sys.executable
    if Path(entry).exists() and Path(entry).is_file():
        cmd = [python_exec, entry]
    else:
        cmd = [python_exec, "-m", entry]

    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")

    console.print(f"[cyan]Running:[/cyan] {' '.join(cmd)}")
    subprocess.run(cmd, env=env, cwd=cwd)


@app.command()
def version() -> None:
    """Show DiscordKit CLI version."""
    from discordkit import __version__

    print(f"discordkit CLI [bold]{__version__}[/bold]")


def main() -> None:
    """Entrypoint used by the console script in pyproject.toml."""
    app()


if __name__ == "__main__":
    main()
