# Phase 18F Streamlit Import Repair

## Symptom
Streamlit Cloud fails at `app.py` around the Phase 18F import block with a redacted `ImportError`.

## Root cause
The deployed `app.py` is newer than the deployed `generic_absorber_v4` package, or the Phase 18F module/export surface is incomplete. This is a mixed-version deployment failure, not a physics/database failure.

## Repair
- Phase 18F imports are loaded directly from `generic_absorber_v4.chemical_import`.
- The import is startup-safe: if Phase 18F is unavailable, the main simulator still loads.
- Only the Expansion Framework tab is disabled and shows the concrete import error.
- Full synchronized Phase 18F package files are included in this ZIP.

## Validation
- `python -m py_compile app.py generic_absorber_v4/*.py` PASS
- Full regression suite: 186/186 PASS
- No physics, database values, or solver equations changed.
