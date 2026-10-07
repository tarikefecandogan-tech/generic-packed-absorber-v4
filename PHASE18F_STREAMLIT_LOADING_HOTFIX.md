# Phase 18F Streamlit Loading Hotfix

Problem: Streamlit Cloud starts the server successfully but the browser remains on Loading.

Root cause addressed: the Phase 18F UI used one st.tabs call with 27 top-level tabs. With the default tab behavior, Streamlit computes and sends all tab content on every rerun. This app contains database explorers, provenance views, validation tools, sweep/comparison interfaces and legacy development tabs, so the first render can become excessively heavy.

Hotfix:
- Main st.tabs now uses `on_change="rerun"` and `key="main_tabs"`.
- Each of the 27 top-level tab bodies is guarded with `<tab>.open`.
- Only the active top-level tab is rendered.
- No absorber physics, database contents, solver APIs, or Phase 18F import framework behavior were changed.

Verification:
- `python -m py_compile app.py`: PASS
- 27/27 top-level tab guards present
- `pytest -q`: 186/186 PASS

Deployment: replace the entire repository contents with this package, commit/push, then use Streamlit Manage app -> Reboot app.
