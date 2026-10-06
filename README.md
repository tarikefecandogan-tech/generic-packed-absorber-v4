# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 5 — Generic Counter-Current ODE Solver**.

The development sequence preserves the locked V3 reference behavior before
adding new chemistry or revising correlations.

## Implemented

1. **Phase 1 — Canonical data objects**
   - solutes, carrier gases, solvents, packings
   - gas/liquid transport pairs
   - equilibrium pairs
   - source / method / confidence provenance
2. **Phase 2 — Registry / exact pair lookup**
   - explicit missing-pair errors
   - no silent chemical substitution
3. **Phase 3 — Property resolver**
   - `USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING`
   - operating-point Air / Water / Henry property resolution
4. **Phase 4 — Generic Onda + two-film core**
   - common Onda state and wetted area
   - `kL`, `kG`, `KG`, `m`, absorption factor, HTU/NTU
   - locked ACN/VAc coefficient parity
5. **Phase 5 — Generic counter-current solver**
   - shooting method + `solve_ivp` + Brent root solve
   - `y_out`, `x_bottom`, component removal
   - nonzero liquid inlet loading
   - absorption and desorption without driving-force clamp
   - profiles and mass-balance / boundary diagnostics
   - 1–4 independent dilute solutes

## Current gates

- `PHASE1_DATA_GATE = PASS`
- `PHASE2_REGISTRY_GATE = PASS`
- `PHASE3_RESOLVER_GATE = PASS`
- `PHASE4_MASS_TRANSFER_GATE = PASS`
- `PHASE5_COUNTERCURRENT_GATE = PASS`
- **40 automated tests PASS**

## Locked reference

`REF_SCRUBBER_2026_10_06`

The V4 Phase 5 ACN and VAc outlet mole fractions, liquid-bottom loadings and
component removals reproduce the locked V3 reference case.

## Streamlit

Entrypoint: `app.py`

Install dependencies from `requirements.txt`, then run:

```bash
streamlit run app.py
```

The app now contains a **Counter-Current Solver** tab in addition to the data,
resolver and mass-transfer inspection tabs.

## Scope boundary

Phase 5 still does **not** implement concentration-basis reconstruction,
required-height design, pressure drop or flooding. Those are intentionally kept
out of the solver until their planned phases.

Next: **Phase 6 — Generic Hydraulics**.
