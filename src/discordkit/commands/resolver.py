"""
discordkit.commands.resolver
============================

Automatic resolution of slash command option values from raw Discord interaction data
into rich Python objects (User, Member, Role, Channel, Attachment, primitives).

This makes `ctx.options["user"]` return an actual `User` instance when the option
was declared as `user: Annotated[User, Option(...)]`.
"""

from __future__ import annotations

import inspect
from typing import Any, get_type_hints

from ..models import Attachment, Channel, Member, Role, User
from ..types import ApplicationCommandOptionType
from .command import Command

# Map Discord option type -> model (for resolution)
_OPTION_TYPE_TO_MODEL: dict[int, type] = {
    ApplicationCommandOptionType.USER: User,
    ApplicationCommandOptionType.ROLE: Role,
    ApplicationCommandOptionType.CHANNEL: Channel,
    ApplicationCommandOptionType.ATTACHMENT: Attachment,
}


def _get_expected_type_for_param(callback: Any, param_name: str) -> Any:
    """Try to get the actual annotation for a parameter (supports Annotated)."""
    try:
        hints = get_type_hints(callback, include_extras=True)
        return hints.get(param_name)
    except Exception:
        return None


def _unwrap_annotated(annotation: Any) -> Any:
    """Strip Annotated[...] wrapper and return the base type."""
    from typing import get_args, get_origin

    origin = get_origin(annotation)
    if origin is not None and origin.__name__ == "Annotated":
        args = get_args(annotation)
        if args:
            return args[0]
    return annotation


def _is_member_type(ann: Any) -> bool:
    """Check if the annotation wants a Member (or Optional[Member])."""
    base = _unwrap_annotated(ann)
    # Handle Optional
    from typing import get_origin, get_args
    origin = get_origin(base)
    if origin is not None:
        # Union / | None
        args = get_args(base)
        for a in args:
            if a is Member or (isinstance(a, type) and issubclass(a, Member)):
                return True
    return base is Member or (isinstance(base, type) and issubclass(base, Member))


def resolve_options(command: Command, interaction: dict[str, Any]) -> dict[str, Any]:
    """
    Resolve the options from a raw APPLICATION_COMMAND interaction into
    a clean dict of name -> value (with models where appropriate).

    Uses the command's callback type hints + the "resolved" object provided by Discord.
    """
    data = interaction.get("data", {}) or {}
    raw_options = data.get("options", []) or []
    resolved = data.get("resolved", {}) or {}

    # Get the registered callback for type hints (best source of truth)
    callback = command.callback

    # Flatten options (handle simple subcommand nesting at top level for now)
    flat_options: list[dict[str, Any]] = _flatten_options(raw_options)

    result: dict[str, Any] = {}

    for opt in flat_options:
        name: str = opt.get("name")
        raw_value: Any = opt.get("value")
        discord_type: int = opt.get("type", 0)

        if not name:
            continue

        # Start with the raw value (good for str/int/bool/float)
        value: Any = raw_value

        # Try to get the expected annotation from the handler signature
        expected_ann = _get_expected_type_for_param(callback, name)
        base_type = _unwrap_annotated(expected_ann) if expected_ann else None

        # Resolve based on Discord type or expected annotation
        model_cls = _OPTION_TYPE_TO_MODEL.get(discord_type)

        # Special handling for users (can become Member in guild context)
        if discord_type == ApplicationCommandOptionType.USER or (base_type and (base_type is User or base_type is Member)):
            user_id = str(raw_value)
            users = resolved.get("users", {}) or {}
            members = resolved.get("members", {}) or {}

            user_data = users.get(user_id)
            member_data = members.get(user_id)

            if member_data and user_data:
                # Merge for a proper Member
                member_full = {**member_data, "user": user_data}
                try:
                    value = Member.model_validate(member_full)
                except Exception:
                    value = User.model_validate(user_data) if user_data else raw_value
            elif user_data:
                value = User.model_validate(user_data)
            # else: keep raw id as fallback

        elif model_cls is not None:
            key = _get_resolved_key_for_type(discord_type)
            resolved_obj = (resolved.get(key, {}) or {}).get(str(raw_value))
            if resolved_obj:
                try:
                    value = model_cls.model_validate(resolved_obj)
                except Exception:
                    # Fallback to raw if validation fails
                    pass

        # If annotation wants Member but we only got User, keep as-is (user can cast or we improve later)
        result[name] = value

    return result


def _get_resolved_key_for_type(discord_type: int) -> str:
    if discord_type == ApplicationCommandOptionType.USER:
        return "users"
    if discord_type == ApplicationCommandOptionType.ROLE:
        return "roles"
    if discord_type == ApplicationCommandOptionType.CHANNEL:
        return "channels"
    if discord_type == ApplicationCommandOptionType.ATTACHMENT:
        return "attachments"
    return "users"


def _flatten_options(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Recursively flatten options that may contain subcommands or subcommand groups.

    For top-level slash commands with subcommands, the handler is usually registered
    on the root command, and we collect the leaf parameter options.
    """
    flat: list[dict[str, Any]] = []

    for opt in options:
        opt_type = opt.get("type")
        if opt_type in (1, 2):  # SUB_COMMAND or SUB_COMMAND_GROUP
            # Recurse into the sub-options
            sub_options = opt.get("options", []) or []
            flat.extend(_flatten_options(sub_options))
        else:
            flat.append(opt)

    return flat


__all__ = ["resolve_options"]
