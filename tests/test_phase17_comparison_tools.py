import math

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    NamedCase,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    compare_named_cases,
    compare_packings,
    compare_solvents,
    run_generic_absorber_case,
)


def reference_case():
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
        operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=feed.canonical_y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )
    return r, case


def vdc_case(solvent="water"):
    r = build_phase14_registry()
    return r, GenericAbsorberCase(
        operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
        solute_ids=("VDC",),
        carrier_id="air",
        solvent_id=solvent,
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"VDC": 1000e-6},
        liquid_inlet_x={"VDC": 0.0},
        solvent_evaporation_expected=(solvent == "acrylonitrile"),
    )


def test_phase17_catalog_adds_legacy_packing_alternatives_without_changing_reference_packing():
    r = build_phase14_registry()
    assert len(r.packings) >= 9
    p25 = r.get_packing("25mm_metal_pall_ring")
    assert p25.area_m2_m3 == 212.0
    assert p25.packing_factor_ft_inv == 48.0
    assert r.get_packing("38mm_metal_pall_ring").area_m2_m3 == 145.0
    assert r.get_packing("imtp_25").packing_factor_ft_inv == 41.0


def test_phase17_packing_comparison_baseline_matches_direct_simulator():
    r, case = reference_case()
    comp = compare_packings(case, ["25mm_metal_pall_ring", "38mm_metal_pall_ring"], registry=r)
    direct = run_generic_absorber_case(case, registry=r)
    assert comp.successful_alternatives == 2
    baseline = comp.alternatives[0]
    assert math.isclose(baseline.outlet_mgVOC_Nm3, direct.outlet_report.total_mgVOC_Nm3, rel_tol=1e-10)
    assert math.isclose(baseline.flooding_percent, direct.hydraulics.flooding.flooding_percent, rel_tol=1e-10)
    assert comp.alternatives[0].packing_id != comp.alternatives[1].packing_id


def test_phase17_packing_comparison_exposes_per_component_metrics():
    r, case = reference_case()
    comp = compare_packings(case, ["25mm_metal_pall_ring", "imtp_25"], registry=r)
    for alt in comp.alternatives:
        assert alt.success
        assert set(alt.component_metrics) == {"ACN", "VAc"}
        assert alt.component_metrics["VAc"].HTU_OG_m > 0
        assert alt.component_metrics["VAc"].absorption_factor > 0


def test_phase17_vdc_solvent_comparison_runs_water_and_acrylonitrile_same_basis():
    r, case = vdc_case("water")
    comp = compare_solvents(
        case,
        ["water", "acrylonitrile"],
        registry=r,
        solvent_evaporation_expected={"acrylonitrile": True},
    )
    assert comp.successful_alternatives == 2
    water, acn = comp.alternatives
    assert water.solvent_id == "water"
    assert acn.solvent_id == "acrylonitrile"
    assert water.component_metrics["VDC"].inlet_ppmv == acn.component_metrics["VDC"].inlet_ppmv
    assert acn.voc_mass_removal_percent > water.voc_mass_removal_percent
    assert acn.status == "OUTSIDE_RECOMMENDED_RANGE"
    assert acn.confidence == "SCREENING"


def test_phase17_unsupported_solvent_alternative_is_retained_as_failure():
    r, case = reference_case()
    comp = compare_solvents(
        case,
        ["water", "acrylonitrile"],
        registry=r,
        solvent_evaporation_expected={"acrylonitrile": True},
    )
    assert comp.successful_alternatives == 1
    assert comp.failed_alternatives == 1
    failed = [x for x in comp.alternatives if not x.success][0]
    assert failed.solvent_id == "acrylonitrile"
    assert "not resolvable" in failed.error


def test_phase17_named_scenario_comparison_keeps_labels_and_full_validity():
    r, water_case = vdc_case("water")
    _, acn_case = vdc_case("acrylonitrile")
    comp = compare_named_cases(
        [NamedCase("VDC / Water", water_case), NamedCase("VDC / AN", acn_case)],
        registry=r,
    )
    assert [x.label for x in comp.alternatives] == ["VDC / Water", "VDC / AN"]
    assert comp.successful_alternatives == 2
    assert comp.alternatives[0].status != comp.alternatives[1].status
    assert comp.alternatives[1].status == "OUTSIDE_RECOMMENDED_RANGE"


def test_phase17_records_do_not_contain_hidden_composite_score():
    r, case = reference_case()
    comp = compare_packings(case, ["25mm_metal_pall_ring", "38mm_metal_pall_ring"], registry=r)
    rows = comp.records()
    assert rows
    forbidden = {"score", "best_score", "overall_score", "rank_score"}
    for row in rows:
        assert forbidden.isdisjoint(row)
        assert "status" in row and "confidence" in row
        assert "flooding_percent" in row and "wet_pressure_drop_mbar_m" in row


def test_phase17_geometric_fallback_packings_stay_visible_in_hydraulic_results():
    r, case = reference_case()
    comp = compare_packings(case, ["cmr_2"], registry=r)
    alt = comp.alternatives[0]
    assert alt.success
    assert alt.simulation.hydraulics.flooding.packing_factor_estimated is True
    assert alt.simulation.hydraulics.flooding.packing_factor_basis == "geometric a/eps^3 fallback"
