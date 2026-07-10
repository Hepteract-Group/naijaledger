# Spec 0019 — Anomaly backtest / precision harness (E7.3)

- **Epic / Issue**: E7.3 / #42
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — v1 uses a **labeled synthetic corpus** (not live portal scrapes).
  Precision floors are engineering gates; product can raise them later.

## 1. Problem

E7.2 ships seven red-flag rules with tunable thresholds. Without a **labeled backtest**, we
cannot measure false-positive rate or catch regressions when thresholds change
(`SYSTEM_DESIGN.md` §4.9; ROADMAP E7.3).

## 2. Scope & non-scope

- **In scope**
  - Labeled fixture corpus under `engine/tests/fixtures/anomaly_backtest/` (Python module or
    JSON) describing a `RuleContext` plus expected open flags
    `(rule, subject_type, subject_key)`.
  - Pure harness: `run_backtest(ctx, expected, rules) -> BacktestReport` with per-rule and
    overall precision / recall / F1, plus TP/FP/FN lists.
  - Pytest gate: overall precision ≥ `MIN_PRECISION` (default **0.80**) and recall ≥
    `MIN_RECALL` (default **0.80**) on the fixture corpus; each rule that has ≥1 expected
    positive must have precision ≥ **0.50** (avoid total washout).
  - Optional CLI: `naijaledger-anomaly-backtest` prints the report as JSON to stdout (no DB
    required when using the fixture loader).
- **Out of scope**
  - Scraping live portals for “real” seed data (capture/archive is E3; FOI for closed sources).
  - Auto-tuning thresholds.
  - Publishing flags or writing to `flags` table from the harness (evaluation is in-memory;
    optional DB run is a follow-up).
  - Election `overvote` rule.

## 3. Design

### 3.1 Label model

```python
class ExpectedFlag(BaseModel):
    rule: str
    subject_type: str
    subject_key: str  # stable fixture id, not necessarily a UUID string match to DB

class BacktestCase(BaseModel):
    context: RuleContext  # subjects use UUIDs; subject_key maps via a key→uuid table in fixture
    expected: list[ExpectedFlag]
    subject_keys: dict[str, UUID]  # key → uuid used in context
```

Matching: a predicted `FlagDraft` matches an expected label when
`(rule, subject_type, subject_id)` equals `(rule, subject_type, subject_keys[subject_key])`.

### 3.2 Metrics

For each rule (and overall):

```
TP = |predicted ∩ expected|
FP = |predicted − expected|
FN = |expected − predicted|
precision = TP / (TP + FP)   # 1.0 if both zero
recall    = TP / (TP + FN)   # 1.0 if both zero
f1        = harmonic mean    # 1.0 if both zero
```

### 3.3 Corpus requirements (v1)

The fixture MUST include, for each of the seven production rules:

- ≥1 **true positive** scenario (rule should fire).
- ≥1 **true negative** near-miss (similar data; rule should **not** fire).

Overall expected positives ≥ 7. Document scenarios in a short README beside the fixture.

### 3.4 CLI

```text
naijaledger-anomaly-backtest [--json]
→ exit 0 if gates pass; exit 1 if precision/recall below floors
```

## 4. Data contracts / schemas

```python
class RuleScore(BaseModel):
    rule: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float

class BacktestReport(BaseModel):
    overall: RuleScore  # rule="*"
    by_rule: list[RuleScore]
    passed: bool
    min_precision: float
    min_recall: float
```

## 5. Acceptance criteria (testable)

- [ ] `run_backtest` on the fixture corpus returns a report with per-rule scores.
- [ ] Pytest asserts `report.passed` (overall precision/recall floors).
- [ ] Corpus covers all seven production rule ids with ≥1 expected positive each.
- [ ] A deliberate FP in a unit test of the scorer increments `fp` and lowers precision.
- [ ] CLI (if shipped) exits 0 on the fixture corpus.
- [ ] Harness does not write to `flags` / `review_decisions`.

## 6. Risks & mitigations

- **Synthetic ≠ real** — document that E7.3 v1 is a regression gate; a later issue can add a
  curated anonymized dump from archived OCDS once volume exists.
- **Overfitting thresholds to the fixture** — keep corpus small and scenarios distinct; do not
  tune solely to pass.

## 7. Open questions

None blocking.
