# Streamlit Community Cloud deployment — Phase 3

Use the same GitHub repository and the same Streamlit app created for Phase 1/2.

1. Extract the Phase 3 ZIP locally.
2. Upload the updated files/folders to the **root of the existing GitHub repository**.
3. Confirm the repository root contains `app.py`, `requirements.txt`, and the folder `generic_absorber_v4/`.
4. Inside `generic_absorber_v4/`, confirm `resolver.py` is present together with `__init__.py`, `models.py`, `reference_data.py`, and `registry.py`.
5. Commit with a message such as `Phase 3 - property resolver`.
6. Streamlit Community Cloud should redeploy automatically from the existing app.
7. After redeploy, the sidebar should show:
   - `PHASE1_DATA_GATE = PASS`
   - `PHASE2_REGISTRY_GATE = PASS`
   - `PHASE3_RESOLVER_GATE = PASS`

Do not create a new Streamlit application unless the existing deployment has been deleted.
