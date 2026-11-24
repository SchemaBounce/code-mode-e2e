---
paths:
  - '.github/workflows/**'
---

# CI Triggers: Pre-commit Is the Gate, Actions Verify Once Per Promotion

## Absolute Rule

**Pre-commit hooks are the pre-merge gate. GitHub Actions run once per
promotion (`push: branches: [main]`) to verify what already passed locally,
plus `workflow_dispatch` for a manual re-run. No workflow in this repo uses a
`pull_request` trigger at all: no `opened`, no `reopened`, no `synchronize`,
nothing on `development`, nothing on feature branches.**

User ruling, 2026-08-29/30: "We are paying too much money for GitHub Actions.
Move gates into pre-commit hooks. I will build far less often. Stay efficient."

## The contract

1. **Pre-commit is the gate.** `.husky/pre-commit` (frontend) and
   `.githooks/pre-commit` (core-api) run scoped tests, lint, type-check, and
   the cross-repo contract checks. Cross-repo contracts read the sibling
   checkout (`../core-api` or `../frontend`), never a token or an API. A gate
   that can run locally goes in the hook, never in a workflow.
2. **Test, coverage, contract, and validation workflows** fire only on
   `push: branches: [main]` plus `workflow_dispatch`. One post-merge
   verification per promotion.
3. **Deploy workflows** fire on `push: branches: [main]` only, with
   `timeout-minutes` set.
4. **Scheduled runs** are allowed only for checks that need a runner and are
   not tied to a code change, at weekly cadence or slower, against
   production: Lighthouse (weekly, prod URLs), govulncheck / security scan
   (weekly, core-api), the Constellation index (weekly). Anything else
   periodic stays out of Actions.
5. **Every job has `timeout-minutes`.** A hung runner bills until GitHub's
   6-hour default kills it.

### Allowed trigger shapes

```yaml
# Test / coverage / contract / validation
on:
  push:
    branches: [main]
    paths: [...] # Keep it. Skips no-op promotions.
  workflow_dispatch:

# Deploy
on:
  push:
    branches: [main]
    paths: [...]
  workflow_dispatch:

# Weekly prod audit (Lighthouse, security scan, Constellation index)
on:
  schedule:
    - cron: '0 9 * * 1' # Weekly or slower. Never daily, never hourly.
  workflow_dispatch:
```

### Prohibited

- `pull_request:` on any workflow, with any `types:` or `branches:` filter
- `push: branches: [development]`, `push: branches: ['**']`, or any
  feature-branch push
- `schedule:` on anything tied to a code change (tests, coverage, builds,
  contracts), or on any check more often than weekly
- A job without `timeout-minutes`
- Adding a workflow for a check that `.husky/pre-commit` could run

## Why

Thirty days ending 2026-08-30, this repo, 51 promotions to `main`:

- Test Coverage: 1,096 job-minutes, 35 of 66 runs failed (two suites broken
  on `main`, see `llmCatalogResolver.test.ts` and `machinePaths.test.ts`).
- Lighthouse: 363 job-minutes.
- Smoke on build: 299 job-minutes.
- Agent Control Plane E2E: 236 job-minutes.

Every one of those was driven by the promotion count, and the PR-opened run
doubled it: the same commit was built and tested twice (opened, then
post-merge). Pre-commit already runs the scoped tests, lint, and type-check
on every commit to `development`, so the PR run repeated work that had
already passed on the author's machine.

### Why weekly cron replaces the old "no cron" rule

The previous version of this file banned `schedule:` outright and ran
Lighthouse and the security scan on every promotion instead. That cost
about 12 minutes per promotion, twice per promotion (build plus audit), for a
result that only changes when production changes. A weekly audit against the
production URLs costs about 3 minutes and reads the site users actually see.
The old objections still hold for anything more frequent: weekend red-X
noise, pages from transient env failures, coverage nobody reads. Weekly
against prod is the cadence that keeps the signal and drops the cost.

## Re-running after a promotion

If the post-merge run fails, fix on `development` and run the scoped test
locally. Do not add a trigger to "make CI run on my dev push". Use
`gh workflow run <workflow>.yml --ref main` or the Actions UI when you need
the runner again.

## Workflows covered

What exists after the 2026-08-30 change:

- `test-coverage.yml`: push main + dispatch. Runs `vitest --changed
<before-sha>` sharded (see `scoped-tests.md`).
- `deploy-cloudflare.yml`: push main. Includes the bundle smoke check that
  `smoke-on-build.yml` used to run.
- `security-scan.yml`: weekly + dispatch. npm audit against main; a weekly sweep catches advisories on dependencies that did not change.
- `lighthouse.yml`: weekly, against production URLs.
- `constellation-index.yml`: weekly.

Deleted: `smoke-on-build.yml`, `agent-control-plane-e2e.yml`,
`tier-pricing-contract.yml`. Their checks moved to pre-commit or into
`deploy-cloudflare.yml`.

## When adding a new check

1. Can it run locally? Put it in `.husky/pre-commit`, scoped per
   `scoped-tests.md`. Stop here.
2. Does it need a runner and follow a code change? Add a job to an existing
   push-main workflow, with `paths:` and `timeout-minutes`.
3. Does it need a runner and audit production on its own clock? Weekly
   `schedule:` plus `workflow_dispatch`, against prod, with
   `timeout-minutes`.
4. Never add `pull_request:`.

## Related

- `scoped-tests.md`: this rule governs when a workflow fires; that one governs
  what it runs. Both must hold.
- core-api `.githooks/pre-commit`: the sibling gate for backend changes.
