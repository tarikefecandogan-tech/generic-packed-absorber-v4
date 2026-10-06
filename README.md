# Generic Packed Absorber Simulator V4 — Phase 1 Data Layer

This package implements **Phase 1 only** of the agreed V4 migration plan.

## Included
- `SoluteSpec`
- `CarrierGasSpec`
- `SolventSpec`
- `PackingSpec`
- `GasTransportPair`
- `LiquidTransportPair`
- `EquilibriumPair`
- provenance / confidence metadata
- locked reference data for ACN + VAc / Water / Air + 25 mm Metal Pall Ring
- data-integrity tests

## Intentionally not included in this phase
- Onda calculations
- two-film `KG`
- counter-current ODE
- GPDC flooding
- pressure drop
- unit/concentration conversion
- property resolver / fallback correlations
- VDC or other new chemistry
- Streamlit integration

## Locked reference
`REF_SCRUBBER_2026_10_06`

The values in `reference_data.py` are copied from the existing project reference engine so later V4 phases can prove numerical parity before adding new chemistry.

## Run the gate

```bash
python phase1_check.py
pytest -q
```

Expected:

```text
PHASE1_DATA_GATE=PASS
7 passed
```

## Reference-condition policy
The legacy V3 `DG` and `DL` constants do not declare reference T/P in the source. Phase 1 therefore stores those conditions as `None` rather than inventing metadata. Later transport-correlation work may introduce verified reference conditions.

## Streamlit preview added

This package now includes a lightweight Phase 1 Streamlit frontend:

```bash
pip install -r requirements.txt
streamlit run app.py
```

The frontend is intentionally data-only and displays the locked reference dataset, binary pair architecture, packing definition, and provenance/confidence metadata.

For Streamlit Community Cloud instructions, see `STREAMLIT_DEPLOY.md`.
