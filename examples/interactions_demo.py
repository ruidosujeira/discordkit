"""
Demonstrates how to define buttons and modals (callback routing coming soon).
"""

from discordkit.interactions import Button, Modal, SelectMenu
from discordkit.types import ButtonStyle

# Buttons
confirm_btn = Button(
    label="Confirm",
    style=ButtonStyle.SUCCESS,
    custom_id="confirm_action",
)

cancel_btn = Button(
    label="Cancel",
    style=ButtonStyle.DANGER,
    custom_id="cancel_action",
)

# Select
language_select = SelectMenu(
    custom_id="language_select",
    placeholder="Choose your favorite language",
    options=[
        {"label": "Python", "value": "py"},
        {"label": "Rust", "value": "rs"},
        {"label": "TypeScript", "value": "ts"},
    ],
)

# Modal
feedback_modal = Modal(title="Send Feedback", custom_id="feedback_form")
feedback_modal.add_text_input(
    label="What do you think?",
    custom_id="feedback_text",
    style=2,  # paragraph
    required=True,
    max_length=2000,
)

print("Components defined (attach via ctx.respond(components=[...]))")
print("Button payload example:", confirm_btn.to_dict())
