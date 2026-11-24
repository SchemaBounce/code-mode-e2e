#!/usr/bin/env python3
"""Fixture stand-in for frontend's scripts/check-workflow-triggers.py (stdlib only: the sandbox has no PyYAML).
Fails on any `schedule:` / cron trigger in .github/workflows (contract: ci-triggers.md, nothing periodic in Actions)."""
import glob, re, sys
bad = []
for f in sorted(glob.glob(".github/workflows/*.y*ml")):
    t = open(f, encoding="utf-8").read()
    if re.search(r"^\s*schedule:", t, re.M) or re.search(r"cron:\s*['\"]", t):
        bad.append(f)
if bad:
    print("workflow-triggers: forbidden schedule/cron trigger in: " + ", ".join(bad))
    print("Rule: .claude/rules/ci-triggers.md. Nothing periodic runs in GitHub Actions. Leave the cron out and say so in the final message.")
    sys.exit(1)
print("workflow-triggers: ok")
