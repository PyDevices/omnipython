# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

# Freezing endpointkit into a firmware. Both modules are pure Python with no
# LVGL and run on MicroPython and CPython; fake is only for tests and demos,
# so a board may leave it out.
metadata(
    description="One list of everything a device connects to, by kind, and one choice per kind.",
    version="0.0.1",
    license="MIT",
)

package("endpointkit", files=("__init__.py", "fake.py"))
