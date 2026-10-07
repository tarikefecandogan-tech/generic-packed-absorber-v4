# Generic Packed Absorber Simulator V4 — Phase 11

Phase 11 introduces controlled transport-property estimation correlations while preserving every prior V3 parity and generic-architecture gate.

Current resolver precedence:

`USER OVERRIDE > REGISTERED DATABASE > CORRELATION ESTIMATE > MISSING`

Built-in correlation fallbacks:

- **Fuller–Schettler–Giddings** for missing gas-phase binary diffusivity `DG`.
- **Wilke–Chang** for missing dilute liquid-phase diffusivity `DL`.

Estimates are never silent: they are returned with `ResolutionTier.CORRELATION_ESTIMATE`, `estimated=True`, and **Confidence C**. If required pure-component inputs are missing, resolution blocks rather than inventing a value.

Regression state:

- Phase 1–11 gates: PASS
- Automated tests: **104/104 PASS**
- Locked V3 full parity: **82/82 PASS**
- Phase 10 synthetic generic chemistry gate: PASS

Run locally:

```bash
pip install -r requirements.txt
streamlit run app.py
```

See `PHASE11_STATUS.md` for the implemented equations, inputs, and gate details.
