# 2026-10-01 — Federal payments sources after Open Treasury

Spike for #178 / informs #172.

## Question

Is there a lawful, fetchable federal **payments** leaf now that Open Treasury (`opentreasury.gov.ng`) is unsafe/unreachable (expired TLS; curl times out)?

## Method

HTTP/TLS probes + public page inspection. No fetch of expired-TLS hosts. AgentMail signup was available (`naijaledger@agentmail.to`) but **not required** for the viable source.

## Inventory

| Source | URL | Reachable? | Auth | Payload | Verdict |
| --- | --- | --- | --- | --- | --- |
| Open Treasury (official) | https://opentreasury.gov.ng/ | No (timeout) | Public historically | Daily MDA payment Excel/PDF | **Do not scrape** — retired/unsafe |
| payment.gov.ng | https://payment.gov.ng/ | DNS NXDOMAIN | — | — | Dead |
| BudgIT GovSpend | https://www.govspend.ng/ + `https://app.govspend.ng/api/` | Yes (TLS OK) | **None** for payments JSON | Paginated payment rows | **Best interim leaf** (secondary; mined from Open Treasury) |
| OAGF FAAC PDFs | https://oagf.gov.ng/publications/faac-report/ | Yes | None | Monthly federation disbursement PDFs | Useful **macro transfers**, not MDA payment microdata |
| OAGF GIFMIS reports page | https://oagf.gov.ng/publications/gifmis-reports/ | Yes | None | Empty (“publications being uploaded”) | No leaf |
| GIFMIS marketing | https://gifmis.gov.ng/ | Yes | — | Marketing / news | No payment extracts |
| GIFMIS PFM | https://pfm.gifmis.gov.ng/cas/login | Yes | Staff login | Internal PFM | **Closed** — not a public scrape target |
| MoF / Budget Office | finance.gov.ng, budgetoffice.gov.ng | Yes | — | Budget/docs | Not payment microdata |
| CBN | cbn.gov.ng | Yes | — | Macro/stats | Not MDA payments |
| Remita | remita.net | Yes | Commercial | Payment rails | Not transparency data |
| RevOp / FTeR | press coverage only | N/A | MDA/billing | **Revenue** collection | Wrong direction for payments anomaly |
| OpenStates.ng | openstates.ng | Yes | — | Discovery UI | Already demoted (spec 0039) |

### Other candidates considered

- Wayback / mirrors of Open Treasury Excel packs — not found as a durable bulk archive in this spike.
- Commercial US “GovSpend.com” API docs — **unrelated** product; ignore.
- IPPIS payroll aggregates in press — not a downloadable public feed.

## GovSpend proof (2026-10-01)

- Explore UI: ~**467,930** payment records; newest samples dated **2026-06-19**.
- Public API (no signup):
  - `GET https://app.govspend.ng/api/payments/?page=N` → JSON pages (~100 rows), `last` ≈ 4680.
  - Fields: `date`, `payment_no`, `payer_code`, `organization_name`, `beneficiary_name`, `amount`, `description`.
  - Coverage sampled from **2018-09-01** (last page) through **2026-06-19**.
  - `GET /api/organizations/` and `/api/organizations/all` also public JSON.
- Download UI at `/download/` offers CSV/XLS/XLSX/ODS/JSON with date filters — **no login**.
- Bulk download API paths (`/payments/download/`, `/payments/search_download/`) returned 500/403/404 in probe; prefer paginated JSON.
- Admin shell at `app.govspend.ng/api/` HTML says “Sign in” for some routes; **payments list does not require it**.
- Provenance: BudgIT states GovSpend is mined from the FG Open Treasury portal. Treat as **civic secondary** with attribution; seek written reuse permission under #64.

## Signup / AgentMail

Not needed for GovSpend. Keep `naijaledger@agentmail.to` for partnership reply and any future signup-gated source.

## Recommendation (for #172)

1. **Approve BudgIT GovSpend** as the interim federal payments source (`ingest_role=leaf`, category=`payments`), with mandatory credit and rate-limited pagination of the public JSON API.
2. **Open partnership / reuse confirmation** with BudgIT (`info@budgit.org`) before large-scale production ingest (ties to #64). Public browse/download is intentional for CSOs/media; still ask for written OK + attribution language.
3. Optionally seed **OAGF FAAC PDF catalog** as a separate federation-transfer source — does **not** replace MDA payments for `budget_payment_mismatch`.
4. Keep Open Treasury retired until TLS is fixed; then re-evaluate as primary official leaf.
5. Do **not** attempt GIFMIS PFM credential scraping or Remita.

## Follow-ups

- Spec + implement GovSpend → `payments` normalizer (new story after #172 decision).
- Draft partnership email (AgentMail) to BudgIT.
- Parallel FOI/legal ask to OAGF for machine-readable daily payments while official portal is down.
