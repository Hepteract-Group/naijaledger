## Summary
Closes #

What changed and **why** (focus on the why).

## Spec
Which spec does this satisfy? `specs/NNNN-...md` (or N/A + reason)

## How verified
- [ ] lint
- [ ] typecheck
- [ ] tests
- [ ] acceptance criteria met

## Rollback
How to revert this safely if needed.

## Merge review (required before self-merge)
- Reviewer model: <!-- e.g. claude-opus-4-8-thinking-medium -->
- Implementer model: <!-- e.g. composer / session -->
- Verdict: <!-- approve | approve-with-fixes (fixed in <sha>) | block → needs-human -->
- Notes / link: <!-- short summary or comment URL -->

Trivial docs/typo (under ~20 lines): write `merge-review: skipped (trivial)` instead.

## Merge eligibility (per AGENTS.md)
- [ ] CI green
- [ ] Reversible, low/medium risk (no public-claim publication, secrets, destructive migration, or `needs-human`)
- [ ] Trail is clear
- [ ] Merge review attested (or trivial skip)
If any box is unchecked → label `needs-human` and request review.
