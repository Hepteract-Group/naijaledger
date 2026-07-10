"""Narrative drafting and claim verification (E8.2)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from naijaledger.agents.models import (
    AgentAction,
    AgentContext,
    Citation,
    ToolResult,
)
from naijaledger.agents.runtime import run_agent
from naijaledger.agents.story import (
    Claim,
    ProposeResult,
    StoryDraft,
    VerificationFinding,
    VerificationReport,
)
from naijaledger.anomaly.models import Flag

MAX_CLAIMS = 20


def draft_story_from_flags(
    flags: list[Flag] | list[dict[str, Any]],
    *,
    created_by: str = "narrative",
    max_claims: int = MAX_CLAIMS,
) -> StoryDraft:
    claims: list[Claim] = []
    for raw in flags[:max_claims]:
        flag = raw if isinstance(raw, Flag) else _flag_from_dict(raw)
        summary = ""
        if isinstance(flag.evidence, dict):
            summary = str(flag.evidence.get("summary") or "").strip()
        text = f"{flag.rule} on {flag.subject_type}/{flag.subject_id}" + (
            f": {summary}" if summary else ""
        )
        claims.append(
            Claim(
                id=uuid4(),
                text=text,
                citations=[
                    Citation(
                        kind="flag",
                        subject_type=flag.subject_type,
                        subject_id=flag.subject_id,
                        label=flag.rule,
                        detail={"flag_id": str(flag.id), "summary": summary},
                    )
                ],
                source_flag_id=flag.id,
                subject_type=flag.subject_type,
                subject_id=flag.subject_id,
            )
        )

    title = (
        f"Anomaly narrative ({len(claims)} claim{'s' if len(claims) != 1 else ''})"
        if claims
        else "Anomaly narrative (empty)"
    )
    body = "\n\n".join(f"- {claim.text}" for claim in claims) if claims else ""
    return StoryDraft(
        id=uuid4(),
        title=title,
        body=body,
        claims=claims,
        created_by=created_by,
    )


def verify_story(story: StoryDraft) -> VerificationReport:
    findings: list[VerificationFinding] = []
    for claim in story.claims:
        if not claim.text.strip():
            findings.append(
                VerificationFinding(claim_id=claim.id, ok=False, reason="empty claim text")
            )
            continue
        if not claim.citations:
            findings.append(VerificationFinding(claim_id=claim.id, ok=False, reason="no citations"))
            continue
        bad = False
        for citation in claim.citations:
            if not citation.label.strip():
                findings.append(
                    VerificationFinding(
                        claim_id=claim.id, ok=False, reason="citation missing label"
                    )
                )
                bad = True
                break
            if citation.subject_id is None and citation.document_id is None:
                findings.append(
                    VerificationFinding(
                        claim_id=claim.id,
                        ok=False,
                        reason="citation missing subject_id and document_id",
                    )
                )
                bad = True
                break
        if not bad:
            findings.append(
                VerificationFinding(claim_id=claim.id, ok=True, reason="citations present")
            )

    ok = bool(story.claims) and all(finding.ok for finding in findings)
    if not story.claims:
        findings = [
            VerificationFinding(
                claim_id=uuid4(),
                ok=False,
                reason="story has no claims",
            )
        ]
        ok = False
    return VerificationReport(story_id=story.id, ok=ok, findings=findings)


def _flag_from_dict(data: dict[str, Any]) -> Flag:
    return Flag.model_validate(data)


class NarrativeAgent:
    id = "narrative"

    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction:
        if not history:
            return AgentAction(type="call_tool", tool="list_open_flags", args={"limit": 20})
        last = history[-1]
        result = last.get("result") or {}
        flags = result.get("data") if result.get("ok") else []
        if not isinstance(flags, list):
            flags = []
        story = draft_story_from_flags(flags, created_by=self.id)
        return AgentAction(
            type="finish",
            summary=f"drafted story with {len(story.claims)} claims",
            drafts=[story.model_dump(mode="json")],
        )


class VerificationAgent:
    id = "verification"

    def __init__(self, story: StoryDraft) -> None:
        self._story = story

    def step(self, ctx: AgentContext, history: list[dict[str, Any]]) -> AgentAction:
        report = verify_story(self._story)
        return AgentAction(
            type="finish",
            summary="verified" if report.ok else "verification failed",
            drafts=[report.model_dump(mode="json")],
        )


def propose_verified_story(ctx: AgentContext) -> ProposeResult:
    narrative = run_agent(NarrativeAgent(), ctx, max_steps=4)
    if not narrative.finished or not narrative.drafts:
        empty = draft_story_from_flags([])
        report = verify_story(empty)
        return ProposeResult(story=empty, report=report, verified=False)
    story = StoryDraft.model_validate(narrative.drafts[0])
    verification = run_agent(VerificationAgent(story), ctx, max_steps=2)
    if verification.finished and verification.drafts:
        report = VerificationReport.model_validate(verification.drafts[0])
    else:
        report = verify_story(story)
    return ProposeResult(story=story, report=report, verified=report.ok)


def flags_from_tool_result(result: ToolResult) -> list[dict[str, Any]]:
    if not result.ok or not isinstance(result.data, list):
        return []
    return [row for row in result.data if isinstance(row, dict)]
