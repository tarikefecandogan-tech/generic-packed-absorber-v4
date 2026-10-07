# Streamlit deployment — Phase 11

Use the same GitHub repository and Streamlit app. Replace the local repository contents with the complete Phase 11 package, then commit and push.

Recommended commit message:

`Phase 11 - Fuller and Wilke-Chang property estimators`

Important files that must come from the same Phase 11 package:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/resolver.py`
- `generic_absorber_v4/correlations.py`
- `generic_absorber_v4/estimation_validation.py`
- `tests/test_phase11_property_estimators.py`
- `PHASE11_STATUS.md`

Streamlit entry point remains `app.py`.

If Streamlit Cloud retains an old Python module after deployment, use **Manage app → Reboot app**.


## Phase 12 deployment check

After deployment/reboot, confirm the sidebar shows `PHASE12_VDC_WATER_GATE = PASS` and the `VDC / Water` tab is visible.

The Phase 12 package adds `generic_absorber_v4/vdc_water.py` and updates `generic_absorber_v4/applicability.py`, `generic_absorber_v4/__init__.py`, and `app.py`. Upload the complete package rather than only the new module.
