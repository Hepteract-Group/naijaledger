# Spec 0008 — Catalog link-discovery (HTML indexes → child artifacts)

- **Epic / Issue**: E3.4b / #80
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no

## 1. Problem

Several approved seeds are **catalog pages** — HTML indexes linking PDF/XLSX/JSON files.
`make fetch-sources` archives only the catalog URL. Extraction (E4) needs the child files.

## 2. Scope & non-scope

- In scope: discover same-origin artifact links from known catalog URLs; HTTP-fetch children;
  `fetch_records` + deduped `documents` under parent `source_id`; provenance in `documents.meta`.
- Out of scope: NOCOPO per-row JSON API actions (needs separate extractor); Gombe `/publication`
  seed (optional follow-up). Budget Office year-folder expansion is in scope (index → year HTML →
  `/download`).

## 3. Design

```
catalog fetch (ok, html document)
    → [Budget Office] expand year/folder catalog links (capped; recent first)
    → extract hrefs (pdf|xlsx|csv|json|/download|/viewdocument)
    → same-origin filter + SSRF validate
    → skip if child URL already has ok fetch_record
    → httpx GET each child → archive → fetch_record → documents (dedup sha256)
```

Budget Office index has no direct artifact links; year pages under
`…/budget-documents/{YYYY}-budget` (and approved/amendment variants) expose Joomla `/download`.
Settings: `catalog_subdir_max` (default 3 year pages), `catalog_discovery_max_children` (default 50).
When `/download` links exist on a year page, `/viewdocument` viewers are skipped.
Year-folder HTML is always archived on each discovery run (`documents.meta.discovery.kind =
budget_office_year_page`; MinIO/document dedup by content hash) and becomes the intermediate
parent for PDF children (#149).

Child `documents.meta`:

```json
{
  "discovery": {
    "catalog_url": "https://…/2026-budget",
    "parent_document_id": "uuid-of-year-page-or-index",
    "parent_fetch_id": "uuid"
  }
}
```

Catalog URLs (v1): Lagos registered-awards, Jigawa contracts, Budget documents, NEITI documents.

## 4. Acceptance criteria

- [x] Lagos fixture HTML yields ≥1 `AWARD-REGISTER-*.pdf` URL; child fetch archives PDF document.
- [x] Jigawa fixture HTML yields ≥1 `storage/contracts/reports/*.pdf` URL; child fetch archives PDF.
- [x] Budget Office index fixture yields year-folder links; year-page fixture yields `/download`;
  discovery expands year page(s), archives year HTML + PDF children (skips `/viewdocument` when
  downloads exist); year page is intermediate parent for children.
- [x] Child `documents.format` from Content-Type or URL extension.
- [x] Re-run skips child URLs that already have successful `fetch_records`.
- [x] Unit tests use fixture HTML only (no live network).

## 5. Risks & mitigations

- **Runaway link counts** — `catalog_discovery_max_children` cap (default 50);
  Budget Office also caps year pages via `catalog_subdir_max` (default 3).
- **Off-origin links** — same-origin check + `validate_probe_url` before fetch.

## 6. Open questions

- NOCOPO row JSON downloads via JS actions → follow-up issue after E4 JSON path.
