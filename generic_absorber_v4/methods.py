"""Phase 15 — live Methods & Assumptions / engineering audit trail.

The Phase 15 layer is deliberately *report-only*.  It consumes a completed
``GenericAbsorberSimulationResult`` and exposes the exact methods, equations,
resolved property provenance, assumptions, diagnostics and model limitations
that were active for that case.

No mass-transfer, equilibrium, ODE, unit, or hydraulic quantity is recalculated
here.  Live numerical values are read from the verified Phase 14 result object.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Tuple

from .simulation import GenericAbsorberSimulationResult

PHASE15_LIVE_METHODS_ID = "PHASE15_LIVE_METHODS_ASSUMPTIONS_2026_10_07"


@dataclass(frozen=True)
class MethodEquation:
    section: str
    title: str
    equation: str
    active_method: str
    live_value: str = ""
    note: str = ""


@dataclass(frozen=True)
class PropertyAuditRow:
    scope: str
    property_name: str
    value: float
    unit: str
    tier: str
    confidence: str
    method: str
    source: str
    estimated: bool
    note: str = ""


@dataclass(frozen=True)
class AssumptionAuditRow:
    category: str
    assumption: str
    state: str
    consequence: str


@dataclass(frozen=True)
class DiagnosticAuditRow:
    scope: str
    diagnostic: str
    value: str
    interpretation: str


@dataclass(frozen=True)
class LiveMethodsReport:
    report_id: str
    case_id: str
    summary: Tuple[str, ...]
    equations: Tuple[MethodEquation, ...]
    properties: Tuple[PropertyAuditRow, ...]
    assumptions: Tuple[AssumptionAuditRow, ...]
    diagnostics: Tuple[DiagnosticAuditRow, ...]

    @property
    def sections(self) -> Tuple[str, ...]:
        seen = []
        for item in self.equations:
            if item.section not in seen:
                seen.append(item.section)
        return tuple(seen)


def _fmt(value: float, digits: int = 6) -> str:
    if value == 0:
        return "0"
    av = abs(value)
    if av >= 1e4 or av < 1e-3:
        return f"{value:.{digits}e}"
    return f"{value:.{digits}g}"


def _prop(scope: str, name: str, p) -> PropertyAuditRow:
    return PropertyAuditRow(
        scope=scope,
        property_name=name,
        value=float(p.value),
        unit=p.unit,
        tier=p.tier.value,
        confidence=p.confidence.value,
        method=p.method,
        source=p.source,
        estimated=bool(p.estimated),
        note=p.note or "",
    )


def build_live_methods_report(result: GenericAbsorberSimulationResult) -> LiveMethodsReport:
    """Build the live audit trail for one already-computed integrated result."""
    case = result.case
    common = result.common
    packing = result.registry.get_packing(case.packing_id)
    first = result.resolved_components[case.solute_ids[0]]
    hydraulic = result.hydraulics

    summary = (
        f"Carrier: {result.registry.get_carrier(case.carrier_id).name} ({case.carrier_id})",
        f"Solvent: {result.registry.get_solvent(case.solvent_id).name} ({case.solvent_id})",
        "Solutes: " + ", ".join(case.solute_ids),
        f"Packing: {packing.name} ({case.packing_id})",
        f"T = {_fmt(case.operating.temperature_K)} K; P = {_fmt(case.operating.pressure_Pa)} Pa",
        f"Final validity = {result.post_applicability.status.value}; overall confidence = {result.post_applicability.confidence.overall.value}",
    )

    eqs: list[MethodEquation] = []
    eqs.extend([
        MethodEquation(
            "1. Canonical case & bulk flow",
            "Column cross-sectional area",
            "A_c = π D² / 4",
            "cylindrical packed-column geometry",
            f"A_c = {_fmt(common.area_m2)} m²",
        ),
        MethodEquation(
            "1. Canonical case & bulk flow",
            "Actual gas molar flow",
            "ṅ_G = Q_G,actual P / (R T)",
            "ideal-gas conversion at operating T/P",
            f"ṅ_G = {_fmt(common.gas_molar_flow_mol_s)} mol/s",
            "The physics core receives actual gas volumetric flow; normal/actual conversion belongs to the UI/unit boundary.",
        ),
        MethodEquation(
            "1. Canonical case & bulk flow",
            "Liquid molar flow",
            "ṅ_L = ṁ_L / MW_L",
            "single dominant solvent; dilute solute loading",
            f"ṅ_L = {_fmt(common.liquid_molar_flow_mol_s)} mol/s",
        ),
        MethodEquation(
            "1. Canonical case & bulk flow",
            "Superficial gas velocity",
            "U_G = Q_G,actual / A_c",
            "superficial packed-column velocity",
            f"U_G = {_fmt(common.gas_superficial_velocity_m_s)} m/s",
        ),
    ])

    eqs.extend([
        MethodEquation(
            "2. Onda wetting / effective area",
            "Liquid Reynolds number",
            "Re_L = L' / (a_t μ_L)",
            "locked V3 Onda-compatible definition",
            f"Re_L = {_fmt(common.Re_L)}",
        ),
        MethodEquation(
            "2. Onda wetting / effective area",
            "Gas Reynolds number",
            "Re_G = G' / (a_t μ_G)",
            "locked V3 Onda-compatible definition",
            f"Re_G = {_fmt(common.Re_G)}",
        ),
        MethodEquation(
            "2. Onda wetting / effective area",
            "Liquid Froude number",
            "Fr_L = L'² a_t / (ρ_L² g)",
            "Onda wetting term",
            f"Fr_L = {_fmt(common.Fr_L)}",
        ),
        MethodEquation(
            "2. Onda wetting / effective area",
            "Liquid Weber number",
            "We_L = L'² / (ρ_L σ_L a_t)",
            "Onda wetting term",
            f"We_L = {_fmt(common.We_L)}",
        ),
        MethodEquation(
            "2. Onda wetting / effective area",
            "Effective wetted area",
            "a_e/a_t = 1 − exp[−1.45(σ_c/σ_L)^0.75 Re_L^0.10 Fr_L^−0.05 We_L^0.20]",
            "Onda-type random-packing wetting correlation; V3 numerical guards retained",
            f"a_e = {_fmt(common.effective_area_m2_m3)} m²/m³; wetting = {_fmt(100*common.wetting_fraction)} %",
        ),
    ])

    for sid in case.solute_ids:
        rp = result.resolved_components[sid]
        mt = result.transfer_results[sid]
        solved = result.solver_results.components[sid]
        eqprop = rp.equilibrium.active_property

        if rp.equilibrium.model == "henry_pc":
            eq_title = "Henry equilibrium"
            eq_equation = "p* = H_pc C_L;  m = H_pc (ρ_L/MW_L) / P;  y* = m x"
            eq_method = eqprop.method
            eq_live = f"H_pc = {_fmt(eqprop.value)} {eqprop.unit}; m = {_fmt(mt.equilibrium_slope_m)}"
        else:
            eq_title = "Linear equilibrium"
            eq_equation = "y* = m x"
            eq_method = eqprop.method
            eq_live = f"m = {_fmt(mt.equilibrium_slope_m)}"

        eqs.extend([
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                eq_title,
                eq_equation,
                eq_method,
                eq_live,
                f"Source: {eqprop.source}; confidence {eqprop.confidence.value}; tier {eqprop.tier.value}.",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Liquid Schmidt number",
                "Sc_L = μ_L / (ρ_L D_L)",
                "Onda liquid-film correlation input",
                f"Sc_L = {_fmt(mt.Sc_L)}",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Liquid-film coefficient",
                "k_L = 0.0051(μ_L g/ρ_L)^(1/3)[L'/(a_e μ_L)]^(2/3) Sc_L^−1/2 (a_t d_p)^0.4",
                "Onda liquid-side coefficient; locked V3 basis",
                f"k_L = {_fmt(mt.k_L)}",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Gas Schmidt number",
                "Sc_G = μ_G / (ρ_G D_G)",
                "Onda gas-film correlation input",
                f"Sc_G = {_fmt(mt.Sc_G)}",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Gas-film coefficient",
                "k_G = 5.23[a_t D_G/(R T)] Re_G^0.7 Sc_G^(1/3) (a_t d_p)^−2",
                "Onda gas-side coefficient; locked V3 basis",
                f"k_G = {_fmt(mt.k_G)}",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Overall gas-side coefficient",
                "1/K_G = 1/k_G + H_eff/k_L",
                "two-film resistance addition; V3 coefficient basis preserved",
                f"K_G = {_fmt(mt.K_G)}; gas resistance = {_fmt(100*mt.gas_resistance_fraction)} %; liquid resistance = {_fmt(100*mt.liquid_resistance_fraction)} %",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Absorption factor",
                "A = ṅ_L / (m ṅ_G)",
                "diagnostic only; not used as a shortcut for the ODE result",
                f"A = {_fmt(mt.absorption_factor)}",
            ),
            MethodEquation(
                f"3. {sid} equilibrium & two-film transfer",
                "Overall gas HTU / NTU",
                "HTU_OG = G'_mol / (K_G a_e P);  NTU_OG = Z / HTU_OG",
                "rate-based packed-bed diagnostic",
                f"HTU_OG = {_fmt(mt.HTU_OG_m)} m; NTU_OG = {_fmt(mt.NTU_OG)}",
            ),
            MethodEquation(
                f"4. {sid} counter-current boundary-value solve",
                "Local driving force and transfer rate",
                "Δy = y − m x;  r = K_G a_e P (y − m x)",
                "negative driving force is retained; desorption is allowed",
                f"min Δy = {_fmt(solved.diagnostics.min_driving_force_y)}; max Δy = {_fmt(solved.diagnostics.max_driving_force_y)}",
            ),
            MethodEquation(
                f"4. {sid} counter-current boundary-value solve",
                "Counter-current ODEs",
                "dy/dz = −r/G'_mol;  dx/dz = −r/L'_mol",
                "solve_ivp integration with shooting on unknown x_bottom",
                f"mode = {solved.diagnostics.mode}; y_out = {_fmt(solved.gas_outlet_y)}; x_bottom = {_fmt(solved.liquid_bottom_x)}",
            ),
            MethodEquation(
                f"4. {sid} counter-current boundary-value solve",
                "Boundary conditions",
                "y(0)=y_in;  x(Z)=x_in",
                "Brent root solve closes the liquid-top boundary",
                f"y_in = {_fmt(solved.gas_inlet_y)}; x_in = {_fmt(solved.liquid_inlet_x)}; boundary error = {_fmt(solved.diagnostics.boundary_error_x)}",
            ),
        ])

    pf = hydraulic.flooding
    pd = hydraulic.pressure_drop
    eqs.extend([
        MethodEquation(
            "5. Hydraulics",
            "Liquid holdup",
            "h_L = [12 μ_L (L'/ρ_L) a_t² / (g ρ_L)]^(1/3), bounded to ≤0.90 ε",
            "V3 packed-bed screening holdup expression",
            f"h_L = {_fmt(pd.liquid_holdup_fraction)}",
        ),
        MethodEquation(
            "5. Hydraulics",
            "Dry pressure drop",
            "ΔP_dry/Z = ψ (a_t/ε³) ρ_G U_G²/2",
            "screening packed-bed pressure-drop expression",
            f"ΔP_dry/Z = {_fmt(pd.dry_pressure_drop_Pa_m)} Pa/m",
        ),
        MethodEquation(
            "5. Hydraulics",
            "Wet pressure drop",
            "ΔP_wet/Z = (ΔP_dry/Z)[ε/(ε−h_L)]³",
            "screening packed-bed pressure-drop expression",
            f"ΔP_wet/Z = {_fmt(pd.wet_pressure_drop_Pa_m)} Pa/m; total = {_fmt(pd.total_pressure_drop_mbar)} mbar",
        ),
        MethodEquation(
            "5. Hydraulics",
            "Packing factor",
            "F_p = registered empirical/literature value; fallback = (a_t/ε³) converted to ft⁻¹",
            f"active basis: {pf.packing_factor_basis}",
            f"F_p = {_fmt(pf.packing_factor_ft_inv)} ft⁻¹; estimated = {pf.packing_factor_estimated}",
        ),
        MethodEquation(
            "5. Hydraulics",
            "GPDC flood curve",
            "C_P = 0.0394 log10(F_LV)^3 + 0.0552 log10(F_LV)^2 − 0.7634 log10(F_LV) + 0.7863",
            "V3 GPDC cubic fit; root solved only inside 0.01 ≤ F_LV ≤ 8",
            f"F_LV = {_fmt(pf.F_LV_flood)}; C_P = {_fmt(pf.CP_flood)}; GPDC valid = {pf.gpdc_valid}",
        ),
        MethodEquation(
            "5. Hydraulics",
            "Flooding fraction",
            "%Flood = 100 U_G / U_flood",
            "GPDC capacity diagnostic",
            f"U_flood = {_fmt(pf.flood_velocity_m_s)} m/s; %Flood = {_fmt(pf.flooding_percent)} %; {pf.hydraulic_regime}",
        ),
        MethodEquation(
            "5. Hydraulics",
            "Kister–Gill flooding pressure-drop diagnostic",
            "(ΔP/Z)_flood = 0.115 F_p^0.7 inH₂O/ft",
            "diagnostic only; it does not define %Flood",
            f"(ΔP/Z)_flood = {_fmt(pf.flood_pressure_drop_mbar_m)} mbar/m; operating/flood ΔP ratio = {_fmt(hydraulic.pressure_drop_ratio_to_flood)}",
        ),
    ])

    eqs.extend([
        MethodEquation(
            "6. Reporting & validation",
            "Gas reporting basis",
            "canonical y_i → ppmv / mgVOC/Nm³ / mgC/Nm³",
            "component-wise outlet reconstruction; inlet composition fractions are never reused for outlet",
            f"Outlet = {_fmt(result.outlet_report.total_ppmv)} ppmv = {_fmt(result.outlet_report.total_mgVOC_Nm3)} mgVOC/Nm³ = {_fmt(result.outlet_report.total_mgC_Nm3)} mgC/Nm³",
        ),
        MethodEquation(
            "6. Reporting & validation",
            "Final model verdict",
            "pre-applicability gate → solver → post-applicability gate",
            "BLOCK / WARNING / INFO issues combined with thermodynamics, mass-transfer and hydraulics confidence",
            f"status = {result.post_applicability.status.value}; overall confidence = {result.post_applicability.confidence.overall.value}",
        ),
    ])

    props: list[PropertyAuditRow] = []
    props.extend([
        _prop(case.carrier_id, "carrier MW", first.carrier.MW),
        _prop(case.carrier_id, "carrier density", first.carrier.density),
        _prop(case.carrier_id, "carrier viscosity", first.carrier.viscosity),
        _prop(case.solvent_id, "solvent MW", first.solvent.MW),
        _prop(case.solvent_id, "solvent density", first.solvent.density),
        _prop(case.solvent_id, "solvent viscosity", first.solvent.viscosity),
        _prop(case.solvent_id, "solvent surface tension", first.solvent.surface_tension),
    ])
    for sid in case.solute_ids:
        rp = result.resolved_components[sid]
        props.extend([
            _prop(sid, "gas diffusivity D_G", rp.gas_diffusivity),
            _prop(sid, "liquid diffusivity D_L", rp.liquid_diffusivity),
            _prop(sid, f"equilibrium ({rp.equilibrium.model})", rp.equilibrium.active_property),
        ])

    packing_prov = packing.provenance
    if packing_prov is not None:
        props.append(PropertyAuditRow(
            scope=case.packing_id,
            property_name="packing metadata",
            value=float(packing.area_m2_m3),
            unit="m²/m³ (a_t shown)",
            tier="DATABASE",
            confidence=packing_prov.confidence.value,
            method=packing_prov.method,
            source=packing_prov.source,
            estimated=False,
            note=packing_prov.validity_note or "",
        ))

    assumptions: list[AssumptionAuditRow] = [
        AssumptionAuditRow("Model scope", "Steady-state operation", "ACTIVE", "No transient inventory or startup/shutdown dynamics are solved."),
        AssumptionAuditRow("Model scope", "Isothermal column", "ACTIVE", "No energy balance or heat of absorption is coupled to the mass-transfer equations."),
        AssumptionAuditRow("Model scope", "Physical, non-reactive absorption", "ACTIVE", "Reaction-enhanced absorption and electrolytes are outside V4.0."),
        AssumptionAuditRow("Model scope", "1–4 independent dilute solutes", "ACTIVE", "Each solute is solved independently against shared bulk gas/liquid flows; coupled multicomponent VLE is not solved."),
        AssumptionAuditRow("Bulk phases", "Ideal gas carrier", "ACTIVE", "Gas density/molar flow use the ideal-gas basis unless explicitly overridden in the resolver."),
        AssumptionAuditRow("Bulk phases", "Constant G, L, T and P through the packed bed", "ACTIVE", "Local solvent evaporation, bulk depletion, pressure variation and local property updates are not coupled to the ODE."),
        AssumptionAuditRow("Packing", "Random packing", "ACTIVE", f"Selected packing class = {packing.packing_class}; Onda/GPDC implementation is not a structured-packing vendor model."),
        AssumptionAuditRow("Mass transfer", "Onda-type effective area + film coefficients", "ACTIVE", "Coefficients are evaluated once at the operating point and held constant along z."),
        AssumptionAuditRow("Hydraulics", "Screening pressure-drop + GPDC flooding", "ACTIVE", "Not a vendor guarantee; distributors, supports, entrainment, fouling and maldistribution are excluded."),
        AssumptionAuditRow("Units", "Canonical gas composition = mole fraction y", "ACTIVE", "ppmv/mgVOC/mgC conversions are confined to the unit/reporting layer."),
    ]

    total_y = result.inlet_report.total_y
    dilute_state = "GREEN" if total_y < 0.01 else ("YELLOW" if total_y < 0.05 else "RED")
    assumptions.append(AssumptionAuditRow(
        "Dilute-domain screen",
        "Total inlet solute mole fraction",
        f"{dilute_state}: y_total = {_fmt(total_y)}",
        "Engineering screen: <0.01 preferred; 0.01–0.05 caution; ≥0.05 outside the preferred dilute range.",
    ))

    any_preloaded = any(float(case.liquid_inlet_x.get(sid, 0.0)) > 0 for sid in case.solute_ids)
    assumptions.append(AssumptionAuditRow(
        "Boundary conditions",
        "Solvent inlet loading",
        "PRELOADED" if any_preloaded else "FRESH FOR ALL SOLUTES",
        "Nonzero x_in is supported. Negative local y−mx is retained and can produce desorption.",
    ))
    assumptions.append(AssumptionAuditRow(
        "Volatility",
        "Solvent evaporation",
        "EXPECTED BUT NOT MODELLED" if case.solvent_evaporation_expected else "NOT FLAGGED",
        "When flagged, applicability is downgraded because V4.0 keeps bulk gas/liquid flows constant and omits solvent vaporization.",
    ))
    assumptions.append(AssumptionAuditRow(
        "Hydraulics",
        "Foaming correction",
        "EXPECTED BUT NOT MODELLED" if case.foaming_expected else "NOT FLAGGED",
        "No foaming derating is applied to flooding or pressure-drop capacity.",
    ))

    for sid in case.solute_ids:
        rp = result.resolved_components[sid]
        eqp = rp.equilibrium.active_property
        assumptions.append(AssumptionAuditRow(
            f"{sid} thermodynamics",
            "Equilibrium model",
            rp.equilibrium.model,
            f"{eqp.method}; tier {eqp.tier.value}; confidence {eqp.confidence.value}.",
        ))
        for label, p in (("D_G", rp.gas_diffusivity), ("D_L", rp.liquid_diffusivity)):
            assumptions.append(AssumptionAuditRow(
                f"{sid} transport",
                label,
                f"{p.tier.value} / confidence {p.confidence.value}",
                f"{p.method}." + (" Correlation estimate, not measured pair data." if p.estimated else ""),
            ))

    diagnostics: list[DiagnosticAuditRow] = []
    for sid in case.solute_ids:
        solved = result.solver_results.components[sid]
        diagnostics.extend([
            DiagnosticAuditRow(sid, "solver mode", solved.diagnostics.mode, "NET_ABSORPTION / NET_DESORPTION / NEAR_EQUILIBRIUM / NO_TRANSFER"),
            DiagnosticAuditRow(sid, "relative mass-balance error", _fmt(solved.diagnostics.relative_mass_balance_error), "Post-solver numerical closure check."),
            DiagnosticAuditRow(sid, "liquid boundary error", _fmt(solved.diagnostics.boundary_error_x), "x(Z) − x_in after the shooting solve."),
            DiagnosticAuditRow(sid, "driving-force range", f"{_fmt(solved.diagnostics.min_driving_force_y)} to {_fmt(solved.diagnostics.max_driving_force_y)}", "Negative values are not clamped; they indicate local desorption."),
        ])
    diagnostics.extend([
        DiagnosticAuditRow("hydraulics", "% flood", _fmt(pf.flooding_percent), pf.hydraulic_regime),
        DiagnosticAuditRow("hydraulics", "GPDC range", str(pf.gpdc_valid), f"F_LV = {_fmt(pf.F_LV_flood)}; intended numerical range 0.01–8."),
        DiagnosticAuditRow("validity", "final status", result.post_applicability.status.value, f"Blocks={len(result.post_applicability.blocks)}, warnings={len(result.post_applicability.warnings)}, infos={len(result.post_applicability.infos)}"),
        DiagnosticAuditRow("confidence", "thermodynamics", result.post_applicability.confidence.thermodynamics.value, "Weak property/equilibrium data reduce the final confidence."),
        DiagnosticAuditRow("confidence", "mass transfer", result.post_applicability.confidence.mass_transfer.value, "Includes transport-property confidence and correlation-domain diagnostics."),
        DiagnosticAuditRow("confidence", "hydraulics", result.post_applicability.confidence.hydraulics.value, "Includes packing-factor quality and GPDC validity."),
        DiagnosticAuditRow("confidence", "overall", result.post_applicability.confidence.overall.value, "Overall rating follows the weakest critical confidence branch."),
    ])

    return LiveMethodsReport(
        report_id=PHASE15_LIVE_METHODS_ID,
        case_id=result.case_id,
        summary=summary,
        equations=tuple(eqs),
        properties=tuple(props),
        assumptions=tuple(assumptions),
        diagnostics=tuple(diagnostics),
    )
