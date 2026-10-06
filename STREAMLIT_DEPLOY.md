# Streamlit Community Cloud Deployment

1. Upload the contents of this folder to the root of your GitHub repository.
2. Confirm that `app.py` and `requirements.txt` are visible in the repository root.
3. Open Streamlit Community Cloud: https://share.streamlit.io/
4. Choose **Create app** / **New app**.
5. Select your GitHub repository and the `main` branch.
6. Set **Main file path** to:

   `app.py`

7. Deploy.

The app should open with the title **Generic Packed Absorber Simulator V4** and show:

`PHASE1_DATA_GATE = PASS`

## Important
Phase 1 is data-only. It does not yet calculate scrubber outlet concentration, Onda coefficients, flooding, pressure drop, or required height.
