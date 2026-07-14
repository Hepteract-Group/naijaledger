"""Persist and read published narrative stories (spec 0038)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.review.models import ReviewDecision, ReviewEnqueue
from naijaledger.review.service import enqueue_review
from naijaledger.stories.models import (
    NarrativeStoryDocument,
    PublishedStory,
    StoryNext,
    StoryStep,
    parse_narrative,
)

_COLUMNS = """
    id, slug, title, lede, steps, next_label, next_to,
    review_decision_id, published_at, created_at, updated_at
"""


class StoryNotFoundError(LookupError):
    pass


def _row_to_story(row: Row[Any]) -> PublishedStory:
    mapping = row._mapping
    steps_raw = mapping["steps"]
    if isinstance(steps_raw, str):
        steps_raw = json.loads(steps_raw)
    return PublishedStory(
        id=mapping["id"],
        slug=mapping["slug"],
        title=mapping["title"],
        lede=mapping["lede"],
        demo=False,
        steps=[StoryStep.model_validate(step) for step in steps_raw],
        next=StoryNext(label=mapping["next_label"], to=mapping["next_to"]),
        published_at=mapping["published_at"],
        review_decision_id=mapping["review_decision_id"],
    )


def enqueue_narrative_for_review(
    connection: Connection,
    document: NarrativeStoryDocument,
    *,
    subject_id: UUID | None = None,
) -> ReviewDecision:
    """Enqueue a scrolly narrative for human approve_publish."""
    story_id = subject_id or uuid4()
    meta = {
        "story_title": document.title,
        "story_slug": document.slug,
        "narrative": document.model_dump(mode="json"),
    }
    return enqueue_review(
        connection,
        ReviewEnqueue(subject_type="story", subject_id=story_id, meta=meta),
    )


def publish_story_from_review(
    connection: Connection,
    review: ReviewDecision,
) -> PublishedStory | None:
    """Materialize stories row when approve_publish includes meta.narrative."""
    if review.subject_type != "story" or review.decision != "approve_publish":
        return None
    raw = (review.meta or {}).get("narrative")
    if raw is None:
        return None
    document = parse_narrative(raw)
    steps_json = json.dumps([step.model_dump(mode="json") for step in document.steps])
    row = connection.execute(
        text(
            f"""
            INSERT INTO stories (
                id, slug, title, lede, steps, next_label, next_to,
                review_decision_id, published_at, created_at, updated_at
            ) VALUES (
                :id, :slug, :title, :lede, CAST(:steps AS jsonb),
                :next_label, :next_to, :review_decision_id,
                now(), now(), now()
            )
            ON CONFLICT (id) DO UPDATE SET
                slug = EXCLUDED.slug,
                title = EXCLUDED.title,
                lede = EXCLUDED.lede,
                steps = EXCLUDED.steps,
                next_label = EXCLUDED.next_label,
                next_to = EXCLUDED.next_to,
                review_decision_id = EXCLUDED.review_decision_id,
                published_at = now(),
                updated_at = now()
            RETURNING {_COLUMNS}
            """
        ),
        {
            "id": review.subject_id,
            "slug": document.slug,
            "title": document.title,
            "lede": document.lede,
            "steps": steps_json,
            "next_label": document.next.label,
            "next_to": document.next.to,
            "review_decision_id": review.id,
        },
    ).one()
    return _row_to_story(row)


def list_stories(
    connection: Connection,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[PublishedStory]:
    rows = connection.execute(
        text(
            f"""
            SELECT {_COLUMNS}
            FROM stories
            ORDER BY published_at DESC, created_at DESC, slug DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"limit": limit, "offset": offset},
    ).all()
    return [_row_to_story(row) for row in rows]


def get_story(connection: Connection, story_id: UUID) -> PublishedStory:
    try:
        row = connection.execute(
            text(f"SELECT {_COLUMNS} FROM stories WHERE id = :id"),
            {"id": story_id},
        ).one()
    except NoResultFound as exc:
        raise StoryNotFoundError(str(story_id)) from exc
    return _row_to_story(row)


def get_story_by_slug(connection: Connection, slug: str) -> PublishedStory:
    try:
        row = connection.execute(
            text(f"SELECT {_COLUMNS} FROM stories WHERE slug = :slug"),
            {"slug": slug},
        ).one()
    except NoResultFound as exc:
        raise StoryNotFoundError(slug) from exc
    return _row_to_story(row)
