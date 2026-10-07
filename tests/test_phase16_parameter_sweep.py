import math
import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    InvalidSweepDefinition,
    MAX_SWEEP_POINTS,
    SweepAxis,
    SweepVariable,
    apply_sweep_values,
    base_value_for_variable,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    run_generic_absorber_case,
    run_parameter_sweep,
    suggested_sweep_bounds,
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
    return r, GenericAbsorberCase(
        operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y=feed.canonical_y,
        liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
    )


def test_phase16_single_axis_middle_point_matches_direct_integrated_simulation():
    registry, case = reference_case()
    axis = SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 1500.0, 3500.0, 3)
    sweep = run_parameter_sweep(case, [axis], registry=registry)
    direct = run_generic_absorber_case(case, registry=registry)
    mid = sweep.points[1]
    assert sweep.total_points == 3
    assert sweep.successful_points == 3
    assert math.isclose(mid.coordinates["liquid_mass_kg_h"], 2500.0, rel_tol=0, abs_tol=1e-12)
    assert math.isclose(mid.outlet_mgVOC_Nm3, direct.outlet_report.total_mgVOC_Nm3, rel_tol=1e-10)
    assert math.isclose(mid.flooding_percent, direct.hydraulics.flooding.flooding_percent, rel_tol=1e-10)


def test_phase16_temperature_sweep_reruns_property_resolver_and_hydraulics():
    registry, case = reference_case()
    sweep = run_parameter_sweep(
        case,
        [SweepAxis(SweepVariable.TEMPERATURE_C, 17.0, 27.0, 3)],
        registry=registry,
    )
    viscosities = [p.solvent_viscosity_Pa_s for p in sweep.points]
    densities = [p.carrier_density_kg_m3 for p in sweep.points]
    dps = [p.wet_pressure_drop_mbar_m for p in sweep.points]
    assert viscosities[0] > viscosities[-1]
    assert densities[0] > densities[-1]
    assert not math.isclose(dps[0], dps[-1], rel_tol=1e-6)


def test_phase16_two_axis_grid_size_and_coordinates_are_deterministic():
    registry, case = reference_case()
    sweep = run_parameter_sweep(
        case,
        [
            SweepAxis(SweepVariable.GAS_ACTUAL_M3_H, 80.0, 160.0, 4),
            SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 1500.0, 3000.0, 3),
        ],
        registry=registry,
    )
    assert sweep.is_two_dimensional
    assert sweep.total_points == 12
    assert sweep.successful_points == 12
    xs = sorted({p.coordinates["gas_actual_m3_h"] for p in sweep.points})
    ys = sorted({p.coordinates["liquid_mass_kg_h"] for p in sweep.points})
    assert len(xs) == 4
    assert len(ys) == 3


def test_phase16_component_metrics_include_A_HTU_NTU_and_removal():
    registry, case = reference_case()
    sweep = run_parameter_sweep(
        case,
        [SweepAxis(SweepVariable.PACKED_HEIGHT_M, 1.0, 2.0, 3)],
        registry=registry,
    )
    point = sweep.points[0]
    assert set(point.component_metrics) == {"ACN", "VAc"}
    for metrics in point.component_metrics.values():
        assert metrics.absorption_factor > 0
        assert metrics.HTU_OG_m > 0
        assert metrics.NTU_OG > 0
        assert metrics.removal_percent is not None


def test_phase16_feed_scale_is_canonical_and_does_not_change_registered_case():
    _, case = reference_case()
    scaled = apply_sweep_values(case, {SweepVariable.FEED_SCALE: 2.0})
    for sid in case.solute_ids:
        assert math.isclose(scaled.gas_inlet_y[sid], 2.0 * case.gas_inlet_y[sid], rel_tol=1e-15)
        assert math.isclose(case.gas_inlet_y[sid], case.gas_inlet_y[sid], rel_tol=0)
    assert scaled.operating == case.operating


def test_phase16_invalid_or_excessive_sweep_definitions_are_rejected():
    _, case = reference_case()
    with pytest.raises(InvalidSweepDefinition):
        SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 0.0, 1000.0, 3)
    with pytest.raises(InvalidSweepDefinition):
        run_parameter_sweep(
            case,
            [
                SweepAxis(SweepVariable.GAS_ACTUAL_M3_H, 50.0, 150.0, 16),
                SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 1000.0, 3000.0, 16),
            ],
        )
    assert MAX_SWEEP_POINTS == 225


def test_phase16_failed_points_are_retained_instead_of_aborting_grid():
    registry, case = reference_case()
    sweep = run_parameter_sweep(
        case,
        [SweepAxis(SweepVariable.FEED_SCALE, 1.0, 1000.0, 3)],
        registry=registry,
    )
    assert sweep.total_points == 3
    assert sweep.successful_points >= 1
    assert sweep.failed_points >= 1
    assert any(p.error for p in sweep.points if not p.success)


def test_phase16_helpers_return_base_and_sensible_default_bounds():
    _, case = reference_case()
    assert math.isclose(base_value_for_variable(case, SweepVariable.TEMPERATURE_C), 22.0, abs_tol=1e-12)
    lo, hi = suggested_sweep_bounds(case, SweepVariable.LIQUID_MASS_KG_H)
    assert lo < case.operating.liquid_mass_kg_h < hi


def test_phase16_screening_case_keeps_validity_status_at_each_point():
    registry = build_phase14_registry()
    case = GenericAbsorberCase(
        operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
        solute_ids=("VDC",),
        carrier_id="air",
        solvent_id="acrylonitrile",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"VDC": 1000e-6},
        liquid_inlet_x={"VDC": 0.0},
        solvent_evaporation_expected=True,
    )
    sweep = run_parameter_sweep(
        case,
        [SweepAxis(SweepVariable.LIQUID_MASS_KG_H, 1500.0, 3000.0, 3)],
        registry=registry,
    )
    assert sweep.successful_points == 3
    assert {p.status for p in sweep.points} == {"OUTSIDE_RECOMMENDED_RANGE"}
    assert {p.confidence for p in sweep.points} == {"SCREENING"}
