# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 7 — Generic Units & Composition Layer**.

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
   - Kister–Gill pressure-drop-at-flood diagnostic
7. **Phase 7 — Generic units & composition**
   - canonical solver variables remain `y_i` and `x_i`
   - ppmv / mgVOC/Nm³ / mgC/Nm³ conversion
   - mole-, VOC-mass- and carbon-mass fraction handling
   - component-by-component or total-mixture input
   - dilute liquid mg/L ↔ x conversion
   - actual ↔ normal gas-flow conversion
   - multicomponent outlet reconstruction and basis-dependent removal reporting

## Current gates

- `PHASE1_DATA_GATE = PASS`
- `PHASE2_REGISTRY_GATE = PASS`
- `PHASE3_RESOLVER_GATE = PASS`
- `PHASE4_MASS_TRANSFER_GATE = PASS`
- `PHASE5_COUNTERCURRENT_GATE = PASS`
- `PHASE6_HYDRAULICS_GATE = PASS`
- `PHASE7_UNITS_COMPOSITION_GATE = PASS`
- **62 automated tests PASS**

## Locked reference

`REF_SCRUBBER_2026_10_06`

Phase 7 reproduces the locked reference feed and outlet in all three reporting
bases. The locked 5000 mgVOC/Nm³ feed is 2055.40921081 ppmv and
3353.13446738 mgC/Nm³. The locked solved outlet is 106.622281367 mgVOC/Nm³,
29.2909820172 ppmv and 60.6459573478 mgC/Nm³.

## Streamlit

Entrypoint: `app.py`

```bash
streamlit run app.py
```

The application now includes a **Units & Composition** tab in addition to the
resolver, mass-transfer, counter-current and hydraulics views.

## Scope boundary

Phase 7 is a conversion/reporting layer. It does **not** alter Onda, two-film,
ODE or GPDC equations. Normal reporting uses 273.15 K and 101325 Pa. Fractions
are not silently normalized and outlet mixture composition is never inferred
from inlet fractions.

Required-height design and full applicability/validity classification remain
outside this phase.

Next: **Phase 8 — Applicability / Validity Engine**.
