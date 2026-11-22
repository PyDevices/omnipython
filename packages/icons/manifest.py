# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# Freezing icons into a firmware. Frozen, the font in _material.py stays in
# flash and ttfio draws from it in place; the firmware needs ttfio, the C
# module. lvgl.py only imports where LVGL is built in.
metadata(
    description="Material Symbols icons at any size, drawn from a font that stays in flash.",
    version="0.0.1",
    license="MIT AND Apache-2.0",
)

package("icons", files=("__init__.py", "_material.py", "gfx.py", "lvgl.py"))
