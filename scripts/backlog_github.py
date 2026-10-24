#!/usr/bin/env python3
"""GitHub Issues as the backlog: the same JSON shape as `backlog.py list --json`.

  backlog.py github list [--status open|closed|all] [--repo OWNER/NAME] [--json]
  backlog.py github from-json FILE [--status ...] [--json]

`list` reads the issues through the gh CLI's REST calls (`gh api`; installed and logged in). Without gh,
fetch the issues another way (e.g. the GitHub MCP tools), save them as a JSON list, and pass the file to
`from-json` ("-" reads stdin). Both the REST names (created_at, html_url) and gh's GraphQL names
(createdAt, url) are accepted.

Fields read from each issue: number, title, body, state, labels, assignees, created/closed dates, url.
They map onto the file format like this:

  priority   a label P1, P2 or P3 (also "priority: P1", "priority/p1"), else a "Priority: P1" line in the body
  area       every other label, minus an "area:" prefix
  owner      the first assignee
  depends    "Depends on #12" or "Blocked by #12, #14" lines in the body
  sections   `## ` headings in the body: Done when, Needs <someone> (a checklist), and so on

Standard library only.
"""

import argparse
import json
import re
import subprocess
import sys

PRIORITIES = ("P1", "P2", "P3")
PRIORITY_LABEL = re.compile(r"(?i)^(?:priority\s*[:/ -]\s*)?(p[123])$")
DEPENDS_LINE = re.compile(r"(?im)^\W*(?:depends on|blocked by)\b(.*)$")
DONE_RE = re.compile(r"^(done when|close when|acceptance( criteria)?)\b", re.I)
STEP_RE = re.compile(r"\s*(?:[-*]|\d+[.)])\s")
TICKED_RE = re.compile(r"\s*(?:[-*]|\d+[.)])\s+\[[xX]\]")
PRIORITY_LINE = re.compile(r"(?im)^\W*priority\W*\s*(p[123])\b")
GH_JQ = (".[] | select(.pull_request == null) | {number, title, body, state, created_at, closed_at, html_url,"
         " labels: [.labels[].name], assignees: [.assignees[].login]}")


def sections_of(body):
    """Return [(heading, [lines])] for each `## ` heading in a Markdown body."""
    out = []
    for line in (body or "").replace("\r\n", "\n").splitlines():
        if line.startswith("## "):
            out.append((line[3:].strip(), []))
        elif out:
            out[-1][1].append(line)
    return out


def unticked_needs(sections):
    """`## Needs ...` sections that still have steps to do (done once every step is `- [x]`)."""
    names = []
    for name, lines in sections:
        if name.lower().startswith("needs"):
            steps = [l for l in lines if STEP_RE.match(l)]
            if not steps or not all(TICKED_RE.match(l) for l in steps):
                names.append(name)
    return names


def normalize(raw):
    """Map gh/GitHub API issue dicts onto the dicts `backlog.py list --json` prints."""
    issues = []
    for it in raw:
        labels = [(l.get("name") if isinstance(l, dict) else str(l)) or "" for l in it.get("labels") or []]
        priority, areas = "", []
        for name in labels:
            m = PRIORITY_LABEL.match(name.strip())
            if m:
                priority = priority or m.group(1).upper()
            else:
                areas.append(re.sub(r"(?i)^area\s*[:/]\s*", "", name.strip()))
        body = it.get("body") or ""
        if not priority:
            m = PRIORITY_LINE.search(body)
            priority = m.group(1).upper() if m else ""
        depends = []
        for m in DEPENDS_LINE.finditer(body):
            depends += ["#" + n for n in re.findall(r"#(\d+)", m.group(1)) if "#" + n not in depends]
        secs = sections_of(body)
        assignees = it.get("assignees") or []
        created = it.get("createdAt") or it.get("created_at") or ""
        closed = it.get("closedAt") or it.get("closed_at") or ""
        state = (it.get("state") or "").lower()
        issues.append({
            "number": "#{}".format(it["number"]),
            "file": it.get("html_url") or it.get("url") or "",
            "title": it.get("title") or "",
            "status": "closed" if state == "closed" else "open",
            "priority": priority,
            "area": areas,
            "opened": created[:10] or None,
            "closed": closed[:10] or None,
            "depends": depends,
            "owner": (assignees[0].get("login") if isinstance(assignees[0], dict) else assignees[0]) if assignees else None,
            "sections": [name for name, _ in secs],
            "needs_human": unticked_needs(secs),
            "_has_done_when": any(DONE_RE.match(name) for name, _ in secs),
        })
    state = {i["number"]: i["status"] for i in issues}
    for i in issues:
        i["open_depends"] = [d for d in i["depends"] if state.get(d) == "open"]
        i["ready"] = (i["status"] == "open" and i.pop("_has_done_when") and not i["open_depends"]
                      and not i["needs_human"])
        i.pop("_has_done_when", None)
    return issues


def select(issues, status):
    sel = [i for i in issues if status == "all" or i["status"] == status]
    sel.sort(key=lambda i: (PRIORITIES.index(i["priority"]) if i["priority"] in PRIORITIES else 9,
                            int(i["number"].lstrip("#"))))
    return sel


def fetch(repo):
    # REST rather than `gh issue list`, which needs GraphQL (not available everywhere).
    path = "repos/{}/issues?state=all&per_page=100".format(repo or "{owner}/{repo}")
    cmd = ["gh", "api", path, "--paginate", "--jq", GH_JQ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        sys.exit("The gh CLI isn't installed. Fetch the issues another way and use `github from-json`.")
    if out.returncode != 0:
        sys.exit("gh failed: {}\n(Is it logged in? `gh auth status`.) Or fetch the issues another way and use "
                 "`github from-json`.".format(out.stderr.strip()))
    return [json.loads(line) for line in out.stdout.splitlines() if line.strip()]


def show(issues, as_json):
    if as_json:
        print(json.dumps(issues, indent=2))
        return
    for i in issues:
        flags = []
        if i["open_depends"]:
            flags.append("blocked by " + ", ".join(i["open_depends"]))
        if i["needs_human"]:
            flags.append("needs a person")
        if i["status"] == "open" and not i["ready"] and not flags:
            flags.append("no 'Done when'")
        if not i["priority"]:
            flags.append("no priority label")
        print("{:>5}  {:2}  {:6}  {}{}".format(i["number"], i["priority"] or "--", i["status"], i["title"],
                                               "  [" + "; ".join(flags) + "]" if flags else ""))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="backlog.py github", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "from-json"):
        p = sub.add_parser(name)
        if name == "from-json":
            p.add_argument("file", help="JSON list of issues, or - for stdin")
        else:
            p.add_argument("--repo", help="OWNER/NAME (default: the current repo)")
        p.add_argument("--status", default="open", choices=("open", "closed", "all"))
        p.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if args.cmd == "list":
        raw = fetch(args.repo)
    else:
        f = sys.stdin if args.file == "-" else open(args.file, encoding="utf-8")
        with f:
            raw = json.load(f)
    show(select(normalize(raw), args.status), args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
