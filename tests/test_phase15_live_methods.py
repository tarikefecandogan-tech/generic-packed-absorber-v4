import math

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    PHASE15_LIVE_METHODS_ID,
    build_live_methods_report,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    run_generic_absorber_case,
)


def op(T=295.15):
    return AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, T, 101325.0)


def reference_result(T=295.15):
    r = build_phase14_registry()
    solutes = {sid: r.get_solute(sid) for sid in ("ACN", "VAc")}
    feed = canonical_y_from_total_and_fractions(
        5000.0,
        GasConcentrationBasis.MG_VOC_NM3,
        {"ACN": 0.93, "VAc": 0.07},
        CompositionFractionBasis.VOC_MASS,
        solutes,
    )
    case = GenericAbsorberCase(
        operating=op(T),
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=feed.canonical_y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )
    return run_generic_absorber_case(case, registry=r)


def test_phase15_reference_report_is_live_and_complete():
    result = reference_result()
    report = build_live_methods_report(result)
    assert report.report_id == PHASE15_LIVE_METHODS_ID
    assert report.case_id == result.case_id
    assert len(report.sections) >= 6
    assert any("Onda" in x.section for x in report.equations)
    assert any("counter-current" in x.section for x in report.equations)
    assert any(x.scope == "ACN" and x.property_name == "gas diffusivity D_G" for x in report.properties)
    assert any(x.scope == "VAc" and "equilibrium" in x.property_name for x in report.properties)
    assert any(x.diagnostic == "% flood" for x in report.diagnostics)


def test_phase15_live_values_come_from_result_not_recomputed_reference_constants():
    result = reference_result()
    report = build_live_methods_report(result)
    area_item = next(x for x in report.equations if x.title == "Column cross-sectional area")
    assert f"{result.common.area_m2:.6g}" in area_item.live_value
    flood_item = next(x for x in report.equations if x.title == "Flooding fraction")
    assert f"{result.hydraulics.flooding.flooding_percent:.6g}" in flood_item.live_value


def test_phase15_temperature_change_updates_live_report():
    r1 = build_live_methods_report(reference_result(295.15))
    r2 = build_live_methods_report(reference_result(300.15))
    p1 = next(x for x in r1.properties if x.scope == "water" and x.property_name == "solvent viscosity")
    p2 = next(x for x in r2.properties if x.scope == "water" and x.property_name == "solvent viscosity")
    assert not math.isclose(p1.value, p2.value, rel_tol=1e-6)
    assert any("300.15" in s for s in r2.summary)


def test_phase15_vdc_acn_surfaces_screening_thermodynamics_and_evaporation_limit():
    r = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=op(),
        solute_ids=("VDC",),
        carrier_id="air",
        solvent_id="acrylonitrile",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"VDC": 1000e-6},
        liquid_inlet_x={"VDC": 0.0},
        solvent_evaporation_expected=True,
    )
    result = run_generic_absorber_case(case, registry=r)
    report = build_live_methods_report(result)
    eq = next(x for x in report.properties if x.scope == "VDC" and "equilibrium" in x.property_name)
    assert eq.confidence == "D"
    assert eq.tier == "DATABASE"
    evap = next(x for x in report.assumptions if x.assumption == "Solvent evaporation")
    assert evap.state == "EXPECTED BUT NOT MODELLED"
    assert result.post_applicability.status.value == "OUTSIDE_RECOMMENDED_RANGE"


def test_phase15_preloaded_solvent_and_desorption_are_explicit():
    r = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=op(),
        solute_ids=("ACN",),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"ACN": 100e-6},
        liquid_inlet_x={"ACN": 5e-4},
    )
    result = run_generic_absorber_case(case, registry=r)
    report = build_live_methods_report(result)
    loading = next(x for x in report.assumptions if x.assumption == "Solvent inlet loading")
    assert loading.state == "PRELOADED"
    driving = next(x for x in report.diagnostics if x.scope == "ACN" and x.diagnostic == "driving-force range")
    assert "Negative values are not clamped" in driving.interpretation
