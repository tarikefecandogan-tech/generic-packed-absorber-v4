# Generic Packed Absorber Simulator V4 — Phase 18E Status

## Phase 18E — Database Explorer & Coverage Matrix

**Status:** PASS  
**Gate:** `PHASE18E_DATABASE_EXPLORER_GATE = PASS`  
**Date:** 2026-10-07

## Objective

Expose the validated Phase-18B SQLite engineering database through a **read-only Database Explorer** without changing any absorber physics, solver equation, repository cut-over policy, or reference result.

Phase 18E adds:

- searchable chemical / solvent / carrier / packing catalog views;
- explicit equilibrium, gas-transport and liquid-transport pair tables;
- a carrier-aware **solute × solvent coverage matrix**;
- resolver-aware distinction between database data, correlation-estimated transport, screening equilibrium and truly missing critical data;
- a prioritized data-expansion backlog;
- a deterministic read-only explorer acceptance gate.

## Coverage classification

At the chosen audit temperature/pressure and carrier:

- **VERIFIED** — equilibrium and transport resolve from registered database values; equilibrium confidence is A/B.
- **ESTIMATED** — equilibrium is A/B database-backed, but one or both transport properties require Confidence-C Fuller/Wilke–Chang estimates.
- **SCREENING** — the equilibrium path is Confidence D / surrogate.
- **MISSING** — at least one critical equilibrium/transport property cannot be resolved.
- **UNSUPPORTED** — registered physics exists but is not supported by the current V4 calculation domain.

The matrix is a **data-coverage diagnostic**, not a performance or design-validity score.

## Current coverage snapshot

For `Air`, 298.15 K and 1 atm:

| Solute / Solvent | Water | Acrylonitrile |
|---|---|---|
| ACN | VERIFIED | MISSING |
| VAc | VERIFIED | MISSING |
| VDC | ESTIMATED | SCREENING |

Coverage totals:

- VERIFIED: **2**
- ESTIMATED: **1**
- SCREENING: **1**
- MISSING: **2**
- UNSUPPORTED: **0**
- Resolvable cells: **4 / 6 = 66.7%**

## Data-expansion backlog

Highest-priority true gaps are currently:

1. ACN / Acrylonitrile — missing critical pair data.
2. VAc / Acrylonitrile — missing critical pair data.

Secondary improvement targets:

- VDC / Acrylonitrile — replace Confidence-D screening equilibrium with design-grade binary VLE / activity-coefficient data.
- VDC / Water — replace correlation-estimated gas/liquid transport with measured or trusted database diffusivities when available.

## New files

- `generic_absorber_v4/database_explorer.py`
- `tests/test_phase18e_database_explorer.py`
- `phase18e_check.py`
- `PHASE18E_STATUS.md`
- `app.py` — new **Database Explorer** product tab

## Regression / safety results

- Full automated suite: **177 / 177 PASS**
- V3 full parity: **82 / 82 PASS**
- Phase 18C Python ↔ SQLite parity: **5 / 5 scenarios, 119 / 119 metrics exact match**
- SQLite integrity: **ok**
- Foreign-key violations: **0**
- Explorer read-only database checksum test: **PASS**
- Phase 18E deterministic coverage statuses: **PASS**
- Search test (`VDC` cross-table hits): **PASS**

## Engineering conclusion

Phase 18E turns the SQLite primary database into an auditable engineering catalog rather than an opaque solver backend. It also makes missing-data priorities explicit before the chemical database is expanded.

No physics calculation was added to the explorer layer. Coverage is derived from the existing repository + resolver behavior and therefore respects the established priority:

`USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING`
