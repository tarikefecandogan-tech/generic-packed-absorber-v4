# Phase 18H Status — Second Verified Industrial VOC Batch

**Phase ID:** `PHASE18H_SECOND_VERIFIED_INDUSTRIAL_VOC_BATCH_2026_10_07`  
**Primary data snapshot:** `PHASE18H_VERIFIED_CHEMICAL_BATCH_2026_10_07`  
**Primary database:** `database/absorber_database_v18h.db`  
**Parent snapshot:** Phase 18G  
**SQL schema:** unchanged Phase 18B.1

## Acceptance result

- `PHASE18H_SECOND_VERIFIED_INDUSTRIAL_VOC_BATCH_GATE = PASS`
- Automated tests: **226/226 PASS**
- Locked V3 parity: **82/82 PASS**
- Phase 1–18H gate scripts: **PASS**
- SQLite `integrity_check`: **OK**
- Foreign-key violations: **0**
- Phase 18G parent records preserved: **PASS**
- Phase 18F safe-import/lazy-tab deployment repair preserved: **PASS**

## Added verified VOCs

| Solute | CAS | Formula | MW g/mol | kH° mol/(kg·bar) | dln(kH)/d(1/T), K | Hpc @ 298.15 K, Pa·m³/mol |
|---|---|---|---:|---:|---:|---:|
| 2-Butanone (MEK) | 78-93-3 | C4H8O | 72.1057 | 20.0 | 5000 | 5.014667 |
| Chloroform | 67-66-3 | CHCl3 | 119.378 | 0.25 | 4500 | 401.173385 |
| Trichloroethylene (TCE) | 79-01-6 | C2HCl3 | 131.388 | 0.10 | 4600 | 1002.933462 |
| Tetrachloroethylene (PCE) | 127-18-4 | C2Cl4 | 165.833 | 0.058 | 4800 | 1729.195625 |
| 1,2-Dichloroethane (EDC) | 107-06-2 | C2H4Cl2 | 98.959 | 0.72 | 4200 | 139.296314 |

### Henry selection policy

Phase 18H keeps the Phase 18G rule unchanged:

> NIST/Sander table: first method `L` row containing both `kH°` and `d ln(kH)/d(1/T)`; no cross-source averaging.

NIST Chemistry WebBook source pages:

- MEK: https://webbook.nist.gov/cgi/cbook.cgi?ID=C78933&Mask=10
- Chloroform: https://webbook.nist.gov/cgi/cbook.cgi?ID=C67663&Mask=10
- TCE: https://webbook.nist.gov/cgi/cbook.cgi?ID=C79016&Mask=10
- PCE: https://webbook.nist.gov/cgi/cbook.cgi?ID=C127184&Mask=10
- EDC: https://webbook.nist.gov/cgi/cbook.cgi?ID=C107062&Mask=10

Identity and water Henry records are **Confidence B** curated-database data. NIST literature scatter is preserved in the provenance note; no hidden averaging is performed.

## Transport governance

No fixed gas- or liquid-diffusion pair was added for the five new solutes.

- `D_G`: Fuller fallback → `CORRELATION_ESTIMATE / Confidence C`
- `D_L`: Wilke–Chang fallback → `CORRELATION_ESTIMATE / Confidence C`
- Fuller and Le Bas group-contribution inputs have separate field-level Confidence-C provenance.

Therefore each new `solute / water` coverage cell is **ESTIMATED**, not fully database-backed/VERIFIED. `solute / acrylonitrile` equilibrium remains **MISSING**.

## Database inventory after Phase 18H

- Solutes: **13**
- Carrier gases: **1**
- Solvents: **2**
- Packings: **10**
- Gas transport pairs: **2**
- Liquid transport pairs: **2**
- Equilibrium pairs: **14**
- Structured sources: **18**
- Provenance records: **31**
- Property/method usage links: **63**

The Phase 18G five-VOC batch remains unchanged in the same snapshot lineage.

## Deterministic 1000 ppmv water fixtures

These are software/data-chain health checks under the standard V4 fixture (`D=0.5 m`, `Z=1.4 m`, `Qg=117.53 actual m³/h`, `L=2500 kg/h`, `T=295.15 K`, `P=101325 Pa`, 25 mm metal Pall ring). They are **not plant-calibrated design guarantees**.

| Solute | Outlet ppmv | Removal % | A | HTU m | Readiness |
|---|---:|---:|---:|---:|---|
| 2-Butanone | 7.1403 | 99.2860 | 12.3712 | 0.2649 | READY_WITH_WARNINGS |
| Chloroform | 859.232 | 14.0768 | 0.1520 | 3.1857 | READY_WITH_WARNINGS |
| TCE | 942.803 | 5.7197 | 0.0610 | 7.9450 | READY_WITH_WARNINGS |
| PCE | 966.744 | 3.3256 | 0.0356 | 14.1716 | READY_WITH_WARNINGS |
| EDC | 631.375 | 36.8625 | 0.4334 | 1.2701 | READY_WITH_WARNINGS |

All fixture relative mass-balance errors are below `1e-8` (actual values ~`1e-14` or smaller).

## Deployment hardening preserved

This release is built on the accepted Phase 18F import/loading repair and the repaired Phase 18G release:

- top-level Streamlit tabs remain lazy (`on_change="rerun"` + `.open` guards);
- Phase 18F, Phase 18G and Phase 18H feature modules use startup-safe imports in `app.py`;
- a missing optional batch module cannot take down the core simulator;
- deploy the **entire ZIP** together to avoid mixed-version `app.py` / package / database states.

## Snapshot hashes

- `absorber_database_v18h.db` SHA-256: `c91c33cfc9f6aaa71c278b39c5ccd3f127557c79d64a08e5e43549c06f314f97`
- `phase18h_verified_batch.json` SHA-256: `6e0831744721f743f8be28f7cf639cb7dc319165ba061830ce02355dcecb4a13`

## Local Streamlit startup note

The build container used for this release does not have the `streamlit` executable installed, so a live local Streamlit server health-check could not be executed here. Deployment readiness was instead checked by full Python compilation, 226/226 tests, all Phase 1–18H gates, 108/108 root package imports, direct safe-module smoke imports, SQLite primary-backend activation, and clean-ZIP revalidation. `requirements.txt` includes `streamlit>=1.40,<2` for Streamlit Cloud installation.
