#!/usr/bin/env python3
"""Manage an in-repo issue backlog: one Markdown file per issue.

  init                 create the backlog directory and its README (conventions + index)
  list                 list issues (--status, --priority, --area, --json)
  next                 print the next free issue number
  new                  create an issue from the template and add it to the index
  close N              mark issue N closed, optionally add a Resolution
  index                rewrite the README's index table from the issue files
  check                fail if any issue file or the index is malformed or out of step
  github list          the same listing from GitHub Issues instead (see backlog_github.py)

Each issue is `NNN-short-slug.md` with a frontmatter block:

  ---
  status: open            # open | closed
  priority: P2            # P1 fix soon, P2 worth doing, P3 tidy-up
  area: docs, ci          # optional, comma-separated
  opened: 2026-09-14
  closed: 2026-09-20      # required once status is closed
  depends: 004, 012       # optional: issues that must close first
  ---

  # Title in plain English

followed by sections such as Problem, Proposed fix, Done when, Progress, Resolution.
A section whose heading starts with "Needs" (e.g. "## Needs the account holder")
holds steps only a person can do; it stops blocking once every step is ticked (`- [x]`).

Standard library only. The backlog directory is --dir, else $BACKLOG_DIR, else
`issues/` (or an existing `backlog/`) at the git root.
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

STATUSES = ("open", "closed")
PRIORITIES = ("P1", "P2", "P3")
REQUIRED = ("status", "priority", "opened")
FILE_RE = re.compile(r"^(\d{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DONE_RE = re.compile(r"^(done when|close when|acceptance( criteria)?)\b", re.I)
TABLE_HEAD = "| # | Priority | Issue |"
TABLE_RULE = "|---|---|---|"

README_TEMPLATE = """# Issues

Issues live here as files: one Markdown file per issue, versioned with the code they're about.
Format and conventions: https://github.com/AaronLWalker/starting-block

- **Open one:** `sb-backlog new --title "..." --priority P2` (or `python3 <plugin>/scripts/backlog.py new ...`),
  or copy an existing file, give it the next number and set `status: open`.
- **Close one:** set `status: closed`, add `closed: YYYY-MM-DD` and a `## Resolution` saying what fixed it
  (a commit hash or pull request). Leave the file in place so the history stays findable.
- **List open issues:** `sb-backlog list`

Priority: **P1** fix soon (risk or blocking), **P2** worth doing, **P3** tidy-up.

A `## Needs <someone>` section is a checklist of steps only a person can do (an account setting, a
purchase, a credential, a decision). Agents stop there until every box is ticked.

{head}
{rule}
"""

ISSUE_TEMPLATE = """---
status: open
priority: {priority}
{area}opened: {opened}
---

# {title}

## Problem
{problem}

## Proposed fix
-

## Done when
{done}
"""


class Issue:
    def __init__(self, path):
        self.path = path
        self.file = path.name
        m = FILE_RE.match(path.name)
        self.number = m.group(1) if m else None
        self.text = path.read_text(encoding="utf-8")
        self.meta, self.body, self.meta_error = parse_frontmatter(self.text)
        self.title = None
        self.sections = []
        self.section_text = {}
        current = None
        for line in self.body.splitlines():
            if self.title is None and line.startswith("# "):
                self.title = line[2:].strip()
            elif line.startswith("## "):
                current = line[3:].strip()
                self.sections.append(current)
                self.section_text[current] = []
            elif current is not None:
                self.section_text[current].append(line)

    @property
    def status(self):
        return self.meta.get("status", "")

    @property
    def priority(self):
        return self.meta.get("priority", "")

    @property
    def areas(self):
        return split_list(self.meta.get("area", ""))

    @property
    def depends(self):
        return [d.zfill(3) for d in split_list(self.meta.get("depends", ""))]

    @property
    def needs(self):
        """`## Needs ...` sections with steps still to do. A section is done when every step is `- [x]`."""
        outstanding = []
        for name in self.sections:
            if not name.lower().startswith("needs"):
                continue
            steps = [l.strip() for l in self.section_text[name] if re.match(r"\s*(?:[-*]|\d+[.)])\s", l)]
            if not steps or not all(re.match(r"(?:[-*]|\d+[.)])\s+\[[xX]\]", st) for st in steps):
                outstanding.append(name)
        return outstanding

    @property
    def has_done_when(self):
        return any(DONE_RE.match(s) for s in self.sections)

    def to_dict(self, by_number):
        open_deps = [d for d in self.depends if d in by_number and by_number[d].status != "closed"]
        return {
            "number": self.number,
            "file": self.file,
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "area": self.areas,
            "opened": self.meta.get("opened"),
            "closed": self.meta.get("closed"),
            "depends": self.depends,
            "open_depends": open_deps,
            "sections": self.sections,
            "needs_human": self.needs,
            "ready": self.status == "open" and self.has_done_when and not open_deps and not self.needs,
        }


def split_list(value):
    return [v.strip() for v in re.split(r"[,\s]+", value.strip("[] ")) if v.strip()]


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "no frontmatter (file must start with ---)"
    meta = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:]), None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, value = line.partition(":")
        if not sep:
            return meta, "", "frontmatter line {} isn't `key: value`".format(i + 1)
        value = re.sub(r"\s+#.*$", "", value).strip()
        meta[key.strip()] = value
    return meta, "", "frontmatter is never closed with ---"


def write_file(path, text):
    """Write UTF-8 with LF line endings on every platform (Path.write_text would use CRLF on Windows)."""
    with open(str(path), "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def utf8_output():
    """Print UTF-8 even where the console defaults to a legacy code page (Windows)."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def git_root():
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", check=True)
        return Path(out.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd()


def backlog_dir(arg):
    if arg:
        return Path(arg)
    if os.environ.get("BACKLOG_DIR"):
        return Path(os.environ["BACKLOG_DIR"])
    root = git_root()
    for name in ("issues", "backlog"):
        if (root / name).is_dir():
            return root / name
    return root / "issues"


def load(directory):
    issues = []
    stray = []
    for p in sorted(directory.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        if FILE_RE.match(p.name):
            issues.append(Issue(p))
        elif re.match(r"^\d", p.name):
            stray.append(p.name)
    return issues, stray


def require_dir(directory):
    if not directory.is_dir():
        sys.exit("No backlog at {}. Run `backlog.py init` first, or pass --dir.".format(directory))


def slugify(title, limit=6):
    words = re.findall(r"[a-z0-9]+", re.sub(r"['\u2019]", "", title.lower()))
    stop = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "is", "it", "its", "with"}
    kept = [w for w in words if w not in stop] or words
    return "-".join(kept[:limit]) or "issue"


def next_number(issues):
    nums = [int(i.number) for i in issues if i.number]
    return "{:03d}".format(max(nums) + 1 if nums else 1)


def index_row(issue):
    prio = issue.priority + (" (closed)" if issue.status == "closed" else "")
    return "| [{n}]({f}) | {p} | {t} |".format(n=issue.number, f=issue.file, p=prio, t=issue.title or "")


def find_table(lines):
    """Return (start, end) line indexes of the index table, end exclusive, or None."""
    for i, line in enumerate(lines):
        if line.strip().replace(" ", "") == TABLE_HEAD.replace(" ", ""):
            j = i + 1
            while j < len(lines) and lines[j].strip().startswith("|"):
                j += 1
            return i, j
    return None


def render_index(directory, issues):
    readme = directory / "README.md"
    rows = [index_row(i) for i in sorted(issues, key=lambda i: int(i.number))]
    table = [TABLE_HEAD, TABLE_RULE] + rows
    if readme.exists():
        lines = readme.read_text(encoding="utf-8").splitlines()
    else:
        lines = README_TEMPLATE.format(dirname=directory.name, head=TABLE_HEAD, rule=TABLE_RULE).splitlines()
    span = find_table(lines)
    if span:
        lines[span[0]:span[1]] = table
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines += table
    return "\n".join(lines) + "\n"


def write_index(directory, issues):
    readme = directory / "README.md"
    new = render_index(directory, issues)
    if not readme.exists() or readme.read_text(encoding="utf-8") != new:
        write_file(readme, new)
        return True
    return False


def set_meta(text, updates):
    """Set frontmatter keys in place, keeping order; new keys go right after `status`."""
    lines = text.splitlines()
    end = lines.index("---", 1)
    for key, value in updates.items():
        for i in range(1, end):
            if lines[i].split(":", 1)[0].strip() == key:
                lines[i] = "{}: {}".format(key, value)
                break
        else:
            at = next((i + 1 for i in range(1, end) if lines[i].startswith("status:")), end)
            lines.insert(at, "{}: {}".format(key, value))
            end += 1
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def today():
    return dt.date.today().isoformat()


# ---- commands ---------------------------------------------------------------

def cmd_init(args):
    d = backlog_dir(args.dir)
    d.mkdir(parents=True, exist_ok=True)
    readme = d / "README.md"
    if readme.exists():
        print("{} already exists; left as is.".format(readme))
    else:
        write_file(readme, README_TEMPLATE.format(dirname=d.name, head=TABLE_HEAD, rule=TABLE_RULE))
        print("Created {}".format(readme))
    return 0


def cmd_list(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    issues, _ = load(d)
    by_number = {i.number: i for i in issues}
    sel = [i for i in issues
           if (args.status == "all" or i.status == args.status)
           and (not args.priority or i.priority == args.priority)
           and (not args.area or args.area in i.areas)]
    sel.sort(key=lambda i: (PRIORITIES.index(i.priority) if i.priority in PRIORITIES else 9, int(i.number)))
    if args.json:
        print(json.dumps([i.to_dict(by_number) for i in sel], indent=2))
        return 0
    for i in sel:
        info = i.to_dict(by_number)
        flags = []
        if info["open_depends"]:
            flags.append("blocked by " + ", ".join(info["open_depends"]))
        if info["needs_human"]:
            flags.append("needs a person")
        if i.status == "open" and not i.has_done_when:
            flags.append("no 'Done when'")
        print("{}  {:2}  {:6}  {}{}".format(i.number, i.priority, i.status, i.title,
                                            "  [" + "; ".join(flags) + "]" if flags else ""))
    return 0


def cmd_next(args):
    d = backlog_dir(args.dir)
    issues, _ = load(d) if d.is_dir() else ([], [])
    print(next_number(issues))
    return 0


def cmd_new(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    if args.priority not in PRIORITIES:
        sys.exit("--priority must be one of " + ", ".join(PRIORITIES))
    issues, _ = load(d)
    num = next_number(issues)
    path = d / "{}-{}.md".format(num, args.slug or slugify(args.title))
    area = "area: {}\n".format(args.area) if args.area else ""
    write_file(path, ISSUE_TEMPLATE.format(
        priority=args.priority, area=area, opened=args.date or today(), title=args.title,
        problem=args.problem or "", done=args.done or ""))
    if args.depends:
        write_file(path, set_meta(path.read_text(encoding="utf-8"), {"depends": args.depends}))
    issues, _ = load(d)
    write_index(d, issues)
    print(path)
    return 0


def cmd_close(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    issues, _ = load(d)
    num = args.number.zfill(3)
    match = [i for i in issues if i.number == num]
    if not match:
        sys.exit("No issue {} in {}".format(num, d))
    issue = match[0]
    text = set_meta(issue.text, {"status": "closed", "closed": args.date or today()})
    if args.resolution:
        if "## Resolution" in text:
            sys.exit("Issue {} already has a Resolution section; edit it by hand.".format(num))
        text = text.rstrip("\n") + "\n\n## Resolution\n" + args.resolution.strip() + "\n"
    write_file(issue.path, text)
    issues, _ = load(d)
    write_index(d, issues)
    print(issue.path)
    return 0


def cmd_index(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    issues, _ = load(d)
    changed = write_index(d, issues)
    print(("Updated " if changed else "Already current: ") + str(d / "README.md"))
    return 0


def check(directory):
    """Return (errors, warnings) as lists of strings."""
    errors, warnings = [], []
    issues, stray = load(directory)
    for name in stray:
        errors.append("{}: filename should be NNN-lowercase-slug.md".format(name))
    seen = {}
    for i in issues:
        seen.setdefault(i.number, []).append(i.file)
    for num, files in seen.items():
        if len(files) > 1:
            errors.append("number {} is used by {}".format(num, ", ".join(files)))
    by_number = {i.number: i for i in issues}
    for i in issues:
        where = i.file
        if i.meta_error:
            errors.append("{}: {}".format(where, i.meta_error))
            continue
        for key in REQUIRED:
            if not i.meta.get(key):
                errors.append("{}: missing `{}:`".format(where, key))
        if i.status and i.status not in STATUSES:
            errors.append("{}: status `{}` isn't one of {}".format(where, i.status, ", ".join(STATUSES)))
        if i.priority and i.priority not in PRIORITIES:
            errors.append("{}: priority `{}` isn't one of {}".format(where, i.priority, ", ".join(PRIORITIES)))
        for key in ("opened", "closed"):
            v = i.meta.get(key)
            if v and not DATE_RE.match(v):
                errors.append("{}: `{}: {}` isn't YYYY-MM-DD".format(where, key, v))
        if not i.title:
            errors.append("{}: no `# Title` line after the frontmatter".format(where))
        if i.status == "closed":
            if not i.meta.get("closed"):
                errors.append("{}: closed, but has no `closed:` date".format(where))
            elif i.meta.get("opened", "") > i.meta["closed"]:
                errors.append("{}: closed before it was opened".format(where))
            if "Resolution" not in i.sections:
                warnings.append("{}: closed without a `## Resolution`".format(where))
        if i.status == "open":
            if i.meta.get("closed"):
                errors.append("{}: open, but has a `closed:` date".format(where))
            if not i.has_done_when:
                warnings.append("{}: open with no `## Done when` (refine it before executing)".format(where))
        for dep in i.depends:
            if dep not in by_number:
                errors.append("{}: depends on {}, which doesn't exist".format(where, dep))
            elif dep == i.number:
                errors.append("{}: depends on itself".format(where))
    readme = directory / "README.md"
    if not readme.exists():
        errors.append("README.md is missing (run `backlog.py index`)")
    else:
        valid = [i for i in issues if i.number and not i.meta_error and len(seen[i.number]) == 1]
        current = readme.read_text(encoding="utf-8")
        if current != render_index(directory, valid):
            listed = set(re.findall(r"^\|\s*\[(\d{3,})\]", current, re.M))
            have = {i.number for i in valid}
            detail = []
            if have - listed:
                detail.append("missing " + ", ".join(sorted(have - listed)))
            if listed - have:
                detail.append("lists absent " + ", ".join(sorted(listed - have)))
            if not detail:
                detail.append("a title, priority or status differs from the files")
            errors.append("README.md index is out of date ({}); run `backlog.py index`".format("; ".join(detail)))
    return errors, warnings


def cmd_check(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    errors, warnings = check(d)
    for e in errors:
        print("error: " + e)
    for w in warnings:
        print("warning: " + w)
    if not errors and not warnings:
        print("Backlog OK: {}".format(d))
    return 1 if errors or (args.strict and warnings) else 0


def main(argv=None):
    utf8_output()
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["github"]:  # the backlog in GitHub Issues: see backlog_github.py
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import backlog_github
        return backlog_github.main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", help="backlog directory (default: $BACKLOG_DIR, else issues/ at the git root)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the backlog directory and README")

    p = sub.add_parser("list", help="list issues")
    p.add_argument("--status", default="open", choices=STATUSES + ("all",))
    p.add_argument("--priority", choices=PRIORITIES)
    p.add_argument("--area")
    p.add_argument("--json", action="store_true")

    sub.add_parser("next", help="print the next free number")

    p = sub.add_parser("new", help="create an issue")
    p.add_argument("--title", required=True)
    p.add_argument("--priority", default="P2")
    p.add_argument("--area", help="comma-separated areas")
    p.add_argument("--depends", help="comma-separated issue numbers")
    p.add_argument("--slug", help="filename slug (default: from the title)")
    p.add_argument("--problem", help="text for the Problem section")
    p.add_argument("--done", help="text for the Done when section")
    p.add_argument("--date", help="opened date (default: today)")

    p = sub.add_parser("close", help="close an issue")
    p.add_argument("number")
    p.add_argument("--resolution", help="text for a new Resolution section")
    p.add_argument("--date", help="closed date (default: today)")

    sub.add_parser("index", help="rewrite the README index table")

    p = sub.add_parser("check", help="validate issue files and the index")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")

    args = ap.parse_args(argv)
    return {"init": cmd_init, "list": cmd_list, "next": cmd_next, "new": cmd_new, "close": cmd_close,
            "index": cmd_index, "check": cmd_check}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
