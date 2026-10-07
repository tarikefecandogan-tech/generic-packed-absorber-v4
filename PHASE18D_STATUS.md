# Generic Packed Absorber Simulator V4 — Phase 18D Status

## Phase 18D — SQLite Primary Read Source / Controlled Cut-over

**Status:** PASS  
**Gate:** `PHASE18D_SQLITE_PRIMARY_CUTOVER_GATE = PASS`  
**Date:** 2026-10-07

## Objective

Move the product-facing simulator from the verified in-code Python registry to the Phase-18B SQLite engineering database as the **primary read source**, without changing any physical model, equation, numerical solver or reference result.

The Python registry remains available as:

- the verified reference backend;
- an explicitly labelled controlled fallback;
- a regression oracle for database parity.

## Cut-over policy

Primary selection follows this sequence:

1. Locate `database/absorber_database_v18b.db`.
2. Require SQLite `integrity_check = ok`.
3. Require zero foreign-key violations.
4. Require schema version `18B.1`.
5. Require successful complete `AbsorberDataRegistry` reconstruction.
6. Only then activate SQLite as the product primary backend.

If any of those checks fail:

- **fallback enabled:** activate `Verified Python Registry — CONTROLLED FALLBACK` and surface the exact failure reason;
- **strict mode:** raise `PrimaryRepositoryUnavailableError` and stop.

There is no silent database fallback and no backend may masquerade as SQLite after a failed validation.

## Product/UI behavior

The Streamlit **Simulator** now defaults to:

`Primary engineering database` → SQLite Engineering Database v18B

The user can still explicitly select:

`Verified Python Registry — reference`

The active backend is reported on the result page.

The **Repository Backends** tab now exposes:

- requested primary backend;
- active backend;
- SQLite integrity state;
- foreign-key status;
- fallback state/reason;
- primary/reference inventory;
- full Phase-18D cut-over gate;
- Phase-18C dual-backend parity reference test.

## Regression results

- Full automated suite: **169 / 169 PASS**
- V3 full parity metrics: **82 / 82 PASS**
- Python ↔ SQLite deterministic scenarios: **5 / 5 PASS**
- Python ↔ SQLite numerical metrics: **119 / 119 exact match**
- SQLite integrity: **ok**
- Foreign-key violations: **0**
- Missing-database controlled fallback test: **PASS**
- Missing-database strict-mode rejection test: **PASS**
- Corrupt-database non-masquerading test: **PASS**

## Backward compatibility

The lower-level library call:

```python
run_generic_absorber_case(case)
```

remains backward-compatible and still uses the verified Python default registry when no backend is explicitly passed.

The **product-facing Streamlit simulator**, however, explicitly passes the Phase-18D primary repository and therefore uses SQLite by default. This separation avoids silently changing existing API consumers while completing the application cut-over.

## New/changed files

- `generic_absorber_v4/repository.py`
  - SQLite primary selector
  - controlled fallback policy
  - strict-mode failure
  - packaged default DB path
  - cut-over audit decision
- `generic_absorber_v4/cutover_validation.py`
  - Phase-18D cut-over regression gate
- `tests/test_phase18d_primary_cutover.py`
- `phase18d_check.py`
- `app.py`
  - SQLite primary selected by default
  - fallback visibly surfaced
  - Phase-18D repository status UI

## Engineering conclusion

Phase 18D completes the **read-side production cut-over** to the engineering SQLite database while retaining the Python registry as a verified reference/fallback source.

The calculation chain itself is unchanged:

`Repository → AbsorberDataRegistry → Property Resolver → Onda → ODE → Hydraulics → Units → Applicability`

No physics was moved into the database or repository layer.
