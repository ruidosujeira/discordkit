"""
discordkit.interactions
=======================

First-class support for message components and modals.

v0.1 contains the basic building blocks. Full callback routing will be
added alongside the interaction handling improvements in the Client.
"""

from __future__ import annotations

from .button import Button
from .modal import Modal
from .select import SelectMenu

__all__ = ["Button", "Modal", "SelectMenu"]
