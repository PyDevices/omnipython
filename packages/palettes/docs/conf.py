# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Sphinx configuration for the palettes documentation.

Everything shared by the OmniPython documentation projects (theme, top bar,
Markdown and docstring setup, the reference map) comes from omnipython-docs.
"""

from omnipython_docs import configure

globals().update(configure(
    "palettes", __file__,
    repo="PyDevices/omnipython", edit_path="packages/palettes/docs",
    source_dirs=["../lib"], api_packages=["palettes"],
    version_file="../VERSION",
))
