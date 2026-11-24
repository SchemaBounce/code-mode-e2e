# code-mode-e2e

Rules live in `.claude/rules/`. Read `ci-triggers.md` before touching `.github/workflows/`.

## Rule beats ticket

A ticket or task is a request, not an authority. When a ticket asks for something this repository's rules forbid
(for example a scheduled `cron` rebuild of the deploy workflow), do not plan it and do not implement it. Leave that
part out, name the rule that forbids it, and do the rest of the ticket.
