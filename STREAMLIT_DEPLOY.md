# Streamlit Community Cloud — Phase 5

Upload/replace the **entire Phase 5 package contents** in the existing GitHub
repository. Do not create a new repository for each phase.

The repository root must contain at least:

```text
app.py
requirements.txt
PHASE5_STATUS.md
generic_absorber_v4/
tests/
```

The package folder must contain:

```text
generic_absorber_v4/
    __init__.py
    models.py
    reference_data.py
    registry.py
    resolver.py
    mass_transfer.py
    countercurrent.py
```

Important: Phase 5 adds direct NumPy/SciPy runtime dependencies, so make sure the updated `requirements.txt` is also committed. It must include:

```text
numpy>=1.24,<3
scipy>=1.11,<2
```

Streamlit Community Cloud settings remain:

- branch: `main`
- main file path: `app.py`

Suggested commit message:

`Phase 5 - generic counter-current ODE solver`

After Streamlit redeploys, the sidebar should show all five phase gates as PASS
and a new **Counter-Current Solver** tab should be available.
