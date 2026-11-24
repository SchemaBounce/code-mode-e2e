#!/usr/bin/env python3
"""Mechanical gate for the GitHub Actions trigger contract.

The contract is prose in .claude/rules/ci-triggers.md (frontend) and
.claude/rules/ci-path-filters.md plus CLAUDE.md (core-api). Prose let an agent add
`schedule: - cron: '0 */6 * * *'` to deploy-cloudflare.yml on 2026-11-24 (prod
code session cs_13el654u) with a comment "CONFLICT FOR REVIEW". This script
encodes exactly what the rule says, nothing stricter:

  1. No `pull_request` / `pull_request_target` trigger, on any workflow.
  2. `push` fires only on branch `main` (never development, '**', a feature
     branch, or no branch filter).
  3. `schedule:` only on the allowlisted audit workflows, and every cron weekly
     or slower: Lighthouse, security scan, Constellation index.
  4. Every job has `timeout-minutes` (a job that calls a reusable workflow with
     `uses:` cannot set one and is exempt; the called workflow's jobs are checked).
  5. A push-triggered workflow keeps a `paths:` filter.

Existing violations live in a baseline file that can only shrink: a violation
not in the baseline fails, a baseline entry that no longer violates fails (delete
it), and `--check-baseline-shrink` fails a commit that adds an entry.

Usage:
  check-workflow-triggers.py [--root DIR] [--baseline FILE] [FILE ...]
  check-workflow-triggers.py --check-baseline-shrink   (compares with HEAD)
Exit 0 clean, 1 violations, 2 cannot parse.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

# Taken from the rule file: "Lighthouse (weekly, prod URLs), govulncheck /
# security scan (weekly, core-api), the Constellation index (weekly)."
SCHEDULE_ALLOWLIST = {"lighthouse.yml", "security-scan.yml", "constellation-index.yml"}
BASELINE_DEFAULT = ".github/workflow-triggers-baseline.json"
_DOW = r"(?:[0-7]|sun|mon|tue|wed|thu|fri|sat)"
_INT = re.compile(r"^\d+$")


def load_yaml(path):
    try:
        import yaml  # PyYAML
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except ImportError:
        pass
    # No PyYAML (a Node-only sandbox): the repo's `yaml` npm package parses it.
    code = ("const Y=require('yaml'),fs=require('fs');"
            "console.log(JSON.stringify(Y.parse(fs.readFileSync(process.argv[1],'utf8'))))")
    out = subprocess.run(["node", "-e", code, path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError("need PyYAML or node with the `yaml` package: " + out.stderr.strip())
    return json.loads(out.stdout)


def rule_doc(root):
    for name in ("ci-triggers.md", "ci-path-filters.md"):
        if os.path.exists(os.path.join(root, ".claude/rules", name)):
            return ".claude/rules/" + name
    return ".claude/rules/ci-triggers.md"


def cron_is_weekly_or_slower(expr):
    """Fixed minute and hour, and a single weekday or a single day of month."""
    f = str(expr).split()
    if len(f) != 5:
        return False
    minute, hour, dom, month, dow = f
    if not (_INT.match(minute) and _INT.match(hour)):
        return False
    if not (month == "*" or _INT.match(month)):
        return False
    one_dow = re.fullmatch(_DOW, dow.lower()) is not None
    one_dom = _INT.match(dom) is not None
    return (dom == "*" and one_dow) or (one_dom and dow == "*") or (one_dom and one_dow)


def check_file(path, root):
    """Return a list of (key, message) violations for one workflow file."""
    doc = rule_doc(root)
    name = os.path.basename(path)
    wf = load_yaml(path) or {}
    on = wf.get("on", wf.get(True))  # PyYAML reads the key `on` as boolean True
    if isinstance(on, str):
        on = {on: None}
    elif isinstance(on, list):
        on = {e: None for e in on}
    on = on or {}
    v = []

    for ev in ("pull_request", "pull_request_target"):
        if ev in on:
            v.append((f"{name}::{ev}", f"{name}: `{ev}:` is banned on every workflow ({doc}). "
                      "Pre-commit is the pre-merge gate; run the check in the pre-commit hook, or trigger "
                      "the workflow with `push: branches: [main]` plus `workflow_dispatch`."))

    if "push" in on:
        push = on["push"] or {}
        branches = push.get("branches") if isinstance(push, dict) else None
        if branches is None and isinstance(push, dict) and "tags" in push:
            pass  # tag-only push is not a branch push
        elif branches is None or list(map(str, branches if isinstance(branches, list) else [branches])) != ["main"]:
            v.append((f"{name}::push-branches", f"{name}: `push` must list exactly `branches: [main]` ({doc}). "
                      "Never development, '**' or a feature branch. Use `gh workflow run <file> --ref <branch>` "
                      "or `workflow_dispatch` when you need the runner on other code."))
        if not isinstance(push, dict) or "paths" not in push:
            v.append((f"{name}::push-paths", f"{name}: a push-triggered workflow keeps a `paths:` filter ({doc}) "
                      "so promotions that do not touch its domain skip it."))

    if "schedule" in on:
        crons = [str(e.get("cron", "")) for e in (on["schedule"] or []) if isinstance(e, dict)]
        if name not in SCHEDULE_ALLOWLIST:
            v.append((f"{name}::schedule", f"{name}: `schedule:` is allowed only on {sorted(SCHEDULE_ALLOWLIST)} "
                      f"({doc}, 'Scheduled runs'). Anything tied to a code change (tests, builds, deploys, "
                      "contracts) or periodic outside those audits stays out of Actions. Instead: add the check to "
                      "the pre-commit hook, or run it on `push: branches: [main]` plus `workflow_dispatch`, and "
                      "leave out the schedule. Do not add a 'conflict for review' comment; ask the person."))
        for c in crons:
            if not cron_is_weekly_or_slower(c):
                v.append((f"{name}::cron:{c}", f"{name}: cron '{c}' runs more often than weekly ({doc}: "
                          "'Weekly or slower. Never daily, never hourly'). Use a form like '0 9 * * 1'."))

    for job, spec in (wf.get("jobs") or {}).items():
        if isinstance(spec, dict) and "uses" not in spec and "timeout-minutes" not in spec:
            v.append((f"{name}::timeout:{job}", f"{name}: job '{job}' has no `timeout-minutes` ({doc}). "
                      "A hung runner bills until GitHub's 6-hour default kills it; add the number of minutes "
                      "the job needs plus margin."))
    return v


def load_baseline(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh).get("violations", {})


def check_baseline_shrink(path):
    """Fail when the working baseline holds a key HEAD's baseline lacks."""
    old = subprocess.run(["git", "show", f"HEAD:{path}"], capture_output=True, text=True)
    prior = set(json.loads(old.stdout).get("violations", {})) if old.returncode == 0 else None
    now = set(load_baseline(path))
    if prior is None:
        return []  # the baseline is being created in this commit: seeded once
    return sorted(now - prior)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--root", default=".")
    ap.add_argument("--baseline", default=None)
    ap.add_argument("--check-baseline-shrink", action="store_true")
    a = ap.parse_args(argv)
    os.chdir(a.root)
    base_path = a.baseline or BASELINE_DEFAULT

    if a.check_baseline_shrink:
        grown = check_baseline_shrink(base_path)
        if grown:
            print(f"workflow-triggers: {base_path} may only shrink; new entries: {grown}. Fix the workflow "
                  "instead of baselining it.", file=sys.stderr)
            return 1
        return 0

    files = a.files or sorted(glob.glob(".github/workflows/*.yml") + glob.glob(".github/workflows/*.yaml"))
    baseline = load_baseline(base_path)
    seen, bad = set(), []
    try:
        for f in files:
            if not os.path.exists(f):
                continue  # deleted workflow
            for key, msg in check_file(f, "."):
                seen.add(key)
                if key not in baseline:
                    bad.append(msg)
    except Exception as e:  # unparsable: a gate that cannot tell blocks
        print(f"workflow-triggers: cannot parse workflows: {e}", file=sys.stderr)
        return 2
    if not a.files:  # a full scan can also prove a baseline entry stale
        for key in sorted(set(baseline) - seen):
            bad.append(f"{base_path}: entry '{key}' no longer violates; delete it (the baseline only shrinks).")
    for m in bad:
        print("workflow-triggers: " + m, file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
