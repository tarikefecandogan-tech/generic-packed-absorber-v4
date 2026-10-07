# Phase 18C — Repository Abstraction & Dual-Backend Parity

**Gate:** `PHASE18C_REPOSITORY_ABSTRACTION_GATE = PASS`

## Objective
Decouple the integrated simulator from the engineering-data storage implementation. The physics chain now accepts a backend-neutral repository contract and can run from either:

- the verified Python registry, or
- the Phase 18B SQLite engineering database.

No mass-transfer, ODE, hydraulics, units, equilibrium, or applicability equations were changed.

## Architecture

`Simulator -> AbsorberDataRepository -> AbsorberDataRegistry -> Resolver -> Physics`

New module: `generic_absorber_v4/repository.py`

Key types/functions:

- `AbsorberDataRepository`
- `RepositoryDescriptor`
- `RepositoryKind`
- `PythonRegistryRepository`
- `RegistryLoaderRepository`
- `build_python_registry_repository()`
- `build_sqlite_v18b_repository()`
- `resolve_registry_source()`

`run_generic_absorber_case()` now accepts `repository=` while preserving the existing `registry=` API. Passing both is rejected explicitly.

## Backend parity suite
New module: `generic_absorber_v4/repository_validation.py`.

Deterministic scenarios executed independently on both backends:

1. ACN + VAc / Water locked reference case
2. VDC / Water
3. VDC / Acrylonitrile screening case
4. ACN + VAc + VDC / Water
5. VDC / Water with preloaded solvent

**Results:** 5/5 scenarios PASS, **119/119 numerical metrics match**, maximum absolute error `0.0`, maximum relative error `0.0`, and readiness/confidence states match.

Registry dictionaries and inventory also match exactly.

## Regression state

- Automated tests: **163/163 PASS**
- Locked V3 parity: **82/82 PASS**
- Phase 1–18C check scripts: PASS
- Streamlit package imports: **101/101 available**
- SQLite integrity: `OK`
- SQLite foreign-key violations: `0`

## Streamlit
The **Simulator** now exposes an `Engineering data backend` selector. The selected backend is recorded in each result and shown on the results page.

New **Repository Backends** tab provides:

- backend descriptors,
- registry inventories,
- SQLite integrity/FK status,
- registry-object parity,
- full dual-backend scenario parity.

Sweep and Comparison continue from the Simulator result registry, so they remain consistent with the backend used for the baseline case.

## Governance rule
Phase 18C does **not** delete the Python registry or silently make SQLite authoritative. It introduces a verified switchable data-access layer. A future cut-over can occur only after repository parity remains stable as the database expands.
