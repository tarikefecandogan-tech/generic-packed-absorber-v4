# Generic Packed Absorber Simulator V4

## Current development stage: Phase 4 — Generic Onda Mass-Transfer Core

This repository is being built in controlled phases from the locked ACN + VAc / Water / Air reference scrubber model.

### Completed gates

- `PHASE1_DATA_GATE = PASS` — immutable generic data objects and locked reference dataset.
- `PHASE2_REGISTRY_GATE = PASS` — exact pair registry, lookup and missing-pair safety.
- `PHASE3_RESOLVER_GATE = PASS` — operating-point property resolution with provenance and precedence.
- `PHASE4_MASS_TRANSFER_GATE = PASS` — chemistry-independent Onda/two-film coefficient core with V3 intermediate parity.

### Phase 4 calculation chain

```text
Phase 1 data objects
    ↓
Phase 2 exact pair registry
    ↓
Phase 3 resolved operating-point properties
    ↓
Phase 4 common Onda state
    ↓
a_e, ReL, ReG, FrL, WeL
    ↓
per-solute ScL, ScG, kL, kG, KG, m, A, HTU, NTU
```

The Phase 4 physics functions receive resolved numeric values and contain no chemical-name special cases.

### Streamlit

Run locally with:

```bash
streamlit run app.py
```

The new **Mass Transfer** tab exposes the current Onda/two-film coefficient layer. It intentionally does not show outlet concentration or flooding yet.

### Tests

```bash
PYTHONPATH=. pytest -q
```

Current packaged result: **31 passed**.

### Next planned phase

**Phase 5 — Generic counter-current ODE solver**, including non-zero inlet solvent loading and component mass-balance closure.
