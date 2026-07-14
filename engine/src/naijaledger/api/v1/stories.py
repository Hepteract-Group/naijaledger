from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from naijaledger.api.schemas import Page, PublicStory
from naijaledger.stories.service import (
    StoryNotFoundError,
    get_story,
    get_story_by_slug,
    list_stories,
)

router = APIRouter(tags=["stories"])

_DESCRIPTION = (
    "Human-approved narrative stories only. Rows appear after approve_publish "
    "with a scrollytelling payload in review meta. Never auto-published."
)


@router.get(
    "/stories",
    response_model=Page[PublicStory],
    summary="List published narrative stories",
    description=_DESCRIPTION,
)
def list_stories_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
) -> Page[PublicStory]:
    items = list_stories(connection, limit=limit, offset=offset)
    return Page(
        items=[PublicStory.model_validate(item.model_dump()) for item in items],
        limit=limit,
        offset=offset,
        count=len(items),
    )


@router.get(
    "/stories/by-slug/{slug}",
    response_model=PublicStory,
    summary="Get a published story by slug",
    description=_DESCRIPTION,
)
def get_story_by_slug_endpoint(
    slug: str,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicStory:
    try:
        story = get_story_by_slug(connection, slug)
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="story not found") from exc
    return PublicStory.model_validate(story.model_dump())


@router.get(
    "/stories/{story_id}",
    response_model=PublicStory,
    summary="Get a published story by id",
    description=_DESCRIPTION,
)
def get_story_endpoint(
    story_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicStory:
    try:
        story = get_story(connection, story_id)
    except StoryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="story not found") from exc
    return PublicStory.model_validate(story.model_dump())
