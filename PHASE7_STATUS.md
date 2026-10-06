# Phase 7 Status — Generic Units & Composition Layer

**Gate:** `PHASE7_UNITS_COMPOSITION_GATE = PASS`

Phase 7 adds the UI/reporting conversion boundary around the existing generic
physics. No Onda, ODE or hydraulics equations were changed.

## Canonical solver basis

- gas composition: component mole fraction `y_i`
- liquid loading: component mole fraction `x_i`
- operating gas flow used by the physics core: actual m³/h at operating T/P
- normal reporting reference: 273.15 K, 101325 Pa

## Added

- `ppmv ↔ y_i`
- `mgVOC/Nm³ ↔ y_i`
- `mgC/Nm³ ↔ y_i`
- total-mixture concentration + mole/VOC-mass/carbon-mass fraction input
- component-by-component concentration input
- dilute liquid `mg/L ↔ x_i`
- actual ↔ normal ideal-gas volumetric flow conversion
- multicomponent inlet/outlet reconstruction from solved component `y_i`
- molar-, VOC-mass- and carbon-basis overall removal reporting
- captured component VOC mass in kg/h when gas molar flow is supplied
- explicit concentration target object preserving value, basis and scope

## Locked reference parity

Reference feed, 5000 mgVOC/Nm³ with 93/7 VOC-mass fractions:

- ACN `y_in = 1.96428492994e-3`
- VAc `y_in = 9.11242808759e-5`
- total = 2055.40921081 ppmv
- total = 3353.13446738 mgC/Nm³

Using the locked Phase 5 component outlets:

- total outlet = 106.622281367 mgVOC/Nm³
- total outlet = 60.6459573478 mgC/Nm³
- total outlet = 29.2909820172 ppmv
- VOC-mass removal = 97.8675543727%

The overall removal is intentionally basis-dependent for a multicomponent
mixture. Outlet composition is reconstructed from solved component outlets; the
inlet mixture fractions are never reused to infer outlet composition.

## Data-governance rules

- mass, mole and carbon fractions are distinct bases
- fractions are **not silently normalized**
- a caller may explicitly request normalization
- positive mgC input for a zero-carbon solute is rejected
- unit conversion remains outside the mass-transfer, ODE and hydraulics cores

## Regression status

- Phase 1 gate: PASS
- Phase 2 gate: PASS
- Phase 3 gate: PASS
- Phase 4 gate: PASS
- Phase 5 gate: PASS
- Phase 6 gate: PASS
- Phase 7 gate: PASS
- **62 automated tests PASS**

Next planned phase: **Phase 8 — Applicability / Validity Engine**.
