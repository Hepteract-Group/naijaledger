"""Human-review queue (E8.3 / spec 0022)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.agents.story import StoryDraft, VerificationReport
from naijaledger.review.models import DecidedKind, ReviewDecision, ReviewEnqueue

_COLUMNS = """
    id, subject_type, subject_id, decision, reviewer, rationale, decided_at,
    meta, created_at, updated_at
"""


class ReviewNotFoundError(LookupError):
    pass


class ReviewStateError(ValueError):
    pass


class ReviewPermissionError(PermissionError):
    pass


def _row_to_decision(row: Row[Any]) -> ReviewDecision:
    mapping = row._mapping
    return ReviewDecision(
        id=mapping["id"],
        subject_type=mapping["subject_type"],
        subject_id=mapping["subject_id"],
        decision=mapping["decision"],
        reviewer=mapping["reviewer"],
        rationale=mapping["rationale"],
        decided_at=mapping["decided_at"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def get_review_decision(connection: Connection, decision_id: UUID) -> ReviewDecision:
    try:
        row = connection.execute(
            text(f"SELECT {_COLUMNS} FROM review_decisions WHERE id = :id"),
            {"id": decision_id},
        ).one()
    except NoResultFound as exc:
        raise ReviewNotFoundError(str(decision_id)) from exc
    return _row_to_decision(row)


def enqueue_review(connection: Connection, data: ReviewEnqueue) -> ReviewDecision:
    existing = connection.execute(
        text(
            f"""
            SELECT {_COLUMNS}
            FROM review_decisions
            WHERE subject_type = :subject_type
              AND subject_id = :subject_id
              AND decision = 'pending'
            FOR UPDATE
            """
        ),
        {"subject_type": data.subject_type, "subject_id": data.subject_id},
    ).first()
    if existing is not None:
        return _row_to_decision(existing)

    row = connection.execute(
        text(
            f"""
            INSERT INTO review_decisions (subject_type, subject_id, decision, meta)
            VALUES (:subject_type, :subject_id, 'pending', CAST(:meta AS jsonb))
            RETURNING {_COLUMNS}
            """
        ),
        {
            "subject_type": data.subject_type,
            "subject_id": data.subject_id,
            "meta": json.dumps(data.meta) if data.meta is not None else None,
        },
    ).one()
    return _row_to_decision(row)


def list_pending_reviews(connection: Connection, *, limit: int = 100) -> list[ReviewDecision]:
    rows = connection.execute(
        text(
            f"""
            SELECT {_COLUMNS}
            FROM review_decisions
            WHERE decision = 'pending'
            ORDER BY created_at ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()
    return [_row_to_decision(row) for row in rows]


def _assert_reviewer_for_decision(decision: DecidedKind, reviewer: str) -> None:
    if not reviewer.strip():
        raise ReviewPermissionError("reviewer required")
    if decision == "approve_publish":
        if reviewer.startswith("agent:") or reviewer.startswith("system:"):
            raise ReviewPermissionError(
                "approve_publish requires a human reviewer (not agent:/system:)"
            )
    elif reviewer.startswith("agent:"):
        raise ReviewPermissionError("agent: reviewers cannot decide reviews")


def decide_review(
    connection: Connection,
    decision_id: UUID,
    *,
    decision: DecidedKind,
    reviewer: str,
    rationale: str | None = None,
) -> ReviewDecision:
    _assert_reviewer_for_decision(decision, reviewer)
    current = get_review_decision(connection, decision_id)
    if current.decision != "pending":
        raise ReviewStateError(f"review is {current.decision}, not pending")
    result = connection.execute(
        text(
            """
            UPDATE review_decisions
            SET decision = :decision,
                reviewer = :reviewer,
                rationale = :rationale,
                decided_at = now(),
                updated_at = now()
            WHERE id = :id AND decision = 'pending'
            """
        ),
        {
            "id": decision_id,
            "decision": decision,
            "reviewer": reviewer,
            "rationale": rationale,
        },
    )
    if result.rowcount != 1:
        raise ReviewStateError("review is no longer pending")
    return get_review_decision(connection, decision_id)


def is_approved_for_publish(connection: Connection, subject_type: str, subject_id: UUID) -> bool:
    row = connection.execute(
        text(
            """
            SELECT decision
            FROM review_decisions
            WHERE subject_type = :subject_type
              AND subject_id = :subject_id
              AND decision <> 'pending'
            ORDER BY decided_at DESC, updated_at DESC, id DESC
            LIMIT 1
            """
        ),
        {"subject_type": subject_type, "subject_id": subject_id},
    ).first()
    return row is not None and row.decision == "approve_publish"


def enqueue_story_for_review(
    connection: Connection,
    story: StoryDraft,
    report: VerificationReport,
) -> ReviewDecision:
    meta = {
        "story_id": str(story.id),
        "story_title": story.title,
        "verified": report.ok,
        "claim_count": len(story.claims),
    }
    if not report.ok:
        latest = connection.execute(
            text(
                f"""
                SELECT {_COLUMNS}
                FROM review_decisions
                WHERE subject_type = 'story'
                  AND subject_id = :subject_id
                  AND decision = 'needs_more_evidence'
                ORDER BY decided_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"subject_id": story.id},
        ).first()
        if latest is not None:
            return _row_to_decision(latest)
        row = connection.execute(
            text(
                f"""
                INSERT INTO review_decisions (
                    subject_type, subject_id, decision, reviewer, rationale, decided_at, meta
                ) VALUES (
                    'story', :subject_id, 'needs_more_evidence', 'system:verification',
                    :rationale, now(), CAST(:meta AS jsonb)
                )
                RETURNING {_COLUMNS}
                """
            ),
            {
                "subject_id": story.id,
                "rationale": "verification failed",
                "meta": json.dumps(meta),
            },
        ).one()
        return _row_to_decision(row)

    return enqueue_review(
        connection,
        ReviewEnqueue(subject_type="story", subject_id=story.id, meta=meta),
    )
