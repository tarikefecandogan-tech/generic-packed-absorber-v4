import math
import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    SimulationBlockedError,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    compatible_solutes,
    run_generic_absorber_case,
)


def op():
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=295.15,
        pressure_Pa=101325.0,
    )


def test_phase14_catalog_contains_all_registered_real_chemistry():
    r = build_phase14_registry()
    assert set(r.solutes) == {"ACN", "VAc", "VDC"}
    assert set(r.carriers) == {"air"}
    assert set(r.solvents) == {"water", "acrylonitrile"}
    assert "25mm_metal_pall_ring" in r.packings


def test_phase14_reference_case_preserves_full_v3_result():
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
        operating=op(),
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=feed.canonical_y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )
    result = run_generic_absorber_case(case, registry=r)
    assert math.isclose(result.outlet_report.total_mgVOC_Nm3, 106.6222813666, rel_tol=1e-9)
    assert math.isclose(result.stream_balance.overall_removal_voc_mass, 0.9786755437267, rel_tol=1e-9)
    assert math.isclose(result.hydraulics.flooding.flooding_percent, 7.16437111733, rel_tol=1e-9)
    assert result.pass_gate


def test_phase14_vdc_water_matches_phase12_behavior():
    r = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=op(),
        solute_ids=("VDC",),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"VDC": 1000e-6},
        liquid_inlet_x={"VDC": 0.0},
    )
    result = run_generic_absorber_case(case, registry=r)
    assert math.isclose(result.solver_results.components["VDC"].removal_fraction, 0.0220302746141, rel_tol=1e-9)
    assert result.pass_gate


def test_phase14_vdc_acn_matches_phase13_screening_behavior():
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
    assert math.isclose(result.solver_results.components["VDC"].removal_fraction, 0.9999072870896, rel_tol=1e-9)
    assert result.post_applicability.status.value == "OUTSIDE_RECOMMENDED_RANGE"
    assert result.post_applicability.confidence.overall.value == "SCREENING"
    assert result.pass_gate


def test_phase14_compatibility_filters_resolvable_chemistry():
    r = build_phase14_registry()
    water = {x.solute_id: x.ready for x in compatible_solutes(
        r, carrier_id="air", solvent_id="water", temperature_K=295.15, pressure_Pa=101325.0
    )}
    acn = {x.solute_id: x.ready for x in compatible_solutes(
        r, carrier_id="air", solvent_id="acrylonitrile", temperature_K=295.15, pressure_Pa=101325.0
    )}
    assert water == {"ACN": True, "VAc": True, "VDC": True}
    assert acn == {"ACN": False, "VAc": False, "VDC": True}


def test_phase14_incompatible_case_is_blocked_before_physics():
    r = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=op(),
        solute_ids=("ACN",),
        carrier_id="air",
        solvent_id="acrylonitrile",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"ACN": 1000e-6},
        liquid_inlet_x={"ACN": 0.0},
        solvent_evaporation_expected=True,
    )
    with pytest.raises(SimulationBlockedError) as exc:
        run_generic_absorber_case(case, registry=r)
    assert exc.value.report.blocks


def test_phase14_three_solute_water_case_runs_as_one_integrated_case():
    r = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=op(),
        solute_ids=("ACN", "VAc", "VDC"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"ACN": 500e-6, "VAc": 100e-6, "VDC": 100e-6},
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0, "VDC": 0.0},
    )
    result = run_generic_absorber_case(case, registry=r)
    assert set(result.solver_results.components) == {"ACN", "VAc", "VDC"}
    assert result.outlet_report.total_y < result.inlet_report.total_y
    assert result.stream_balance.total_captured_kg_h > 0
    for solved in result.solver_results.components.values():
        assert solved.diagnostics.relative_mass_balance_error <= 1e-7
