# Streamlit Cloud Deployment — Phase 9

Use the same GitHub repository; do **not** create a new repository for Phase 9.

## Required repository root

```text
app.py
requirements.txt
README.md
STREAMLIT_DEPLOY.md
PHASE1_STATUS.md
...
PHASE9_STATUS.md
phase1_check.py
...
phase9_check.py
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
    hydraulics.py
    units.py
    applicability.py
    parity.py
```

`parity.py` and the Phase 9 version of `generic_absorber_v4/__init__.py` must be
uploaded together with the Phase 9 `app.py`. Mixing an old `__init__.py` with a
new app can produce an `ImportError`.

## Streamlit Cloud entrypoint

- branch: `main`
- main file path: `app.py`

The existing `requirements.txt` remains sufficient:

```text
streamlit>=1.40,<2
pandas>=2.0,<3
numpy>=1.24,<3
scipy>=1.11,<2
```

After pushing the update, allow Streamlit to redeploy. If the running app keeps
an old module cache, use **Manage app → Reboot app** once.

## Expected Phase 9 screen

The sidebar should show all Phase 1–9 gates as PASS. The new **V3 Parity Gate**
tab should report:

```text
PHASE9_FULL_V3_PARITY_GATE = PASS
82/82 metrics passed
```

The packaged Python regression suite contains **85 passing tests**.
