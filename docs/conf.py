# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT

"""Sphinx configuration for the OmniPython documentation.

Everything shared by the OmniPython documentation projects (theme, top bar,
Markdown and docstring setup, the reference map) comes from omnipython-docs.
"""

import json
from pathlib import Path

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


_REPO = Path(__file__).resolve().parent.parent


def _tested_table(repo):
    """The tested-boards table, written from the ``tested.json`` records beside
    each board config, so the page can't say more than the records do."""
    configs = repo / "board_configs"
    rows = []
    for record in sorted(configs.rglob("tested.json")):
        data = json.loads(record.read_text(encoding="utf-8"))
        run = data["runs"][-1]
        where = record.parent.relative_to(configs).as_posix()
        rows.append((data["board"], where, run))
    untested = sum(1 for m in configs.rglob("manifest.py") if not (m.parent / "tested.json").is_file())
    lines = []
    for board, where, run in rows:
        left_out = ", ".join(f"`{name}`" for name in run.get("skipped", ())) or "nothing"
        checks = ", ".join(f"`{name}`" for name in run["checks"])
        lines += [
            f"### {board}",
            "",
            f"- **Hardware:** {run['hardware']}",
            f"- **Firmware:** {run['firmware']}",
            f"- **Run on:** {run['date']}",
            f"- **Passed ({len(run['checks'])}):** {checks}",
            f"- **Left out:** {left_out}",
            f"- **Config:** [`board_configs/{where}`](https://github.com/PyDevices/omnipython/tree/main/board_configs/{where})",
            "",
        ]
    lines.append(f"{len(rows)} boards have a record. {untested} more board configs have none yet.")
    return "\n".join(lines) + "\n"


def _write_tested_table(app):
    out = Path(app.srcdir) / "boards" / "_tested-boards.inc"
    text = _tested_table(_REPO)
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")


def setup(app):
    app.connect("builder-inited", _write_tested_table)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}
