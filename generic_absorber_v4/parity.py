"""Phase 9 full locked-V3 parity harness for Generic Packed Absorber Simulator V4.

This module is intentionally a *verification* layer, not a new physics model.
It executes the existing Phase 1-8 V4 calculation chain for the locked reference
case and compares the resulting values against a frozen numerical fixture taken
from ``scrubber_model.py / ScrubberSimulationV34`` on 2026-10-06.

The production V4 physics modules never import or call the legacy engine.  The
legacy numerical fixture is immutable and carries the reference source hash so
an intentional future physics revision can create a new reference ID instead of
silently moving the baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping

from .applicability import ApplicabilityCase, assess_post_applicability, assess_pre_applicability
from .countercurrent import ComponentBoundaryConditions, solve_independent_solutes
from .mass_transfer import AbsorberOperatingPoint, evaluate_component_from_resolver
from .hydraulics import evaluate_hydraulics_from_resolver
from .reference_data import REFERENCE_ID, locked_reference_data
from .registry import build_reference_registry
from .resolver import build_reference_resolver
from .units import (
    CompositionFractionBasis,
    GasConcentrationBasis,
    canonical_y_from_total_and_fractions,
    gas_stream_balance,
    report_gas_stream,
)

REFERENCE_SOURCE_SHA256 = "90ddffaa5517d2851d9bec7e3621653fc01959e236a2b4bccb34e276219fd967"
REFERENCE_SOURCE_LABEL = "scrubber_model.py / ScrubberSimulationV34 locked 2026-10-06"


@dataclass(frozen=True)
class ParityTolerance:
    rtol: float
    atol: float


TOLERANCE_ALGEBRA = ParityTolerance(rtol=1e-12, atol=1e-14)
TOLERANCE_COEFFICIENT = ParityTolerance(rtol=1e-10, atol=1e-14)
TOLERANCE_SOLVER = ParityTolerance(rtol=1e-8, atol=1e-12)
TOLERANCE_REPORTING = ParityTolerance(rtol=1e-10, atol=1e-12)
TOLERANCE_HYDRAULICS = ParityTolerance(rtol=1e-10, atol=1e-12)


@dataclass(frozen=True)
class ReferenceMetric:
    section: str
    name: str
    expected: Any
    tolerance: ParityTolerance | None = None
    unit: str = ""


@dataclass(frozen=True)
class ParityMetricResult:
    section: str
    name: str
    expected: Any
    actual: Any
    passed: bool
    unit: str = ""
    rtol: float | None = None
    atol: float | None = None
    absolute_error: float | None = None
    relative_error: float | None = None


@dataclass(frozen=True)
class FullParityReport:
    reference_id: str
    reference_source: str
    reference_source_sha256: str
    metrics: tuple[ParityMetricResult, ...]

    @property
    def passed(self) -> bool:
        return all(metric.passed for metric in self.metrics)

    @property
    def total_count(self) -> int:
        return len(self.metrics)

    @property
    def passed_count(self) -> int:
        return sum(metric.passed for metric in self.metrics)

    @property
    def failed_count(self) -> int:
        return self.total_count - self.passed_count

    @property
    def failures(self) -> tuple[ParityMetricResult, ...]:
        return tuple(metric for metric in self.metrics if not metric.passed)

    @property
    def sections(self) -> Mapping[str, tuple[ParityMetricResult, ...]]:
        names: dict[str, list[ParityMetricResult]] = {}
        for metric in self.metrics:
            names.setdefault(metric.section, []).append(metric)
        return {key: tuple(value) for key, value in names.items()}

    def section_passed(self, section: str) -> bool:
        items = self.sections.get(section, ())
        return bool(items) and all(item.passed for item in items)


# Frozen fixture transcribed from the locked legacy engine.  These are reference
# observations, not equations.  They must only change when a new reference ID is
# intentionally created.
V3_REFERENCE_METRICS: tuple[ReferenceMetric, ...] = (
    # Units / feed reconstruction
    ReferenceMetric("Units & Feed", "feed_total_mgVOC_Nm3", 5000.0, TOLERANCE_ALGEBRA, "mgVOC/Nm³"),
    ReferenceMetric("Units & Feed", "feed_total_mgC_Nm3", 3353.1344673788512, TOLERANCE_ALGEBRA, "mgC/Nm³"),
    ReferenceMetric("Units & Feed", "feed_total_ppmv", 2055.409210811772, TOLERANCE_ALGEBRA, "ppmv"),
    ReferenceMetric("Units & Feed", "ACN_y_in", 1.964284929935824e-3, TOLERANCE_ALGEBRA, "mol/mol"),
    ReferenceMetric("Units & Feed", "VAc_y_in", 9.112428087594802e-5, TOLERANCE_ALGEBRA, "mol/mol"),
    ReferenceMetric("Units & Feed", "ACN_feed_mgVOC_Nm3", 4650.0, TOLERANCE_ALGEBRA, "mgVOC/Nm³"),
    ReferenceMetric("Units & Feed", "VAc_feed_mgVOC_Nm3", 350.0000000000001, TOLERANCE_ALGEBRA, "mgVOC/Nm³"),

    # Resolved bulk state + common Onda quantities
    ReferenceMetric("Bulk & Common Onda", "gas_density_kg_m3", 1.1973955442078126, TOLERANCE_ALGEBRA, "kg/m³"),
    ReferenceMetric("Bulk & Common Onda", "gas_viscosity_Pa_s", 1.822876469548802e-5, TOLERANCE_ALGEBRA, "Pa·s"),
    ReferenceMetric("Bulk & Common Onda", "liquid_density_kg_m3", 997.8003203172385, TOLERANCE_ALGEBRA, "kg/m³"),
    ReferenceMetric("Bulk & Common Onda", "liquid_viscosity_Pa_s", 9.547755753950499e-4, TOLERANCE_ALGEBRA, "Pa·s"),
    ReferenceMetric("Bulk & Common Onda", "surface_tension_N_m", 0.07243227047929218, TOLERANCE_ALGEBRA, "N/m"),
    ReferenceMetric("Bulk & Common Onda", "column_area_m2", 0.19634954084936207, TOLERANCE_ALGEBRA, "m²"),
    ReferenceMetric("Bulk & Common Onda", "gas_molar_flow_mol_s", 1.3479875317121093, TOLERANCE_ALGEBRA, "mol/s"),
    ReferenceMetric("Bulk & Common Onda", "liquid_molar_flow_mol_s", 38.54812347734912, TOLERANCE_ALGEBRA, "mol/s"),
    ReferenceMetric("Bulk & Common Onda", "gas_molar_flux_mol_m2_s", 6.865244124743207, TOLERANCE_ALGEBRA, "mol/(m²·s)"),
    ReferenceMetric("Bulk & Common Onda", "liquid_molar_flux_mol_m2_s", 196.32398074677934, TOLERANCE_ALGEBRA, "mol/(m²·s)"),
    ReferenceMetric("Bulk & Common Onda", "gas_mass_flux_kg_m2_s", 0.19909207961755299, TOLERANCE_ALGEBRA, "kg/(m²·s)"),
    ReferenceMetric("Bulk & Common Onda", "liquid_mass_flux_kg_m2_s", 3.53677651315323, TOLERANCE_ALGEBRA, "kg/(m²·s)"),
    ReferenceMetric("Bulk & Common Onda", "gas_superficial_velocity_m_s", 0.16627093743635965, TOLERANCE_ALGEBRA, "m/s"),
    ReferenceMetric("Bulk & Common Onda", "Re_L", 17.47311987323168, TOLERANCE_ALGEBRA),
    ReferenceMetric("Bulk & Common Onda", "Re_G", 51.51822401515305, TOLERANCE_ALGEBRA),
    ReferenceMetric("Bulk & Common Onda", "Fr_L", 2.715156150626979e-4, TOLERANCE_ALGEBRA),
    ReferenceMetric("Bulk & Common Onda", "We_L", 8.164012046442508e-4, TOLERANCE_ALGEBRA),
    ReferenceMetric("Bulk & Common Onda", "effective_area_m2_m3", 108.8616313828827, TOLERANCE_ALGEBRA, "m²/m³"),
    ReferenceMetric("Bulk & Common Onda", "wetting_fraction", 0.5134982612400127, TOLERANCE_ALGEBRA),

    # ACN coefficient layer
    ReferenceMetric("ACN Mass Transfer", "ACN_DG_m2_s", 1.0e-5, TOLERANCE_ALGEBRA, "m²/s"),
    ReferenceMetric("ACN Mass Transfer", "ACN_DL_m2_s", 1.0e-9, TOLERANCE_ALGEBRA, "m²/s"),
    ReferenceMetric("ACN Mass Transfer", "ACN_H_Pa_m3_mol", 1.0361313639640817, TOLERANCE_COEFFICIENT, "Pa·m³/mol"),
    ReferenceMetric("ACN Mass Transfer", "ACN_m", 0.5663795710741079, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_Sc_L", 956.8804057824822, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_Sc_G", 1.5223678410752755, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_k_L", 7.11620147627118e-5, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_k_G", 2.92160381730706e-6, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_K_G", 2.802392662477365e-6, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_absorption_factor", 50.49051331523841, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_HTU_OG_m", 0.2220933460636276, TOLERANCE_COEFFICIENT, "m"),
    ReferenceMetric("ACN Mass Transfer", "ACN_NTU_OG", 6.303655759227084, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_gas_resistance_fraction", 0.9591966733738814, TOLERANCE_COEFFICIENT),
    ReferenceMetric("ACN Mass Transfer", "ACN_liquid_resistance_fraction", 0.040803326626118644, TOLERANCE_COEFFICIENT),

    # VAc coefficient layer
    ReferenceMetric("VAc Mass Transfer", "VAc_DG_m2_s", 0.9e-5, TOLERANCE_ALGEBRA, "m²/s"),
    ReferenceMetric("VAc Mass Transfer", "VAc_DL_m2_s", 0.9e-9, TOLERANCE_ALGEBRA, "m²/s"),
    ReferenceMetric("VAc Mass Transfer", "VAc_H_Pa_m3_mol", 44.41319462729455, TOLERANCE_COEFFICIENT, "Pa·m³/mol"),
    ReferenceMetric("VAc Mass Transfer", "VAc_m", 24.27754529773116, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_Sc_L", 1063.2004508694247, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_Sc_G", 1.6915198234169726, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_k_L", 6.751021486100878e-5, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_k_G", 2.7234307051966124e-6, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_K_G", 9.755549053955852e-7, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_absorption_factor", 1.1779113136890638, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_HTU_OG_m", 0.6379884514458746, TOLERANCE_COEFFICIENT, "m"),
    ReferenceMetric("VAc Mass Transfer", "VAc_NTU_OG", 2.1943970879522614, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_gas_resistance_fraction", 0.35820808788493, TOLERANCE_COEFFICIENT),
    ReferenceMetric("VAc Mass Transfer", "VAc_liquid_resistance_fraction", 0.64179191211507, TOLERANCE_COEFFICIENT),

    # Counter-current solution + reporting
    ReferenceMetric("Counter-Current & Outlet", "ACN_y_out", 3.991282910574221e-6, TOLERANCE_SOLVER, "mol/mol"),
    ReferenceMetric("Counter-Current & Outlet", "ACN_x_bottom", 6.854941710034729e-5, TOLERANCE_SOLVER, "mol/mol"),
    ReferenceMetric("Counter-Current & Outlet", "ACN_removal_fraction", 0.9979680733432574, TOLERANCE_SOLVER),
    ReferenceMetric("Counter-Current & Outlet", "ACN_outlet_mgVOC_Nm3", 9.448458953852734, TOLERANCE_REPORTING, "mgVOC/Nm³"),
    ReferenceMetric("Counter-Current & Outlet", "VAc_y_out", 2.5299699106660017e-5, TOLERANCE_SOLVER, "mol/mol"),
    ReferenceMetric("Counter-Current & Outlet", "VAc_x_bottom", 2.301816729348773e-6, TOLERANCE_SOLVER, "mol/mol"),
    ReferenceMetric("Counter-Current & Outlet", "VAc_removal_fraction", 0.7223605073920776, TOLERANCE_SOLVER),
    ReferenceMetric("Counter-Current & Outlet", "VAc_outlet_mgVOC_Nm3", 97.17382241277288, TOLERANCE_REPORTING, "mgVOC/Nm³"),
    ReferenceMetric("Counter-Current & Outlet", "outlet_total_mgVOC_Nm3", 106.62228136662561, TOLERANCE_REPORTING, "mgVOC/Nm³"),
    ReferenceMetric("Counter-Current & Outlet", "outlet_total_mgC_Nm3", 60.645957347814814, TOLERANCE_REPORTING, "mgC/Nm³"),
    ReferenceMetric("Counter-Current & Outlet", "outlet_total_ppmv", 29.29098201723424, TOLERANCE_REPORTING, "ppmv"),
    ReferenceMetric("Counter-Current & Outlet", "overall_VOC_mass_removal_fraction", 0.9786755437266749, TOLERANCE_REPORTING),

    # Hydraulics
    ReferenceMetric("Hydraulics", "hydraulic_Re_L", 17.47311987323168, TOLERANCE_HYDRAULICS),
    ReferenceMetric("Hydraulics", "liquid_holdup_fraction", 0.05713056691346087, TOLERANCE_HYDRAULICS),
    ReferenceMetric("Hydraulics", "dry_dP_Pa_m", 4.729685067279156, TOLERANCE_HYDRAULICS, "Pa/m"),
    ReferenceMetric("Hydraulics", "wet_dP_Pa_m", 5.683288286702279, TOLERANCE_HYDRAULICS, "Pa/m"),
    ReferenceMetric("Hydraulics", "wet_dP_mbar_m", 0.05683288286702279, TOLERANCE_HYDRAULICS, "mbar/m"),
    ReferenceMetric("Hydraulics", "total_dP_Pa", 7.95660360138319, TOLERANCE_HYDRAULICS, "Pa"),
    ReferenceMetric("Hydraulics", "U_flood_m_s", 2.3208029666997687, TOLERANCE_HYDRAULICS, "m/s"),
    ReferenceMetric("Hydraulics", "F_LV_flood", 0.0440888436630539, TOLERANCE_HYDRAULICS),
    ReferenceMetric("Hydraulics", "CP_flood", 1.8245028673067514, TOLERANCE_HYDRAULICS),
    ReferenceMetric("Hydraulics", "packing_factor_ft_inv", 48.0, TOLERANCE_ALGEBRA, "ft⁻¹"),
    ReferenceMetric("Hydraulics", "packing_factor_basis", "empirical"),
    ReferenceMetric("Hydraulics", "packing_factor_estimated", False),
    ReferenceMetric("Hydraulics", "flooding_percent", 7.164371117329295, TOLERANCE_HYDRAULICS, "%"),
    ReferenceMetric("Hydraulics", "hydraulic_regime", "UNDERLOADED / HIGH CAPACITY MARGIN"),
    ReferenceMetric("Hydraulics", "flood_dP_mbar_m", 14.12232286238167, TOLERANCE_HYDRAULICS, "mbar/m"),
    ReferenceMetric("Hydraulics", "dP_ratio_to_flood", 0.004024329667353191, TOLERANCE_HYDRAULICS),
)


def _reference_actuals() -> Mapping[str, Any]:
    """Execute the complete existing V4 reference chain and flatten outputs."""

    db = locked_reference_data()
    registry = build_reference_registry()
    resolver = build_reference_resolver()

    feed = canonical_y_from_total_and_fractions(
        5000.0,
        GasConcentrationBasis.MG_VOC_NM3,
        {"ACN": 0.93, "VAc": 0.07},
        CompositionFractionBasis.VOC_MASS,
        db.solutes,
    )

    operating = AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=295.15,
        pressure_Pa=101325.0,
    )

    resolved = {}
    transfers = {}
    common = None
    for sid in ("ACN", "VAc"):
        resolved[sid] = resolver.resolve_component_properties(
            sid, "air", "water", operating.temperature_K, operating.pressure_Pa
        )
        common_i, transfer_i = evaluate_component_from_resolver(
            resolver=resolver,
            registry=registry,
            solute_id=sid,
            carrier_id="air",
            solvent_id="water",
            packing_id="25mm_metal_pall_ring",
            operating=operating,
        )
        if common is None:
            common = common_i
        transfers[sid] = transfer_i

    assert common is not None
    boundaries = {
        sid: ComponentBoundaryConditions(
            gas_inlet_y=feed.canonical_y[sid], liquid_inlet_x=0.0
        )
        for sid in ("ACN", "VAc")
    }
    solved = solve_independent_solutes(common, transfers, boundaries)
    outlet_y = {sid: solved.components[sid].gas_outlet_y for sid in ("ACN", "VAc")}
    outlet = report_gas_stream(outlet_y, db.solutes)
    balance = gas_stream_balance(
        feed.canonical_y,
        outlet_y,
        db.solutes,
        gas_molar_flow_mol_s=common.gas_molar_flow_mol_s,
    )

    _, hydraulics = evaluate_hydraulics_from_resolver(
        resolver=resolver,
        registry=registry,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=operating,
    )

    # Phase 8 is executed as part of the integrated chain too.  Its status is
    # asserted in tests but is not called a V3 metric because V3 had no explicit
    # applicability engine.
    app_case = ApplicabilityCase(
        operating=operating,
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=dict(feed.canonical_y),
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )
    pre = assess_pre_applicability(registry, app_case)
    post = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=registry.get_packing("25mm_metal_pall_ring"),
    )

    acn = transfers["ACN"]
    vac = transfers["VAc"]
    acn_s = solved.components["ACN"]
    vac_s = solved.components["VAc"]
    pd = hydraulics.pressure_drop
    fl = hydraulics.flooding

    actuals: dict[str, Any] = {
        "feed_total_mgVOC_Nm3": feed.report.total_mgVOC_Nm3,
        "feed_total_mgC_Nm3": feed.report.total_mgC_Nm3,
        "feed_total_ppmv": feed.report.total_ppmv,
        "ACN_y_in": feed.canonical_y["ACN"],
        "VAc_y_in": feed.canonical_y["VAc"],
        "ACN_feed_mgVOC_Nm3": feed.report.components["ACN"].mgVOC_Nm3,
        "VAc_feed_mgVOC_Nm3": feed.report.components["VAc"].mgVOC_Nm3,
        "gas_density_kg_m3": resolved["ACN"].carrier.density.value,
        "gas_viscosity_Pa_s": resolved["ACN"].carrier.viscosity.value,
        "liquid_density_kg_m3": resolved["ACN"].solvent.density.value,
        "liquid_viscosity_Pa_s": resolved["ACN"].solvent.viscosity.value,
        "surface_tension_N_m": resolved["ACN"].solvent.surface_tension.value,
        "column_area_m2": common.area_m2,
        "gas_molar_flow_mol_s": common.gas_molar_flow_mol_s,
        "liquid_molar_flow_mol_s": common.liquid_molar_flow_mol_s,
        "gas_molar_flux_mol_m2_s": common.gas_molar_flux_mol_m2_s,
        "liquid_molar_flux_mol_m2_s": common.liquid_molar_flux_mol_m2_s,
        "gas_mass_flux_kg_m2_s": common.gas_mass_flux_kg_m2_s,
        "liquid_mass_flux_kg_m2_s": common.liquid_mass_flux_kg_m2_s,
        "gas_superficial_velocity_m_s": common.gas_superficial_velocity_m_s,
        "Re_L": common.Re_L,
        "Re_G": common.Re_G,
        "Fr_L": common.Fr_L,
        "We_L": common.We_L,
        "effective_area_m2_m3": common.effective_area_m2_m3,
        "wetting_fraction": common.wetting_fraction,
        "ACN_DG_m2_s": acn.gas_diffusivity_m2_s,
        "ACN_DL_m2_s": acn.liquid_diffusivity_m2_s,
        "ACN_H_Pa_m3_mol": acn.henry_effective_Pa_m3_mol,
        "ACN_m": acn.equilibrium_slope_m,
        "ACN_Sc_L": acn.Sc_L,
        "ACN_Sc_G": acn.Sc_G,
        "ACN_k_L": acn.k_L,
        "ACN_k_G": acn.k_G,
        "ACN_K_G": acn.K_G,
        "ACN_absorption_factor": acn.absorption_factor,
        "ACN_HTU_OG_m": acn.HTU_OG_m,
        "ACN_NTU_OG": acn.NTU_OG,
        "ACN_gas_resistance_fraction": acn.gas_resistance_fraction,
        "ACN_liquid_resistance_fraction": acn.liquid_resistance_fraction,
        "VAc_DG_m2_s": vac.gas_diffusivity_m2_s,
        "VAc_DL_m2_s": vac.liquid_diffusivity_m2_s,
        "VAc_H_Pa_m3_mol": vac.henry_effective_Pa_m3_mol,
        "VAc_m": vac.equilibrium_slope_m,
        "VAc_Sc_L": vac.Sc_L,
        "VAc_Sc_G": vac.Sc_G,
        "VAc_k_L": vac.k_L,
        "VAc_k_G": vac.k_G,
        "VAc_K_G": vac.K_G,
        "VAc_absorption_factor": vac.absorption_factor,
        "VAc_HTU_OG_m": vac.HTU_OG_m,
        "VAc_NTU_OG": vac.NTU_OG,
        "VAc_gas_resistance_fraction": vac.gas_resistance_fraction,
        "VAc_liquid_resistance_fraction": vac.liquid_resistance_fraction,
        "ACN_y_out": acn_s.gas_outlet_y,
        "ACN_x_bottom": acn_s.liquid_bottom_x,
        "ACN_removal_fraction": acn_s.removal_fraction,
        "ACN_outlet_mgVOC_Nm3": outlet.components["ACN"].mgVOC_Nm3,
        "VAc_y_out": vac_s.gas_outlet_y,
        "VAc_x_bottom": vac_s.liquid_bottom_x,
        "VAc_removal_fraction": vac_s.removal_fraction,
        "VAc_outlet_mgVOC_Nm3": outlet.components["VAc"].mgVOC_Nm3,
        "outlet_total_mgVOC_Nm3": outlet.total_mgVOC_Nm3,
        "outlet_total_mgC_Nm3": outlet.total_mgC_Nm3,
        "outlet_total_ppmv": outlet.total_ppmv,
        "overall_VOC_mass_removal_fraction": balance.overall_removal_voc_mass,
        "hydraulic_Re_L": pd.Re_L_hydraulic,
        "liquid_holdup_fraction": pd.liquid_holdup_fraction,
        "dry_dP_Pa_m": pd.dry_pressure_drop_Pa_m,
        "wet_dP_Pa_m": pd.wet_pressure_drop_Pa_m,
        "wet_dP_mbar_m": pd.wet_pressure_drop_mbar_m,
        "total_dP_Pa": pd.total_pressure_drop_Pa,
        "U_flood_m_s": fl.flood_velocity_m_s,
        "F_LV_flood": fl.F_LV_flood,
        "CP_flood": fl.CP_flood,
        "packing_factor_ft_inv": fl.packing_factor_ft_inv,
        "packing_factor_basis": fl.packing_factor_basis,
        "packing_factor_estimated": fl.packing_factor_estimated,
        "flooding_percent": fl.flooding_percent,
        "hydraulic_regime": fl.hydraulic_regime,
        "flood_dP_mbar_m": fl.flood_pressure_drop_mbar_m,
        "dP_ratio_to_flood": hydraulics.pressure_drop_ratio_to_flood,
        # Additional integrated-chain health metadata, intentionally not part of
        # the legacy numeric metric list.
        "phase8_pre_status": pre.status.value,
        "phase8_final_status": post.status.value,
        "phase8_overall_confidence": post.confidence.overall.value,
        "ACN_mass_balance_relative_error": acn_s.diagnostics.relative_mass_balance_error,
        "VAc_mass_balance_relative_error": vac_s.diagnostics.relative_mass_balance_error,
    }
    return actuals


def _compare(reference: ReferenceMetric, actual: Any) -> ParityMetricResult:
    expected = reference.expected
    tol = reference.tolerance

    if tol is None:
        passed = actual == expected
        return ParityMetricResult(
            section=reference.section,
            name=reference.name,
            expected=expected,
            actual=actual,
            passed=passed,
            unit=reference.unit,
        )

    expected_f = float(expected)
    actual_f = float(actual)
    abs_error = abs(actual_f - expected_f)
    scale = abs(expected_f)
    rel_error = abs_error / scale if scale > 0 else (0.0 if abs_error == 0 else math.inf)
    passed = math.isclose(actual_f, expected_f, rel_tol=tol.rtol, abs_tol=tol.atol)
    return ParityMetricResult(
        section=reference.section,
        name=reference.name,
        expected=expected_f,
        actual=actual_f,
        passed=passed,
        unit=reference.unit,
        rtol=tol.rtol,
        atol=tol.atol,
        absolute_error=abs_error,
        relative_error=rel_error,
    )


def run_full_v3_parity() -> FullParityReport:
    """Run the integrated V4 reference case and compare every locked V3 metric."""

    actuals = _reference_actuals()
    results = tuple(_compare(metric, actuals[metric.name]) for metric in V3_REFERENCE_METRICS)
    return FullParityReport(
        reference_id=REFERENCE_ID,
        reference_source=REFERENCE_SOURCE_LABEL,
        reference_source_sha256=REFERENCE_SOURCE_SHA256,
        metrics=results,
    )


def reference_chain_health() -> Mapping[str, Any]:
    """Return non-V3 integrated health metadata for the same reference run."""

    actuals = _reference_actuals()
    return {
        "phase8_pre_status": actuals["phase8_pre_status"],
        "phase8_final_status": actuals["phase8_final_status"],
        "phase8_overall_confidence": actuals["phase8_overall_confidence"],
        "ACN_mass_balance_relative_error": actuals["ACN_mass_balance_relative_error"],
        "VAc_mass_balance_relative_error": actuals["VAc_mass_balance_relative_error"],
    }
