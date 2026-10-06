# Streamlit Community Cloud — Phase 8

Update the **existing GitHub repository** with the entire Phase 8 package.
Do not create a new repository.

Repository root should contain at least:

```text
app.py
requirements.txt
PHASE8_STATUS.md
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
    applicability.py
```

No new third-party dependency is required in Phase 8. Keep the existing
Streamlit / Pandas / NumPy / SciPy requirements.

Streamlit Community Cloud settings remain:

- branch: `main`
- main file path: `app.py`

Suggested commit message:

`Phase 8 - applicability validity and confidence engine`

After redeploy, the sidebar should show eight PASS gates and the new
**Applicability & Validity** tab should be visible.
