# Spec 0006 — Multi-format document sources (HTML catalogs → PDF/XLSX/JSON)

- **Epic / Issue**: E3.4 / E4.4 follow-up from seed audit
- **Status**: Draft
- **Author**: agent
- **Needs human decision?**: no

## 1. Problem

State procurement data is not always a single HTML table. Common patterns:

| Pattern | Example | Formats |
|---------|---------|---------|
| HTML listing page | Benue `/all-awards/`, Ekiti `/Home/Procurements` | `html` |
| HTML index linking files | Lagos `/registered-awards/` | `html` index → `pdf` registers |
| Publication repository | Gombe `/publication` | `html` index → `xlsx`, `pdf` |
| OCDS JSON API | Adamawa `/api` (future) | `json` |

The registry schema already allows `format ∈ {pdf, xlsx, csv, json, html, image}` and the fetch
layer archives raw bytes with `Content-Type`. **Parsing** is out of scope for E3; extraction is E4.

## 2. Scope & non-scope

- In scope (this spec): classify seed URL patterns; define how catalog vs document sources relate;
  acceptance criteria for E3.4 `documents` dedup and E4 parsers.
- Out of scope (now): building parsers (E4.3–E4.4), Playwright fetcher wiring (separate E3.3
  follow-up for JS SPAs that need browser rendering).

## 3. Design

### 3.1 Source types

1. **Leaf source** — URL returns the artifact directly (HTML table, PDF bytes, XLSX file).
   `source.format` matches the response body.

2. **Catalog source** — HTML page listing links to child artifacts. `source.format=html`.
   After fetch, a **link-discovery** step (E3.4+) extracts same-origin `pdf|xlsx|csv|json` hrefs
   and enqueues child fetches (each becomes a `documents` row + optional child `sources` entry).

### 3.2 Fetch pipeline (current → target)

```
URL → validate → fetch bytes → archive (MinIO) → fetch_record
                                    ↓
                         [E3.4] documents dedup by sha256
                                    ↓
              [catalog only] discover linked artifacts → child fetch_records
                                    ↓
                         [E4] extract by format (pdf|xlsx|json|html tables)
```

### 3.3 Format routing (E4)

| `documents.format` | Extractor (ROADMAP) |
|--------------------|---------------------|
| `html` | table scrape / DOM parser |
| `pdf` | PeaDF + table extraction (E4.3) |
| `xlsx`, `csv` | structured parser (E4.4) |
| `json` | OCDS normalizer path (E5.2) |

### 3.4 Seed catalog implications

- Keep **one catalog source per listing page** where HTML rows are the primary data
  (Benue awards, Ekiti procurements, Gombe projects).
- Keep **catalog HTML sources** where the index is the stable URL but files rotate
  (Lagos registered-awards → monthly PDFs). Link discovery fetches each PDF as a separate
  `document` with `format=pdf`.
- Gombe `/publication` is a second catalog candidate (XLSX templates); defer as optional
  seed until link-discovery ships.

## 4. Acceptance criteria (testable)

- [ ] `documents.format` is set from `Content-Type` or URL extension when creating document rows.
- [ ] Catalog fetch of Lagos registered-awards discovers ≥1 PDF link and archives each child.
- [ ] E4.4 xlsx parser produces `extractions` rows from a Gombe SUBEB XLSX fixture.
- [ ] E4.3 pdf parser produces table blocks from a Lagos award-register PDF fixture.
- [ ] HTML table sources (Benue, Ekiti) produce row-level extractions without requiring PDF step.

## 5. Risks & mitigations

- **Empty JS SPAs** (Kwara) — Scrapling `Fetcher.get` does not execute JS; Playwright path or
  substitute state required. Kwara confirmed empty even with Playwright (0 table rows).
- **MIME mismatch** — some servers return `application/octet-stream` for PDF/XLSX; fall back to
  URL extension sniffing when classifying `documents.format`.

## 6. Verified catalog examples (2026-07-08)

| Catalog URL | Child pattern | Sample child content |
|-------------|---------------|----------------------|
| Lagos registered-awards | `…/AWARD-REGISTER-*.pdf` | MDA / project / amount / contractor |
| Jigawa `/contracts` | `…/storage/contracts/reports/*.pdf` | date / project / contract no / contractor / amount / MDA |
| Budget documents year pages | Joomla `/download` + `/viewdocument/{id}` | Appropriation bills (binary download, not bare `.pdf` href) |
| NEITI `/documents/all` | `/INFORMATION/DOCUMENTS/…/*.pdf` | Mixed engagement + audit PDFs — filter needed |
| Gombe `/publication` | Cloudinary `raw/upload/*.xlsx` + `*.pdf` | Education sector Q1 2025 contract award workbook |

## 7. Open questions

- Should child PDF/XLSX URLs become separate `sources` rows or only `documents` linked to the
  parent catalog source? (Lean toward `documents` + parent `source_id` until human review queue
  needs per-file cadence.)
- Budget Office Joomla downloads: treat year index as catalog and resolve `/download` endpoints
  that may not end in `.pdf`?
