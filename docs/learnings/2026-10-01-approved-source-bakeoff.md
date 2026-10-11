# 2026-10-01 — Re-probe of the 11 July-approved sources

Spike for #186. Probed the seed URL for each of the 11 July-approved sources as of 1 October 2026. No rows were written to Postgres. Expired TLS certificates were not bypassed.

**Valid as of 2026-10-01; re-probe before acting.**

Main now has 18 approved sources: these 11 plus 7 Open Contracting Partnership (OCP) Data Registry bulk sources (#203 / spec 0041) that were added later and have their own licence and Open Data Commons Public Domain Dedication and License (PDDL) compliance gates. The OCP sources were not probed here. Oyo and Plateau OCP sources remain proposed (not approved).

## Ranks

`load now` means the page or a child file still contains award, tender, or budget rows, and a loader spec is justified. `fetch-only` means the URL responds but the body is not a row leaf. `down` means the URL failed TLS and was not fetched.

| Source | Result on 2026-10-01 | Existing loader | Rank | Follow-up |
| --- | --- | --- | --- | --- |
| Nigeria Open Contracting Portal (NOCOPO) — Open Data | Certificate for `*.bpp.gov.ng` expired 2026-09-13 (Sectigo DV). Not fetched with verification. Re-checked 2026-10-11: public DNS resolves to 18.169.6.94; the host serves HTTP 200 only when certificate checks are skipped (-k), which this project does not do.¹ | None. #173 is blocked until the certificate is renewed. | down | None |
| Budget Office of the Federation — Budget Documents | HTTP 200. Index links year folders. The 2026 folder still exposes `/download` links. | Appropriation PDF path, `specs/0037-appropriation-budget-lines.md` | load now | No new spec |
| Nigeria Extractive Industries Transparency Initiative (NEITI) — Documents library | HTTP 200 only when the system trust store is used. Python's default certificate bundle failed the chain. Child PDFs are mixed speeches, letters, and audits. | None | fetch-only | No normalizer until an allowlist exists |
| Lagos State Public Procurement Agency — Registered Awards | HTTP 200. Monthly award-register PDF links. December 2025 file starts with `%PDF-1.7`. | Link discovery only | load now | #192 |
| Kaduna State Open Contracting Portal | HTTP 200. Static HTML has ministry filter names and no award rows, no naira amounts, and no project API. July 2026 pages had embedded project cards. The scheduled fetch method is non-JavaScript. A browser render was not re-run: the Playwright browser binary is not installed locally. | None | fetch-only | Browser re-run (#186 follow-up) |
| Ekiti State Open Contracting Portal | HTTP 200. About 2,737 table rows and Open Contracting Data Standard (OCDS) ids in the HTML. | `specs/0032-ekiti-html-portal-load.md` | load now | No new spec |
| Adamawa State Open Contracting Portal | HTTP 200. Page reports 659 projects and shows 9 on the first page, with detail links. Some visible amounts are ₦0. | None | load now | #190 |
| Gombe State Due Process Portal | Certificate for `project.dueprocess.gm.gov.ng` has expired. Not fetched. | None | down | Covered by OCP Data Registry (spec 0041) |
| Jigawa State Open Contracting Portal | HTTP 200. Report files under `/storage/contracts/reports/` include `.xlsx` and `.pdf`. One spreadsheet returned a ZIP header (`PK`). July audit saw PDFs only. | Link discovery only | load now | #193 |
| Anambra State Public Procurement Portal | HTTP 200. Awards table with about 240 distinct OCDS ids (July count was higher, and many ids were repeated in the HTML). | None | load now | #189 |
| Benue State Procurement Portal | HTTP 200. 10 award rows: project, location, year, ministry, contractor, status. The amount column from the July audit is gone. Example: solar backup equipment / Makurdi / 2026 / Benue State Universal Basic Education Board / RYLIN TECH NIGERIA LIMITED / Awarded. | None | load now | #191 |

## What this does not cover

GovSpend is federal ministry and agency payments, not one of these 11. Its contract is `specs/0040-govspend-payments.md`.

Federation Account Allocation Committee (FAAC) monthly PDFs are not in the registry. This bake-off did not probe them.

OpenStates.ng and the Corporate Affairs Commission (CAC) Beneficial Ownership Register stay proposed. They were not probed.

## Method

HTTP GET with redirects, 35 second timeout, `User-Agent: NaijaLedger/bakeoff`. NEITI, NOCOPO, and Gombe were retried with the operating-system trust store after the default bundle rejected them. Child-file checks used a short range request and read the magic bytes only.

## 2026-10-11 TLS re-check

NOCOPO and Gombe TLS status re-verified on 2026-10-11 at 09:41:38 UTC (10:41 BST) before #173 work.

### Method

- **Tool**: `curl` 7.81.0, with `--max-time 35` and `-A "NaijaLedger/re-check"`, using system CA bundle `/etc/ssl/certs/ca-certificates.crt`
- **System resolver**: `10.0.0.2` (from `/etc/resolv.conf`)
- **Network location**: Cursor Cloud Agent VM
- **Attempts**: 1 per host per resolver
- **DNS cross-check**: `dig` 9.18.39 queries to Cloudflare (1.1.1.1) and Google (8.8.8.8) public resolvers

### Results

#### NOCOPO (`nocopo.bpp.gov.ng`)

System resolver (curl): Failed to resolve host after 10 seconds (local environment issue; see footnote 1).

```
curl: (6) Could not resolve host: nocopo.bpp.gov.ng
```

Cloudflare resolver (dig @1.1.1.1):

```
18.169.6.94
```

Google resolver (dig @8.8.8.8):

```
18.169.6.94
```

Pinned-IP test (curl --resolve nocopo.bpp.gov.ng:443:18.169.6.94):

```
curl: (60) SSL certificate problem: certificate has expired
```

Pinned-IP test with -k flag (skipping certificate verification):

```
HTTP/2 200
content-length: 39968
content-type: text/html; charset=utf-8
```

**Conclusion**: Public DNS resolvers return an A record (18.169.6.94). The host serves HTTP 200 at /Open-Data when certificate verification is skipped, but the certificate for `*.bpp.gov.ng` expired 2026-09-13 23:59:59 GMT (Sectigo DV R36). #173 remains blocked until the certificate is renewed.

#### Gombe (`project.dueprocess.gm.gov.ng`)

System resolver (curl): Resolved to 138.201.31.212, TLS handshake completed, certificate expired.

```
curl: (60) SSL certificate problem: certificate has expired
```

Cloudflare resolver (dig @1.1.1.1):

```
138.201.31.212
```

Google resolver (dig @8.8.8.8):

```
138.201.31.212
```

**Conclusion**: Host resolves consistently across all resolvers and accepts TLS connections, but the certificate has expired.
