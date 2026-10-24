#!/usr/bin/env python3
"""Find secrets in a git repo before it's pushed or made public.

  secret_scan.py                 scan the tracked files in the working tree
  secret_scan.py --history       also scan every line ever added, on every ref
  secret_scan.py --staged        scan only what's staged (for a pre-commit hook)
  secret_scan.py --json          machine-readable findings

Exits 1 when anything is found, 0 when clean. Matches are printed redacted.

Suppress a false positive with `secret-scan: ignore` on the same line, or list
path globs (one per line) in `.secretscanignore` at the repo root.

Pattern matching finds the common shapes, not every secret. If gitleaks or
trufflehog is installed, run it too.
"""

import argparse
import fnmatch
import json
import math
import re
import subprocess
import sys
from pathlib import Path

RULES = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY")),
    ("wireguard-key", re.compile(r"(?i)\b(?:PrivateKey|PresharedKey|WIREGUARD_PRIVATE_KEY)\s*[=:]\s*['\"]?([A-Za-z0-9+/]{42,43}=)")),
    ("aws-access-key", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b")),
    ("github-token", re.compile(r"\b((?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{50,})\b")),
    ("slack-token", re.compile(r"\b(xox[abprs]-[A-Za-z0-9-]{10,})\b")),
    ("anthropic-key", re.compile(r"\b(sk-ant-[A-Za-z0-9_-]{20,})")),
    ("openai-key", re.compile(r"\b(sk-(?:proj-)?[A-Za-z0-9_-]{32,})")),
    ("google-api-key", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b")),
    ("stripe-key", re.compile(r"\b((?:sk|rk)_live_[A-Za-z0-9]{20,})\b")),
    ("jwt", re.compile(r"\b(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})")),
    ("xml-api-key", re.compile(r"(?i)<(?:ApiKey|Password|Secret|Token)>([^<\s]{12,})</")),
    ("url-credentials", re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s:/@'\"]+:([^\s@/'\"]{6,})@[^\s'\"]+")),
    ("assignment", re.compile(
        r"(?i)\b[\w.-]*(?:api[_-]?key|apikey|secret|token|passw(?:or)?d|passwd|client[_-]?secret|auth[_-]?key)"
        r"[\w.-]*['\"]?\s*[:=]\s*['\"]?([^\s'\"#,;}{)]{8,})")),
]

PLACEHOLDER = re.compile(
    r"(?i)^(?:\$\{?[\w:.-]+\}?|\{env:[^}]+\}|<[^>]*>|%\(?\w+\)?s?|\{\{.*\}\}|x{4,}|\*{4,}|\.{3,}"
    r"|changeme|change[_-]?me|example\w*|placeholder|redacted|dummy|sample|your[\w-]*|none|null|true|false"
    r"|password|secret|token|string|required|optional)$")

SENSITIVE_FILES = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "id_rsa", "id_ed25519", "id_ecdsa",
                   "*.kdbx", "credentials.json", "*.tfstate", ".netrc", ".pgpass", "wg*.conf"]
SAFE_FILES = [".env.example", ".env.sample", ".env.template", "*.pub"]
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pdf", ".zip", ".gz", ".tgz", ".woff",
                 ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".mkv", ".lock", ".svg"}


def entropy(s):
    if not s:
        return 0.0
    counts = {c: s.count(c) for c in set(s)}
    return -sum(n / len(s) * math.log2(n / len(s)) for n in counts.values())


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, errors="replace", check=True).stdout


def looks_secret(value):
    """A generic `key = value` match counts only if the value looks like a credential, not code."""
    if PLACEHOLDER.match(value) or re.search(r"[(\[]", value):
        return False
    if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", value) and not re.search(r"\d", value):
        return False  # an identifier or attribute path such as os.environ or self.token
    return entropy(value) >= 3.0 and (bool(re.search(r"\d", value)) or len(value) >= 16)


def redact(value):
    return value[:4] + "…" + "({} chars)".format(len(value)) if len(value) > 8 else "…"


def scan_line(line):
    if "secret-scan: ignore" in line:
        return []
    found = []
    for rule, rx in RULES:
        for m in rx.finditer(line):
            value = m.group(1) if m.groups() else m.group(0)
            if rule == "assignment":
                if not looks_secret(value):
                    continue
            elif rule == "url-credentials" and PLACEHOLDER.match(value):
                continue
            found.append((rule, value))
        if found and rule != "assignment":
            break  # the specific rule wins; don't double-report as a generic assignment
    return found


def ignored(path, globs):
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(Path(path).name, g) for g in globs)


def load_ignores(root):
    f = root / ".secretscanignore"
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text().splitlines() if l.strip() and not l.startswith("#")]


def sensitive_name(path):
    name = Path(path).name
    if any(fnmatch.fnmatch(name, g) for g in SAFE_FILES):
        return False
    return any(fnmatch.fnmatch(name, g) for g in SENSITIVE_FILES)


def scan_tracked(root, globs, staged):
    findings = []
    if staged:
        files = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", cwd=root).split("\0")
    else:
        files = git("ls-files", "-z", cwd=root).split("\0")
    for path in filter(None, files):
        if ignored(path, globs):
            continue
        if sensitive_name(path):
            findings.append({"where": path, "line": None, "rule": "sensitive-file", "match": Path(path).name})
        p = root / path
        if p.suffix.lower() in SKIP_SUFFIXES or not p.is_file() or p.is_symlink():
            continue
        try:
            text = git("show", ":" + path, cwd=root) if staged else p.read_text(encoding="utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError):
            continue
        if "\0" in text[:8000]:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for rule, value in scan_line(line):
                findings.append({"where": path, "line": n, "rule": rule, "match": redact(value)})
    return findings


def scan_history(root, globs):
    findings, seen = [], set()
    log = git("log", "--all", "-p", "-U0", "--no-color", "--no-renames", "--format=@@commit %h", cwd=root)
    commit, path = None, None
    for line in log.splitlines():
        if line.startswith("@@commit "):
            commit = line.split()[1]
        elif line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
            if path and sensitive_name(path) and not ignored(path, globs) and (path, "file") not in seen:
                seen.add((path, "file"))
                findings.append({"where": "{} (commit {})".format(path, commit), "line": None,
                                 "rule": "sensitive-file", "match": Path(path).name})
        elif line.startswith("+") and path and not ignored(path, globs) \
                and Path(path).suffix.lower() not in SKIP_SUFFIXES:
            for rule, value in scan_line(line[1:]):
                key = (path, rule, value)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({"where": "{} (commit {})".format(path, commit), "line": None,
                                 "rule": rule, "match": redact(value)})
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", nargs="?", default=".", help="any path inside the repo (default: .)")
    ap.add_argument("--history", action="store_true", help="also scan all history on all refs")
    ap.add_argument("--staged", action="store_true", help="scan only staged changes")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        root = Path(git("rev-parse", "--show-toplevel", cwd=args.path).strip())
    except (OSError, subprocess.CalledProcessError):
        sys.exit("{} isn't inside a git repository".format(args.path))
    globs = load_ignores(root)
    findings = scan_tracked(root, globs, args.staged)
    if args.history:
        findings += scan_history(root, globs)
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            loc = f["where"] + (":{}".format(f["line"]) if f["line"] else "")
            print("{}: {}: {}".format(loc, f["rule"], f["match"]))
        print("{} finding(s){}".format(len(findings), "" if findings else ": clean"), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
