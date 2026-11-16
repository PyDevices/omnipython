# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Sphinx configuration for the OmniPython documentation.

Everything shared by the OmniPython documentation projects (theme, top bar,
Markdown and docstring setup, the reference map) comes from omnipython-docs.
"""

from omnipython_docs import configure

globals().update(configure(
    "omnipython", __file__,
    repo="PyDevices/omnipython", edit_path="docs",
    source_dirs=["../lib", "../utils", "../packages/vtterm"],
    api_packages=["displaydev", "audiodev", "appdev", "multimer", "bledev", "vtterm"],
    mock_imports=["bleak", "_bleio", "bluetooth", "IPython", "pygame", "js",
                  "pyodide", "_wasm_bridge", "uwin32", "aioble", "PIL", "lvgl",
                  # vtterm draws with pygraphics and colors from palettes.
                  "pygraphics", "palettes", "usb"],
    # windisplay builds window styles from uwin32 constants at import time,
    # which a mock cannot stand in for.
    api_skip=["windisplay"],
    version_file="../VERSION",
))

# index.md is plain Markdown so the docs read on GitHub too; the site
# navigation lives in contents.md.
master_doc = "contents"
