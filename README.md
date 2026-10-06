# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 9 — Full V3 Parity Gate**.

The development sequence preserves the locked V3 reference behavior before
adding new chemistry or revising correlations.

## Implemented

1. **Phase 1 — Canonical data objects**
   - solutes, carrier gases, solvents, packings
   - gas/liquid transport pairs and equilibrium pairs
   - source / method / confidence provenance
2. **Phase 2 — Registry / exact pair lookup**
   - explicit missing-pair errors
   - no silent chemical substitution
3. **Phase 3 — Property resolver**
   - `USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING`
   - operating-point carrier / solvent / equilibrium property resolution
4. **Phase 4 — Generic Onda + two-film core**
   - common Onda state and wetted area
   - `kL`, `kG`, `KG`, `m`, absorption factor, HTU/NTU
5. **Phase 5 — Generic counter-current solver**
   - shooting + `solve_ivp` + Brent root solve
   - `y_out`, `x_bottom`, removal and bed profiles
   - preloaded solvent and desorption support
6. **Phase 6 — Generic hydraulics**
   - liquid holdup and screening dry/wet pressure drop
   - GPDC flood velocity / percent flood / hydraulic regime
   - empirical packing factor with visible geometric fallback
7. **Phase 7 — Generic units & composition**
   - ppmv / mgVOC/Nm³ / mgC/Nm³ ↔ canonical `y_i`
   - liquid mg/L ↔ canonical `x_i`
   - mixture fraction-basis handling and outlet reconstruction
8. **Phase 8 — Applicability / validity / confidence**
   - pre-solver data and physics-domain gate
   - post-solver Onda / ODE / driving-force / hydraulic checks
   - explicit readiness states and categorical confidence
9. **Phase 9 — Full V3 parity harness**
   - complete reference chain executed as one regression case
   - 82 locked expected-vs-actual V3 metrics
   - declared tolerance classes for algebra, coefficients, solver, reporting and hydraulics
   - frozen legacy source SHA-256 to prevent silent baseline drift

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
- **82/82 locked V3 parity metrics PASS**
- **85 automated tests PASS**

## Locked reference

`REF_SCRUBBER_2026_10_06`

Reference source SHA-256:

`90ddffaa5517d2851d9bec7e3621653fc01959e236a2b4bccb34e276219fd967`

The Phase 9 parity harness covers feed/unit reconstruction, bulk fluid state,
common Onda quantities, ACN and VAc mass-transfer coefficients, counter-current
outlet results and generic hydraulics.

Primary locked outlet remains `106.6222813666 mgVOC/Nm³`, with
`97.8675543727 %` overall VOC-mass removal.

## Streamlit

Entrypoint: `app.py`

```bash
streamlit run app.py
```

The application now includes a **V3 Parity Gate** tab. Pressing the gate button
runs the complete reference chain and displays section-level PASS/FAIL plus every
expected/actual/error/tolerance row.

## Scope boundary

Phase 9 is verification, not a physics revision. It does not add reactive
absorption, non-isothermal energy balances, coupled nonideal VLE, default
Fuller/Wilke–Chang estimation, solvent evaporation or new chemistry.

Required-height design is still outside the current implemented parity scope.

Next: **Phase 10 — Synthetic Generic Chemistry Test**.
