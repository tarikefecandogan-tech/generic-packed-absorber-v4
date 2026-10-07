# Streamlit Cloud Deployment — Phase 10

Use the existing GitHub repository. Do **not** create a new repository.

## Repository root

```text
app.py
requirements.txt
README.md
STREAMLIT_DEPLOY.md
PHASE1_STATUS.md
...
PHASE10_STATUS.md
phase1_check.py
...
phase10_check.py
generic_absorber_v4/
tests/
```

The package folder must now include:

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
    parity.py
    synthetic_validation.py
```

Upload/copy the complete Phase 10 package over the local GitHub Desktop clone so
that `app.py`, `generic_absorber_v4/__init__.py` and
`generic_absorber_v4/synthetic_validation.py` are from the same Phase 10 build.
Mixing phase versions can cause `ImportError`.

## Streamlit Cloud

- branch: `main`
- main file path: `app.py`

Dependencies remain:

```text
streamlit>=1.40,<2
pandas>=2.0,<3
numpy>=1.24,<3
scipy>=1.11,<2
```

After `Commit to main` and `Push origin`, allow Streamlit to redeploy. If an old
module remains cached, use **Manage app → Reboot app**.

## Expected screen

The sidebar should show Phase 1–10 gates as PASS. The new **Synthetic Generic
Test** tab should report:

```text
PHASE10_SYNTHETIC_GENERIC_GATE = PASS
```

The packaged regression suite contains **96 passing tests**. Phase 9 still
independently reports **82/82 locked V3 parity metrics PASS**.
