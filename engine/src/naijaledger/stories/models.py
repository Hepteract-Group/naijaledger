"""Scrollytelling story documents (spec 0038 / web NarrativeStory)."""

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class StoryCitation(BaseModel):
    id: str
    label: str
    href: str | None = None


class StoryVisualStat(BaseModel):
    kind: Literal["stat"]
    title: str
    value: str
    detail: str | None = None


class StoryVisualQuote(BaseModel):
    kind: Literal["quote"]
    title: str
    detail: str


class StoryVisualPlaceholder(BaseModel):
    kind: Literal["placeholder"]
    title: str
    detail: str | None = None


StoryVisual = Annotated[
    StoryVisualStat | StoryVisualQuote | StoryVisualPlaceholder,
    Field(discriminator="kind"),
]


class StoryStep(BaseModel):
    id: str
    headline: str
    body: str
    visual: StoryVisual
    citations: list[StoryCitation]


class StoryNext(BaseModel):
    label: str
    to: str


class NarrativeStoryDocument(BaseModel):
    """Approved narrative payload (demo flag is never persisted)."""

    slug: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1)
    lede: str = Field(min_length=1)
    steps: list[StoryStep] = Field(min_length=1)
    next: StoryNext


class PublishedStory(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    slug: str
    title: str
    lede: str
    demo: Literal[False] = False
    steps: list[StoryStep]
    next: StoryNext
    published_at: datetime
    review_decision_id: UUID | None = None


_narrative_adapter = TypeAdapter(NarrativeStoryDocument)


def parse_narrative(raw: Any) -> NarrativeStoryDocument:
    return _narrative_adapter.validate_python(raw)
