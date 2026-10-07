# Phase 14 Status — Integrated Generic Absorber Simulator

**Gate:** `PHASE14_INTEGRATED_SIMULATOR_GATE = PASS`

## Scope
Phase 14 introduces no new transport, equilibrium, ODE, or hydraulic correlation. It integrates the verified Phase 1–13 layers into one product-facing simulation workflow.

### New core module
- `generic_absorber_v4/simulation.py`
- `GenericAbsorberCase`
- `GenericAbsorberSimulationResult`
- `run_generic_absorber_case()`
- `build_phase14_registry()`
- `compatible_solutes()`

### Integrated workflow
1. Canonical case/input construction
2. Pre-applicability gate
3. Property resolution (`override > database > correlation > missing`)
4. Common Onda state
5. Per-solute mass-transfer coefficients
6. 1–4 independent counter-current ODE solves
7. Packed-column hydraulics
8. Gas reporting and capture balance
9. Post-applicability / confidence verdict

### Product-facing Streamlit UI
The new **Simulator** tab supports:
- registered carrier / solvent / packing selection
- automatic compatible-solute filtering
- 1–4 solutes
- actual or normal gas-flow input
- component-by-component gas concentrations
- total concentration + mole / VOC-mass / carbon-mass fractions
- fresh or preloaded solvent
- solvent loading as liquid mole fraction or mg/L
- applicability flags for solvent evaporation and foaming
- total and component outlet performance
- capture rate, A, HTU, NTU, equilibrium slope
- pressure drop and flooding
- confidence / validity issues
- property provenance
- gas/liquid/driving-force profiles

## Regression / validation
- Full automated suite: **122/122 PASS**
- Full V3 parity harness: **82/82 PASS**
- Phase 1–14 gate scripts: **all PASS**

### Integrated reference checks
- ACN + VAc / water reference case reproduces **106.622281 mgVOC/Nm³ outlet** and **97.867554% VOC-mass removal**.
- VDC / water integrated case reproduces Phase 12 behavior.
- VDC / acrylonitrile integrated case reproduces Phase 13 screening behavior and remains `OUTSIDE_RECOMMENDED_RANGE / SCREENING`.
- Three-solute ACN + VAc + VDC / water case runs through one integrated case.
- Incompatible chemistry is blocked before the physics core.

## Explicit Phase 14 limits
- Rating mode only; no required-height design yet.
- No solvent evaporation material balance.
- No coupled nonideal multicomponent VLE.
- No reaction / electrolyte chemistry.
- No energy balance.
- No structured-packing vendor model.
- VDC/AN thermodynamics remain screening-level until direct binary data are registered.

## Next planned phase
Phase 15 — Live Methods & Assumptions audit trail.
