# Phase 18F — Chemical Database Expansion Framework

**Status:** PASS  
**Framework ID:** `PHASE18F_CHEMICAL_EXPANSION_FRAMEWORK_2026_10_07`  
**Import contract:** `18F.1`  
**Primary SQLite schema target:** `18B.1`

## Purpose
Phase 18F adds a controlled ingestion path for future chemical/property data without adding any new real chemistry to the shipped primary database. The framework is data-governance infrastructure; it performs no absorber physics and it never invents missing values.

## New files
- `generic_absorber_v4/chemical_import.py`
- `database/templates/chemical_import_template.json`
- `chemical_import_cli.py`
- `tests/test_phase18f_chemical_import_framework.py`
- `phase18f_check.py`

## Import contract
A package may contain:
- structured bibliographic `sources`,
- reusable `provenance` records,
- `solutes`, `carriers`, `solvents`,
- `gas_transport_pairs`, `liquid_transport_pairs`,
- `equilibrium_pairs`.

Every imported engineering record requires a `provenance_key`. Confidence A/B provenance additionally requires a source title and a DOI or URL. Missing estimator inputs (e.g. Fuller volume or Le-Bas boiling volume) remain explicit warnings rather than fabricated values.

## Validation rules
The validator blocks, among other cases:
- missing/incorrect contract version,
- missing record provenance,
- invalid confidence class,
- A/B sources without bibliographic locator,
- duplicate package keys,
- append-only collisions with existing IDs/pairs,
- broken pair references,
- invalid/nonpositive physical quantities,
- incomplete model-specific Henry or linear-equilibrium fields,
- invalid temperature-validity ranges.

It also reports readiness warnings for:
- missing CAS/formula,
- unavailable Fuller fallback inputs,
- unavailable Wilke–Chang fallback inputs,
- newly imported solutes with no equilibrium pair in the package,
- model types that can be stored but are outside the standard V4 physical-absorption solver.

## Write policy
- **Dry-run is the default.**
- Streamlit Phase 18F is **dry-run only** and has no production write button.
- Real writes require an explicit operator call using `chemical_import_cli.py --commit` or the Python API.
- Commit is one SQLite transaction.
- Optional automatic pre-import backup is enabled by default.
- Replacement of an existing entity/pair requires explicit `--allow-replace` / `allow_replace=True`.

## Gate results
`PHASE18F_CHEMICAL_EXPANSION_GATE = PASS`

Gate checks:
- valid QA package passes dry-run,
- dry-run leaves primary DB byte-identical,
- real commit succeeds only on a temporary database copy,
- expected inventory delta is exact,
- imported synthetic solute is visible through Registry + Resolver + Database Explorer,
- its fallback transport path is resolved and its D-confidence equilibrium remains SCREENING,
- invalid provenance is blocked before mutation,
- duplicate append-only import is blocked,
- failed validation leaves the temporary DB byte-identical,
- primary production database remains byte-identical,
- SQLite integrity = `ok`,
- foreign-key violations = `0`.

## Regression results
- `186/186` pytest tests PASS.
- Phase 1–18F check scripts PASS.
- Locked Phase 9 reference remains `82/82` parity metrics PASS.
- Phase 18C Python/SQLite backend parity remains 5/5 scenarios and 119/119 metrics exact match.

## Important scope boundary
The bundled synthetic Phase 18F package is **QA-only** and is never added to the shipped database. It is intentionally non-scientific and is imported only into temporary copies during the gate. Phase 18F therefore changes the ingestion architecture, not the production chemistry inventory.
