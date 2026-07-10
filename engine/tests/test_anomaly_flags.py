from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.rules_smoke import SmokeEmptyRule
from naijaledger.anomaly.runner import production_rules, run_anomaly_rules
from naijaledger.anomaly.service import (
    confirm_flag,
    dismiss_flag,
    list_open_flags,
    upsert_open_flag,
)


def test_flags_table_exists(db_connection) -> None:
    assert (
        db_connection.execute(
            text("SELECT 1 FROM information_schema.tables WHERE table_name = 'flags'")
        ).scalar()
        == 1
    )


def test_invalid_rule_fails_check(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO flags (
                        subject_type, subject_id, rule, severity, evidence, status, created_by
                    ) VALUES (
                        'tender', :sid, 'not_a_rule', 'low', '{"summary":"x"}'::jsonb,
                        'open', 'test'
                    )
                    """
                ),
                {"sid": uuid4()},
            )


def test_invalid_severity_fails_check(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO flags (
                        subject_type, subject_id, rule, severity, evidence, status, created_by
                    ) VALUES (
                        'tender', :sid, 'smoke', 'critical', '{"summary":"x"}'::jsonb,
                        'open', 'test'
                    )
                    """
                ),
                {"sid": uuid4()},
            )


def test_invalid_status_fails_check(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO flags (
                        subject_type, subject_id, rule, severity, evidence, status, created_by
                    ) VALUES (
                        'tender', :sid, 'smoke', 'low', '{"summary":"x"}'::jsonb,
                        'published', 'test'
                    )
                    """
                ),
                {"sid": uuid4()},
            )


def test_evidence_without_summary_fails_check(db_connection) -> None:
    with pytest.raises(IntegrityError):
        with db_connection.begin_nested():
            db_connection.execute(
                text(
                    """
                    INSERT INTO flags (
                        subject_type, subject_id, rule, severity, evidence, status, created_by
                    ) VALUES (
                        'tender', :sid, 'smoke', 'low', '{"detail":"no summary"}'::jsonb,
                        'open', 'test'
                    )
                    """
                ),
                {"sid": uuid4()},
            )


def test_upsert_and_review(db_connection) -> None:
    subject_id = uuid4()
    draft = FlagDraft(
        subject_type="tender",
        subject_id=subject_id,
        rule="smoke",
        severity="low",
        evidence={"summary": "first"},
        created_by="smoke",
    )
    first = upsert_open_flag(db_connection, draft)
    assert first is not None
    second = upsert_open_flag(
        db_connection,
        draft.model_copy(update={"evidence": {"summary": "updated"}, "severity": "medium"}),
    )
    assert second is not None
    assert second.id == first.id
    assert second.evidence["summary"] == "updated"
    assert second.severity == "medium"
    assert len(list_open_flags(db_connection)) == 1

    confirmed = confirm_flag(db_connection, first.id, reviewed_by="reviewer")
    assert confirmed.status == "confirmed"
    assert confirmed.reviewed_by == "reviewer"
    assert list_open_flags(db_connection) == []


def test_sticky_dismissal_suppresses_reopen(db_connection) -> None:
    subject_id = uuid4()
    draft = FlagDraft(
        subject_type="award",
        subject_id=subject_id,
        rule="smoke",
        severity="high",
        evidence={"summary": "noise"},
        created_by="smoke",
    )
    flag = upsert_open_flag(db_connection, draft)
    assert flag is not None
    dismiss_flag(db_connection, flag.id, reviewed_by="reviewer")

    suppressed = upsert_open_flag(
        db_connection,
        draft.model_copy(update={"evidence": {"summary": "again"}}),
    )
    assert suppressed is None
    assert list_open_flags(db_connection) == []
    assert (
        db_connection.execute(
            text(
                """
                SELECT count(*) FROM flags
                WHERE rule = 'smoke' AND subject_id = :sid AND status = 'dismissed'
                """
            ),
            {"sid": subject_id},
        ).scalar()
        == 1
    )


def test_sticky_confirm_suppresses_reopen(db_connection) -> None:
    subject_id = uuid4()
    draft = FlagDraft(
        subject_type="contract",
        subject_id=subject_id,
        rule="smoke",
        severity="medium",
        evidence={"summary": "interesting"},
        created_by="smoke",
    )
    flag = upsert_open_flag(db_connection, draft)
    assert flag is not None
    confirm_flag(db_connection, flag.id, reviewed_by="reviewer")
    assert upsert_open_flag(db_connection, draft) is None
    assert list_open_flags(db_connection) == []


def test_dismiss_flag(db_connection) -> None:
    flag = upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="award",
            subject_id=uuid4(),
            rule="smoke",
            severity="high",
            evidence={"summary": "noise"},
            created_by="smoke",
        ),
    )
    assert flag is not None
    dismissed = dismiss_flag(db_connection, flag.id, reviewed_by="reviewer")
    assert dismissed.status == "dismissed"


def test_run_smoke_rule(db_connection) -> None:
    before_flags = db_connection.execute(text("SELECT count(*) FROM flags")).scalar()
    result = run_anomaly_rules(db_connection, [SmokeEmptyRule()])
    assert result.rules_run == ["smoke"]
    assert result.drafts == 0
    assert result.upserted == 0
    assert db_connection.execute(text("SELECT count(*) FROM flags")).scalar() == before_flags
    prod_ids = [rule.id for rule in production_rules()]
    assert "smoke" not in prod_ids
    assert len(prod_ids) == 7
