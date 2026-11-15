# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Radio button group coordinator."""

from typing import Any

from ..widget import Widget
from .radio_button import RadioButton

class RadioGroup(Widget):
    """Invisible coordinator that enforces single radio selection."""

    radio_buttons: list[RadioButton]
    def __init__(self, parent: Widget) -> None: ...
    def invalidate(self) -> None:
        """No-op: an invisible, zero-size group never needs redrawing."""
    def draw(self, area: Any = None) -> None:
        """No-op: the group draws nothing."""
    def add(self, radio_button: RadioButton) -> None:
        """Add a radio button to the group."""
    def set_checked(self, selected_button: RadioButton) -> None:
        """Check `selected_button` and uncheck every other button in the group."""
