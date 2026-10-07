# Generic Packed Absorber Simulator V4 — Phase 12

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


## Phase 12 — VDC / Water

Phase 12 adds the first real chemistry outside the locked ACN/VAc reference dataset.

- VDC identity: 1,1-dichloroethylene, CAS 75-35-4, MW 96.943 g/mol.
- VDC/water equilibrium: NIST WebBook / Gossett (1987) measured Henry dataset, Confidence B.
- VDC/air DG: Fuller fallback, Confidence C.
- VDC/water DL: Wilke–Chang fallback, Confidence C.
- Applicability pre-check now recognizes estimatable missing transport pairs instead of blocking them as missing data.
- Deterministic VDC/water gate: PASS.
- Automated tests: 110/110 PASS.
- Locked V3 parity: 82/82 PASS.

The default VDC/water fixture gives A << 1 and only low VDC removal at the reference L/G and packed height. This is a screening result, not plant calibration.
