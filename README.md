# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 6 — Generic Packed-Column Hydraulics**.

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
   - liquid holdup
   - dry/wet screening pressure drop
   - GPDC flood velocity and percent flood
   - hydraulic-regime classification
   - empirical packing factor with visible geometric fallback
   - Kister–Gill pressure-drop-at-flood diagnostic

## Current gates

- `PHASE1_DATA_GATE = PASS`
- `PHASE2_REGISTRY_GATE = PASS`
- `PHASE3_RESOLVER_GATE = PASS`
- `PHASE4_MASS_TRANSFER_GATE = PASS`
- `PHASE5_COUNTERCURRENT_GATE = PASS`
- `PHASE6_HYDRAULICS_GATE = PASS`
- **48 automated tests PASS**

## Locked reference

`REF_SCRUBBER_2026_10_06`

Phase 6 reproduces the locked V3 hydraulic reference values for the 25 mm Metal
Pall Ring case, including wet pressure drop, GPDC flood velocity, F_LV, CP and
percent flood.

## Streamlit

Entrypoint: `app.py`

```bash
streamlit run app.py
```

The application now includes a **Hydraulics** tab in addition to the data,
property resolver, mass-transfer and counter-current solver tabs.

## Scope boundary

The packed-bed pressure-drop expression remains a **screening-level model**.
GPDC is used for capacity/flooding. Kister–Gill pressure drop at flood is shown
only as a diagnostic. Foaming, entrainment, distributor/support pressure losses,
demisters, fouling and maldistribution are not modeled.

Concentration-basis reconstruction and required-height design remain outside
Phase 6.

Next: **Phase 7 — Generic Units & Composition Layer**.
