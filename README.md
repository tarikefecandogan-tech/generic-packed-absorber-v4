# Generic Packed Absorber Simulator V4 — Phase 14

Phase 14 is the first integrated product-facing release of the V4 development track. It connects the verified data, resolver, Onda/two-film, counter-current ODE, units, hydraulics and applicability layers through a single generic simulation workflow.

**Current gates:** Phase 1–14 PASS · **122/122 tests PASS** · **82/82 locked V3 parity metrics PASS**.

The main Streamlit tab is now **Simulator**. Development and validation tabs remain available for auditability.

---

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


## Phase 13 — VDC / Acrylonitrile

Phase 13 adds liquid acrylonitrile as a real solvent and runs a VDC/AN screening case through the complete generic chain.

Data governance is intentionally conservative:

- Acrylonitrile bulk liquid properties: near-ambient literature/database values, Confidence B.
- VDC/air gas diffusivity: Fuller fallback, Confidence C.
- VDC in acrylonitrile liquid diffusivity: Wilke–Chang fallback, Confidence C; phi=1.0 is a screening assumption.
- VDC/AN equilibrium: **Confidence D** ideal-dilute Raoult surrogate at 22 °C and 1 atm, `m = Psat,VDC/P`, gamma_inf=1.
- Acrylonitrile evaporation is materially important near ambient conditions but is not modelled in V4.0, therefore Phase 13 is explicitly outside the recommended design domain.

The deterministic Phase 13 fixture uses the same column/flow basis as Phase 12 so the solvent effect is easy to compare. The screening calculation predicts much stronger VDC uptake into AN than water, but this is not design validation until direct VDC/AN equilibrium data and solvent evaporation are represented.

The project pilot trial (300 L/h N2, 18 L/h AN, final liquid 93.84% AN / 6.16% VDC, outlet 1100 ppm VOC) is preserved as external qualitative evidence only. It is not used to fit the equilibrium slope because the available slide summary does not document inlet VDC and a complete material-balance basis.
