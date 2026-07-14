"""Published stories API (spec 0038 / #137)."""

from __future__ import annotations

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection

from naijaledger.api.app import app
from naijaledger.api.deps import get_connection
from naijaledger.review.models import ReviewEnqueue
from naijaledger.review.service import decide_review, enqueue_review
from naijaledger.stories.models import (
    NarrativeStoryDocument,
    StoryCitation,
    StoryNext,
    StoryStep,
    StoryVisualStat,
)
from naijaledger.stories.service import enqueue_narrative_for_review, list_stories


@pytest.fixture
def api_client(db_connection: Connection) -> Generator[TestClient, None, None]:
    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    app.dependency_overrides[get_connection] = _override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def _sample_document(*, slug: str = "follow-the-ledger") -> NarrativeStoryDocument:
    return NarrativeStoryDocument(
        slug=slug,
        title="Follow the ledger",
        lede="Cited narrative without auto-publishing accusations.",
        steps=[
            StoryStep(
                id="source",
                headline="Start from a public source",
                body="Every figure begins as a registered source.",
                visual=StoryVisualStat(
                    kind="stat",
                    title="Provenance",
                    value="1:1",
                    detail="datum to region",
                ),
                citations=[StoryCitation(id="c1", label="Sources", href="/sources")],
            )
        ],
        next=StoryNext(label="Explore", to="/explore"),
    )


def test_stories_empty_page(api_client: TestClient) -> None:
    response = api_client.get("/v1/stories")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["count"] == 0


def test_story_not_found(api_client: TestClient) -> None:
    assert api_client.get(f"/v1/stories/{uuid4()}").status_code == 404
    assert api_client.get("/v1/stories/by-slug/missing").status_code == 404


def test_approve_without_narrative_does_not_publish(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    pending = enqueue_review(
        db_connection,
        ReviewEnqueue(subject_type="story", subject_id=uuid4(), meta={"story_title": "draft"}),
    )
    decide_review(
        db_connection,
        pending.id,
        decision="approve_publish",
        reviewer="human:alice",
    )
    assert list_stories(db_connection) == []
    assert api_client.get("/v1/stories").json()["items"] == []


def test_approve_narrative_publishes_and_reads(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    document = _sample_document()
    pending = enqueue_narrative_for_review(db_connection, document)
    decided = decide_review(
        db_connection,
        pending.id,
        decision="approve_publish",
        reviewer="human:alice",
        rationale="ready",
    )
    assert decided.decision == "approve_publish"

    listed = api_client.get("/v1/stories")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["slug"] == "follow-the-ledger"
    assert items[0]["demo"] is False
    assert items[0]["steps"][0]["visual"]["kind"] == "stat"

    by_slug = api_client.get("/v1/stories/by-slug/follow-the-ledger")
    assert by_slug.status_code == 200
    assert by_slug.json()["id"] == items[0]["id"]

    by_id = api_client.get(f"/v1/stories/{items[0]['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["title"] == document.title


def test_list_order_newest_first(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    first = enqueue_narrative_for_review(db_connection, _sample_document(slug="alpha"))
    decide_review(db_connection, first.id, decision="approve_publish", reviewer="human:alice")
    second = enqueue_narrative_for_review(db_connection, _sample_document(slug="beta"))
    decide_review(db_connection, second.id, decision="approve_publish", reviewer="human:bob")

    slugs = [item["slug"] for item in api_client.get("/v1/stories").json()["items"]]
    assert set(slugs) == {"alpha", "beta"}
    assert len(slugs) == 2
    # Tie-break when published_at matches: slug DESC → beta before alpha.
    assert slugs[0] == "beta"
