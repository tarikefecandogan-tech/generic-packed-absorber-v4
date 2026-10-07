# Phase 18B deployment note

Upload the complete Phase 18B package, including both database files under `database/`. The Streamlit app now includes a **Data Provenance** tab backed by `database/absorber_database_v18b.db`. The existing Phase 18A migration database remains in the package for backward auditability.

Critical new files:

- `generic_absorber_v4/source_metadata.py`
- `generic_absorber_v4/database_v18b.py`
- `database/absorber_database_v18b.db`
- `database/schema_v18b.sql`
- `PHASE18B_STATUS.md`

Recommended commit message: `Phase 18B - structured engineering provenance database`

---

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

## Phase 15 update

Upload the complete Phase 15 package over the existing repository. In particular, keep these files from the same Phase 15 package:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/methods.py`
- `tests/test_phase15_live_methods.py`
- `PHASE15_STATUS.md`

After deploy, run a case under **Simulator**, then open **Methods & Assumptions**. The audit should update to that exact case. If Streamlit Cloud keeps an old module cached, use **Manage app → Reboot app**.


## Phase 16 update

Upload the complete Phase 16 package over the existing repository so the UI and package exports remain version-aligned. Important files include:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/sweep.py`
- `tests/test_phase16_parameter_sweep.py`
- `phase16_check.py`
- `PHASE16_STATUS.md`

Recommended commit message:

`Phase 16 - full physics parameter sweep`

After deployment, run a baseline under **Simulator**, open **Parameter Sweep**, and confirm the sidebar shows `PHASE16_PARAMETER_SWEEP_GATE = PASS`. If Streamlit Cloud retains an old module, use **Manage app → Reboot app**.


## Phase 17 update

Upload the **complete Phase 17 package** over the existing repository so the new comparison engine, packing catalog, UI imports and tests remain version-aligned. Important files include:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/comparison.py`
- `generic_absorber_v4/packing_catalog.py`
- `generic_absorber_v4/simulation.py`
- `tests/test_phase17_comparison_tools.py`
- `phase17_check.py`
- `PHASE17_STATUS.md`

Recommended commit message:

`Phase 17 - engineering comparison tools`

After deployment, run a baseline under **Simulator**, open **Comparison**, and confirm the sidebar shows `PHASE17_COMPARISON_GATE = PASS`. If Streamlit Community Cloud retains an old module, use **Manage app → Reboot app**.

Phase 17 completes the originally planned product roadmap through comparison tools.


## Phase 18A update

Upload the **complete Phase 18A package** over the existing repository. The SQLite file must be committed with the code; do not upload only the new Python modules.

Important aligned files:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/database.py`
- `generic_absorber_v4/database_migration.py`
- `database/absorber_database.db`
- `database/schema.sql`
- `tests/test_phase18a_database_migration.py`
- `phase18a_check.py`
- `PHASE18A_STATUS.md`

Recommended commit message:

`Phase 18A - SQLite database schema and migration parity`

After deployment, confirm the sidebar shows `PHASE18A_DATABASE_MIGRATION_GATE = PASS` and open **Database Migration**. The page should report schema version `18A.1`, SQLite integrity `OK`, zero foreign-key violations, and the migrated engineering-record counts. Use the parity button to verify exact round-trip equality.

Phase 18A deliberately leaves the production simulator on the verified Python registry. SQLite cut-over belongs to the later repository-abstraction/parity phase.


## Phase 18C update

Upload the **complete Phase 18C package** over the existing repository. Keep the SQLite database and repository abstraction files version-aligned.

Important files:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/simulation.py`
- `generic_absorber_v4/repository.py`
- `generic_absorber_v4/repository_validation.py`
- `database/absorber_database_v18b.db`
- `tests/test_phase18c_repository_abstraction.py`
- `phase18c_check.py`
- `PHASE18C_STATUS.md`

Recommended commit message:

`Phase 18C - repository abstraction and dual-backend parity`

After deployment, confirm the sidebar shows `PHASE18C_REPOSITORY_ABSTRACTION_GATE = PASS`. In **Simulator**, switch between **Verified Python Registry** and **SQLite Engineering Database v18B**. In **Repository Backends**, run the dual-backend parity suite; all five scenarios and 119 numerical metrics should pass. If Streamlit Community Cloud retains an old module, use **Manage app → Reboot app**.


## Phase 18D — primary database cut-over

The deployed repository **must include**:

```text
database/absorber_database_v18b.db
```

The Simulator now selects the Phase-18D primary repository by default. At app startup the SQLite file is validated for integrity, foreign keys, schema version, and full registry reconstruction.

If SQLite cannot be validated, the app does **not** pretend SQLite is active. With the standard UI policy it switches to an explicitly labelled `CONTROLLED_FALLBACK` Python Registry and displays the reason. Phase-18D strict-mode API calls can instead raise an error and stop.

After updating GitHub, use **Manage app → Reboot app** if Streamlit is still holding an older module graph.

## Phase 18E — Database Explorer & Coverage Matrix

Upload the **complete Phase 18E package** over the existing repository. Keep these files version-aligned:

- `app.py`
- `generic_absorber_v4/__init__.py`
- `generic_absorber_v4/database_explorer.py`
- `database/absorber_database_v18b.db`
- `tests/test_phase18e_database_explorer.py`
- `phase18e_check.py`
- `PHASE18E_STATUS.md`

Recommended commit message:

`Phase 18E - database explorer and coverage matrix`

After deployment, use **Manage app → Reboot app** if Streamlit is retaining an older module graph. Confirm the sidebar shows `PHASE18E_DATABASE_EXPLORER_GATE = PASS`, then open **Database Explorer**. The default Air / 25 °C / 1.01325 bar coverage matrix should classify ACN/Water and VAc/Water as VERIFIED, VDC/Water as ESTIMATED, VDC/Acrylonitrile as SCREENING, and ACN/VAc with Acrylonitrile as MISSING.
