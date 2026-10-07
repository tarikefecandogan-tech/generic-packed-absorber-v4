# Generic Packed Absorber Simulator V4 — Phase 15 Status

## Gate

**PHASE15_LIVE_METHODS_GATE = PASS**

- Full automated regression suite: **127/127 PASS**
- Locked V3 parity: **82/82 metrics PASS**
- Phase 1–15 check scripts: **all PASS**
- Phase 14 integrated simulator results remain unchanged.

## Scope

Phase 15 adds a **live Methods & Assumptions / engineering audit trail** to the integrated simulator. It is a report-only layer: it reads the already-computed Phase 14 result and does **not** recalculate equilibrium, mass transfer, ODE, units, or hydraulics.

## New module

`generic_absorber_v4/methods.py`

Primary API:

`build_live_methods_report(result)`

The report contains:

1. Active-case summary.
2. Symbolic equations and the exact active method for the case.
3. Live result values next to the corresponding equations.
4. Resolved property provenance: tier, confidence, method, source, estimated flag, notes.
5. Active model assumptions and limitations.
6. Solver, mass-balance, driving-force, GPDC and confidence diagnostics.
7. Case-specific applicability issues.

## Live behavior verified

- Changing temperature changes resolved property values in the audit trail.
- VDC/acrylonitrile surfaces the Confidence D equilibrium surrogate and solvent-evaporation limitation.
- Preloaded solvent is explicitly reported instead of being described as fresh solvent.
- Negative driving force is documented as a valid local desorption condition and is not silently clamped.
- The audit uses the current simulation result rather than a second calculation path.

## Streamlit

A new **Methods & Assumptions** tab is placed next to **Simulator**. Run a case in Simulator first; the tab then shows the live audit for that exact result.

## Architecture rule

`Simulation result → audit/report`

not

`UI/report → second physics calculation`

This preserves the V4 rule that there is one authoritative calculation for each physical quantity.
