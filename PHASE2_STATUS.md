# V4 Phase 2 — Status

**Gate:** PASS

## Implemented
- `AbsorberDataRegistry`
- exact solute–carrier gas-transport lookup
- exact solute–solvent liquid-transport lookup
- exact solute–solvent equilibrium lookup
- explicit `MissingPairDataError`
- `find_*` optional discovery vs `require_*` critical lookup
- foreign-key checks when registering pairs
- duplicate-registration protection
- explicit `replace=True` overwrite path
- `PairAvailability` / `READY` vs `INCOMPLETE` data-readiness report
- reference-registry builder from the locked Phase 1 snapshot
- Streamlit registry lookup and missing-pair safety demonstration

## Locked behavior
- ACN/Air -> `DG = 1.0e-5 m2/s`
- VAc/Air -> `DG = 0.9e-5 m2/s`
- ACN/Water -> `DL = 1.0e-9 m2/s` + locked Henry pair
- VAc/Water -> `DL = 0.9e-9 m2/s` + locked Henry pair

## Safety rule
Missing pair data are **never** replaced by another chemical pair or a hidden default in Phase 2.

## Explicitly untouched
- water property calculation
- carrier viscosity calculation
- Fuller / Wilke-Chang estimates
- Onda mass transfer
- two-film `KG`
- counter-current ODE / shooting solver
- pressure drop / GPDC
- required height
- unit/concentration conversion

## Next gate
**Phase 3 — Property Resolver**: resolve user overrides vs verified database vs future correlation estimates vs missing, while preserving provenance and confidence.
