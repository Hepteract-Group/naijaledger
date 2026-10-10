# 2026-10-01 — Lawful routes to award data for the 30 missing states

Probe of the 28 states with no portal in the registry, plus Kaduna and Gombe (portal exists, no usable
rows). Every claim below was produced by fetching the URL on 2026-10-01. Tickets filed the same day:
[#198 spec: Osun awarded-contracts HTML loader](https://github.com/Hepteract-Group/naijaledger/issues/198),
[#199 spec: Ebonyi awarded-contracts HTML loader](https://github.com/Hepteract-Group/naijaledger/issues/199),
[#200 spec: Ogun awards JSON API loader](https://github.com/Hepteract-Group/naijaledger/issues/200),
[#201 spec: Ondo contract-award CSV and PDF loader](https://github.com/Hepteract-Group/naijaledger/issues/201),
[#202 spike: find a live Edo award page](https://github.com/Hepteract-Group/naijaledger/issues/202),
[#203 spec: Open Contracting Partnership state bulk award files](https://github.com/Hepteract-Group/naijaledger/issues/203),
[#204 spec: Delta project-detail HTML loader](https://github.com/Hepteract-Group/naijaledger/issues/204).

**Award/contract rows** mean a row naming who was paid, for what, how much. **Budget / appropriation
PDFs** are a different thing — they say what a state planned to spend, not who got the money. A budget
PDF is a weaker substitute and cannot answer "who was awarded this contract". Nothing below treats one
as the other.

## 1. Is there a single dataset covering most of the 30?

**Yes, partly: the Open Contracting Partnership (OCP) Data Registry**
(<https://data.open-contracting.org/en/search/?country=Nigeria>). It lists **13 Nigerian publishers**.
It is not a live feed — OCP harvests each publisher with Kingfisher Collect, merges releases, and
serves a frozen bulk download (`full.jsonl.gz`, plus per-year files) even after the source portal dies.
Most state datasets carry the Open Data Commons Public Domain Dedication and Licence (PDDL).

Of the 30 states we need, the registry covers **9**: Abia, Cross River, Ebonyi, Edo, Enugu, Gombe,
Osun, Oyo, Plateau. I downloaded all nine `full.jsonl.gz` files and counted real awards:

| State | Pub. | Records | Awards with supplier **and** amount | Award dates in file |
| --- | --- | --- | --- | --- |
| Osun | [118](https://data.open-contracting.org/en/publication/118) | 492 | **491** | 2019-02 → 2026-09 |
| Ebonyi | [86](https://data.open-contracting.org/en/publication/86) | 470 | **470** | 2018-01 → 2025 |
| Enugu | [104](https://data.open-contracting.org/en/publication/104) | 359 | **358** | 2018-01 → 2022-06 |
| Edo | [102](https://data.open-contracting.org/en/publication/102) | 466 | **215** | 2020-01 → 2021-12 |
| Plateau | [125](https://data.open-contracting.org/en/publication/125) | 166 | **136** | 2022-09 → 2025-03 |
| Abia | [107](https://data.open-contracting.org/en/publication/107) | 113 | **113** | 2018-02 → 2021-09 |
| Gombe | [103](https://data.open-contracting.org/en/publication/103) | 131 | **102** | 2019-01 → 2022-07 |
| Cross River | [105](https://data.open-contracting.org/en/publication/105) | 16 | **16** | 2016-10 → 2021-06 |
| Oyo | [106](https://data.open-contracting.org/en/publication/106) | 304 | **0** | — (tender-only releases) |

Counted in the files: **1,901 award rows across 8 states** (Oyo contributes 0). Not all are
lawfully loadable under our gate. Seven publications state the Open Data Commons Public Domain
Dedication and Licence (PDDL) on the page — **1,765 rows** across Abia, Cross River, Ebonyi, Edo,
Enugu, Gombe, and Osun. Plateau’s page reads `License: -` and Oyo states no open licence; both stay
out of the loader (`specs/0041-ocp-state-bulk-awards.md`). Each PDDL file is one HTTP GET.

Two schema traps. Edo nests awards one level deeper (`awards[0].awards[0]`), which is why a naive
reader sees 466 empty awards instead of 215 real ones. Oyo's releases carry tender objects only, so
Oyo yields nothing despite 304 records.

No other candidate comes close. Budeshi ([37](https://data.open-contracting.org/en/publication/37)) is
federal-only and stopped in Nov 2021; its live site (<https://budeshi.ng/>) is a JavaScript shell and
its backend `https://budeshi-engine.vercel.app/api/projects` returned HTTP 504 on three attempts.
BudgIT GovSpend is federal payer spend, not state awards (see
[federal payments note](2026-10-01-federal-payments-sources.md)). Federation Account Allocation
Committee (FAAC) PDFs are monthly transfer totals, not contracts — they solve nothing here (#197).
OpenStates.ng is a discovery page with no contract rows.

## 2. Per-state status, verified 2026-10-01

Fourteen states were checked individually. The other sixteen have no portal in the registry and none
surfaced in this pass.

### Live award rows on the state's own site (3)

| State | URL | What it returns |
| --- | --- | --- |
| Osun | <https://egp.osunstate.gov.ng/award_publication.php> | **498 award rows** in static HTML: Open Contracting Data Standard (OCDS) identifier, procuring entity, contractor, contract price, award date. Newest 2026-07. Summary page claims ₦307bn over 496 projects. |
| Ebonyi | <https://ebonyieprocure.eb.gov.ng/award_contract_.php> | **705 award rows**, OCDS identifier + amount + contractor + budget year. Newest 2025-11. (OCP marks this publisher "no longer updated" — wrong; the site is current.) |
| Delta | <https://www.contracts.deltappc.dl.gov.ng/projects> | **433 projects**, paginated 12/page. Each detail page is server-rendered and carries Contract Sum, Contractor, Date Awarded, Certificate of No Objection reference, MDA. Sample: ₦149,972,605.04 to O-PLUS SERVICES & CONSULTING ENTERPRISES, awarded 2026-08-27. Not OCDS. |

### Public award API (1)

| State | URL | What it returns |
| --- | --- | --- |
| Ogun | <https://api.eprocurements.ogunstate.gov.ng/api/awards/data> | **151 award rows** as JSON, no auth: contractor, contract amount, budgeted amount, award date, OCDS identifier. 2019-07 → 2022-11. A second endpoint `/api/open-document` adds **32 rows** (2021). `/api/awards` returns 401. No licence published. |

### Portal up, award rows broken or absent (6)

| State | URL | Observed |
| --- | --- | --- |
| Kaduna | <https://www.ocds.kdsg.gov.ng/Projects> | HTTP 200, filter dropdowns only, zero award cards. The portal documents an OCDS API at <https://www.ocds.kdsg.gov.ng/api>: `/api/mda_list` works (28 MDAs, JSON) but `/api/project_list` and `/api/mda_records` both return **HTTP 500**. Backend project queries are failing; this is a bug to report, not a blocked crawl. Kaduna is **not** in the OCP registry, so there is no archive fallback. |
| Gombe | <https://project.dueprocess.gm.gov.ng/projects> | TLS certificate (CN `www.project.dueprocess.gm.gov.ng`) **expired 2026-08-31**. Not fetched; we do not bypass TLS. The host OCP harvested from, `gombe.stateopencontracting.com`, is now **DNS-dead**. The July 2026 `/publication` Cloudinary XLSX/PDF route is unreachable for the same TLS reason. Archive is the only lawful path today. |
| Abia | <https://abiaeprocurement.ab.gov.ng/ocds.php> | HTTP 200, award table renders **header row only, zero data rows**. `/packages.php` advertises per-year "Download JSON" but `/report/media/ocds2024.json` is 404. `/report/summary.php` still claims 580 projects worth ₦53.1bn — so the data exists server-side and the public view is broken. |
| Enugu | <https://dueprocess.en.gov.ng/award_contract_.php> | Same template, same failure: header row only. Its bulk page <https://dueprocess.en.gov.ng/report/ocds_report.php> lists `media/ocds2018.json` … `ocds2026.json`, and **every one of those files is 404**. |
| Oyo | <https://ocdsoyo.oyostate.gov.ng/projects.php> | HTTP 500; site root HTTP 403. Archive has records but no awards. |
| Cross River | <https://ocds.dppib-crsgov.org/> | React shell. Its backend `https://ocdsapi.dppib-crsgov.org/api/ocdsapi/getExistingYearList` returns **HTTP 500**. The parent site <http://dppib-crsgov.org/> is up but is a contractor-registration page. |

### Portal exists, no awards published yet (2)

| State | URL | Observed |
| --- | --- | --- |
| Kano | <https://procurement.kn.gov.ng/> | A brand-new "Kano State Digital Procurement Platform". Its own counters read **2 total tenders, 1 open, 0 contracts**, and the one listed tender is titled "Test 1". Nothing to ingest, but this is the most promising future source among the 28 — worth a recheck each quarter. |
| Rivers | <https://pmis.rsbopp.rv.gov.ng/> | Rivers State Bureau of Public Procurement portal is live but publishes **bid/tender opportunities only** (newest listed 2023), no award table. Single-page app; no public API found in its bundle. |

### Dead (2)

| State | URL | Observed |
| --- | --- | --- |
| Edo | <http://edpms.edostate.gov.ng/ocds/> | Does not resolve. OCP archive only. |
| Plateau | <https://plateaustatebpp.com/ocds> | The domain now **redirects to `patejonesconstruction.com`**, an unrelated commercial site. The government domain has lapsed. Do not seed it. OCP archive only. |

### Nothing found in this pass (16, then 15)

Akwa Ibom, Bauchi, Bayelsa, Borno, Imo, Katsina, Kebbi, Kogi, Kwara, Nasarawa, Niger, Sokoto, Taraba,
Yobe, Zamfara. No Open Contracting Partnership registry entry, no portal surfaced this pass. (Kwara's
awarded-contracts page was already found to render zero rows — `specs/0005-state-ocds-portal-audit.md`.)
For these the only lawful routes are a Freedom of Information (FOI) request or a partnership.

**Ondo was in this list and should not be.** A later probe the same day found public award files on
the Bureau site. See the correction below.

## 3. Why the portals died, and the legal lever

Most of these portals were built under the World Bank **States Fiscal Transparency, Accountability and
Sustainability** programme (P162009, $750m, board-approved 2018-06-27). Its status is **Closed**,
closing date **2024-04-30** (<https://search.worldbank.org/api/v2/projects?format=json&id=P162009>).
The disbursement-linked incentive to keep publishing ended; the dead domains and HTTP 500s date from
after that.

There is no federal statute compelling a *state* to publish awards. The Public Procurement Act 2007
(<https://bpp.gov.ng/wp-content/uploads/2019/01/Public-Procurement-Act-2007pdf.pdf>) binds federal
MDAs; each state has its own procurement law.

The lever that changed is FOI. On **11 April 2025** the Supreme Court held in **SC/614/2018, Osakwe &
Ors v. EDOSACA** that the Freedom of Information Act 2011 binds all 36 states under the doctrine of
covering the field, and ordered a state agency to release contract records, amounts paid and
selection criteria. Certified true copy:
<https://media.premiumtimesng.com/wp-content/files/2025/05/SUPREME-COURT-JUDGMENT-on-FOI-Act_watermark_watermark_compressed_watermark.pdf>
(reported at <https://www.premiumtimesng.com/news/787268-freedom-of-information-foi-act-applicable-to-36-states-supreme-court-rules.html>).
A state bureau can no longer answer "the FOI Act does not apply to us".

Side note: the Bureau of Public Procurement's own wildcard certificate `*.bpp.gov.ng` **expired
2026-09-13**, so `nocopo.bpp.gov.ng` cannot be fetched over valid TLS today. The apex `bpp.gov.ng`
renewed on 2026-09-14 and is fine. Our federal NOCOPO seed is therefore blocked too, and the OCP
registry mirror ([64](https://data.open-contracting.org/en/publication/64), data to Sep 2026) is the
stopgap.

## 4. If we absolutely had to get them — ranked plan

| # | Step | Yield | Blocker |
| --- | --- | --- | --- |
| 1 | Download the PDDL state bulk files from the OCP Data Registry and write one OCDS normalizer (with an Edo nested-award special case). | **7 states, ~1,765 award rows** (Plateau and Oyo refused for licence; Oyo would yield 0 awards anyway) | Stale: six of the seven stop between 2021 and 2025. Static snapshots. Spec stores `ocp_retrieved_on`; whether public views must show it is open on #203. |
| 2 | Scrape the three live state sources: Osun award table, Ebonyi award table, Delta list + 433 detail pages. | **3 states, ~1,636 current rows** (2 overlap with step 1, so +1 net state: Delta) | Delta needs 433 detail fetches behind encrypted URL slugs and has no OCDS identifiers; Osun/Ebonyi are plain HTML tables and cheap. |
| 3 | Ingest the Ogun public JSON API (`/api/awards/data`, `/api/open-document`). | **1 state, 183 rows** | Ends 2022-11. No published licence or terms — get written reuse confirmation before production ingest. |
| 4 | Email six bureaux with a specific, reproducible bug and ask for a data export: Kaduna (`/api/project_list` 500, contact `kadppa@kdsg.gov.ng`), Abia, Enugu (advertised bulk JSON 404), Cross River (API 500), Oyo (500/403), Gombe (certificate expired 2026-08-31). | up to **6 states**, incl. 2 with no archive at all (Kaduna) | Entirely on their response. Treat as a 1–3 month track, not a sprint. Pair with step 5 where no reply lands. |
| 5 | FOI requests citing SC/614/2018 to the 16 states with nothing, asking for the award register in machine-readable form; route through PPDC / Media Rights Agenda who already litigate these. | up to **16 states** | 7-day statutory clock is routinely ignored; enforcement means litigation. Needs a partner and a human sign-off before any public claim. |

Steps 1–3 are code we control. Steps 4–5 are correspondence and must not block the build.

## 5. Next month vs. FOI / partnership

**Realistic in the next month (9 states with award rows, pending #203 licence/public-view answers):**
Abia, Cross River, Ebonyi, Edo, Enugu, Gombe, Osun from the OCP archive; Delta and Ogun from their own
live sources. Ebonyi and Osun get both an archive backfill and a current live feed. Plateau needs a
licence before any archive load.

**Needs a letter, not a crawler (21 states):** the 15 with nothing after the Ondo correction, plus
Kaduna (no archive exists, so the API bug must actually be fixed), Oyo (archive has no awards and no
open licence), Plateau (archive exists, no open licence), Rivers (publishes tenders only), and Kano
(platform real but empty — recheck quarterly rather than writing).

## Same-day correction

A second probe, after the tables above were written:

- **Ondo has award files.** `https://eprocurement.on.gov.ng/` timed out. WordPress media search on
  `https://bpp.on.gov.ng/wp-json/wp/v2/media?search=Contract-Awards` returned 13 files, mostly CSV
  award lists (2019–2022), plus
  `https://bpp.on.gov.ng/wp-content/uploads/2026/04/Contract-Awards-in-Health-April-2026.pdf`. Ticket
  [#201](https://github.com/Hepteract-Group/naijaledger/issues/201). Ondo drops out of the silent list,
  so the Freedom of Information set is 15 states, not 16.
- **Edo still has no live award page.** `https://e-procurement.edostate.gov.ng/` is a vendor
  registration page. `https://edostateocds.cloudware.ng/` and
  `https://eprocurement.edostate.gov.ng/epps/home.do` timed out. The archive in section 1 is the only
  Edo award set we can load today. Ticket
  [#202](https://github.com/Hepteract-Group/naijaledger/issues/202).
- **Ogun publishes no licence.** [#200](https://github.com/Hepteract-Group/naijaledger/issues/200) stays
  `needs-info` until reuse is confirmed. Do not email the state unless asked.

## Follow-ups to file

- Open Contracting Partnership bulk files: [#203](https://github.com/Hepteract-Group/naijaledger/issues/203), spec `specs/0041-ocp-state-bulk-awards.md`. One tender per `ocid`. Oyo and Plateau stay out until the publication page states an open licence.
- Osun [#198](https://github.com/Hepteract-Group/naijaledger/issues/198), Ebonyi
  [#199](https://github.com/Hepteract-Group/naijaledger/issues/199), Delta
  [#204](https://github.com/Hepteract-Group/naijaledger/issues/204).
- Correct `specs/0005-state-ocds-portal-audit.md`: Kaduna is now empty with a 500ing API, and the
  Gombe certificate expired 2026-08-31.
- Bug-report emails to the six bureaux in step 4.
- FOI templates citing SC/614/2018 for the 16 silent states; raise with PPDC under the partnership
  track (#64).
- Recheck `procurement.kn.gov.ng` (Kano) quarterly.
