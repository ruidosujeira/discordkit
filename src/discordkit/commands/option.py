"""
discordkit.commands.option
==========================

Powerful, first-class support for slash command options using `Annotated` + `Option`.

This is one of the flagship DX features of DiscordKit.

Usage:
    from typing import Annotated
    from discordkit.commands import Option, command
    from discordkit.models import User, Role, Channel

    @command(description="Configure something")
    async def config(
        ctx,
        name: Annotated[str, Option("The display name", min_length=2, max_length=32)],
        level: Annotated[int, Option("Power level", min_value=1, max_value=100, choices=[("Low", 1), ("High", 50)])],
        target: Annotated[User, Option("The user to affect")],
        channel: Annotated[Channel, Option("Target channel", channel_types=[0, 5])],  # text + forum
        role: Annotated[Role | None, Option("Optional role to assign")] = None,
    ):
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from ..types import ApplicationCommandOptionType

# =============================================================================
# Public Option metadata class
# =============================================================================


@dataclass(slots=True)
class Option:
    """Rich metadata for a slash command parameter.

    Use inside `Annotated`:

        level: Annotated[int, Option("User level", min_value=0, max_value=100)]

    All fields are strongly validated at command registration time.
    """

    # Required (first positional arg for excellent DX)
    description: str

    # Behavior
    required: bool | None = None          # None = auto-detect from default value
    autocomplete: bool = False

    # Constraints (type dependent)
    min_length: int | None = None
    max_length: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None

    # Fixed choices (great DX)
    # Accepts:
    #   - ["red", "blue"]
    #   - [("Red", "red"), ("Blue", "blue")]
    #   - [{"name": "Red", "value": "red"}, ...]
    choices: Sequence[str | int | float | tuple[str, Any] | dict[str, Any]] | None = None

    # For CHANNEL options
    channel_types: list[int] | None = None

    # ------------------------------------------------------------------
    # Internal / advanced
    # ------------------------------------------------------------------
    # Future: autocomplete handler reference
    _autocomplete_handler: Any | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.description or not self.description.strip():
            raise ValueError("Option.description cannot be empty")

        # Normalize choices into canonical list[dict]
        if self.choices is not None:
            self.choices = self._normalize_choices(self.choices)

        # Basic sanity checks (full validation happens later with type info)
        if self.min_length is not None and self.min_length < 0:
            raise ValueError("min_length must be >= 0")
        if self.max_length is not None and self.max_length < 0:
            raise ValueError("max_length must be >= 0")
        if (
            self.min_length is not None
            and self.max_length is not None
            and self.min_length > self.max_length
        ):
            raise ValueError("min_length cannot be greater than max_length")

        if (
            self.min_value is not None
            and self.max_value is not None
            and self.min_value > self.max_value
        ):
            raise ValueError("min_value cannot be greater than max_value")

        if self.choices and self.autocomplete:
            raise ValueError("cannot use both choices and autocomplete")

    @staticmethod
    def _normalize_choices(raw: Sequence[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in raw:
            if isinstance(item, dict):
                if "name" not in item or "value" not in item:
                    raise ValueError(f"Choice dict must have 'name' and 'value': {item}")
                normalized.append({"name": str(item["name"]), "value": item["value"]})
            elif isinstance(item, (list, tuple)) and len(item) == 2:
                name, value = item
                normalized.append({"name": str(name), "value": value})
            else:
                # Simple value -> name is str(value)
                normalized.append({"name": str(item), "value": item})
        return normalized

    def __repr__(self) -> str:
        return f"Option({self.description!r}, required={self.required})"


# =============================================================================
# Type aliases for beautiful command signatures (optional but nice DX)
# =============================================================================

# Users can also import these for clarity:
# from discordkit.commands import UserOption, ChannelOption, ...

# For runtime, people usually just use the model classes directly in Annotated.

# =============================================================================
# Advanced option building (used by Command)
# =============================================================================

import inspect
from typing import TYPE_CHECKING, Any, Callable, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from ..models import Attachment, Channel, Member, Message, Role, User

try:
    from types import UnionType  # Python 3.10+
except ImportError:
    UnionType = None  # type: ignore[misc,assignment]

from ..types import ApplicationCommandOptionType

# Mapping of Python / DiscordKit types -> Discord API option type
_TYPE_TO_OPTION: dict[Any, ApplicationCommandOptionType] = {
    str: ApplicationCommandOptionType.STRING,
    int: ApplicationCommandOptionType.INTEGER,
    bool: ApplicationCommandOptionType.BOOLEAN,
    float: ApplicationCommandOptionType.NUMBER,
}

# Will be populated after models are imported (see bottom of file)
_DISCORD_TYPE_TO_OPTION: dict[Any, ApplicationCommandOptionType] = {}


def _get_discord_type_mapping() -> dict[Any, ApplicationCommandOptionType]:
    """Lazy import to avoid circular dependencies."""
    global _DISCORD_TYPE_TO_OPTION
    if _DISCORD_TYPE_TO_OPTION:
        return _DISCORD_TYPE_TO_OPTION

    # Import here to prevent circular import at module load
    from ..models import Attachment, Channel, Member, Message, Role, User

    _DISCORD_TYPE_TO_OPTION = {
        User: ApplicationCommandOptionType.USER,
        Member: ApplicationCommandOptionType.USER,  # Members are resolved as users in options
        Role: ApplicationCommandOptionType.ROLE,
        Channel: ApplicationCommandOptionType.CHANNEL,
        # Message is rarely used as option type (usually via context), but supported for completeness
        Message: ApplicationCommandOptionType.STRING,  # fallback, real message options aren't direct
        Attachment: ApplicationCommandOptionType.ATTACHMENT,
    }
    return _DISCORD_TYPE_TO_OPTION


def _is_optional(annotation: Any) -> bool:
    """Return True if annotation represents an optional type (T | None / Optional[T])."""
    origin = get_origin(annotation)
    if origin is UnionType:
        args = get_args(annotation)
        return type(None) in args
    # typing.Union / Optional
    if origin is getattr(__import__("typing"), "Union", None):
        args = get_args(annotation)
        return type(None) in args
    return False


def _unwrap_optional(annotation: Any) -> Any:
    """Return the inner type from Optional[T] / T | None."""
    origin = get_origin(annotation)
    if origin is UnionType or origin is getattr(__import__("typing"), "Union", None):
        args = [a for a in get_args(annotation) if a is not type(None)]
        return args[0] if args else annotation
    return annotation


def _extract_annotated_metadata(annotation: Any) -> tuple[Any, list[Any]]:
    """Given an annotation that may be Annotated[T, Option(...), ...], return (T, [metadata...])."""
    origin = get_origin(annotation)
    if origin is not None and origin.__name__ == "Annotated":
        args = get_args(annotation)
        if args:
            base_type = args[0]
            metadata = list(args[1:])
            return base_type, metadata
    return annotation, []


def resolve_application_option_type(annotation: Any) -> ApplicationCommandOptionType:
    """Resolve a Python type annotation to a Discord ApplicationCommandOptionType."""
    # Handle Optional first
    if _is_optional(annotation):
        annotation = _unwrap_optional(annotation)

    # Annotated handling (strip metadata for base type)
    base, _ = _extract_annotated_metadata(annotation)
    annotation = base

    # Direct known types
    if annotation in _TYPE_TO_OPTION:
        return _TYPE_TO_OPTION[annotation]

    # Discord model types (lazy)
    discord_map = _get_discord_type_mapping()
    if annotation in discord_map:
        return discord_map[annotation]

    # Fallbacks for string annotations (when from __future__ annotations)
    if isinstance(annotation, str):
        lower = annotation.lower()
        if lower in ("str", "string"):
            return ApplicationCommandOptionType.STRING
        if lower in ("int", "integer"):
            return ApplicationCommandOptionType.INTEGER
        if lower in ("bool", "boolean"):
            return ApplicationCommandOptionType.BOOLEAN
        if lower in ("float", "number"):
            return ApplicationCommandOptionType.NUMBER
        if lower in ("user", "discordkit.models.user.user"):
            return ApplicationCommandOptionType.USER
        if lower in ("member",):
            return ApplicationCommandOptionType.USER
        if lower in ("role", "discordkit.models.role.role"):
            return ApplicationCommandOptionType.ROLE
        if lower in ("channel", "discordkit.models.guild.channel"):
            return ApplicationCommandOptionType.CHANNEL
        if lower in ("attachment", "discordkit.models.message.attachment"):
            return ApplicationCommandOptionType.ATTACHMENT

    # Default to string (lenient)
    return ApplicationCommandOptionType.STRING


def build_option_dict(
    param_name: str,
    annotation: Any,
    default: Any = inspect.Parameter.empty,
    explicit_option: Option | None = None,
) -> dict[str, Any]:
    """Build a single Discord API option dict from a function parameter.

    This is the heart of the advanced options system.
    """
    # Extract base type + any Option from Annotated
    base_annotation, metadata = _extract_annotated_metadata(annotation)

    option_meta: Option | None = explicit_option
    for m in metadata:
        if isinstance(m, Option):
            if option_meta is not None:
                # Multiple Option() in Annotated is weird — last wins
                pass
            option_meta = m
            break

    # Resolve the Discord type
    opt_type = resolve_application_option_type(base_annotation if base_annotation is not inspect.Parameter.empty else str)

    # Determine if required
    is_required: bool
    if option_meta is not None and option_meta.required is not None:
        is_required = option_meta.required
    else:
        # Auto-infer: has no default or default is Ellipsis -> required
        is_required = default is inspect.Parameter.empty

    option: dict[str, Any] = {
        "name": param_name,
        "description": (option_meta.description if option_meta else f"{param_name} parameter"),
        "type": int(opt_type),
        "required": is_required,
    }

    # Add constraints from Option
    if option_meta:
        if option_meta.min_length is not None:
            option["min_length"] = option_meta.min_length
        if option_meta.max_length is not None:
            option["max_length"] = option_meta.max_length
        if option_meta.min_value is not None:
            option["min_value"] = option_meta.min_value
        if option_meta.max_value is not None:
            option["max_value"] = option_meta.max_value
        if option_meta.choices:
            option["choices"] = option_meta.choices
        if option_meta.autocomplete:
            option["autocomplete"] = True
        if option_meta.channel_types:
            option["channel_types"] = option_meta.channel_types

        # Type-specific adjustments
        if opt_type == ApplicationCommandOptionType.CHANNEL and option_meta.channel_types:
            option["channel_types"] = option_meta.channel_types

    # Final validation (lightweight)
    _validate_option_dict(option, opt_type, param_name)

    return option


def _validate_option_dict(option: dict[str, Any], opt_type: ApplicationCommandOptionType, param_name: str) -> None:
    """Raise clear errors for obviously invalid Option configurations."""
    name = option["name"]

    if "choices" in option and option.get("autocomplete"):
        raise ValueError(f"Parameter '{param_name}': cannot use both choices and autocomplete")

    if opt_type in (ApplicationCommandOptionType.STRING,):
        if "min_value" in option or "max_value" in option:
            raise ValueError(f"Parameter '{param_name}': min_value/max_value only valid for INTEGER or NUMBER")
    elif opt_type in (ApplicationCommandOptionType.INTEGER, ApplicationCommandOptionType.NUMBER):
        if "min_length" in option or "max_length" in option:
            raise ValueError(f"Parameter '{param_name}': min_length/max_length only valid for STRING")

    if "channel_types" in option and opt_type != ApplicationCommandOptionType.CHANNEL:
        raise ValueError(f"Parameter '{param_name}': channel_types can only be used with Channel options")


def build_options_from_signature(callback: Callable[..., Any]) -> list[dict[str, Any]]:
    """Parse a command callback signature and return a list of Discord option dicts.

    Supports the full Annotated[T, Option(...)] system with excellent DX.
    """
    try:
        sig = inspect.signature(callback)
    except (ValueError, TypeError):
        return []

    # Use get_type_hints with include_extras so Annotated metadata is preserved
    try:
        type_hints = get_type_hints(callback, include_extras=True)
    except Exception:
        type_hints = {}

    options: list[dict[str, Any]] = []

    for param_name, param in sig.parameters.items():
        if param_name in {"self", "ctx", "context"}:
            continue

        annotation = type_hints.get(param_name, param.annotation)
        if annotation is inspect.Parameter.empty:
            annotation = str  # fallback

        default = param.default

        option_dict = build_option_dict(param_name, annotation, default)
        options.append(option_dict)

    return options


__all__ = ["Option", "build_options_from_signature", "build_option_dict", "resolve_application_option_type"]

