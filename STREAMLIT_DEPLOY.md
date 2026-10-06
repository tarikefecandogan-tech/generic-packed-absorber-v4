# Streamlit Community Cloud — Phase 7

Update the **existing GitHub repository** with the entire Phase 7 package.
Do not create a new repository.

Repository root should contain at least:

```text
app.py
requirements.txt
PHASE7_STATUS.md
generic_absorber_v4/
tests/
```

Package folder:

```text
generic_absorber_v4/
    __init__.py
    models.py
    reference_data.py
    registry.py
    resolver.py
    mass_transfer.py
    countercurrent.py
    hydraulics.py
    units.py
```

No new third-party dependency is required in Phase 7; keep the existing
Streamlit/Pandas/NumPy/SciPy requirements.

Streamlit Community Cloud settings remain:

- branch: `main`
- main file path: `app.py`

Suggested commit message:

`Phase 7 - generic units and composition layer`

After redeploy, the sidebar should show seven PASS gates and the new
**Units & Composition** tab should be visible.
