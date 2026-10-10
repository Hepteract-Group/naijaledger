# Spec 0041 — Open Contracting Partnership state bulk awards

- **Epic / Issue**: E5 / #203
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no — the seven files this loader writes are under the Open Data Commons Public Domain Dedication and Licence (PDDL). Two publications have no open licence and are reported, not loaded.

## 1. Problem

Eight states have award rows in the Open Contracting Partnership (OCP) Data Registry and no usable live portal in our registry. One normalizer covers them. Live HTML loaders for Osun (#198) and Ebonyi (#199) stay separate. This spec is the archive.

Derives from `docs/architecture/SYSTEM_DESIGN.md` §4.5–4.7 and `specs/0012-ocds-normalizer.md`. Probe notes: `docs/learnings/2026-10-01-missing-state-procurement.md`. Licence and “Last retrieved” lines were read from the publication pages on 2026-10-10.

## 2. Scope & non-scope

- **In scope**
  - Nine seed rows, one per publication below. Seven are loaded. Two are refused for licence.
  - Download `full.jsonl.gz`, archive the bytes, flatten the Edo shape, then use the existing Open Contracting Data Standard (OCDS) normalizer (`normalize_ocds_release` / `load_normalized_release`).
  - Stamp `tenders.state_code` from the publication, not from the JSON.
  - Record the registry’s “Last retrieved” date on each loaded tender.
  - One row per `ocid`. A second load updates that row and does not insert another tender.
  - Fixture tests. No live network in unit tests.
- **Out of scope**
  - Federal publishers on the same registry, including Nigeria Open Contracting Portal (NOCOPO) publication 64.
  - Per-year files (`2018.jsonl.gz` and the rest). `full.jsonl.gz` is the only download.
  - Live portal crawls (#198, #199, #204).
  - Ogun (#200). That API has no licence.
  - Emailing state bureaux. Freedom of Information requests.
  - Copying Oyo or Plateau releases into the canonical store.

## 3. Design

```text
for each publication in the table below:
  GET the publication HTML page
  if the page does not contain "Public Domain Dedication":
      record skip_reason=no_open_licence and do not download
      continue
  parse "Last retrieved: Mon D, YYYY"
  GET full.jsonl.gz
  archive those bytes and write a fetch record before parse
  for each JSON line:
      flatten nested compiled sections (no-op on a normal release)
      copy contract suppliers from the matching award when the contract has none
      set tender.state_code from the publication
      set tender.meta.ocp_publication_id and tender.meta.ocp_retrieved_on
      normalize_ocds_release → load_normalized_release
```

`make fetch-sources` only walks `http`, `scrapling`, and `playwright`. Seed these with `fetch_method=api` so that walker skips the gzip. Loading is a dedicated command.

The download URL is fixed in code: `https://data.open-contracting.org/en/publication/{id}/download?name=full.jsonl.gz`. Callers do not pass a URL.

Politeness:

- Wait at least 1 second between publication requests.
- Send `User-Agent: NaijaLedger/ocp-registry`.
- On HTTP 429 or 5xx, wait 5 seconds and retry that request once. If the retry fails, record the state as failed and continue with the next state. Stop the whole job on 401 or 403.

### 3.1 Which row wins

The open question on #203 is closed here.

`tenders.ocid` is already unique. The archive and a later live table for the same contract are one tender, not two. Osun and Ebonyi HTML loaders must emit the same `ocid` the registry file uses.

Change the shared tender/award/contract upsert used by `load_normalized_release`:

- A null incoming amount, title, award date, signed date, or `state_code` does not erase a stored non-null value.
- `meta` is shallow-merged. Keys on the incoming object replace stored keys. Keys the incoming object does not mention stay. A live loader that never sets `ocp_retrieved_on` must leave that key in place.

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

### 3.3 Oyo

Oyo’s first release has a tender title and no `awards` array. If a later page states PDDL, the loader writes the tender and writes zero awards, and the summary shows `awards_written=0`. Until that licence line exists, do not download the file. The summary row is still required, with `skip_reason=no_open_licence`.

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
| Oyo | 106 | OY | none stated | 2024-04-07 | summary only |
| Plateau | 125 | PL | `License: -` | 2025-11-12 | summary only |

Page URL: `https://data.open-contracting.org/en/publication/{id}`.

Download URL, PDDL rows only: `https://data.open-contracting.org/en/publication/{id}/download?name=full.jsonl.gz`.

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
| expected_cadence | 30 days |
| approved_by | `human:issue-203` |

`apply_seed_catalog` takes one run-wide `approved_by`. Do not pass `human:issue-203` as that argument. Put it on the catalog entry. A fresh seed must leave the July sources on `human:decision-brief-2026-07-07`. If the per-entry field from spec 0040 is not on this branch yet, add it here.

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
| — | `tenders.meta.attribution` = `Open Contracting Partnership Data Registry (https://data.open-contracting.org/)` |

Sample that the Edo fixture must use: amount `183835990` NGN → `18383599000` kobo, supplier `SOLWIN ENGINEERING COMPANY LIMITED`, agency `Directorate of Central Administration`, `state_code` `ED`.

Provenance: `method=json`, `derivation=extracted`, `confidence=1`. Region is a JSON object, not a string:

```json
{"ocid": "ocds-fmoaoq-edsg-dca8-00002", "publication_id": "102"}
```

`ProvenanceContext.region` is still `dict[str, float] | None` in code. Widen it to `dict[str, str | float] | None` if spec 0040 has not already done that. `provenance_edges.region` is already JSONB.

### 4.4 Load summary

Print one line per publication, including the two that were not downloaded:

```text
state publication_id retrieved_on releases awards_written awards_positive_amount skip_reason
```

`skip_reason` is empty on success, `no_open_licence` for Oyo and Plateau, or `fetch_failed` after the retry.

## 5. Acceptance criteria (testable)

- [ ] A flat release fixture (supplier and amount on `awards[0]`) loads one award. A second load of the same `ocid` does not insert a second tender.
- [ ] The Edo fixture, shaped as in §3.2, yields supplier `SOLWIN ENGINEERING COMPANY LIMITED` and `18383599000` kobo. Reading `awards[0].suppliers` without flattening yields no supplier, and the test fails if flatten is skipped.
- [ ] The Edo contract fixture links to that award id. The contract row exists even though the file’s `suppliers` is null.
- [ ] An award with `value.amount` `0` is stored as 0 kobo and is still written. The summary counts it in `awards_written` and not in `awards_positive_amount`.
- [ ] A tender-only release writes a tender and zero awards.
- [ ] A publication page fixture without “Public Domain Dedication” produces `skip_reason=no_open_licence` and does not call the downloader.
- [ ] The loaded tender has `state_code=ED` for the Edo fixture even though the JSON has no `nlStateCode`.
- [ ] `tenders.meta` contains `ocp_publication_id`, `ocp_retrieved_on` (`2022-06-03` for publication 102), and `attribution`.
- [ ] Updating that tender with a payload whose amount is null and whose `meta` omits `ocp_retrieved_on` leaves both the stored amount and `ocp_retrieved_on` in place.
- [ ] A fresh seed leaves July sources on `human:decision-brief-2026-07-07` and sets the nine new rows to `human:issue-203`.
- [ ] Unit tests use fixtures only.

## 6. Risks & mitigations

| Risk | Mitigation |
| --- | --- |
| A naive reader stores the Edo wrapper and drops the supplier | Fixture that fails unless the inner award is used |
| Zero-naira rows look like real prices in a total | Summary splits positive amounts; store 0 as published, do not drop the supplier |
| Osun or Ebonyi live load duplicates the archive | Same `ocid`, one tender; nulls do not wipe stored fields |
| Oyo or Plateau get copied with no licence | Refuse download unless the page contains “Public Domain Dedication” |
| Stale years get read as current | `ocp_retrieved_on` stays on the tender across later updates |

## 7. Open questions

None. The #203 question (which source wins when Osun or Ebonyi is in both the archive and the live table) is decided in §3.1.
