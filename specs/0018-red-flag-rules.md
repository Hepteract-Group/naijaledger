# Spec 0018 — Red-flag rules (E7.2)

- **Epic / Issue**: E7.2 / #41
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — thresholds are v1 defaults (tunable constants); E7.3 measures
  precision. Flags remain hypotheses (P3); never auto-published.

## 1. Problem

E7.1 shipped the `flags` table and `AnomalyRule` runner with an empty `production_rules()`.
Without concrete detectors, the anomaly engine cannot surface the Open Contracting / World Bank
style indicators listed in `SYSTEM_DESIGN.md` §4.9 and ROADMAP E7.2.

## 2. Scope & non-scope

- **In scope**
  - Seven finance rules registered in `production_rules()`:
    `single_bidder`, `short_window`, `threshold_hugging`, `repeat_winner`, `shared_address`,
    `price_outlier`, `budget_payment_mismatch`.
  - Pure evaluate functions over `RuleContext` → `list[FlagDraft]` (compact evidence + `summary`).
  - Tunable constants module (`anomaly/thresholds.py`).
  - OCDS tender meta: persist `numberOfTenderers` when present (helps `single_bidder`).
  - Unit tests with synthetic `RuleContext` (no DB) + one DB integration run of
    `production_rules()` on empty/seeded fixtures.
- **Out of scope**
  - `overvote` (E11).
  - Backtest/precision harness (E7.3).
  - Memgraph-backed rules (optional later).
  - Public API / UI.
  - Changing approval thresholds via admin UI (constants only in v1).

## 3. Design

### 3.1 Registration

```python
def production_rules() -> list[AnomalyRule]:
    return [
        SingleBidderRule(),
        ShortWindowRule(),
        ThresholdHuggingRule(),
        RepeatWinnerRule(),
        SharedAddressRule(),
        PriceOutlierRule(),
        BudgetPaymentMismatchRule(),
    ]
```

Smoke stays test-only.

### 3.2 Rule semantics (v1 defaults)

Amounts in Postgres are **kobo** (`BigInteger`). Thresholds below are NGN major units converted
at evaluate time (`* 100`).

| Rule | Subject | Trigger | Severity |
|------|---------|---------|----------|
| `single_bidder` | `tender` | `meta.numberOfTenderers == 1`, **or** competitive method (`open`/`selective`) with exactly one award and no `numberOfTenderers` | medium |
| `short_window` | `tender` | both bid dates present and `(closes - opens) < SHORT_WINDOW_DAYS` (default **7**) | medium; **high** if `< 3` days |
| `threshold_hugging` | `award` | `value_amount` in `(T - hug_band, T]` for any configured approval threshold `T` | medium |
| `repeat_winner` | `party` (supplier) | same supplier has ≥ `REPEAT_MIN_AWARDS` (default **3**) awards with the same agency within `REPEAT_WINDOW_DAYS` (default **365**) | medium |
| `shared_address` | `party` | ≥2 distinct non-merged companies share the same normalized address key | medium |
| `price_outlier` | `contract` | among contracts for the same `agency_id` with non-null value and sample size ≥ `OUTLIER_MIN_N` (default **5**), value is a MAD outlier (`\|x - median\| / MAD > OUTLIER_MAD_K`, default **3**) | medium |
| `budget_payment_mismatch` | `budget_line` | for matching `agency_id` + `fiscal_year` (from `paid_at`), sum(payments) > `utilised_amount * (1 + MISMATCH_TOLERANCE)` when utilised set; else > `allocated_amount * (1 + MISMATCH_TOLERANCE)` when allocated set (default tolerance **0.10**) | high |

Skip subjects missing required fields (no flag).

### 3.3 Evidence shape

Every draft includes `summary` (human-readable one-liner) plus compact ids/metrics, e.g.:

```json
{
  "summary": "Bidding window 2.1 days (< 7 day threshold)",
  "opens_at": "...",
  "closes_at": "...",
  "window_days": 2.1,
  "threshold_days": 7
}
```

### 3.4 Address normalization (shared_address)

From `party.address` jsonb (best-effort):

```text
lower(street|streetAddress) + "|" + lower(city|locality) + "|" + lower(postalCode|postcode)
```

Ignore empty keys; require street + city at minimum. Do not flag agencies sharing an HQ string
with themselves only — require ≥2 distinct `party.id`s.

### 3.5 OCDS `numberOfTenderers`

When mapping a tender release, if `tender.numberOfTenderers` is an int ≥ 0, store it on
`NormalizedTender.meta["numberOfTenderers"]` (existing meta merge). No schema migration.

## 4. Data contracts / schemas

No new tables. Rule ids already in `ck_flags_rule` (0017).

```python
# anomaly/thresholds.py — module-level constants (kobo / days / ratios)
SHORT_WINDOW_DAYS = 7
SHORT_WINDOW_HIGH_DAYS = 3
APPROVAL_THRESHOLDS_NGN = (5_000_000, 20_000_000, 50_000_000, 100_000_000, 500_000_000)
THRESHOLD_HUG_RATIO = 0.02  # within 2% below T
REPEAT_MIN_AWARDS = 3
REPEAT_WINDOW_DAYS = 365
OUTLIER_MIN_N = 5
OUTLIER_MAD_K = 3.0
MISMATCH_TOLERANCE = 0.10
```

## 5. Acceptance criteria (testable)

- [ ] Each of the seven rules emits expected drafts on a crafted `RuleContext` fixture.
- [ ] Each rule emits **zero** drafts when inputs are empty / missing required fields.
- [ ] `production_rules()` returns exactly those seven ids (no `smoke`).
- [ ] `run_anomaly_rules(connection, production_rules())` succeeds on a migrated DB (empty ok).
- [ ] OCDS tender with `numberOfTenderers: 1` lands in tender `meta` after normalize.
- [ ] Evidence always includes non-empty `summary`; subjects use correct `subject_type`.

## 6. Risks & mitigations

- **False positives** — defaults are conservative; E7.3 measures precision; humans dismiss (sticky).
- **Missing bidder counts** — proxy via single award on competitive tenders; prefer
  `numberOfTenderers` when OCDS provides it.
- **Sparse samples** — price_outlier requires `OUTLIER_MIN_N`; otherwise skip.
- **Threshold list incompleteness** — NGN bands are illustrative federal-style defaults; tune later.

## 7. Open questions

None blocking. If product later wants jurisdiction-specific threshold tables, open a follow-up.
