# 2026-10-01 — Re-probe of the 11 approved sources

Spike for #186. Probed the seed URL for each auto-approved source. No rows were written to Postgres. Expired TLS certificates were not bypassed.

## Ranks

`load now` means the page or a child file still contains award, tender, or budget rows, and a loader spec is justified. `fetch-only` means the URL responds but the body is not a row leaf. `down` means the URL failed TLS and was not fetched.

| Source | Result on 2026-10-01 | Existing loader | Rank | Follow-up |
| --- | --- | --- | --- | --- |
| Nigeria Open Contracting Portal (NOCOPO) — Open Data | Certificate for `*.bpp.gov.ng` has expired. Not fetched. | None. #173 is blocked until the certificate is renewed. | down | None |
| Budget Office of the Federation — Budget Documents | HTTP 200. Index links year folders. The 2026 folder still exposes `/download` links. | Appropriation PDF path, `specs/0037-appropriation-budget-lines.md` | load now | No new spec |
| Nigeria Extractive Industries Transparency Initiative (NEITI) — Documents library | HTTP 200 only when the system trust store is used. Python's default certificate bundle failed the chain. Child PDFs are mixed speeches, letters, and audits. | None | fetch-only | No normalizer until an allowlist exists |
| Lagos State Public Procurement Agency — Registered Awards | HTTP 200. Monthly award-register PDF links. December 2025 file starts with `%PDF-1.7`. | Link discovery only | load now | #192 |
| Kaduna State Open Contracting Portal | HTTP 200. Static HTML has ministry filter names and no award rows, no naira amounts, and no project API. July 2026 pages had embedded project cards. The scheduled fetch method is non-JavaScript. A browser render was not re-run: the Playwright browser binary is not installed locally. | None | fetch-only | None until rows are visible to the scheduled fetch |
| Ekiti State Open Contracting Portal | HTTP 200. About 2,737 table rows and Open Contracting Data Standard (OCDS) ids in the HTML. | `specs/0032-ekiti-html-portal-load.md` | load now | No new spec |
| Adamawa State Open Contracting Portal | HTTP 200. Page reports 659 projects and shows 9 on the first page, with detail links. Some visible amounts are ₦0. | None | load now | #190 |
| Gombe State Due Process Portal | Certificate for `www.project.dueprocess.gm.gov.ng` has expired. Not fetched. | None | down | None |
| Jigawa State Open Contracting Portal | HTTP 200. Report files under `/storage/contracts/reports/` include `.xlsx` and `.pdf`. One spreadsheet returned a ZIP header (`PK`). July audit saw PDFs only. | Link discovery only | load now | #193 |
| Anambra State Public Procurement Portal | HTTP 200. Awards table with about 240 distinct OCDS ids (July count was higher, and many ids were repeated in the HTML). | None | load now | #189 |
| Benue State Procurement Portal | HTTP 200. 10 award rows: project, location, year, ministry, contractor, status. The amount column from the July audit is gone. Example: solar backup equipment / Makurdi / 2026 / Benue State Universal Basic Education Board / RYLIN TECH NIGERIA LIMITED / Awarded. | None | load now | #191 |

## What this does not cover

GovSpend is federal ministry and agency payments, not one of these 11. Its contract is `specs/0040-govspend-payments.md`.

Federation Account Allocation Committee (FAAC) monthly PDFs are not in the registry. This bake-off did not probe them.

OpenStates.ng and the Corporate Affairs Commission (CAC) Beneficial Ownership Register stay proposed. They were not probed.

## Method

HTTP GET with redirects, 35 second timeout, `User-Agent: NaijaLedger/bakeoff`. NEITI, NOCOPO, and Gombe were retried with the operating-system trust store after the default bundle rejected them. Child-file checks used a short range request and read the magic bytes only.
