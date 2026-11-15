# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Radio button widget."""

from ..widget import Widget
from .radio_group import RadioGroup
from .toggle import Toggle

class RadioButton(Toggle):
    """Mutually exclusive checked icon; belongs to a `RadioGroup`."""

    group: RadioGroup
    def __init__(self, parent: Widget, x: int = 0, y: int = 0, w: int | None = None, h: int | None = None, align: int | None = None, align_to: Widget | None = None, fg: int | None = None, bg: int | None = None, visible: bool = True, value: bool = False, padding: tuple[int, int, int, int] | None = None, size: int = 36, group: RadioGroup | None = None) -> None: ...
    def toggle(self, data: object = None, event: object = None) -> None:
        """Check this button and uncheck the others in its group."""
