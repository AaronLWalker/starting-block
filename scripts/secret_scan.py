#!/usr/bin/env python3
"""Find secrets in a git repo before it's pushed or made public.

  secret_scan.py                     scan the tracked files in the working tree
  secret_scan.py --history           also scan every line ever added, on every ref
  secret_scan.py --since REV         like --history, but only commits not reachable from REV
  secret_scan.py --staged            scan only what's staged (for a pre-commit hook)
  secret_scan.py --json              machine-readable findings
  secret_scan.py --baseline FILE     don't report the findings accepted in FILE
  secret_scan.py --write-baseline FILE   write every current finding to FILE
  secret_scan.py --version           print the version

Exits 1 when anything is found, 0 when clean or after --write-baseline.
Matches are printed redacted. History is read from `git log` as it streams.

Suppress a false positive with `secret-scan: ignore` on the same line, or list
path globs (one per line) in `.secretscanignore` at the repo root.

Pattern matching finds the common shapes, not every secret. If `gitleaks` is on
PATH it is run too (`--no-gitleaks` turns that off) and its findings are merged
in as `gitleaks:<RuleID>`: `gitleaks detect --redact` over the working tree
(`--no-git`, limited to tracked files), or over history (`--log-opts=--all`)
with --history or --since. If it can't run or its report can't be read, that's
a warning, not a failure. --staged never runs gitleaks: a pre-commit hook
should be quick and give the same answer on every machine; add
`gitleaks protect --staged` to the hook yourself if you want it.

Baseline file (JSON, UTF-8), for findings you've checked and accepted:

  {"version": 1,
   "findings": [{"where": "config.xml (commit 0123456789ab)", "line": 4,
                 "rule": "xml-api-key", "match": "4f9c…(32 chars)",
                 "sha256": "<hex SHA-256 of the matched value>"}]}

An entry suppresses a finding with the same where, rule and sha256; line and
match are only for people reading the file. The value itself is never stored,
but a hash of a short or guessable password can be brute-forced, so baseline
only false positives and secrets that have been rotated. History findings name
the commit by its first 12 hex digits. gitleaks redacts values before we see
them, so its entries hash its fingerprint (`commit:file:rule:line`, file
relative to the repo) instead, and a working-tree entry from gitleaks goes
stale when its line moves.
"""

import argparse
import base64
import binascii
import fnmatch
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

__version__ = "0.5.0"

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
    ("azure-storage-key", re.compile(r"(?i)\bAccountKey\s*=\s*([A-Za-z0-9+/]{86}==)")),
    ("npm-token", re.compile(r"\b(npm_[A-Za-z0-9]{36})\b")),
    ("pypi-token", re.compile(r"\b(pypi-AgEIcHlwaS5vcmc[A-Za-z0-9_-]{50,})")),
    ("huggingface-token", re.compile(r"\b(hf_[A-Za-z0-9]{34,})\b")),
    ("discord-bot-token", re.compile(
        r"(?<![\w-])([MNO][A-Za-z0-9]{23,26}\.[A-Za-z0-9_-]{6,7}\.[A-Za-z0-9_-]{27,38})(?![\w-])")),
    ("telegram-bot-token", re.compile(r"(?<![\w:-])(\d{8,10}:A[A-Za-z0-9_-]{34})(?![\w-])")),
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

# A GCP service-account key file: reported once, on its private_key line, instead of as a bare private key.
SERVICE_ACCOUNT = re.compile(r'"type"\s*:\s*"service_account"')
SERVICE_ACCOUNT_KEY = re.compile(r'"private_key"\s*:\s*"([^"]{100,})"')

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")

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
    return subprocess.run(["git", "-c", "core.quotepath=off", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def git_lines(*args, cwd):
    """Yield git's output a line at a time, so a large history is never held in memory whole.
    Raises CalledProcessError once the output is read if git failed."""
    cmd = ["git", "-c", "core.quotepath=off", *args]
    with tempfile.TemporaryFile() as err:  # a file, not a pipe: a full stderr pipe would stall git
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=err, text=True,
                                encoding="utf-8", errors="replace")
        try:
            for line in proc.stdout:
                yield line.rstrip("\n")
        finally:
            proc.stdout.close()
            code = proc.wait()
        if code:
            err.seek(0)
            raise subprocess.CalledProcessError(code, cmd, stderr=err.read().decode("utf-8", "replace"))


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def looks_secret(value):
    """A generic `key = value` match counts only if the value looks like a credential, not code."""
    if PLACEHOLDER.match(value) or re.search(r"[(\[]", value):
        return False
    if re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", value) and not re.search(r"\d", value):
        return False  # an identifier or attribute path such as os.environ or self.token
    return entropy(value) >= 3.0 and (bool(re.search(r"\d", value)) or len(value) >= 16)


def random_enough(value):
    """Real tokens are random; xxxx… placeholders and repeated characters aren't."""
    return entropy(value) >= 3.0


def mixed_case(value):
    return bool(re.search(r"[a-z]", value) and re.search(r"[A-Z]", value))


def discord_token(value):
    """The first part of a Discord bot token is the bot's numeric user ID, base64-encoded."""
    first = value.split(".")[0]
    try:
        user_id = base64.b64decode(first + "=" * (-len(first) % 4), validate=True)
    except (binascii.Error, ValueError):
        return False
    return user_id.isdigit() and 17 <= len(user_id) <= 20 and random_enough(value)


CHECKS = {
    "assignment": looks_secret,
    "url-credentials": lambda v: not PLACEHOLDER.match(v),
    "azure-storage-key": random_enough,
    "npm-token": random_enough,
    "pypi-token": random_enough,
    "huggingface-token": lambda v: mixed_case(v[3:]) and random_enough(v),
    "discord-bot-token": discord_token,
    "telegram-bot-token": lambda v: random_enough(v.split(":", 1)[1]),
}


def redact(value):
    return value[:4] + "…" + "({} chars)".format(len(value)) if len(value) > 8 else "…"


def scan_line(line):
    if "secret-scan: ignore" in line:
        return []
    found = []
    for rule, rx in RULES:
        check = CHECKS.get(rule)
        for m in rx.finditer(line):
            value = m.group(1) if m.groups() else m.group(0)
            if check and not check(value):
                continue
            found.append((rule, value))
        if found and rule != "assignment":
            break  # the specific rule wins; don't double-report as a generic assignment
    return found


def scan_document(lines):
    """Scan the (line number, text) pairs of one file, or of the lines one commit added to it.
    Returns (line number, rule, value) triples."""
    found, keys, service_account = [], [], False
    for n, line in lines:
        found += [(n, rule, value) for rule, value in scan_line(line)]
        if "secret-scan: ignore" in line:
            continue
        service_account = service_account or bool(SERVICE_ACCOUNT.search(line))
        keys += [(n, m.group(1)) for m in SERVICE_ACCOUNT_KEY.finditer(line)]
    if service_account and keys:
        key_lines = {n for n, _ in keys}
        found = [f for f in found if f[0] not in key_lines] + [(n, "gcp-service-account", v) for n, v in keys]
        found.sort(key=lambda f: f[0])
    return found


def ignored(path, globs):
    return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(Path(path).name, g) for g in globs)


def load_ignores(root):
    f = root / ".secretscanignore"
    if not f.exists():
        return []
    return [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]


def sensitive_name(path):
    name = Path(path).name
    if any(fnmatch.fnmatch(name, g) for g in SAFE_FILES):
        return False
    return any(fnmatch.fnmatch(name, g) for g in SENSITIVE_FILES)


def finding(where, line, rule, value, match=None):
    return {"where": where, "line": line, "rule": rule, "match": redact(value) if match is None else match,
            "sha256": digest(value)}


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
            findings.append(finding(path, None, "sensitive-file", Path(path).name, Path(path).name))
        p = root / path
        if p.suffix.lower() in SKIP_SUFFIXES or not p.is_file() or p.is_symlink():
            continue
        try:
            text = git("show", ":" + path, cwd=root) if staged else p.read_text(encoding="utf-8", errors="replace")
        except (OSError, subprocess.CalledProcessError):
            continue
        if "\0" in text[:8000]:
            continue
        for n, rule, value in scan_document(enumerate(text.splitlines(), 1)):
            findings.append(finding(path, n, rule, value))
    return findings


def history_files(lines):
    """Group `git log -p -U0` output into (commit, path, [(line number, added text)]), one per file per commit.
    path is None for a deleted file."""
    commit = path = None
    added, n, header = [], 0, False
    for line in lines:
        if line.startswith("@@commit ") or line.startswith("diff "):
            if commit and (path or added):
                yield commit, path, added
            if line.startswith("@@commit "):
                commit = line.split()[1]
            path, added, header = None, [], line.startswith("diff ")
        elif header and line.startswith("+++ "):
            path = line[6:] if line.startswith("+++ b/") else None
        elif line.startswith("@@"):
            header = False
            m = HUNK.match(line)
            n = int(m.group(1)) if m else 0
        elif not header and line.startswith("+"):
            added.append((n, line[1:]))
            n += 1
    if commit and (path or added):
        yield commit, path, added


def scan_history(root, globs, since=None):
    findings, seen = [], set()
    args = ["log", "--all", "-p", "-U0", "--no-color", "--no-renames", "--no-ext-diff", "--format=@@commit %H"]
    if since:
        args += ["--not", since]
    for commit, path, added in history_files(git_lines(*args, cwd=root)):
        if not path or ignored(path, globs):
            continue
        where = "{} (commit {})".format(path, commit[:12])
        if sensitive_name(path) and (path, "file") not in seen:
            seen.add((path, "file"))
            findings.append(finding(where, None, "sensitive-file", Path(path).name, Path(path).name))
        if Path(path).suffix.lower() in SKIP_SUFFIXES:
            continue
        for n, rule, value in scan_document(added):
            key = (path, rule, value)
            if key in seen:
                continue
            seen.add(key)
            findings.append(finding(where, n, rule, value))
    return findings


def relative_path(name, root):
    """gitleaks prints repo-relative paths for history and source-joined ones for --no-git."""
    if os.path.isabs(name):
        try:
            name = Path(name).relative_to(root).as_posix()
        except ValueError:
            name = os.path.relpath(name, str(root))
    name = name.replace("\\", "/")
    return name[2:] if name.startswith("./") else name


def read_gitleaks_report(report, root, globs=(), tracked=None):
    """Turn a gitleaks JSON report into findings. tracked, if given, limits them to those paths
    (gitleaks --no-git also reads untracked and ignored files, such as a local .env)."""
    with open(str(report), encoding="utf-8") as f:
        entries = json.load(f)
    if not isinstance(entries, list):
        raise ValueError("expected a JSON list of findings")
    findings = []
    for e in entries:
        if not isinstance(e, dict) or not e.get("File") or not e.get("RuleID"):
            continue
        path = relative_path(str(e["File"]), root)
        if ignored(path, globs) or (tracked is not None and path not in tracked) \
                or "secret-scan: ignore" in str(e.get("Line") or ""):
            continue
        commit = str(e.get("Commit") or "")
        where = "{} (commit {})".format(path, commit[:12]) if commit else path
        line = e.get("StartLine") if isinstance(e.get("StartLine"), int) and e.get("StartLine") > 0 else None
        rule = "gitleaks:{}".format(e["RuleID"])
        secret = str(e.get("Secret") or "")
        # gitleaks' Fingerprint, rebuilt with a repo-relative path (--no-git prints the clone's absolute path)
        ident = "{}{}:{}:{}".format(commit + ":" if commit else "", path, e["RuleID"], line)
        found = finding(where, line, rule, ident, "…" if not secret or "REDACTED" in secret else redact(secret))
        findings.append(found)
    return findings


def merge(findings, extra):
    """Add extra findings, skipping any at a file and line already reported."""
    seen = {(f["where"], f["line"]) for f in findings if f["line"]}
    return findings + [f for f in extra if not (f["line"] and (f["where"], f["line"]) in seen)]


def warn(msg):
    print("warning: " + msg, file=sys.stderr)


def run_gitleaks(exe, root, globs, history, since=None):
    """Run gitleaks over history or the working tree. Returns findings, or None (with a warning) if it failed."""
    with tempfile.TemporaryDirectory() as tmp:
        report = os.path.join(tmp, "gitleaks.json")
        cmd = [exe, "detect", "--no-banner", "--redact", "--report-format", "json", "--report-path", report,
               "--source", str(root)]
        if history:
            cmd.append("--log-opts=--all" + (" --not " + since if since else ""))  # gitleaks splits it on spaces
        else:
            cmd.append("--no-git")
        try:
            tracked = None if history else set(filter(None, git("ls-files", "-z", cwd=root).split("\0")))
            proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8",
                                  errors="replace")
        except (OSError, subprocess.CalledProcessError) as e:
            warn("couldn't run gitleaks: {}".format(e))
            return None
        if proc.returncode not in (0, 1) or (proc.returncode and not os.path.exists(report)):
            last = [l for l in (proc.stderr or "").splitlines() if l.strip()][-1:] or ["no output"]
            warn("gitleaks exited {} ({}); its findings are left out".format(proc.returncode, last[0][:200]))
            return None
        if not os.path.exists(report):
            return []
        try:
            return read_gitleaks_report(report, root, globs, tracked)
        except (OSError, ValueError) as e:
            warn("couldn't read the gitleaks report ({}); its findings are left out".format(e))
            return None


def load_baseline(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {(e["where"], e["rule"], e["sha256"]) for e in data["findings"]}
    except (OSError, ValueError, KeyError, TypeError) as e:
        sys.exit("can't read baseline {}: {}".format(path, e))


def write_baseline(path, findings):
    entries = sorted(findings, key=lambda f: (f["where"], f["line"] or 0, f["rule"]))
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"version": 1, "findings": entries}, indent=2, ensure_ascii=False) + "\n")


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # Windows consoles default to a legacy code page
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("path", nargs="?", default=".", help="any path inside the repo (default: .)")
    ap.add_argument("--history", action="store_true", help="also scan all history on all refs")
    ap.add_argument("--since", metavar="REV", help="scan only commits not reachable from REV (implies --history)")
    ap.add_argument("--staged", action="store_true", help="scan only staged changes")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--baseline", metavar="FILE", help="don't report findings listed in this baseline file")
    ap.add_argument("--write-baseline", metavar="FILE", help="write the current findings to FILE and exit 0")
    ap.add_argument("--no-gitleaks", action="store_true", help="don't run gitleaks, even if it's installed")
    ap.add_argument("--version", action="version", version="secret_scan.py " + __version__)
    args = ap.parse_args(argv)
    try:
        root = Path(git("rev-parse", "--show-toplevel", cwd=args.path).strip())
    except (OSError, subprocess.CalledProcessError):
        sys.exit("{} isn't inside a git repository".format(args.path))
    since = None
    if args.since:
        try:
            if args.since.startswith("-"):
                raise ValueError
            since = git("rev-parse", "--verify", "--quiet", args.since + "^{commit}", cwd=root).strip()
        except (ValueError, subprocess.CalledProcessError):
            sys.exit("--since: {} isn't a commit in this repository".format(args.since))
    history = args.history or bool(since)
    accepted = load_baseline(args.baseline) if args.baseline else set()
    globs = load_ignores(root)
    try:
        findings = scan_tracked(root, globs, args.staged)
        if history:
            findings += scan_history(root, globs, since)
    except subprocess.CalledProcessError as e:
        sys.exit("git failed: {}".format((e.stderr or "").strip() or e))
    gitleaks = None if args.no_gitleaks or args.staged else shutil.which("gitleaks")
    if gitleaks:
        extra = run_gitleaks(gitleaks, root, globs, history, since)
        if extra is None:
            gitleaks = None
        else:
            findings = merge(findings, extra)
    if args.write_baseline:
        write_baseline(args.write_baseline, findings)
        print("wrote {} finding(s) to {}".format(len(findings), args.write_baseline), file=sys.stderr)
        return 0
    suppressed = [f for f in findings if (f["where"], f["rule"], f["sha256"]) in accepted]
    findings = [f for f in findings if (f["where"], f["rule"], f["sha256"]) not in accepted]
    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            loc = f["where"] + (":{}".format(f["line"]) if f["line"] else "")
            print("{}: {}: {}".format(loc, f["rule"], f["match"]))
        notes = ["{} in baseline".format(len(suppressed))] if suppressed else []
        notes += ["with gitleaks"] if gitleaks else []
        print("{} finding(s){}{}".format(len(findings), "" if findings else ": clean",
                                         " ({})".format(", ".join(notes)) if notes else ""), file=sys.stderr)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
