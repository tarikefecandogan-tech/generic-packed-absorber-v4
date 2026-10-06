# Phase 9 Status — Full V3 Parity Gate

**Gate:** `PHASE9_FULL_V3_PARITY_GATE = PASS`

Phase 9 adds no new absorber correlation and does not revise any Phase 1–8
physics. It executes the complete locked reference calculation chain and checks
its outputs against an immutable numerical fixture from:

- reference ID: `REF_SCRUBBER_2026_10_06`
- source: `scrubber_model.py / ScrubberSimulationV34 locked 2026-10-06`
- source SHA-256: `90ddffaa5517d2851d9bec7e3621653fc01959e236a2b4bccb34e276219fd967`

## Integrated chain under test

`Units/feed -> Registry -> Resolver -> Onda/two-film -> Counter-current ODE -> Outlet reporting -> Hydraulics`

The Phase 8 applicability engine is also executed as a chain-health check. It is
not called a V3 parity metric because the legacy V3 model did not contain that
explicit validity layer.

## Locked parity sections

- Units & Feed: **7/7 PASS**
- Bulk & Common Onda: **19/19 PASS**
- ACN Mass Transfer: **14/14 PASS**
- VAc Mass Transfer: **14/14 PASS**
- Counter-Current & Outlet: **12/12 PASS**
- Hydraulics: **16/16 PASS**
- **Total: 82/82 parity metrics PASS**

The gate includes exact checks for the empirical packing-factor basis, the
packing-factor estimated flag and the hydraulic regime, in addition to numeric
checks.

## Tolerance policy

Phase 9 makes the regression tolerances explicit rather than hiding them inside
individual tests:

- algebra / property reconstruction: `rtol=1e-12`, `atol=1e-14`
- mass-transfer coefficients: `rtol=1e-10`, `atol=1e-14`
- counter-current numerical outputs: `rtol=1e-8`, `atol=1e-12`
- reporting conversions: `rtol=1e-10`, `atol=1e-12`
- hydraulics: `rtol=1e-10`, `atol=1e-12`

A future intentional physics change must create a new reference fixture/ID. The
existing baseline must not move silently to make tests pass.

## Primary reference outputs confirmed

- outlet: `106.6222813666 mgVOC/Nm³`
- overall VOC-mass removal: `97.8675543727 %`
- ACN absorption factor: `50.4905133152`
- VAc absorption factor: `1.17791131369`
- ACN HTU_OG: `0.222093346064 m`
- VAc HTU_OG: `0.637988451446 m`
- wet packed-bed pressure drop: `5.68328828670 Pa/m`
- GPDC flood velocity: `2.32080296670 m/s`
- operating flood fraction: `7.16437111733 %`

## Integrated health check

The same reference run still produces:

- Phase 8 pre-status: `READY`
- Phase 8 final status: `READY_WITH_WARNINGS`
- overall confidence: `MODERATE`
- ACN and VAc relative component mass-balance errors below `1e-10`

The final warning state remains intentional because the locked legacy fixed
`DG/DL` data do not declare their original reference state.

## Regression status

- Phase 1 gate: PASS
- Phase 2 gate: PASS
- Phase 3 gate: PASS
- Phase 4 gate: PASS
- Phase 5 gate: PASS
- Phase 6 gate: PASS
- Phase 7 gate: PASS
- Phase 8 gate: PASS
- Phase 9 gate: PASS
- **85 automated tests PASS**

## Explicit scope boundary

Required-height design is **not** silently claimed by the Phase 9 parity metric
set. Phase 9 validates the calculation chain that was implemented through Phase
8. No new chemistry has been added yet.

Next planned phase: **Phase 10 — Synthetic Generic Chemistry Test**.
