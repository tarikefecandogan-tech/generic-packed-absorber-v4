# Streamlit Community Cloud — Phase 6

Update the **existing GitHub repository** with the entire Phase 6 package.
Do not create a new repository.

Repository root should contain at least:

```text
app.py
requirements.txt
PHASE6_STATUS.md
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
```

Keep the existing `requirements.txt`; Phase 6 uses the NumPy/SciPy dependencies
already introduced in Phase 5.

Streamlit Community Cloud settings remain:

- branch: `main`
- main file path: `app.py`

Suggested commit message:

`Phase 6 - generic packed-column hydraulics`

After redeploy, the sidebar should show six PASS gates and the new
**Hydraulics** tab should be visible.
