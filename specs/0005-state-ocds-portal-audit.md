# Spec 0005 — State / federal seed URL content audit

- **Epic / Issue**: follow-up to E2.3 / fetch failures
- **Status**: Implemented (v5 — NOCOPO Open-Data, retire Open Treasury 2026-07-08)
- **Author**: agent
- **Needs human decision?**: partial — alternate federal payments source when Open Treasury returns

## 1. Important constraint (current product)

**There is no intelligent link-following yet.** `make fetch-sources` archives only the
exact `sources.url`. If that URL is an HTML *index* of PDFs/XLSX, we archive the index HTML —
not the files — until E3.4 catalog link-discovery ships (`specs/0006-multi-format-document-sources.md`).

So today every seed URL must either:

1. **Leaf data** — the page/body itself contains extractable awards/tenders/contracts/payments, or
2. **Known catalog** — explicitly accepted as an index, with a documented child-file pattern and a
   follow-up epic that must fetch children before extraction can succeed.

Do not treat “Agency homepage” or “Portal brand page” as leaf data.

## 2. Content verification method (2026-07-08)

For each seeded URL: HTTP(S) fetch and/or Scrapling `DynamicFetcher` (Playwright), then inspect:

- HTML table / card rows (project title, contractor, amount, OCID, dates)
- Linked `.pdf` / `.xlsx` / Joomla download endpoints
- Sample child artifact text (PDF via `pypdf`; XLSX where downloadable)

Raw probes stored under `.probe/v4/` (gitignored locally; not committed).

## 3. State procurement seeds — verified

| Region | Seed URL | Class | Sample evidence | Retrieval needed later |
|--------|----------|-------|-----------------|------------------------|
| **Lagos** | https://www.lagosppa.gov.ng/registered-awards/ | **Catalog → PDF** | Index lists monthly PDFs. Child `AWARD-REGISTER-NOVEMBER-2025.pdf` (13 pp) has rows: MDA, project, amount, contractor, duration, registration date. Ex: LASCPA / *Repairs servicing…vehicles* / ₦14,854,000 / YASNIC GLOBAL LIMITED | E3.4 link-discovery → E4.3 PDF tables |
| **Kaduna** | https://www.ocds.kdsg.gov.ng/Projects | **Leaf HTML** (SSR) | Curl HTML embeds project cards: title, method, budget, contract amount, award date, contractor. Ex: *Renovation/Landscapping of Health Clinic at Ruhogi* / Single Source / ₦6,744,159.19 / Ziarum Partners Nig. LTD. Totals: 1379 projects. | Scrapling/http HTML extract |
| **Ekiti** | https://ocdsportal.azurewebsites.net/Home/Procurements | **Leaf HTML** | ~9 MB table, **2680** OCIDs. Ex: *CORRECTION OF ROOF LEAKAGES…* / BUREAU OF SPECIAL PROJECT / `ocds-6olpk7-BSP/BPP/CONO/72026/77421663` / ₦947,554.05 | HTML table extract (large payload) |
| **Adamawa** | https://ocdsbpp.adamawastate.gov.ng/projects | **Leaf HTML + detail links** | List: 595 projects; titles + amounts. Detail `…/projects/ocds-adamawa-2025-001`: transformer procurement; award ₦18,501,750 to Amrat Multi-service Nig. Ltd (2019-10-29). Some list amounts show ₦0 — quality flag. | HTML list + optional detail crawl |
| **Gombe** | https://project.dueprocess.gm.gov.ng/projects | **Leaf HTML only after JS** | Plain curl ≈ empty shell. Playwright: **144** projects with titles/LGA/status. Ex: *CONSTRUCTION OF BOLTONGO - NONO - DEBA ROAD…* Yamaltu/Deba / 2019 / 100%. Richer award files live under `/publication` (Cloudinary XLSX/PDF) — not the current seed. | **Playwright/DynamicFetcher** for this URL; optional second source = publication catalog |
| **Jigawa** | https://dueprocess.jigawastate.gov.ng/contracts | **Catalog → PDF** | Page text: consolidated monthly/quarterly award reports as PDF downloads (not an HTML awards grid). Sample PDF: Q2 health awards — *Supply of Hospital Equipment at Hadejia General Hospital…* / AA Aljazzeera… / ₦9,155,055.79 / Min of Health | E3.4 PDF discovery → E4.3 |
| **Anambra** | https://eprocure.bpp.an.gov.ng/awarded_contracts.php | **Leaf HTML** | Awards table with OCID + contractor (~960 OCIDs). (Former `tenders.php` is **tender notices**, not awards — wrong stage for award/contract canonicals.) | HTML table extract |
| **Benue** | https://procurement.benuestate.gov.ng/all-awards/ | **Leaf HTML** | Awards table rows. Ex: desk fabrication / Makurdi / 2026 / SUBEB / APEPAI ENGINEERING LIMITED / **Awarded** | HTML table extract |

### Dropped / invalid (historical)

| URL | Why rejected |
|-----|--------------|
| Kwara `…/ocds-portal/awarded-contracts` | Playwright-rendered DOM still **0 data rows** |
| `lagosstate.gov.ng/lsppa/` | Empty SPA shell |
| Dead `*.azurewebsites.net` state OCDS hosts | DNS dead |

## 4. Federal seeds — verified

| Source | Seed URL | Class | Finding | Retrieval needed |
|--------|----------|-------|---------|------------------|
| **NOCOPO** | https://nocopo.bpp.gov.ng/Open-Data | **JS leaf HTML + per-row JSON** | Homepage is login/marketing shell. `/Open-Data` has JsonReport table (OCID, project title, package/lot, budget year, per-row **Download**). Plain curl = empty table; Playwright renders rows. Ex: `ocds-gyl66f-0517018034-000001` / *PROCUREMENT, TESTING… HOSPITALITY AND TOURISM WORKSHOP* / 2023 / FEPO/23/01. License modal may need dismiss (auto-handled in probe). | **Playwright** for table; E3.4 for per-row JSON downloads + bulk export |
| **Open Treasury** | https://opentreasury.gov.ng/ | **Retired** | TLS certificate expired / portal unsafe per [FIJ (Jul 2025)](https://fij.ng/article/9-months-and-counting-oagfs-open-treasury-portal-unsafe-for-visitors/). Removed from seed catalog; existing rows retired on re-seed. | Human decision on alternate payments source |
| Budget Office | https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents | **Catalog index** | Year folders (`2026-budget`, …) with Joomla `/download` + `/viewdocument/{id}` (Appropriation Bill). | Catalog crawler for DocMan downloads |
| NEITI | https://neiti.gov.ng/documents/all | **Catalog → PDF** | Many PDF links under `/INFORMATION/DOCUMENTS/…` (engagement + audits mixed). | E3.4 PDF children + filter/allowlist |
| OpenStates.ng | https://openstates.ng/ | **Thin SPA overview** | State-name glance page; no contract/budget rows in HTML | Treat as discovery/aggregation UI, not primary leaf; or find API/data routes |
| CAC BOR | https://bor.cac.gov.ng/ | **Search UI only** | Playwright shows PSC search form; no bulk register dump | Needs `api`/`playwright` interactive search strategy — not bulk HTML scrape |

## 5. Acceptance criteria

- [x] Each state seed classified as leaf vs catalog with at least one concrete row/file sample.
- [x] Catalog seeds (Lagos, Jigawa) documented as **insufficient alone** until link-discovery.
- [x] Anambra seed points at **awarded contracts**, not tenders-only.
- [x] Gombe leaf content verified via Playwright (JS required).
- [x] NOCOPO seed points at `/Open-Data` (not homepage); data verified via Playwright.
- [x] Open Treasury retired from catalog (unreliable TLS).
- [x] Federal gaps called out honestly (OpenStates/CAC are not leaf award dumps at current URLs).
- [x] Epic issues filed for catalog discovery + Playwright fetch path + federal re-scoping ([#80](https://github.com/Hepteract-Group/naijaledger/issues/80), [#81](https://github.com/Hepteract-Group/naijaledger/issues/81), [#82](https://github.com/Hepteract-Group/naijaledger/issues/82)).

## 6. Implications for upcoming epics

| Epic | Must account for |
|------|------------------|
| **E3.4 documents** | Dedup by hash; classify format from Content-Type **or** extension; child docs from catalog HTML |
| **E3.4+ link discovery** | Lagos PDF index, Jigawa PDF reports, Budget Joomla downloads, NEITI document lists, Gombe `/publication` Cloudinary URLs, NOCOPO per-row JSON downloads |
| **E3.3 Playwright path** | Wire `fetch_method=playwright` / Scrapling DynamicFetcher for Gombe, NOCOPO Open-Data (and any future SPA); current Scrapling CLI uses non-JS `Fetcher.get` |
| **E4.3 PDF tables** | Lagos / Jigawa award-register PDFs (multi-column tables) |
| **E4.4 XLSX** | Gombe Cloudinary award workbooks |
| **E4 HTML/JSON** | Ekiti, Benue, Anambra awards, Kaduna cards, Adamawa lists, NOCOPO Open-Data table + JSON exports |
| **E5 OCDS** | Prefer pages with OCIDs (Ekiti, Anambra, Adamawa, NOCOPO); map non-OCDS HTML (Benue, Kaduna) via custom normalizers |
