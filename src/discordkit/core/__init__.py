"""
discordkit.core
===============

Core building blocks: Client, Config, Context, low-level HTTP and Gateway.
"""

from .cache import CacheBackend, CacheStats, EvictionPolicy, MemoryCache
from .cache_persistent import PersistentCache
from .client import Client
from .config import Config
from .context import AutocompleteContext, CommandContext, Context, InteractionContext
from .gateway import Gateway, GatewayEvent
from .http import DiscordHTTPClient, DiscordHTTPError

__all__ = [
    "AutocompleteContext",
    "CacheBackend",
    "CacheStats",
    "Client",
    "CommandContext",
    "Config",
    "Context",
    "DiscordHTTPClient",
    "DiscordHTTPError",
    "EvictionPolicy",
    "Gateway",
    "GatewayEvent",
    "InteractionContext",
    "MemoryCache",
    "PersistentCache",
]
