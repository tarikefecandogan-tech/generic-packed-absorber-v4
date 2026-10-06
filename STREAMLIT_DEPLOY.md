# Streamlit Community Cloud — Phase 4

Use the existing GitHub repository; do not create a new repository/app.

Upload/replace the Phase 4 package contents while preserving this repository structure:

```text
app.py
requirements.txt
README.md
PHASE1_STATUS.md
PHASE2_STATUS.md
PHASE3_STATUS.md
PHASE4_STATUS.md
phase1_check.py
phase2_check.py
phase3_check.py
phase4_check.py
generic_absorber_v4/
    __init__.py
    models.py
    reference_data.py
    registry.py
    resolver.py
    mass_transfer.py
tests/
    test_phase1_reference_data.py
    test_phase2_registry.py
    test_phase3_property_resolver.py
    test_phase4_mass_transfer.py
```

Streamlit entry point remains:

```text
app.py
```

After GitHub commit, the existing Streamlit Community Cloud app should redeploy automatically.

Expected sidebar gates:

```text
PHASE1_DATA_GATE = PASS
PHASE2_REGISTRY_GATE = PASS
PHASE3_RESOLVER_GATE = PASS
PHASE4_MASS_TRANSFER_GATE = PASS
```
