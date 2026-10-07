# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 10 — Synthetic Generic Chemistry Verification**.

The project first preserved the locked V3 behavior, then proved that the same
architecture can solve chemistry that does not exist in the V3 database.

## Implemented

1. **Phase 1 — Canonical data objects**
2. **Phase 2 — Registry / exact pair lookup**
3. **Phase 3 — Property resolver**
   - `USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING`
4. **Phase 4 — Generic Onda + two-film core**
5. **Phase 5 — Generic counter-current BVP solver**
6. **Phase 6 — Generic packed-column hydraulics**
7. **Phase 7 — Generic units & composition layer**
8. **Phase 8 — Applicability / validity / confidence engine**
9. **Phase 9 — Full V3 parity harness**
   - 82/82 locked V3 metrics PASS
   - locked source SHA-256 prevents silent baseline drift
10. **Phase 10 — Synthetic generic chemistry gate**
   - fictional carrier, solvent, packing and two solutes
   - Henry and direct-linear equilibrium pathways
   - nonzero solvent inlet loading
   - multicomponent ODE + reporting + hydraulics
   - legacy chemical-name audit of generic physics modules

## Current gates

- `PHASE1_DATA_GATE = PASS`
- `PHASE2_REGISTRY_GATE = PASS`
- `PHASE3_RESOLVER_GATE = PASS`
- `PHASE4_MASS_TRANSFER_GATE = PASS`
- `PHASE5_COUNTERCURRENT_GATE = PASS`
- `PHASE6_HYDRAULICS_GATE = PASS`
- `PHASE7_UNITS_COMPOSITION_GATE = PASS`
- `PHASE8_APPLICABILITY_GATE = PASS`
- `PHASE9_FULL_V3_PARITY_GATE = PASS`
- `PHASE10_SYNTHETIC_GENERIC_GATE = PASS`
- **96 automated tests PASS**
- **82/82 locked V3 parity metrics PASS**

## Reference preservation

Locked reference ID: `REF_SCRUBBER_2026_10_06`

Reference-source SHA-256:

`90ddffaa5517d2851d9bec7e3621653fc01959e236a2b4bccb34e276219fd967`

The original reference outlet remains `106.6222813666 mgVOC/Nm³` with
`97.8675543727 %` VOC-mass removal.

## Phase 10 synthetic verification

Phase 10 uses only:

```text
SYN_H + SYN_M / carrier_x / solvent_q / packing_z
```

The case produces a valid two-component counter-current solution, unit/reporting
reconstruction and hydraulic result without loading ACN/VAc/Air/Water data.
The synthetic values are deliberately fictional and must not be interpreted as
real property data.

## Streamlit

Entrypoint:

```bash
streamlit run app.py
```

The UI includes both **V3 Parity Gate** and **Synthetic Generic Test** tabs.

## Scope boundary

V4.0 is still a steady-state, isothermal, dilute, non-reactive physical
absorption model for random packing and independent solutes. Required-height
design and default property-estimation correlations remain outside the current
implemented milestone.

Next: **Phase 11 — Property-estimation correlations**.
