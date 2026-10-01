---
name: Work
about: Required intake for every epic, feature, task, bug, and chore
title: ""
---

## Type

epic | feature | task | bug | chore — pick one.

## User story

As a _, I want to _, so that _.

## Background / Context

### Current state / problem

### Business driver or technical debt

## Acceptance criteria

- [ ]

### Dependencies on other work

### Epic or feature

<!-- Parent epic or feature link. None if this issue is the epic. -->

## Technical scope

| In scope | Out of scope |
| --- | --- |
| | |

## Design notes

### Architecture modifications

### Technical decisions

### Implementation details

## Assumptions

<!-- Confirmed must be Yes or Accepted risk before implementation. Unconfirmed blocks the branch. -->

| Assumption | Confirmed | Who confirms | Notes |
| --- | --- | --- | --- |
| | No | | |

## Outstanding questions

<!-- Status Open blocks implementation. -->

| Question | Answer | Status |
| --- | --- | --- |
| | | Open |

## Dependencies and restrictions

| Dependency | Internal or external | What it blocks | Restriction |
| --- | --- | --- | --- |
| | | | |

## Risks

| Impact description | Impact scale | Mitigation |
| --- | --- | --- |
| | low | |

Impact scale is high, medium, or low.

## Links

- Epic / parent:
- Related issues:
- Internal docs:
- External docs:

## Testing strategy

<!-- Keep every row. Required is yes or no. Description names the behavior that must pass. -->

| Test | Required | Description |
| --- | --- | --- |
| Unit | | |
| Regression | | |
| Integration | | |
| Performance | | |
| Manual | | |

## Observability

<!-- Logs or metrics this change emits. None, with why, when there is no runtime path. Do not build a log-streaming service unless that service is in scope. -->

| Signal | When it fires | What it includes |
| --- | --- | --- |
| | | |

## Security considerations

<!-- Auth, data, secrets, sandbox, abuse. None, with why, when this change cannot affect them. -->

## Documentation requirements

| Document | Where it lives | Create or update | Done when |
| --- | --- | --- | --- |
| | | | |

<!-- Name the docs this product actually keeps: ADR, runbook, wiki, learning note under docs/learnings/, PAI docs, domain glossary. None, with why, when no doc changes. -->

## Learnings (closeout)

<!-- Fill before closing. Status must be Ready. Empty or Draft blocks close and blocks merge of a PR that closes this issue. -->

| Field | Content |
| --- | --- |
| Status | Draft |
| What we tried | _(fill on close)_ |
| What we learned | _(fill on close)_ |
| What surprised us | None |
| What we would do differently | None |
| Follow-up issues | None |
| Durable note | None — ticket-local only |

Status starts as Draft. Before `gh issue close` or merging a PR with `Closes #N`, set Status to Ready and replace the placeholders with real sentences. If the learning should outlive this ticket, write `docs/learnings/YYYY-MM-DD-<slug>.md`, put that path in Durable note, and add a row to `docs/learnings/README.md`.
