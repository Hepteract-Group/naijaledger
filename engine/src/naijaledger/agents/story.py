"""Story draft + verification models (E8.2 / spec 0021)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from naijaledger.agents.models import Citation


class Claim(BaseModel):
    id: UUID
    text: str
    citations: list[Citation] = Field(default_factory=list)
    source_flag_id: UUID | None = None
    subject_type: str | None = None
    subject_id: UUID | None = None


class StoryDraft(BaseModel):
    id: UUID
    title: str
    body: str
    claims: list[Claim] = Field(default_factory=list)
    created_by: str


class VerificationFinding(BaseModel):
    claim_id: UUID
    ok: bool
    reason: str


class VerificationReport(BaseModel):
    story_id: UUID
    ok: bool
    findings: list[VerificationFinding] = Field(default_factory=list)


class ProposeResult(BaseModel):
    story: StoryDraft
    report: VerificationReport
    verified: bool
