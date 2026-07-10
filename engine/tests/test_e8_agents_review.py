from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.agents.models import AgentContext, Citation, register_tools
from naijaledger.agents.narrative import (
    NarrativeAgent,
    draft_story_from_flags,
    propose_verified_story,
    verify_story,
)
from naijaledger.agents.runtime import run_agent
from naijaledger.agents.story import Claim, StoryDraft
from naijaledger.agents.tools import default_tools
from naijaledger.anomaly.models import Flag, FlagDraft
from naijaledger.anomaly.service import upsert_open_flag
from naijaledger.review.models import ReviewEnqueue
from naijaledger.review.service import (
    ReviewPermissionError,
    decide_review,
    enqueue_review,
    enqueue_story_for_review,
    is_approved_for_publish,
    list_pending_reviews,
)


def _sample_flag(**overrides: object) -> Flag:
    base = {
        "id": uuid4(),
        "subject_type": "tender",
        "subject_id": uuid4(),
        "rule": "single_bidder",
        "severity": "medium",
        "evidence": {"summary": "Only one bidder recorded"},
        "status": "open",
        "created_by": "single_bidder",
        "reviewed_by": None,
        "reviewed_at": None,
        "meta": None,
        "created_at": datetime.now(tz=UTC),
        "updated_at": datetime.now(tz=UTC),
    }
    base.update(overrides)
    return Flag.model_validate(base)


def test_draft_story_from_flags() -> None:
    flag = _sample_flag()
    story = draft_story_from_flags([flag])
    assert len(story.claims) == 1
    assert story.claims[0].citations
    assert flag.rule in story.claims[0].text


def test_draft_empty_fails_verification() -> None:
    story = draft_story_from_flags([])
    report = verify_story(story)
    assert report.ok is False


def test_verify_story_requires_citations() -> None:
    claim = Claim(id=uuid4(), text="x", citations=[])
    story = StoryDraft(
        id=uuid4(),
        title="t",
        body="x",
        claims=[claim],
        created_by="test",
    )
    assert verify_story(story).ok is False

    claim2 = Claim(
        id=uuid4(),
        text="ok",
        citations=[
            Citation(
                kind="flag",
                subject_type="tender",
                subject_id=uuid4(),
                label="single_bidder",
            )
        ],
    )
    story2 = StoryDraft(id=uuid4(), title="t", body="ok", claims=[claim2], created_by="test")
    assert verify_story(story2).ok is True


def test_narrative_agent_run(db_connection) -> None:
    upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="tender",
            subject_id=uuid4(),
            rule="smoke",
            severity="low",
            evidence={"summary": "fixture"},
            created_by="smoke",
        ),
    )
    ctx = AgentContext(
        connection=db_connection,
        tools=register_tools(default_tools()),
        run_id=uuid4(),
    )
    result = run_agent(NarrativeAgent(), ctx, max_steps=4)
    assert result.finished is True
    assert result.drafts
    story = StoryDraft.model_validate(result.drafts[0])
    assert story.claims


def test_propose_verified_story(db_connection) -> None:
    upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="award",
            subject_id=uuid4(),
            rule="smoke",
            severity="medium",
            evidence={"summary": "seeded for narrative"},
            created_by="smoke",
        ),
    )
    ctx = AgentContext(
        connection=db_connection,
        tools=register_tools(default_tools()),
        run_id=uuid4(),
    )
    proposed = propose_verified_story(ctx)
    assert proposed.verified is True
    assert proposed.report.ok is True

    exists = db_connection.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'review_decisions'
            """
        )
    ).scalar()
    if exists:
        # Narrative path alone must not write decisions
        before = db_connection.execute(text("SELECT count(*) FROM review_decisions")).scalar()
        propose_verified_story(ctx)
        after = db_connection.execute(text("SELECT count(*) FROM review_decisions")).scalar()
        assert after == before


def test_review_decisions_table(db_connection) -> None:
    assert (
        db_connection.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = 'review_decisions'")
        ).scalar()
        == 1
    )


def test_pending_check_and_unique(db_connection) -> None:
    subject_id = uuid4()
    first = enqueue_review(
        db_connection, ReviewEnqueue(subject_type="story", subject_id=subject_id)
    )
    assert first.decision == "pending"
    second = enqueue_review(
        db_connection, ReviewEnqueue(subject_type="story", subject_id=subject_id)
    )
    assert second.id == first.id
    assert len(list_pending_reviews(db_connection)) >= 1


def test_invalid_pending_with_reviewer_fails_check(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO review_decisions (
                        subject_type, subject_id, decision, reviewer
                    ) VALUES ('story', :sid, 'pending', 'human:x')
                    """
                ),
                {"sid": uuid4()},
            )


def test_decide_and_gate(db_connection) -> None:
    subject_id = uuid4()
    pending = enqueue_review(
        db_connection, ReviewEnqueue(subject_type="story", subject_id=subject_id)
    )
    assert is_approved_for_publish(db_connection, "story", subject_id) is False

    with pytest.raises(ReviewPermissionError):
        decide_review(
            db_connection,
            pending.id,
            decision="approve_publish",
            reviewer="agent:narrative",
        )

    with pytest.raises(ReviewPermissionError):
        decide_review(
            db_connection,
            pending.id,
            decision="approve_publish",
            reviewer="system:verification",
        )

    decided = decide_review(
        db_connection,
        pending.id,
        decision="approve_publish",
        reviewer="human:alice",
        rationale="looks good",
    )
    assert decided.decision == "approve_publish"
    assert is_approved_for_publish(db_connection, "story", subject_id) is True


def test_enqueue_story_verified_and_failed(db_connection) -> None:
    flag = _sample_flag()
    story = draft_story_from_flags([flag])
    report = verify_story(story)
    assert report.ok is True
    pending = enqueue_story_for_review(db_connection, story, report)
    assert pending.decision == "pending"
    assert list_pending_reviews(db_connection)

    empty = draft_story_from_flags([])
    failed = verify_story(empty)
    decision = enqueue_story_for_review(db_connection, empty, failed)
    assert decision.decision == "needs_more_evidence"
    assert decision.reviewer == "system:verification"
    again = enqueue_story_for_review(db_connection, empty, failed)
    assert again.id == decision.id
    assert is_approved_for_publish(db_connection, "story", empty.id) is False


def test_system_needs_more_evidence_via_decide(db_connection) -> None:
    pending = enqueue_review(db_connection, ReviewEnqueue(subject_type="story", subject_id=uuid4()))
    decided = decide_review(
        db_connection,
        pending.id,
        decision="needs_more_evidence",
        reviewer="system:verification",
    )
    assert decided.decision == "needs_more_evidence"
