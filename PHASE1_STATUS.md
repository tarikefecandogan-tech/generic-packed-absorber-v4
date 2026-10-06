# V4 Phase 1 — Status

**Gate:** PASS

## Implemented
- `SoluteSpec`
- `CarrierGasSpec`
- `SolventSpec`
- `PackingSpec`
- `GasTransportPair`
- `LiquidTransportPair`
- `EquilibriumPair`
- `DataProvenance` + A/B/C/D confidence categories
- locked `REF_SCRUBBER_2026_10_06` reference dataset

## Reference inventory
- Solutes: ACN, VAc
- Carrier: Air
- Solvent: Water
- Packing: 25mm Metal Pall Ring
- Gas transport pairs: ACN–Air, VAc–Air
- Liquid transport pairs: ACN–Water, VAc–Water
- Equilibrium pairs: ACN–Water, VAc–Water

## Verification
- `PHASE1_DATA_GATE=PASS`
- `PHASE1_V3_SOURCE_MATCH=PASS`
- `pytest`: 7 passed

## Explicitly untouched
- Onda mass-transfer equations
- two-film overall coefficient
- counter-current ODE / shooting solver
- GPDC flooding
- pressure-drop model
- required-height solver
- Streamlit production/reference tabs

## Important governance decision
The locked V3 source stores `DG` and `DL` as fixed constants without declared reference temperature/pressure. Phase 1 therefore stores their reference conditions as `None` rather than inventing metadata.

## Next gate
**Phase 2 — Pair Database / Registry Layer**: build lookup/registration mechanics around these objects, still without modifying Onda/ODE/GPDC physics.
