# Generic Packed Absorber Simulator V4

Current implementation milestone: **Phase 8 — Applicability, Validity & Confidence Engine**.

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
   - `BLOCK`, `WARNING`, `INFO` issue model
   - explicit readiness states and categorical confidence
   - weakest-link overall confidence

## Current gates

- `PHASE1_DATA_GATE = PASS`
- `PHASE2_REGISTRY_GATE = PASS`
- `PHASE3_RESOLVER_GATE = PASS`
- `PHASE4_MASS_TRANSFER_GATE = PASS`
- `PHASE5_COUNTERCURRENT_GATE = PASS`
- `PHASE6_HYDRAULICS_GATE = PASS`
- `PHASE7_UNITS_COMPOSITION_GATE = PASS`
- `PHASE8_APPLICABILITY_GATE = PASS`
- **76 automated tests PASS**

## Locked reference

`REF_SCRUBBER_2026_10_06`

The locked V3 numerical results remain unchanged. Phase 8 adds interpretation,
not a new absorption correlation. The reference case passes the pre-solver gate
as `READY` and the final gate as `READY_WITH_WARNINGS`, with overall confidence
`MODERATE`. The warnings expose the fact that the legacy fixed DG/DL values do
not carry an explicit original reference state in the locked V3 source.

## Streamlit

Entrypoint: `app.py`

```bash
streamlit run app.py
```

The application now includes an **Applicability & Validity** tab. It can run the
whole existing reference calculation chain and shows the pre-gate, final verdict,
confidence by domain and individual engineering issues.

## Scope boundary

Phase 8 does not add reactive absorption, non-isothermal energy balances,
solvent evaporation, foaming corrections or coupled nonideal multicomponent VLE.
Those cases are now explicitly identified instead of being silently treated as
supported physics.

Required-height design is still outside the current implementation.

Next: **Phase 9 — Full V3 Parity Gate**.
