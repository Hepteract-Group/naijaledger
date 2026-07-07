# Spec 0005 — State OCDS portal URL audit (seed correction)

- **Epic / Issue**: follow-up to E2.3 / fetch failures
- **Status**: Implemented
- **Author**: agent
- **Needs human decision?**: no (technical URL verification)

## 1. Problem
Seven of eight seeded `*.azurewebsites.net` state OCDS URLs no longer resolve (DNS dead).
Fetch was failing despite a working pipeline.

## 2. Audit results (2026-07-07, DNS + HTTP + Scrapling probe)

| State | Old URL | Verdict | New URL |
|-------|---------|---------|---------|
| Lagos | lagosppaocds.azurewebsites.net | DNS dead; FIJ reports OCDS taken down | https://lagosstate.gov.ng/lsppa/ |
| Kaduna | www.ocds.kdsg.gov.ng | OK | unchanged |
| Ekiti | ekitibppaocds.azurewebsites.net | DNS dead | https://ocdsportal.azurewebsites.net/ |
| Adamawa | adamawappaocds.azurewebsites.net | DNS dead | https://bpp.adamawastate.gov.ng/ |
| Ondo | ondobppaocds.azurewebsites.net | DNS dead; BPP confirms e-proc down | **substitute Kwara** → https://kwppa.kwarastate.gov.ng/ocds-portal/awarded-contracts |
| Osun | osunbppaocds.azurewebsites.net | DNS dead | **substitute Jigawa** → https://ocds.dueprocess.jg.gov.ng/ |
| Anambra | anambrappaocds.azurewebsites.net | DNS dead | https://eprocure.bpp.an.gov.ng/ |
| Rivers | riversbppaocds.azurewebsites.net | DNS dead | **substitute Benue** → https://procurement.benuestate.gov.ng/ |

Substitutions chosen from BudgIT SFTL 2025 progressive performers with live portals.

## 3. Acceptance criteria
- [x] All eight seed URLs resolve and return HTTP 200 via Scrapling fetch probe.
- [x] Obsolete azure URLs retired on re-seed; URL corrections applied for same-state fixes.
- [x] `make fetch-sources` scrapling batch attempts only reachable hosts.
