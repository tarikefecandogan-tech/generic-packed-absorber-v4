"""Phase 5 generic counter-current solver regression and behavior tests."""
from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ComponentBoundaryConditions,
    CounterCurrentSolverError,
    InvalidBoundaryCondition,
    build_reference_registry,
    build_reference_resolver,
    evaluate_component_from_resolver,
    solve_component_countercurrent,
    solve_independent_solutes,
)

T = 295.15
P = 101325.0


def reference_operating():
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=117.53,
        liquid_mass_kg_h=2500.0,
        temperature_K=T,
        pressure_Pa=P,
    )


def reference_transfer(solute_id: str):
    return evaluate_component_from_resolver(
        resolver=build_reference_resolver(),
        registry=build_reference_registry(),
        solute_id=solute_id,
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=reference_operating(),
    )


def test_acn_countercurrent_matches_locked_v3_outlet():
    common, mt = reference_transfer("ACN")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=0.001964284929935824, liquid_inlet_x=0.0),
    )

    assert result.liquid_bottom_x == pytest.approx(6.854941710034729e-05, rel=1e-8, abs=1e-14)
    assert result.gas_outlet_y == pytest.approx(3.991282910574221e-06, rel=1e-8, abs=1e-14)
    assert result.removal_fraction == pytest.approx(0.9979680733432574, rel=1e-8)
    assert result.diagnostics.mode == "NET_ABSORPTION"
    assert abs(result.diagnostics.boundary_error_x) < 1e-10
    assert result.diagnostics.relative_mass_balance_error < 1e-8


def test_vac_countercurrent_matches_locked_v3_outlet():
    common, mt = reference_transfer("VAc")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=9.112428087594802e-05, liquid_inlet_x=0.0),
    )

    assert result.liquid_bottom_x == pytest.approx(2.301816729348773e-06, rel=1e-8, abs=1e-14)
    assert result.gas_outlet_y == pytest.approx(2.5299699106660017e-05, rel=1e-8, abs=1e-14)
    assert result.removal_fraction == pytest.approx(0.7223605073920776, rel=1e-8)
    assert result.diagnostics.relative_mass_balance_error < 1e-8


def test_nonzero_solvent_loading_is_supported_and_boundary_closes():
    common, mt = reference_transfer("ACN")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=0.0010, liquid_inlet_x=2.0e-5),
    )
    assert result.liquid_inlet_x == pytest.approx(2.0e-5)
    assert result.liquid_x_profile[-1] == pytest.approx(2.0e-5, abs=1e-10)
    assert result.diagnostics.relative_mass_balance_error < 1e-8


def test_desorption_is_not_clamped_when_loaded_solvent_enters():
    common, mt = reference_transfer("ACN")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=0.0, liquid_inlet_x=2.0e-5),
    )
    assert result.gas_outlet_y > 0.0
    assert result.liquid_bottom_x < result.liquid_inlet_x
    assert result.removal_fraction is None
    assert result.diagnostics.mode == "NET_DESORPTION"
    assert result.diagnostics.min_driving_force_y < 0.0
    assert result.diagnostics.relative_mass_balance_error < 1e-8


def test_only_both_zero_boundaries_take_zero_transfer_shortcut():
    common, mt = reference_transfer("ACN")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=0.0, liquid_inlet_x=0.0),
    )
    assert result.gas_outlet_y == 0.0
    assert result.liquid_bottom_x == 0.0
    assert result.diagnostics.mode == "NO_TRANSFER"
    assert result.diagnostics.ode_function_evaluations == 0


def test_profiles_and_driving_force_have_matching_shapes():
    common, mt = reference_transfer("VAc")
    result = solve_component_countercurrent(
        common,
        mt,
        ComponentBoundaryConditions(gas_inlet_y=9.112428087594802e-05),
    )
    assert len(result.z_m) == len(result.gas_y_profile)
    assert len(result.z_m) == len(result.liquid_x_profile)
    assert len(result.z_m) == len(result.driving_force_profile_y)
    assert result.z_m[0] == 0.0
    assert result.z_m[-1] == pytest.approx(common.packed_height_m)


def test_independent_multisolute_orchestration_solves_two_components():
    common_a, acn = reference_transfer("ACN")
    common_v, vac = reference_transfer("VAc")
    assert common_a == common_v
    results = solve_independent_solutes(
        common_a,
        {"ACN": acn, "VAc": vac},
        {
            "ACN": ComponentBoundaryConditions(0.001964284929935824),
            "VAc": ComponentBoundaryConditions(9.112428087594802e-05),
        },
    )
    assert set(results.components) == {"ACN", "VAc"}
    assert results.components["ACN"].gas_outlet_y < results.components["ACN"].gas_inlet_y
    assert results.components["VAc"].gas_outlet_y < results.components["VAc"].gas_inlet_y


def test_multisolute_keys_must_match():
    common, acn = reference_transfer("ACN")
    with pytest.raises(CounterCurrentSolverError):
        solve_independent_solutes(
            common,
            {"ACN": acn},
            {"WRONG": ComponentBoundaryConditions(0.001)},
        )


def test_invalid_mole_fraction_boundary_is_rejected():
    with pytest.raises(InvalidBoundaryCondition):
        ComponentBoundaryConditions(gas_inlet_y=-1e-4)
    with pytest.raises(InvalidBoundaryCondition):
        ComponentBoundaryConditions(gas_inlet_y=1.0)
