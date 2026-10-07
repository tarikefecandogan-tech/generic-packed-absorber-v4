# Phase 18G — First Verified Chemical Expansion Batch

**Status:** PASS  
**Date:** 2026-10-07  
**Batch ID:** `PHASE18G_FIRST_VERIFIED_CHEMICAL_BATCH_2026_10_07`  
**Primary data snapshot:** `PHASE18G_VERIFIED_CHEMICAL_BATCH_2026_10_07`  
**Primary SQLite file:** `database/absorber_database_v18g.db`  
**SQL schema:** unchanged `18B.1`

## Purpose

Phase 18G is the first real-chemistry use of the controlled Phase-18F ingestion framework. It expands the shipped primary engineering database while preserving the V4 physics, the frozen Phase-18B historical database, and all previous parity gates.

Five common VOCs were added:

1. Acetone — CAS 67-64-1
2. Benzene — CAS 71-43-2
3. Toluene — CAS 108-88-3
4. Ethylbenzene — CAS 100-41-4
5. Dichloromethane / methylene chloride — CAS 75-09-2

## Scientific data policy

### Identity
Formula, molecular weight and CAS identity are registered from the NIST Chemistry WebBook and classified as **Confidence B / DATABASE**.

### Water equilibrium
NIST/Sander water Henry tables are used. The deterministic selection rule is:

> first method `L` row containing both `kH°` and `d ln(kH)/d(1/T)`.

No cross-source averaging or hidden cherry-picking is performed. Literature scatter remains explicitly noted in provenance.

NIST solubility-form Henry data are converted to the V4 canonical pressure/concentration form:

`Hpc = 1e5 / (kH * rho_water_298)`

with `rho_water_298 = 997.0751177 kg/m3` from the existing V4 water property correlation.

| Solute | kH° mol/(kg·bar) | dln(kH)/d(1/T), K | Hpc, Pa·m3/mol |
|---|---:|---:|---:|
| Acetone | 30.0 | 4600 | 3.3431115411 |
| Benzene | 0.16 | 4100 | 626.833413958 |
| Toluene | 0.15 | 4000 | 668.622308221 |
| Ethylbenzene | 0.12 | 5100 | 835.777885277 |
| Dichloromethane | 0.36 | 4100 | 278.592628426 |

Equilibrium is **Confidence B**.

### Transport
No fixed measured `D_G` or `D_L` pair is fabricated for the new compounds.

- gas transport uses the existing Fuller fallback when needed;
- liquid transport in water uses the existing Wilke–Chang fallback when needed;
- pure-solute Fuller and Le Bas group-contribution inputs are stored as **Confidence C correlation inputs**;
- field-level provenance separates NIST identity data (B) from Fuller/Le Bas estimator inputs (C).

Therefore each new VOC / Water coverage cell is **ESTIMATED**, not VERIFIED.

## Database inventory after expansion

- Solutes: **8**
- Carrier gases: **1**
- Solvents: **2**
- Packings: **10**
- Gas transport pairs: **2** (unchanged)
- Liquid transport pairs: **2** (unchanged)
- Equilibrium pairs: **9**
- Structured sources: **13**
- Provenance records: **21**
- Provenance usage links: **43**
- SQLite integrity: **OK**
- Foreign-key violations: **0**

The historical `absorber_database_v18b.db` remains in the package so Phases 18C/18D can continue to prove the original Python ↔ SQLite parity independently of later data expansion.

## Product cut-over

The product default database file is now:

`database/absorber_database_v18g.db`

`select_primary_data_repository()` returns backend `sqlite_v18g` when the packaged Phase-18G snapshot is healthy. The Python registry remains an explicit controlled fallback/reference backend. The SQL schema is still `18B.1`; Phase 18G is a data snapshot change, not a schema change.

## Deterministic software fixtures

Each new solute was run at 1000 ppmv in the reference column/water operating fixture (D=0.5 m, Z=1.4 m, Qg=117.53 actual m3/h, L=2500 kg/h, 22 °C, 1 atm). These are software/engineering validation fixtures, **not plant-calibrated design guarantees**.

| Solute | Outlet ppmv | Removal % | A | HTU_OG m | Readiness |
|---|---:|---:|---:|---:|---|
| Acetone | 3.03137 | 99.6969 | 18.3054 | 0.230468 | READY_WITH_WARNINGS |
| Benzene | 910.174 | 8.98257 | 0.0959789 | 4.97034 | READY_WITH_WARNINGS |
| Toluene | 916.964 | 8.30360 | 0.0896740 | 5.64716 | READY_WITH_WARNINGS |
| Ethylbenzene | 931.521 | 6.84788 | 0.0744805 | 7.10787 | READY_WITH_WARNINGS |
| Dichloromethane | 800.037 | 19.9963 | 0.215952 | 2.13564 | READY_WITH_WARNINGS |

All fixture relative mass-balance errors are below `4e-14`.

## UI changes

- Product primary backend advances to SQLite v18G.
- Database Explorer reads the v18G snapshot and now shows 8 solutes × 2 solvents.
- Expansion Framework dry-runs against the current v18G primary snapshot.
- New **Verified Batch** tab documents the five additions, Henry-selection policy, coverage state and Phase-18G acceptance gate.
- Historical Phase-18B/18C/18D audit databases/gates remain frozen and separate.

## Acceptance gate

`PHASE18G_FIRST_VERIFIED_CHEMICAL_BATCH_GATE = PASS`

Checks include:

- database integrity and foreign keys;
- exact identity fields;
- exact registered Henry values and Confidence B;
- no new fixed gas/liquid transport pairs;
- Fuller/Wilke–Chang resolution tier = CORRELATION_ESTIMATE / C;
- Water coverage = ESTIMATED for all five new VOCs;
- Acrylonitrile-solvent coverage = MISSING for all five new VOCs;
- field-level B-vs-C provenance split;
- full standard-fixture numerical health and mass balance.

## Regression state

- Automated tests: **206/206 PASS**
- Locked V3 full parity: **82/82 PASS**
- Historical Phase 18C repository parity: **5/5 scenarios, 119/119 numerical metrics exact match**
- Phase 1–18G gate scripts: **PASS**
- `app.py` package import surface: **123/123 imported names available**

## 18F repair rebase (deployment hardening)

This Phase-18G delivery was rebuilt on top of the accepted Phase-18F Streamlit import/loading repair after the original Phase-18G package had been generated.

Preserved hardening:

- top-level Streamlit tabs remain lazy (`on_change="rerun"` + `.open` guards);
- Phase-18F `chemical_import` is an optional safe import at startup, so a mixed deployment cannot crash the core simulator;
- Phase-18G `verified_batch_v18g` is also startup-safe; if missing, only the Verified Batch feature is disabled;
- the current product database is `absorber_database_v18g.db`, while the frozen v18B database remains for historical parity gates;
- full-package deployment is still required to avoid mixed-version GitHub/Streamlit states.

Rebased verification:

- 206/206 tests PASS;
- Phase-18F gate PASS;
- Phase-18G gate PASS;
- locked V3 parity 82/82 PASS;
- `app.py` compiles;
- root package imports have no missing names;
- direct imports of `generic_absorber_v4.chemical_import` and `generic_absorber_v4.verified_batch_v18g` PASS.
