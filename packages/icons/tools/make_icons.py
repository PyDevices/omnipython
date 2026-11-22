# SPDX-FileCopyrightText: 2026 Brad Barnett
#
# SPDX-License-Identifier: MIT
"""Build an icons font module: Material Symbols cut down to the icons you name.

Takes Google's variable Material Symbols font and its codepoints file (both in
google/material-design-icons, under variablefont/), keeps the filled, weight
400 instance at the 20 px optical size, cuts it down to the named icons and
writes one Python module holding the font and its name table. Frozen into
firmware, the module stays in flash and `icons` draws from it through ttfio.

Example::

    python tools/make_icons.py build FONT.ttf FONT.codepoints \\
        --names-file icons/icons.txt --out icons/_material.py

    python tools/make_icons.py build FONT.ttf FONT.codepoints \\
        --names home,wifi --out myicons.py

``select`` writes the list this package ships: the names in ``--keep``, then
the most popular icons in the categories that suit a device's screen, from
Google's metadata (https://fonts.google.com/metadata/icons), up to
``--count``::

    python tools/make_icons.py select METADATA.json FONT.codepoints \\
        --keep KEEP.txt --count 500 --out icons/icons.txt

The module's ``NAMES`` is the sorted names, one per line, and ``CODES`` holds
each one's codepoint in three bytes, big-endian, in the same order. Needs
fontTools.
"""

import argparse
import io
import json
import sys

CATEGORIES = ("UI actions", "Actions", "Audio&Video", "Hardware", "Android",
              "Communicate", "Privacy", "Home", "Images")
FAMILY = "Material Symbols Outlined"


def read_names(path):
    with open(path) as f:
        return [n.strip() for n in f if n.strip() and not n.startswith("#")]


def read_codepoints(path):
    with open(path) as f:
        return {name: int(code, 16) for name, code in (line.split() for line in f if line.strip())}


def select(args):
    with open(args.metadata) as f:
        text = f.read()
    meta = json.loads(text[text.index("{"):])  # the file starts with )]}'
    codes = read_codepoints(args.codepoints)
    keep = read_names(args.keep) if args.keep else []
    missing = [n for n in keep if n not in codes]
    if missing:
        sys.exit("not in the font: " + ", ".join(missing))
    chosen = list(dict.fromkeys(keep))
    ranked = sorted(
        (i for i in meta["icons"]
         if i["name"] in codes and FAMILY not in i.get("unsupported_families", ())
         and set(i["categories"]) & set(CATEGORIES)),
        key=lambda i: (-i["popularity"], i["name"]))
    for icon in ranked:
        if len(chosen) >= args.count:
            break
        if icon["name"] not in chosen:
            chosen.append(icon["name"])
    with open(args.out, "w") as f:
        f.write("# Material Symbols in the icons package's font. Made by tools/make_icons.py select:\n")
        f.write("# iconkit's 129, then the most popular icons in %s.\n" % ", ".join(CATEGORIES))
        for name in sorted(chosen):
            f.write(name + "\n")
    print("%s: %d names" % (args.out, len(chosen)))


def build(args):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer

    codes = read_codepoints(args.codepoints)
    names = sorted(set(args.names.split(",") if args.names else read_names(args.names_file)))
    missing = [n for n in names if n not in codes]
    if missing:
        sys.exit("not in the font: " + ", ".join(missing))
    font = instancer.instantiateVariableFont(TTFont(args.font), {"FILL": 1, "wght": 400, "GRAD": 0, "opsz": 20})
    opts = subset.Options()
    opts.layout_features = []
    opts.notdef_outline = False
    opts.name_IDs = [0, 1, 2]
    opts.hinting = False
    opts.drop_tables += ["GSUB", "GPOS", "DSIG"]
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[codes[n] for n in names])
    sub.subset(font)
    buf = io.BytesIO()
    font.save(buf)
    data = buf.getvalue()
    table = b"".join(codes[n].to_bytes(3, "big") for n in names)
    with open(args.out, "w") as f:
        f.write("# SPDX-FileCopyrightText: Google LLC\n#\n# SPDX-License-Identifier: Apache-2.0\n")
        f.write('"""Material Symbols Outlined, filled, weight 400, 20 px optical size: %d icons.\n\n' % len(names))
        f.write("Made by tools/make_icons.py. Do not edit.\n\"\"\"\n\n")
        f.write("FONT = %r\n" % data)
        f.write("NAMES = %r\n" % ("\n".join(names) + "\n").encode())
        f.write("CODES = %r\n" % table)
    print("%s: %d icons, font %d bytes" % (args.out, len(names), len(data)))


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("select", help="choose the names to ship")
    s.add_argument("metadata")
    s.add_argument("codepoints")
    s.add_argument("--keep", help="names that must be in, one a line")
    s.add_argument("--count", type=int, default=500)
    s.add_argument("--out", required=True)
    b = sub.add_parser("build", help="write the font module")
    b.add_argument("font")
    b.add_argument("codepoints")
    g = b.add_mutually_exclusive_group(required=True)
    g.add_argument("--names", help="comma-separated names")
    g.add_argument("--names-file")
    b.add_argument("--out", required=True)
    args = p.parse_args()
    (select if args.cmd == "select" else build)(args)


if __name__ == "__main__":
    main()
