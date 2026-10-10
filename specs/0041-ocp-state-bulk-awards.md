# Spec 0041 — Open Contracting Partnership state bulk awards

- **Epic / Issue**: E5 / #203
- **Status**: Approved
- **Author**: agent
- **Needs human decision?**: no — §7.1 and §7.2 decided by founder 2026-10-10.

## 1. Problem

Nine Nigerian state publications sit in the Open Contracting Partnership (OCP) Data Registry. Seven of them state the Open Data Commons Public Domain Dedication and Licence (PDDL) on the publication page and have no loaded live source yet. Osun and Ebonyi also have live HTML tables (#198, #199); this spec is the archive backfill for those two and the only load path for the other five PDDL states. One normalizer covers them.

Derives from `docs/architecture/SYSTEM_DESIGN.md` §4.5–4.7 and `specs/0012-ocds-normalizer.md`. Probe notes: `docs/learnings/2026-10-01-missing-state-procurement.md`. Licence and “Last retrieved” lines were read from the publication pages on 2026-10-10.

## 2. Scope & non-scope

- **In scope**
  - Nine seed rows, one per publication below. Seven are loaded. Two are refused for licence.
  - A checked-in signed licence record per loadable state (`docs/licences/ocp-state-*.md`) before download.
  - Download `full.jsonl.gz`, archive the bytes, flatten the Edo shape, then use the existing Open Contracting Data Standard (OCDS) normalizer (`normalize_ocds_release` / `load_normalized_release`).
  - Stamp `tenders.state_code` from the publication, not from the JSON.
  - Record the registry’s “Last retrieved” date on each loaded tender (`meta.ocp_retrieved_on`).
  - One tender per `ocid`, one award per award key, one contract per contract key. A second load does not raise those counts.
  - Publication rule (§7.2): any public surface that shows an amount from `source_kind=ocp_registry` must show the retrieval date next to that amount. The loader PR stores the field; the public API/UI work is #206, not this loader’s first PR.
  - Fixture tests. No live network in unit tests.
- **Out of scope**
  - Federal publishers on the same registry, including Nigeria Open Contracting Portal (NOCOPO) publication 64.
  - Per-year files (`2018.jsonl.gz` and the rest). `full.jsonl.gz` is the only download.
  - Live portal crawls (#198, #199, #204).
  - Ogun (#200). That API has no licence.
  - Emailing state bureaux. Freedom of Information requests.
  - Copying Oyo or Plateau releases into the canonical store.
  - Implementing the public API/UI chrome for the retrieval date in the same PR as the loader (#206).

## 3. Design

```text
for each publication in the table below:
  require docs/licences/ocp-state-{slug}.md with URL, phrase, date read, signer
      if missing → skip_reason=no_licence_record, do not download
  GET the publication HTML page (timeout 30s)
  parse the licence field (fail closed if that field is missing)
  if the licence field is not Open Data Commons Public Domain Dedication and Licence (PDDL):
      record skip_reason=no_open_licence and do not download
      continue
  if the page licence field names a different licence than the signed record (see §3.3):
      record skip_reason=licence_mismatch and do not download
      continue
  parse "Last retrieved: Mon D, YYYY"
  GET full.jsonl.gz (timeout 60s; max 50 MiB compressed; stream decompress)
  if compressed size, decompressed size (>200 MiB), or timeout is exceeded:
      record skip_reason=fetch_failed and continue
  archive those bytes and write a fetch record before parse
  for each JSON line (stream; do not load the whole decompressed file into memory):
      flatten nested compiled sections (no-op on a normal release)
      copy contract suppliers from the matching award when the contract has none
      ensure every award and contract has a non-null OCDS id (see §3.1)
      set tender.state_code from the publication
      set tender.meta.ocp_publication_id, ocp_retrieved_on, source_kind=ocp_registry
      normalize_ocds_release → load_normalized_release
```

`make fetch-sources` only walks `http`, `scrapling`, and `playwright`. Seed these with `fetch_method=api` so that walker skips the gzip. Loading is a dedicated command. Leave `expected_cadence` unset so `enqueue_due_fetch_jobs` does not queue a `fetch_source` job the worker would reject (`unsupported fetch_method: api`). If a later change adds `api` to the worker, cadence can be set then.

The download URL is fixed in code: `https://data.open-contracting.org/en/publication/{id}/download?name=full.jsonl.gz`. Callers do not pass a URL.

Politeness:

- Wait at least 1 second between publication requests.
- Send `User-Agent: NaijaLedger/ocp-registry`.
- On HTTP 429 or 5xx, wait 5 seconds and retry that request once. If the retry fails, record `skip_reason=fetch_failed` and continue with the next state. Stop the whole job on 401 or 403.

### 3.1 Identity and which value wins

#### Tender

`tenders.ocid` is unique. The archive and a later live table for the same contract are one tender. Osun and Ebonyi HTML loaders must emit the same `ocid` the registry file uses.

#### Award

Shared upsert lookup key for this workstream: `(tender_id, meta->>'ocds_award_id')` — not supplier. Supplier may update on the existing row. That keeps archive and live from double-counting when the same award id arrives with a slightly different company string.

Every award written by this loader must have a non-null `ocds_award_id`:

- Prefer the release award’s `id` (after Edo flatten: the **inner** id).
- If that id is missing, set `ocds_award_id` to `{ocid}:award:{index}` where `index` is the zero-based position in the flattened `awards` list.

Never insert an award when `ocds_award_id` is null. Live loaders (#198, #199) must emit the same `ocds_award_id` for the same contract (portal OCDS award id when present; otherwise `{ocid}:award:0` for a single-award HTML row) and must resolve the supplier through the same party get-or-create path as `load_normalized_release` (`party_type` + `lower(canonical_name)` after strip).

#### Contract

Shared upsert lookup key for this workstream: `(agency_id, meta->>'ocds_contract_id')` — not supplier. Supplier may update on the existing row.

Publisher contract ids are only unique inside a release (Nigerian files commonly emit `"1"`, `"0001"`, or a short suffix). To keep distinct contracts from colliding under the same procuring entity, **always store a namespaced identity**:

- `meta.ocds_contract_id` = `{ocid}:{publisher_id}`
- `meta.ocds_contract_id_raw` = the publisher’s original id (for display / debugging)

Every contract written by this loader must have a non-null `ocds_contract_id`:

- Prefer the release contract’s `id`, then namespace it as `{ocid}:{id}` (no double-prefix if already namespaced).
- If missing, set the publisher id to `contract:{index}` and store `ocds_contract_id` as `{ocid}:contract:{index}`.

Never insert a contract when `ocds_contract_id` is null. Live loaders (#198, #199) **must use the same namespaced form** so archive and live converge: when the portal prints a contract id, emit `{ocid}:{that_id}`; otherwise `{ocid}:contract:0` for a single-contract HTML row. Prefer the archive file’s real publisher id (namespaced) over inventing a fallback when both sources cover the same `ocid`.

#### Null-never-erases and meta merge

Change the shared tender/award/contract upsert used by `load_normalized_release` (callers today: Ekiti HTML portal load and any other path through that function):

- A null incoming amount, title, award date, signed date, or `state_code` does not erase a stored non-null value.
- `meta` is shallow-merged. Keys on the incoming object replace stored keys. Keys the incoming object does not mention stay.
- A genuine clear of a stored value is out of scope. No silent “set to null” path in this PR.

Existing portal-load tests must still pass with these merge semantics.

#### Precedence when both values are non-null

Live portal beats archive for the same `ocid` / award key / contract key.

- This loader sets `tenders.meta.source_kind = "ocp_registry"` (and the same key on award/contract meta).
- Live loaders set `source_kind = "live_portal"`.
- When the stored row already has `source_kind = live_portal`, this archive loader does not replace a non-null amount, title, award date, or signed date with a different non-null value.
- Same-kind reloads (archive after archive, live after live) update those fields.
- Null-never-erases still applies in every case.
- A live loader that never sets `ocp_retrieved_on` must leave that key in place.

### 3.2 Edo compiled wrappers

Publication 102 is the only file, of the nine, whose first release is wrapped this way (checked 2026-10-10). Flatten when an `awards[]` item is an object that itself has an `awards` list and has no `suppliers`. A normal release is unchanged.

| Wrapped path | Real object |
| --- | --- |
| `tender.tender` | the tender (`title`, `value`, `procurementMethod`, `procuringEntity`) |
| `awards[i].awards[j]` | the award (`id`, `date`, `value`, `suppliers`) |
| `contract.contracts[]` | the contracts (`id`, `awardID`, `dateSigned`, `value`) |

Keep the top-level `ocid`. The inner award id is the one that matches `awardID`. On the sample `ocds-fmoaoq-edsg-dca8-00002`, the inner award id is `ocds-fmoaoq-edsg-dca8-00002-award`. The outer wrapper id (`…-04-award`) does not match the contract and must not be stored as the award id.

Edo contracts have `suppliers: null`. Before normalize, copy `suppliers` from the award whose `id` equals `awardID`. The existing normalizer skips a contract with no supplier, which would drop these rows.

A probe of the Edo file on 2026-10-10: 466 releases, 466 inner awards, every one has a supplier name. 215 have `value.amount > 0`. 251 have `value.amount == 0`. Store 0 as 0 kobo. Do not drop those awards. The load summary reports `awards_written` and `awards_positive_amount` separately.

### 3.3 Licence gate

Do not search the whole HTML document for the phrase. Parse the publication page’s licence field (the labelled “License” / “Licence” value on the OCP publication page). Fail closed if that field cannot be located.

A field matches the signed PDDL record when, after trimming and case-folding, it equals the signed phrase or contains `public domain dedication` (short form). `licence_mismatch` is only for a located licence field that names a **different** licence (for example Creative Commons or “All rights reserved”). A page that only mentions PDDL in a nav link or related-publications block must produce `skip_reason=no_open_licence`.

### 3.4 Oyo and Plateau

Neither state has a signed licence record on this branch. Gate order applies: summary rows use `skip_reason=no_licence_record` and do not download.

Oyo’s first release has a tender title and no `awards` array. If a later founder-signed record is added **and** the page licence field matches PDDL under §3.3, the loader may write the tender with zero awards (`awards_written=0`). If a record is signed and the page still lacks PDDL, the summary uses `skip_reason=no_open_licence`.

## 4. Data contracts / schemas

### 4.1 Publications (pages read 2026-10-10)

| State | Id | `state_code` | Licence on the page | Last retrieved | This loader |
| --- | --- | --- | --- | --- | --- |
| Abia | 107 | AB | PDDL | 2023-04-26 | load |
| Cross River | 105 | CR | PDDL | 2022-10-17 | load |
| Ebonyi | 86 | EB | PDDL | 2025-11-29 | load |
| Edo | 102 | ED | PDDL | 2022-06-03 | load, after flatten |
| Enugu | 104 | EN | PDDL | 2024-09-09 | load |
| Gombe | 103 | GO | PDDL | 2023-07-19 | load |
| Osun | 118 | OS | PDDL | 2026-10-05 | load |
| Oyo | 106 | OY | none stated | 2024-04-07 | summary only (`no_licence_record`) |
| Plateau | 125 | PL | `License: -` | 2025-11-12 | summary only (`no_licence_record`) |

Page URL: `https://data.open-contracting.org/en/publication/{id}`.

Download URL, PDDL rows only: `https://data.open-contracting.org/en/publication/{id}/download?name=full.jsonl.gz`.

Lawfully loadable under this gate today: **1,765 award rows with supplier and amount across 7 states** (the §1 count of 1,901 across 8 includes Plateau’s 136, which this loader refuses).

### 4.2 Source seed

One row per publication, including Oyo and Plateau (so the refusal is visible in the registry).

| Field | Value |
| --- | --- |
| name | `OCP Data Registry — {State} awards` |
| jurisdiction | `state` |
| region | the state name in the table |
| category | `procurement` |
| url | the download URL. For Oyo and Plateau, the publication page URL, because we do not download |
| fetch_method | `api` |
| format | `json` |
| ingest_role | `leaf` |
| expected_cadence | unset (`null`) — see §3 |
| approved_by | `human:issue-203` |

`apply_seed_catalog` takes one run-wide `approved_by`. Do not pass `human:issue-203` as that argument. Put it on the catalog entry. A fresh seed must leave the July sources on `human:decision-brief-2026-07-07`. If the per-entry `approved_by` field from `specs/0040-govspend-payments.md` (#179, may still be unmerged) is not on this branch yet, add it here. Same for widening `ProvenanceContext.region` to `dict[str, str | float] | None` if 0040 has not landed.

### 4.3 Row fields

Use `amount_to_kobo` (`Decimal`, half up). Do not parse the amount with a binary float.

| Registry field | Canonical field |
| --- | --- |
| release `ocid` | `tenders.ocid` |
| tender `title` | `tenders.title` |
| tender `value.amount` | `tenders.value_amount` in kobo |
| publication state | `tenders.state_code` |
| award `suppliers[].name` | party `company` |
| buyer / procuring entity name | party `agency` |
| award `value.amount` | `awards.value_amount` in kobo |
| award `date` | `awards.awarded_at` |
| contract `dateSigned`, else contract `date` | `contracts.signed_at` |
| publication id | `tenders.meta.ocp_publication_id` (string) |
| Last retrieved, ISO date | `tenders.meta.ocp_retrieved_on` |
| — | `tenders.meta.source_kind` = `ocp_registry` |
| — | `awards.meta.source_kind` = `ocp_registry` |
| — | `contracts.meta.source_kind` = `ocp_registry` |
| — | `tenders.meta.attribution` = `Open Contracting Partnership Data Registry (https://data.open-contracting.org/)` |

Sample that the Edo fixture must use: amount `183835990` NGN → `18383599000` kobo, supplier `SOLWIN ENGINEERING COMPANY LIMITED`, agency `Directorate of Central Administration`, `state_code` `ED`.

Provenance: `method=json`, `derivation=extracted`, `confidence=1`. Region is a JSON object, not a string:

```json
{"ocid": "ocds-fmoaoq-edsg-dca8-00002", "publication_id": "102"}
```

`ProvenanceContext.region` is still `dict[str, float] | None` in code unless 0040 has widened it. Widen it to `dict[str, str | float] | None` in the loader PR if needed. `provenance_edges.region` is already JSONB.

### 4.4 Load summary

Print one line per publication, including the two that were not downloaded:

```text
state publication_id retrieved_on releases awards_written awards_positive_amount skip_reason
```

`skip_reason` is empty on success; otherwise one of `no_licence_record`, `no_open_licence`, `licence_mismatch`, or `fetch_failed`.

## 5. Acceptance criteria (testable)

- [ ] A flat release fixture (supplier and amount on `awards[0]`) loads one award. A second load of the same fixture leaves tender count, award count, and contract count unchanged.
- [ ] The Edo fixture, shaped as in §3.2, yields supplier `SOLWIN ENGINEERING COMPANY LIMITED` and `18383599000` kobo. Reading `awards[0].suppliers` without flattening yields no supplier, and the test fails if flatten is skipped. A second load of that fixture leaves award and contract counts unchanged.
- [ ] The Edo contract fixture links to that award id. The contract row exists even though the file’s `suppliers` is null.
- [ ] An award with `value.amount` `0` is stored as 0 kobo and is still written. The summary counts it in `awards_written` and not in `awards_positive_amount`.
- [ ] An award with a missing `id` still writes once, with `meta.ocds_award_id = "{ocid}:award:0"`, and a second load does not insert another award.
- [ ] A tender-only release writes a tender and zero awards.
- [ ] Missing `docs/licences/ocp-state-{slug}.md` produces `skip_reason=no_licence_record` and does not call the downloader.
- [ ] A publication page fixture whose licence field is empty or absent produces `skip_reason=no_open_licence` and does not call the downloader.
- [ ] A publication page fixture that mentions “Public Domain Dedication” only outside the licence field produces `skip_reason=no_open_licence` and does not call the downloader.
- [ ] A page whose licence field names a different licence (not PDDL / not containing “public domain dedication”) produces `skip_reason=licence_mismatch` and does not call the downloader.
- [ ] A second award payload with the same `ocds_award_id` and a different supplier display string updates the existing award; it does not insert a second award.
- [ ] Contract for public surfaces: any fixture or schema test for a public award/tender payload that includes an amount from `source_kind=ocp_registry` also includes `ocp_retrieved_on` (enforced in the follow-up public API/UI issue).
- [ ] The load archives the gzip bytes and writes a fetch record before any normalize/load call (assert order with a fake HTTP client and spies).
- [ ] A download that fails twice (429 or 5xx) produces a summary row with `skip_reason=fetch_failed` and continues to the next state. A 401 or 403 stops the job.
- [ ] A response larger than 50 MiB compressed, or more than 200 MiB decompressed, produces `skip_reason=fetch_failed`.
- [ ] The loaded tender has `state_code=ED` for the Edo fixture even though the JSON has no `nlStateCode`.
- [ ] `tenders.meta` contains `ocp_publication_id`, `ocp_retrieved_on` (`2022-06-03` for publication 102), `source_kind=ocp_registry`, and `attribution`.
- [ ] Updating that tender with a payload whose amount is null and whose `meta` omits `ocp_retrieved_on` leaves both the stored amount and `ocp_retrieved_on` in place.
- [ ] A stored tender with `source_kind=live_portal` and a non-null amount is not overwritten by a later archive load with a different non-null amount for the same `ocid`.
- [ ] A fresh seed leaves July sources on `human:decision-brief-2026-07-07` and sets the nine new rows to `human:issue-203`. The nine rows have `expected_cadence` null. Seeding them and calling `enqueue_due_fetch_jobs` queues no `fetch_source` job for those source ids.
- [ ] Existing Ekiti / portal-load unit tests still pass after the shared null-never-erases and meta shallow-merge change.
- [ ] Unit tests use fixtures only.

## 6. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| A naive reader stores the Edo wrapper and drops the supplier | Fixture that fails unless the inner award is used |
| Zero-naira rows look like real prices in a total | Summary splits positive amounts; store 0 as published, do not drop the supplier |
| Osun or Ebonyi live load duplicates the archive | Same `ocid`; award/contract lookup by OCDS id without supplier; live loaders share party get-or-create |
| Archive overwrites a fresher live amount | `source_kind`; live beats archive when both non-null |
| Oyo or Plateau get copied with no licence | Licence-field parse, fail closed; substring outside that field refuses |
| `api` seeds enqueue failing fetch jobs | `expected_cadence` unset; criterion that enqueue creates none |
| Stale years get read as current in a public view | §7.2: amount and retrieval date shown together; follow-up issue for API/UI |
| Shared upsert change breaks Ekiti | Named callers + existing tests must pass |

## 7. Decisions (founder 2026-10-10)

### 7.1 Licence gate

Each state needs a short signed record before download: publication URL, exact licence phrase as read, date read, signer. Phrase + date is enough content. Records: `docs/licences/ocp-state-{slug}.md`. The HTML licence-field parse remains fail-closed and must match the signed phrase.

### 7.2 Stale amounts in public views

**Show amount + retrieval date.** Archive rows may appear in public views. Wherever an amount from `source_kind=ocp_registry` is shown (detail page, search hit, public API field, chart tooltip or footnote for a total that includes those rows), the retrieval date (`ocp_retrieved_on`) sits next to that amount or total. Charts that sum archive-only states must not present the sum as current spend without that date.

Identity and precedence for Osun/Ebonyi (archive vs live) are decided in §3.1. No open questions remain for this spec.
