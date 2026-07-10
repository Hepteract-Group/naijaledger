# AGENTS.md — Working agreement for AI agents on NaijaLedger

> Read this **first** in every session. It is intentionally small.
> Detailed reference lives in `.cursor/rules/` and the design docs in `docs/architecture/`.

---

## Project anchor

| Thing | Value |
|---|---|
| Product | **NaijaLedger** — open civic-accountability data platform for Nigeria (public-finance transparency + election-results verification) |
| Org | `Hepteract-Group` (UK umbrella) |
| Repo | `Hepteract-Group/naijaledger` (default branch `main`) |
| Design (source of truth) | `docs/architecture/SYSTEM_DESIGN.md`, `data-model.md`, `ROADMAP.md` |
| Specs | `specs/` (spec-driven development — see below) |
| Stack | Python 3.11+ engine (`/engine`), TypeScript + React/Vite web (`/web`) |
| Method | **Spec-driven development** + **self-directed loop** (see below) |

---

## Prime directives

1. **The design docs are the source of truth.** Build what they describe. If code and docs
   disagree, one of them is a bug — open an issue and reconcile.
2. **Spec before build** for anything non-trivial (see "Spec-driven"). No spec, no big PR.
3. **AI proposes, humans dispose — for *published claims*.** Any data surfaced to the public as
   fact must pass a human `review_decisions` gate. Never auto-publish accusations.
4. **Provenance always.** Every datum links to `source document + page/region` and a fetch record.
5. **Functional code only** — no classes unless a framework requires them.
6. **Never commit secrets** (`.env`, tokens, keys, credentials) or personal data.
7. **Leave a trail.** Every change is a ticket → branch → small commits → PR that explains *what*
   and *why*, and is revertible.

---

## The loop (memorise this)

NaijaLedger is built by agents running a **self-directed loop**. One iteration:

1. **Pick** the highest-priority open issue on the project board that is unblocked and unassigned
   (respect dependency order in `ROADMAP.md`). Assign yourself; move to **In progress**.
2. **Spec** — if the issue is labelled `needs-spec` (or is non-trivial), write/refresh a spec in
   `specs/` first (see below). If the issue is labelled `needs-human`, **stop and escalate**
   (comment with the decision needed) instead of guessing.
3. **Branch** from fresh `main`: `<type>/<issue#>-<slug>`, `<type>` ∈ `feat|fix|chore|docs|spec`.
4. **Implement** in small, focused commits. Run typecheck + lint + tests before pushing.
5. **Self-review (up to 3 passes).** Review your own diff end-to-end, fix what you find, repeat
   until a pass finds nothing. Verify against the spec's acceptance criteria.
6. **PR** with `gh pr create`; body must `Closes #N`, summarise *what/why*, list how it was verified,
   and note rollback. Move ticket to **In review**.
7. **Merge review (stronger model).** A *different, stronger* model than the implementer reviews
   the PR (see `.cursor/rules/merge-review.mdc`). Implement must/should fixes; escalate
   ambiguities with `needs-human`. Attest reviewer model + verdict on the PR before merge.
8. **Merge policy** (see next section) — auto-merge if eligible (including merge-review gate),
   else request human review.
9. **Reflect & seed the next iteration.** After merge, run a gap check: did you spot missing
   implementation, tech debt, or a follow-up? **Create new issues** for them (don't silently drop
   them). Then start the loop again.

The loop continues until the board has no eligible unblocked issues, or a `needs-human` gate is hit.

## Merge policy (this project ALLOWS agent merges — with guardrails)

You **may** merge your own PR **only if ALL of these hold**:
- CI is green (lint + typecheck + tests all pass).
- The change is **reversible** (normal commit on `main`; no history rewrite) and the PR documents
  how to roll it back.
- The change is **low/medium risk**: code/docs/specs/tests only. It does **not** touch:
  publication of public-facing claims, security/secrets, destructive data migrations, deletion of
  evidentiary data, or anything labelled `needs-human`.
- The PR body clearly explains what changed and why (auditable trail).
- Self-review reached a clean pass and acceptance criteria are met.
- Merge review by a stronger model is attested on the PR (`approve` or fixes landed after
  `approve-with-fixes`); no unresolved `ambiguous` / `block` findings.

Otherwise: open the PR, apply `needs-human`, and **wait**. Always prefer escalation when uncertain —
the user has asked to be involved specifically in **areas of uncertainty**.

Never: `push --force` to `main`, hard-reset shared history, delete branches with unmerged work,
skip hooks, or bypass CI.

---

## Spec-driven development

- Specs live in `specs/` and follow `specs/TEMPLATE.md`.
- A spec defines: problem, scope/non-scope, design, data contracts/schemas, acceptance criteria
  (testable), risks, and open questions.
- For `needs-spec` / non-trivial work: **write the spec, open a `spec/*` PR, and either merge it
  (if low-risk and clear) or escalate `needs-human`** before writing implementation code.
- Implementation PRs link the spec they satisfy. If reality diverges from the spec mid-build,
  update the spec in the same PR.

---

## Hard guardrails (do NOT skip)
- Never publish unverified public claims (human gate required).
- Never commit secrets or personal data.
- Never scrape sources in violation of law/ToS; closed sources go through the FOI/legal workstream.
- Functional code only.
- Keep the base context lean — add new instructions as `.cursor/rules/*.mdc`, not by growing this file.

---

## Where to find more detail
| Rule file | Loaded when |
|---|---|
| `.cursor/rules/loop-workflow.mdc` | Always — the self-directed loop + merge policy |
| `.cursor/rules/merge-review.mdc` | Always — stronger-model merge review before self-merge |
| `.cursor/rules/spec-driven.mdc` | When creating/refreshing a spec |
| `.cursor/rules/functional-code.mdc` | Always |
| `.cursor/rules/provenance-and-verification.mdc` | When touching ingestion/extraction/publication |
| `.cursor/rules/security-and-privacy.mdc` | Always |
| `.cursor/rules/workflow-tickets.mdc` | When creating issues / using the project board |

## When in doubt
- Architectural / ambiguous / high-impact → **escalate `needs-human`** (that is what the human is for).
- Don't know an ID, path, or scope → look it up, don't guess.
