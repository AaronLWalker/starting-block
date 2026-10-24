#!/usr/bin/env python3
"""Keep a generated Markdown table in step with its sources.  (Template: copy into the repo and adapt.)

  build              rewrite the table between the markers in OUTPUT
  check              fail if anything below disagrees
  check --offline    the same, skipping live_checks() (use this in the pre-commit hook)

The check fails when:
  - something in the source has no manifest entry, or the manifest lists something the source lacks
  - OUTPUT's table isn't what `build` would write

Adapt the three marked parts: the paths, source_names(), and render_row(). Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# --- ADAPT: where things live ---------------------------------------------------------------
MANIFEST = ROOT / "docs/manifest.json"      # {"items": [{"name": "...", "description": "..."}]}
SOURCE = ROOT / "src/routes.py"             # whatever is authoritative at runtime
OUTPUT = ROOT / "README.md"                 # holds the generated table between the markers
START, END = "<!-- generated:start (edit docs/manifest.json, then run build) -->", "<!-- generated:end -->"
HEADER = ["| Name | What it does |", "|---|---|"]


def source_names():
    """ADAPT: the names the source of truth defines, e.g. route paths, services, CLI commands."""
    return set(re.findall(r'@route\("([^"]+)"\)', SOURCE.read_text(encoding="utf-8")))


def render_row(item):
    """ADAPT: one table row per manifest entry."""
    return "| `{}` | {} |".format(item["name"], item["description"])


def live_checks(items):
    """ADAPT (optional): network or runtime checks, skipped under --offline. Return a list of errors."""
    return []
# ---------------------------------------------------------------------------------------------


def load_items():
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["items"]


def render(items):
    return "\n".join([START] + HEADER + [render_row(i) for i in sorted(items, key=lambda i: i["name"])] + [END])


def rebuilt(text, items):
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.S)
    if not pattern.search(text):
        sys.exit("{} has no generated section; add these two lines where the table goes:\n{}\n{}".format(
            OUTPUT.name, START, END))
    return pattern.sub(lambda _: render(items), text)


def write(path, text):
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def cmd_build(_args):
    write(OUTPUT, rebuilt(OUTPUT.read_text(encoding="utf-8"), load_items()))
    print("Wrote " + str(OUTPUT.relative_to(ROOT)))
    return 0


def cmd_check(args):
    items = load_items()
    errors = []
    listed, defined = {i["name"] for i in items}, source_names()
    for name in sorted(defined - listed):
        errors.append("{} defines '{}' but {} has no entry for it; add one".format(
            SOURCE.name, name, MANIFEST.name))
    for name in sorted(listed - defined):
        errors.append("{} lists '{}' but {} doesn't define it; remove the entry or add it to the source".format(
            MANIFEST.name, name, SOURCE.name))
    text = OUTPUT.read_text(encoding="utf-8")
    if rebuilt(text, items) != text:
        errors.append("{}'s generated table is out of date".format(OUTPUT.name))
    if not args.offline:
        errors += live_checks(items)
    for e in errors:
        print("error: " + e)
    if errors:
        print("\nFix the above, then run: python {} build".format(Path(__file__).relative_to(ROOT).as_posix()))
        return 1
    print("In step: {} entries".format(len(items)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    p = sub.add_parser("check")
    p.add_argument("--offline", action="store_true", help="skip live checks")
    args = ap.parse_args(argv)
    return {"build": cmd_build, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
