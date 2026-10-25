#!/usr/bin/env python3
"""Manage an in-repo issue backlog: one Markdown file per issue.

  init                 create the backlog directory and its README (conventions + index);
                       --refresh-readme rewrites an existing README's text above the index table
  list                 list issues (--status, --priority, --area, --reachable, --json)
  next                 print the next free issue number
  new                  create an issue from the template and add it to the index
  close N              mark issue N closed, optionally add a Resolution
  reopen N             mark issue N open again; its Resolution becomes an Earlier resolution
  hold N --reason ...  put issue N on hold (`hold: <date> <reason>`); `set N hold=` clears it
  set N key=value ...  set frontmatter fields (`key=` removes one) and update the index
  index                rewrite the README's index table from the issue files
  check                fail if any issue file or the index is malformed or out of step
  run-checks           run the `checks` commands from .backlog.toml at the git root; exit 1 if any fail
  install-hook         copy this script into the repo's scripts/ and run `check` from
                       .githooks/pre-commit (--with-secret-scan adds secret_scan.py --staged)
  github list          the same listing from GitHub Issues instead (see backlog_github.py)

Each issue is `NNN-short-slug.md` with a frontmatter block, one `key: value` per line
(lists are comma-separated; YAML lists and indented lines are rejected):

  ---
  status: open            # open | closed
  priority: P2            # P1 fix soon, P2 worth doing, P3 tidy-up
  area: docs, ci          # optional, comma-separated
  opened: 2026-09-14
  closed: 2026-09-20      # required once status is closed
  depends: 004, 012       # optional: issues that must close first
  runs-on: host           # optional: where the work must happen ("repo" is always reachable)
  hold: 2026-09-15 needs the production database   # optional: an agent stopped here; don't retry
  ---

  # Title in plain English

followed by sections such as Problem, Proposed fix, Done when, Progress, Resolution.
A section whose heading starts with "Needs" (e.g. "## Needs the account holder")
holds steps only a person can do; it stops blocking once every step is ticked (`- [x]`).

An issue is ready (`list --json`) when it's open, has a Done when, no open depends, no
unticked Needs, no hold, and every runs-on place is reachable: "repo", the config's
`reachable`, or a `list --reachable NAME` (for a session running somewhere else, e.g. the host).

An optional `.backlog.toml` in the backlog directory changes the vocabulary
(read with tomllib, so it needs Python 3.11+):

  statuses = ["open", "in-progress", "closed"]   # must include "open" and "closed"
  priorities = ["P0", "P1", "P2", "P3"]          # highest first
  done_sections = ["Done when", "Acceptance"]    # heading prefixes that count as Done when
  reachable = ["host"]                           # runs-on places this checkout can work in (default [])
  checks = ["python3 -m unittest"]               # shell commands for run-checks, run from the git root

`check` also warns when the repo has .githooks/ but this clone doesn't use it (unless $CI is set),
and when the repo's scripts/backlog.py or scripts/secret_scan.py differs from this copy.

Standard library only. The backlog directory is --dir, else $BACKLOG_DIR, else
`issues/` (or an existing `backlog/`) at the git root.
"""

import argparse
import datetime as dt
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.9 and 3.10
    tomllib = None

__version__ = "0.4.0"

STATUSES = ("open", "closed")
PRIORITIES = ("P1", "P2", "P3")
DONE_SECTIONS = ("Done when", "Close when", "Acceptance")
CONFIG_FILE = ".backlog.toml"
REQUIRED = ("status", "priority", "opened")
FILE_RE = re.compile(r"^(\d{3,})-([a-z0-9]+(?:-[a-z0-9]+)*)\.md$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
WORD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
TABLE_HEAD = "| # | Priority | Issue |"
TABLE_RULE = "|---|---|---|"
HOOK_START = "# >>> starting-block backlog checks"
HOOK_END = "# <<< starting-block backlog checks"

README_TEMPLATE = """# Issues

Issues live here as files: one Markdown file per issue, versioned with the code they're about.
Format and conventions: https://github.com/AaronLWalker/starting-block

- **Open one:** `sb-backlog new --title "..." --priority P2`, or copy an existing file, give it the next
  number and set `status: open`.
- **Close one:** `sb-backlog close N --resolution "Fixed in <commit or pull request>."` sets `status: closed`
  and the `closed:` date and adds a `## Resolution`. Leave the file in place so the history stays findable.
- **Reopen one:** `sb-backlog reopen N`; the old Resolution is kept as an Earlier resolution.
- **Put one on hold:** `sb-backlog hold N --reason "..."`; `sb-backlog set N hold=` clears it.
- **List open issues:** `sb-backlog list` (`--json` for scripts); `sb-backlog check` validates the files and this index.

Without the plugin's `sb-backlog`, run `python3 <plugin>/scripts/backlog.py` the same way.

Priority: **P1** fix soon (risk or blocking), **P2** worth doing, **P3** tidy-up.

A `## Needs <someone>` section is a checklist (`- [ ] step`) of steps only a person can do (an account
setting, a purchase, a credential, a decision). Agents stop there until every box is ticked (`- [x]`).

`runs-on: host` in the frontmatter says where the work must happen, so agents that can't reach it skip the
issue. `hold: YYYY-MM-DD <reason>` means an agent stopped on the issue; it isn't retried until someone
clears the hold.

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
    def __init__(self, path, done=None):
        self.path = path
        self.file = path.name
        self.done_re = done or DONE_RE
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
    def runs_on(self):
        return split_list(self.meta.get("runs-on", ""))

    @property
    def hold(self):
        """The `hold:` value (`<date> <reason>`), or None when the issue isn't on hold."""
        return self.meta.get("hold") or None

    @property
    def has_done_when(self):
        return any(self.done_re.match(s) for s in self.sections)

    def to_dict(self, by_number, reachable=("repo",)):
        open_deps = [d for d in self.depends if d in by_number and by_number[d].status != "closed"]
        unreachable = unreachable_places(self.runs_on, reachable)
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
            "runs_on": self.runs_on,
            "unreachable": unreachable,
            "hold": self.hold,
            "ready": (self.status == "open" and self.has_done_when and not open_deps and not self.needs
                      and not unreachable and not self.hold),
        }


def split_list(value):
    return [v.strip() for v in re.split(r"[,\s]+", value.strip("[] ")) if v.strip()]


def unreachable_places(runs_on, reachable):
    """The `runs_on` places not in `reachable` (any case); "repo" is always reachable."""
    have = {r.lower() for r in reachable} | {"repo"}
    return [r for r in runs_on if r.lower() not in have]


def hold_reason(hold):
    """The reason part of a `hold:` value, without its leading date."""
    date, _, rest = hold.partition(" ")
    return rest.strip() if valid_date(date) and rest.strip() else hold


def done_re(prefixes):
    """Match a section heading that starts with one of `prefixes` (any case) as a whole word."""
    return re.compile(r"^(?:{})(?!\w)".format("|".join(re.escape(p) for p in prefixes)), re.I)


DONE_RE = done_re(DONE_SECTIONS)


def parse_frontmatter(text):
    """One `key: value` per line. Indented lines and YAML lists are reported, not guessed at."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "no frontmatter (file must start with ---)"
    meta = {}
    bare = None  # (line number, key) of the previous line when it was `key:` with no value
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return meta, "\n".join(lines[i + 1:]), None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0].isspace() or re.match(r"-(\s|$)", line):
            if bare:
                return meta, "", ("frontmatter line {}: `{}:` is followed by indented or `- ` lines (YAML lists "
                                  "and nested values aren't supported); write `{}: a, b` on one line"
                                  ).format(bare[0], bare[1], bare[1])
            if line[0].isspace():
                return meta, "", ("frontmatter line {} is indented (continuation lines aren't supported); "
                                  "put each `key: value` on one line").format(i + 1)
            return meta, "", "frontmatter line {} is a YAML list item; write lists as `key: a, b`".format(i + 1)
        key, sep, value = line.partition(":")
        key = key.strip()
        if not sep or not key or re.search(r"\s", key):
            return meta, "", "frontmatter line {} isn't `key: value`".format(i + 1)
        value = re.sub(r"\s+#.*$", "", value).strip()
        meta[key] = value
        bare = (i + 1, key) if re.match(r"^([|>][+-]?)?$", value) else None
    return meta, "", "frontmatter is never closed with ---"


def load_config(directory):
    """Read `.backlog.toml` from the backlog directory, with the defaults for anything it leaves out."""
    config = {"statuses": STATUSES, "priorities": PRIORITIES, "done_sections": DONE_SECTIONS,
              "reachable": (), "checks": ()}
    path = Path(directory) / CONFIG_FILE
    if path.is_file():
        if tomllib is None:
            sys.exit("{} needs Python 3.11 or later (for tomllib); this is Python {}.{}. "
                     "Use a newer Python or remove the file.".format(path, *sys.version_info[:2]))
        try:
            with open(str(path), "rb") as f:
                data = tomllib.load(f)
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
            sys.exit("{}: {}".format(path, e))
        for key, value in data.items():
            if key not in config:
                sys.exit("{}: unknown key `{}` (expected {})".format(path, key, ", ".join(sorted(config))))
            may_be_empty = key in ("reachable", "checks")
            if not isinstance(value, list) or not (value or may_be_empty) \
                    or not all(isinstance(v, str) and v.strip() for v in value):
                sys.exit("{}: `{}` must be a {}".format(
                    path, key, "list of non-empty strings" if may_be_empty else "non-empty list of strings"))
            value = tuple(v.strip() for v in value)
            if len(set(value)) != len(value):
                sys.exit("{}: `{}` lists a value twice".format(path, key))
            if key in ("statuses", "priorities", "reachable"):
                bad = [v for v in value if not WORD_RE.match(v) or v == "all"]
                if bad:
                    sys.exit("{}: `{}` value `{}` must be one word (letters, digits, `-`, `_`, `.`) "
                             "other than `all`".format(path, key, bad[0]))
            config[key] = value
        missing = [s for s in ("open", "closed") if s not in config["statuses"]]
        if missing:
            sys.exit("{}: `statuses` must include {}".format(
                path, " and ".join('"{}"'.format(s) for s in missing)))
    config["done_re"] = done_re(config["done_sections"])
    return config


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


def git(args, cwd=None):
    """Run git and return its stripped output, or None if git is missing or the command fails."""
    try:
        out = subprocess.run(["git"] + args, cwd=None if cwd is None else str(cwd), capture_output=True,
                             text=True, encoding="utf-8", errors="replace", check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_root():
    root = git(["rev-parse", "--show-toplevel"])
    return Path(root) if root else Path.cwd()


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


def load(directory, config=None):
    config = config or load_config(directory)
    issues = []
    stray = []
    for p in sorted(directory.glob("*.md")):
        if p.name.lower() == "readme.md":
            continue
        if FILE_RE.match(p.name):
            issues.append(Issue(p, config["done_re"]))
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


def find_issue(directory, issues, number):
    """The one issue numbered `number`, with readable frontmatter, or exit with the reason."""
    if not number.isdigit():
        sys.exit("`{}` isn't an issue number".format(number))
    num = number.zfill(3)
    match = [i for i in issues if i.number == num]
    if not match:
        sys.exit("No issue {} in {}".format(num, directory))
    if len(match) > 1:
        sys.exit("Number {} is used by {}; renumber one first.".format(num, ", ".join(i.file for i in match)))
    if match[0].meta_error:
        sys.exit("{}: {}. Fix the frontmatter first.".format(match[0].file, match[0].meta_error))
    return match[0]


def valid_date(value):
    if not DATE_RE.match(value):
        return False
    try:
        dt.date(*map(int, value.split("-")))
    except ValueError:
        return False
    return True


def check_date(flag, value):
    if not valid_date(value):
        sys.exit("{} must be a date as YYYY-MM-DD, not `{}`".format(flag, value))
    return value


def meta_end(lines):
    return next(i for i in range(1, len(lines)) if lines[i].strip() == "---")


def remove_meta(text, keys):
    """Delete the frontmatter lines for `keys`."""
    lines = text.splitlines()
    end = meta_end(lines)
    lines = lines[:1] + [l for l in lines[1:end] if l.split(":", 1)[0].strip() not in keys] + lines[end:]
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def set_meta(text, updates):
    """Set frontmatter keys in place, keeping order; new keys go right after `status`."""
    lines = text.splitlines()
    end = meta_end(lines)
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
    template = README_TEMPLATE.format(dirname=d.name, head=TABLE_HEAD, rule=TABLE_RULE)
    if readme.exists() and args.refresh_readme:
        current = readme.read_text(encoding="utf-8")
        lines = current.splitlines()
        span = find_table(lines)
        if not span:
            sys.exit("{} has no index table (`{}`), so there's nothing to keep; left as is. "
                     "Run `index` to add one first.".format(readme, TABLE_HEAD))
        new = "\n".join(template.splitlines()[:find_table(template.splitlines())[0]] + lines[span[0]:]) + "\n"
        if same_text(current, new):
            print("Already current: {}".format(readme))
        else:
            write_file(readme, new)
            print("Refreshed the text above the index in {}".format(readme))
    elif readme.exists():
        print("{} already exists; left as is.".format(readme))
    else:
        write_file(readme, template)
        print("Created {}".format(readme))
    return 0


def reachable_places(config, extra):
    """Where this call can work: "repo", the config's `reachable`, and each --reachable (comma lists too)."""
    places = ["repo"] + list(config["reachable"])
    for value in extra or []:
        places += split_list(value)
    return places


def cmd_list(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    config = load_config(d)
    prios = config["priorities"]
    if args.status != "all" and args.status not in config["statuses"]:
        sys.exit("--status must be one of " + ", ".join(config["statuses"] + ("all",)))
    if args.priority and args.priority not in prios:
        sys.exit("--priority must be one of " + ", ".join(prios))
    reachable = reachable_places(config, args.reachable)
    issues, _ = load(d, config)
    by_number = {i.number: i for i in issues}
    sel = [i for i in issues
           if (args.status == "all" or i.status == args.status)
           and (not args.priority or i.priority == args.priority)
           and (not args.area or args.area in i.areas)]
    sel.sort(key=lambda i: (prios.index(i.priority) if i.priority in prios else len(prios), int(i.number)))
    if args.json:
        print(json.dumps([i.to_dict(by_number, reachable) for i in sel], indent=2))
        return 0
    for i in sel:
        info = i.to_dict(by_number, reachable)
        flags = []
        if info["open_depends"]:
            flags.append("blocked by " + ", ".join(info["open_depends"]))
        if info["needs_human"]:
            flags.append("needs a person")
        if info["unreachable"]:
            flags.append("runs on " + ", ".join(info["unreachable"]))
        if info["hold"]:
            flags.append("on hold: " + hold_reason(info["hold"]))
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
    config = load_config(d)
    prios = config["priorities"]
    priority = args.priority or prios[(len(prios) - 1) // 2]
    if priority not in prios:
        sys.exit("--priority must be one of " + ", ".join(prios))
    opened = check_date("--date", args.date) if args.date else today()
    issues, _ = load(d, config)
    num = next_number(issues)
    path = d / "{}-{}.md".format(num, args.slug or slugify(args.title))
    area = "area: {}\n".format(args.area) if args.area else ""
    write_file(path, ISSUE_TEMPLATE.format(
        priority=priority, area=area, opened=opened, title=args.title,
        problem=args.problem or "", done=args.done or ""))
    if args.depends:
        write_file(path, set_meta(path.read_text(encoding="utf-8"), {"depends": args.depends}))
    issues, _ = load(d, config)
    write_index(d, issues)
    print(path)
    return 0


def cmd_close(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    issues, _ = load(d)
    issue = find_issue(d, issues, args.number)
    closed = check_date("--date", args.date) if args.date else today()
    text = set_meta(issue.text, {"status": "closed", "closed": closed})
    if args.resolution:
        if "## Resolution" in text:
            sys.exit("Issue {} already has a Resolution section; edit it by hand.".format(issue.number))
        text = text.rstrip("\n") + "\n\n## Resolution\n" + args.resolution.strip() + "\n"
    write_file(issue.path, text)
    issues, _ = load(d)
    write_index(d, issues)
    print(issue.path)
    return 0


def cmd_reopen(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    issues, _ = load(d)
    issue = find_issue(d, issues, args.number)
    if issue.status != "closed":
        sys.exit("Issue {} isn't closed (status: {}).".format(issue.number, issue.status or "none"))
    date = check_date("--date", args.date) if args.date else today()
    text = remove_meta(set_meta(issue.text, {"status": "open"}), ("closed",))
    lines = text.splitlines()
    for k in range(meta_end(lines) + 1, len(lines)):
        if lines[k].startswith("## ") and lines[k][3:].strip() == "Resolution":
            lines[k] = "## Earlier resolution ({})".format(date)
    write_file(issue.path, "\n".join(lines) + "\n")
    issues, _ = load(d)
    write_index(d, issues)
    print(issue.path)
    return 0


def cmd_hold(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    config = load_config(d)
    issues, _ = load(d, config)
    issue = find_issue(d, issues, args.number)
    reason = args.reason.strip()
    if not reason:
        sys.exit("--reason can't be empty: say why the issue is on hold")
    if "\n" in reason or "\r" in reason or re.search(r"\s#", reason):
        sys.exit("--reason must be one line, without ` #` (that starts a comment)")
    if issue.status == "closed":
        sys.exit("Issue {} is closed; only an open issue can be put on hold.".format(issue.number))
    date = check_date("--date", args.date) if args.date else today()
    text = set_meta(issue.text, {"hold": "{} {}".format(date, reason)})
    if text != issue.text:
        write_file(issue.path, text)
    issues, _ = load(d, config)
    write_index(d, issues)
    print(issue.path)
    return 0


def set_error(issue, key, value, config, by_number):
    """Why `key=value` can't be set on `issue` (an empty value removes the key), or None."""
    n = issue.number
    if key == "title":
        return "the title is the `# ` line under the frontmatter; edit it there"
    if key in REQUIRED and not value:
        return "`{}:` is required, so it can't be removed".format(key)
    if key == "status":
        if value == "closed" or issue.status == "closed":
            return ("change status with `close {n}` or `reopen {n}`: they also set the `closed:` date "
                    "and the Resolution section").format(n=n)
        if value not in config["statuses"]:
            return "status `{}` isn't one of {}".format(value, ", ".join(config["statuses"]))
    if key == "priority" and value not in config["priorities"]:
        return "priority `{}` isn't one of {}".format(value, ", ".join(config["priorities"]))
    if key in ("opened", "closed") and value and not valid_date(value):
        return "`{}` must be a date as YYYY-MM-DD, not `{}`".format(key, value)
    if key == "closed" and value and issue.status != "closed":
        return "only a closed issue has a `closed:` date; use `close {}`".format(n)
    if key == "closed" and not value and issue.status == "closed":
        return "a closed issue needs its `closed:` date; use `reopen {}` to reopen it".format(n)
    if key == "depends":
        for dep in split_list(value):
            if not dep.isdigit():
                return "depends `{}` isn't an issue number".format(dep)
            if dep.zfill(3) == n:
                return "an issue can't depend on itself"
            if dep.zfill(3) not in by_number:
                return "depends on {}, which doesn't exist".format(dep.zfill(3))
    return None


def cmd_set(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    config = load_config(d)
    issues, _ = load(d, config)
    issue = find_issue(d, issues, args.number)
    by_number = {i.number: i for i in issues}
    updates, removals = {}, set()
    for pair in args.pairs:
        key, sep, value = pair.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or not KEY_RE.match(key):
            sys.exit("`{}` isn't key=value (keys are letters, digits, `-` and `_`)".format(pair))
        if "\n" in value or "\r" in value or re.search(r"\s#", value):
            sys.exit("`{}`: the value must be one line, without ` #` (that starts a comment)".format(key))
        error = set_error(issue, key, value, config, by_number)
        if error:
            sys.exit("Issue {}: {}".format(issue.number, error))
        updates.pop(key, None)
        removals.discard(key)
        if value:
            updates[key] = value
        else:
            removals.add(key)
    text = remove_meta(set_meta(issue.text, updates), removals)
    if text != issue.text:
        write_file(issue.path, text)
    issues, _ = load(d, config)
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


def check(directory, config=None):
    """Return (errors, warnings) as lists of strings."""
    config = config or load_config(directory)
    statuses, prios = config["statuses"], config["priorities"]
    errors, warnings = [], []
    issues, stray = load(directory, config)
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
        if i.status and i.status not in statuses:
            errors.append("{}: status `{}` isn't one of {}".format(where, i.status, ", ".join(statuses)))
        if i.priority and i.priority not in prios:
            errors.append("{}: priority `{}` isn't one of {}".format(where, i.priority, ", ".join(prios)))
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
            if i.hold:
                warnings.append("{}: closed but still on hold; clear it with `set {} hold=`".format(
                    where, i.number))
        elif i.status in statuses:
            if i.meta.get("closed"):
                errors.append("{}: {}, but has a `closed:` date".format(where, i.status))
            if not i.has_done_when:
                warnings.append("{}: {} with no `## Done when` (refine it before executing)".format(
                    where, i.status))
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
    return errors, warnings + repo_warnings(directory)


def hooks_path_is_ours(value, root):
    return value.replace("\\", "/").rstrip("/") in (".githooks", "./.githooks", (root / ".githooks").as_posix())


def same_file(a, b):
    try:
        return os.path.samefile(str(a), str(b))
    except OSError:
        return False


def repo_warnings(directory):
    """Warnings about the git repo holding the backlog: hooks not enabled, stale copies of the scripts."""
    top = git(["rev-parse", "--show-toplevel"], directory)
    if not top:
        return []
    root = Path(top)
    warnings = []
    if (root / ".githooks").is_dir() and not os.environ.get("CI"):
        hooks_path = git(["config", "--get", "core.hooksPath"], root)
        if not hooks_path or not hooks_path_is_ours(hooks_path, root):
            warnings.append("hooks in .githooks/ aren't enabled in this clone: git config core.hooksPath .githooks")
    here = Path(__file__).resolve()
    if same_file(here, root / "scripts" / "backlog.py"):
        return warnings  # this is the repo's copy running (e.g. from the pre-commit hook)
    for name in ("backlog.py", "secret_scan.py"):
        repo_copy, ours = root / "scripts" / name, here.parent / name
        if not repo_copy.is_file() or not ours.is_file() or same_file(repo_copy, ours):
            continue
        if repo_copy.read_bytes().replace(b"\r\n", b"\n") != ours.read_bytes().replace(b"\r\n", b"\n"):
            warnings.append("scripts/{} differs from the plugin's copy ({}); re-run `sb-backlog install-hook --force` "
                            "to update it".format(name, __version__))
    return warnings


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


def cmd_run_checks(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    checks = load_config(d)["checks"]
    if not checks:
        print("No checks configured: add `checks = [\"<command>\", ...]` to {}".format(d / CONFIG_FILE),
              file=sys.stderr)
        return 3
    top = git(["rev-parse", "--show-toplevel"], d)
    root = Path(top) if top else Path.cwd()
    failed = 0
    for command in checks:
        result = subprocess.run(command, shell=True, cwd=str(root), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        if result.returncode == 0:
            print("PASS {}".format(command))
        else:
            failed += 1
            print("FAIL {} (exit {})".format(command, result.returncode))
            for line in (result.stdout or "").splitlines()[-20:]:
                print("    " + line)
        sys.stdout.flush()
    return 1 if failed else 0


def hook_block(rel, secret_scan):
    """The pre-commit lines install-hook manages, between its two marker comments."""
    lines = [
        HOOK_START + " (written by `backlog.py install-hook`; re-run it to change them) >>>",
        'for PY in python3 python "py -3"; do $PY -c "" >/dev/null 2>&1 && break; done  # Windows: skip Store stub',
        'if ! $PY -c "" >/dev/null 2>&1; then',
        '    echo "pre-commit: no Python found (python3, python or py -3)." >&2',
        '    echo "(To commit anyway: git commit --no-verify)" >&2',
        "    exit 1",
        "fi",
        "if git diff --cached --name-only | grep -q '^{}/'; then".format(rel.replace(".", "\\.")),
        "    if ! $PY scripts/backlog.py --dir {} check; then".format(rel),
        "        echo",
        '        echo "Fix the backlog problems above, then commit again."',
        '        echo "(To commit anyway: git commit --no-verify)"',
        "        exit 1",
        "    fi",
        "fi",
    ]
    if secret_scan:
        lines += [
            "if ! $PY scripts/secret_scan.py --staged; then",
            "    echo",
            '    echo "Unstage the secret above, or mark a false positive with: secret-scan: ignore"',
            '    echo "(To commit anyway: git commit --no-verify)"',
            "    exit 1",
            "fi",
        ]
    return lines + [HOOK_END + " <<<"]


def merge_hook(existing, block):
    """Hook text with `block` added (after the shebang) or replacing the marked lines; None if not sh."""
    if not existing or not existing.strip():
        head = ["#!/bin/sh", "# Enable once per clone:  git config core.hooksPath .githooks"]
        return "\n".join(head + block) + "\n"
    lines = existing.splitlines()
    start = next((k for k, l in enumerate(lines) if l.startswith(HOOK_START)), None)
    if start is not None:
        end = next((k for k in range(start, len(lines)) if lines[k].startswith(HOOK_END)), None)
        if end is None:
            sys.exit("The hook has a `{}` line but no `{}` line; fix it by hand.".format(HOOK_START, HOOK_END))
        lines[start:end + 1] = block
    elif lines[0].startswith("#!"):
        if not re.search(r"\b(sh|bash|dash|ksh|zsh)\b", lines[0]):
            return None
        lines[1:1] = block + [""]
    else:
        lines[0:0] = ["#!/bin/sh"] + block + [""]
    return "\n".join(lines) + "\n"


def same_text(a, b):
    return a.replace("\r\n", "\n") == b.replace("\r\n", "\n")


def cmd_install_hook(args):
    d = backlog_dir(args.dir)
    require_dir(d)
    top = git(["rev-parse", "--show-toplevel"], d)
    if not top:
        sys.exit("{} isn't inside a git repository.".format(d))
    root = Path(top)
    rel = (git(["rev-parse", "--show-prefix"], d) or "").strip("/")
    if not rel or not re.match(r"^[A-Za-z0-9_.][A-Za-z0-9_./-]*$", rel):
        sys.exit("install-hook needs the backlog in a subdirectory of the repo whose path is letters, digits, "
                 "`.`, `_`, `-` and `/` (got `{}`).".format(rel or "."))
    here = Path(__file__).resolve().parent
    names = ["backlog.py"] + (["secret_scan.py"] if args.with_secret_scan else [])
    copies = []
    for name in names:
        src = here / name
        if not src.is_file():
            sys.exit("{} isn't next to backlog.py in {}.".format(name, here))
        text = src.read_text(encoding="utf-8")
        dest = root / "scripts" / name
        if dest.exists():
            if same_text(dest.read_text(encoding="utf-8", errors="replace"), text):
                print("Already current: scripts/{}".format(name))
                continue
            if not args.force:
                sys.exit("scripts/{} already exists and differs from this version; "
                         "pass --force to replace it.".format(name))
        copies.append((dest, text))
    hook = root / ".githooks" / "pre-commit"
    existing = hook.read_text(encoding="utf-8") if hook.exists() else None
    new = merge_hook(existing, hook_block(rel, args.with_secret_scan))
    if new is None:
        sys.exit(".githooks/pre-commit isn't a shell script, so install-hook can't extend it. Add these lines "
                 "to it, or run them from it:\n" + "\n".join(hook_block(rel, args.with_secret_scan)))
    for dest, text in copies:
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_file(dest, text)
        print("Copied {} to scripts/{}".format(dest.name, dest.name))
    if existing is not None and same_text(existing, new):
        print("Already current: .githooks/pre-commit")
    else:
        hook.parent.mkdir(parents=True, exist_ok=True)
        write_file(hook, new)
        print("{} .githooks/pre-commit".format("Updated" if existing else "Wrote"))
    os.chmod(str(hook), os.stat(str(hook)).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    hooks_path = git(["config", "--get", "core.hooksPath"], root)
    if not hooks_path:
        print("Enable it once per clone:  git config core.hooksPath .githooks")
    elif hooks_path_is_ours(hooks_path, root):
        print("core.hooksPath is already .githooks.")
    else:
        print("core.hooksPath is set to `{}`, so git won't run .githooks/pre-commit. Left as is: point it at "
              ".githooks, or call .githooks/pre-commit from the hook there.".format(hooks_path))
    print("On Windows, where chmod doesn't reach git, commit it with:  git add --chmod=+x .githooks/pre-commit")
    return 0


def main(argv=None):
    utf8_output()
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["github"]:  # the backlog in GitHub Issues: see backlog_github.py
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            import backlog_github
        except ImportError:
            sys.exit("`github` needs backlog_github.py next to backlog.py (it ships with the plugin).")
        return backlog_github.main(argv[1:])
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dir", help="backlog directory (default: $BACKLOG_DIR, else issues/ at the git root)")
    ap.add_argument("--version", action="version", version="backlog.py " + __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create the backlog directory and README")
    p.add_argument("--refresh-readme", action="store_true",
                   help="rewrite an existing README's text above the index table from the current template")

    p = sub.add_parser("list", help="list issues")
    p.add_argument("--status", default="open", help="a status, or all (default: open)")
    p.add_argument("--priority")
    p.add_argument("--area")
    p.add_argument("--reachable", action="append", metavar="NAME",
                   help="a runs-on place this call can work in, besides repo and .backlog.toml's `reachable` "
                        "(repeatable, or comma-separated)")
    p.add_argument("--json", action="store_true")

    sub.add_parser("next", help="print the next free number")

    p = sub.add_parser("new", help="create an issue")
    p.add_argument("--title", required=True)
    p.add_argument("--priority", help="default: the middle priority (P2)")
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

    p = sub.add_parser("reopen", help="reopen a closed issue")
    p.add_argument("number")
    p.add_argument("--date", help="date for the Earlier resolution heading (default: today)")

    p = sub.add_parser("hold", help="put an issue on hold so agents don't retry it")
    p.add_argument("number")
    p.add_argument("--reason", required=True, help="why it's on hold (one line)")
    p.add_argument("--date", help="date the hold starts (default: today)")

    p = sub.add_parser("set", help="set frontmatter fields")
    p.add_argument("number")
    p.add_argument("pairs", nargs="+", metavar="key=value", help="`key=` with no value removes the key")

    sub.add_parser("index", help="rewrite the README index table")

    p = sub.add_parser("check", help="validate issue files and the index")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")

    sub.add_parser("run-checks", help="run the `checks` commands from .backlog.toml at the git root")

    p = sub.add_parser("install-hook", help="run `check` from .githooks/pre-commit")
    p.add_argument("--with-secret-scan", action="store_true", help="also run secret_scan.py --staged")
    p.add_argument("--force", action="store_true", help="replace a different scripts/backlog.py or secret_scan.py")

    args = ap.parse_args(argv)
    return {"init": cmd_init, "list": cmd_list, "next": cmd_next, "new": cmd_new, "close": cmd_close,
            "reopen": cmd_reopen, "hold": cmd_hold, "set": cmd_set, "index": cmd_index, "check": cmd_check,
            "run-checks": cmd_run_checks, "install-hook": cmd_install_hook}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
