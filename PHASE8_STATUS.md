# Phase 8 Status — Applicability, Validity & Confidence Engine

**Gate:** `PHASE8_APPLICABILITY_GATE = PASS`

Phase 8 adds an explicit engineering validity layer around the Phase 1–7
calculation chain. It does not change Onda, two-film, ODE, units or GPDC
equations.

## Added

- pre-solver applicability gate for data completeness and model-domain physics
- post-solver validity gate for correlation, numerical and hydraulic diagnostics
- issue severities: `BLOCK`, `WARNING`, `INFO`
- readiness states:
  - `READY`
  - `READY_WITH_WARNINGS`
  - `OUTSIDE_RECOMMENDED_RANGE`
  - `INSUFFICIENT_DATA`
  - `UNSUPPORTED_PHYSICS`
  - `NUMERICAL_FAILURE`
- dilute-gas screening zones: `<0.01`, `0.01–0.05`, `>=0.05` total gas mole fraction
- explicit unsupported-physics checks for reactive, non-isothermal and coupled
  nonideal multicomponent calculations
- explicit warning when solvent evaporation or foaming is expected but not modeled
- Onda screening checks for low `Re_L`, low `Re_G` and low effective wetting
- absorption-factor warning for `A <= 1`
- ODE boundary-closure and solute mass-balance checks
- negative `y-mx` and net desorption reported as physical warnings rather than
  silently clamped
- GPDC validity, high loading, near-flooding and flooding checks
- categorical confidence: `HIGH`, `MODERATE`, `SCREENING`, `NOT_RATED`
- separate thermodynamics / mass-transfer / hydraulics confidence plus weakest-link
  overall confidence

## Locked reference verdict

For `REF_SCRUBBER_2026_10_06`:

- pre-solver status: `READY`
- post-solver status: `READY_WITH_WARNINGS`
- thermodynamics confidence: `MODERATE`
- mass-transfer confidence: `MODERATE`
- hydraulics confidence: `MODERATE`
- overall confidence: `MODERATE`
- blocking issues: none

The warnings are intentional data-quality disclosures: the locked V3 gas- and
liquid-diffusivity values did not specify their original reference temperature
(and gas pressure) in the source. Phase 8 preserves those values for parity but
no longer hides that limitation.

The reference hydraulics point remains an `INFO`-level underloaded/high-capacity
margin condition at about 7.16% of predicted flood velocity.

## Regression status

- Phase 1 gate: PASS
- Phase 2 gate: PASS
- Phase 3 gate: PASS
- Phase 4 gate: PASS
- Phase 5 gate: PASS
- Phase 6 gate: PASS
- Phase 7 gate: PASS
- Phase 8 gate: PASS
- **76 automated tests PASS**

Next planned phase: **Phase 9 — Full V3 Parity Gate**.
