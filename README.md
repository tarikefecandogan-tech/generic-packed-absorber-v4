# Generic Packed Absorber Simulator V4

## Current development stage: Phase 3 — Property Resolver

This repository is being built in controlled phases from the locked ACN + VAc / Water / Air reference scrubber model.

### Completed gates

- `PHASE1_DATA_GATE = PASS` — immutable generic data objects and locked reference dataset.
- `PHASE2_REGISTRY_GATE = PASS` — exact pair registry, lookup and missing-pair safety.
- `PHASE3_RESOLVER_GATE = PASS` — operating-point property resolution with provenance and precedence.

### Phase 3 resolution hierarchy

```text
User Override
    ↓ if absent
Registered Database / Pair
    ↓ if absent
Configured Correlation Estimate Hook
    ↓ if absent
MissingPropertyError
```

The reference build does **not** activate Fuller or Wilke–Chang automatically yet. This is intentional: reference parity is established before adding estimation correlations.

### Streamlit

Run locally with:

```bash
streamlit run app.py
```

The Streamlit app exposes the Phase 1 dataset, Phase 2 registry and the new Phase 3 property resolver. It does not yet calculate scrubber removal or hydraulics.

### Tests

```bash
PYTHONPATH=. pytest -q
```

Current packaged result: **23 passed**.

### Next planned phase

**Phase 4 — Generic Onda mass-transfer core** using only resolved numeric properties. The Phase 4 engine must not branch on chemical names.
