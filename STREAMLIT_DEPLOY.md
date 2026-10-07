# Phase 14 deployment note

Deploy `app.py` from the repository root. Upload the **entire Phase 14 package**, not only `simulation.py`, so `app.py`, `generic_absorber_v4/__init__.py`, `generic_absorber_v4/simulation.py`, and `tests/` stay version-aligned.

After pushing to GitHub, Streamlit Community Cloud should redeploy automatically. If an old module is cached, use **Manage app → Reboot app**.

Expected sidebar gate: `PHASE14_INTEGRATED_SIMULATOR_GATE = PASS`.

---

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


## Phase 13 deployment check

After push/redeploy, confirm the sidebar shows `PHASE13_VDC_ACN_GATE = PASS` and a `VDC / Acrylonitrile` tab is visible.

Upload the complete Phase 13 package rather than only `vdc_acn.py`; `app.py` and `generic_absorber_v4/__init__.py` must be from the same Phase 13 package to avoid mixed-version import errors. If Streamlit Cloud keeps an older module in memory, use **Manage app → Reboot app**.
