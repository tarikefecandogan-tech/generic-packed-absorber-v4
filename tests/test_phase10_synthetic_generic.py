import math

import pytest

from generic_absorber_v4 import (
    SYNTHETIC_CARRIER_ID,
    SYNTHETIC_PACKING_ID,
    SYNTHETIC_SOLUTES,
    SYNTHETIC_SOLVENT_ID,
    build_synthetic_registry,
    run_synthetic_generic_case,
)


@pytest.fixture(scope="module")
def report():
    return run_synthetic_generic_case()


def test_synthetic_registry_is_not_reference_chemistry():
    registry = build_synthetic_registry()
    assert set(registry.solutes) == set(SYNTHETIC_SOLUTES)
    assert set(registry.carriers) == {SYNTHETIC_CARRIER_ID}
    assert set(registry.solvents) == {SYNTHETIC_SOLVENT_ID}
    assert set(registry.packings) == {SYNTHETIC_PACKING_ID}
    assert not ({"ACN", "VAc"} & set(registry.solutes))
    assert "air" not in registry.carriers
    assert "water" not in registry.solvents


def test_all_synthetic_pairs_are_explicitly_ready():
    registry = build_synthetic_registry()
    for sid in SYNTHETIC_SOLUTES:
        availability = registry.availability(sid, SYNTHETIC_CARRIER_ID, SYNTHETIC_SOLVENT_ID)
        assert availability.status.value == "READY"
        assert availability.missing == ()


def test_resolver_handles_custom_constant_fluids_and_two_equilibrium_models(report):
    h = report.resolved_components["SYN_H"]
    m = report.resolved_components["SYN_M"]
    assert h.carrier.density.value == pytest.approx(120000.0 * 0.031 / (8.314462618 * 303.15))
    assert h.carrier.viscosity.value == pytest.approx(1.95e-5)
    assert h.solvent.density.value == pytest.approx(820.0)
    assert h.solvent.viscosity.value == pytest.approx(1.45e-3)
    assert h.solvent.surface_tension.value == pytest.approx(0.026)
    assert h.equilibrium.model == "henry_pc"
    assert m.equilibrium.model == "linear_m"


def test_common_onda_state_is_finite_and_shared(report):
    c = report.common
    assert c.Re_L == pytest.approx(11.225571013658259, rel=1e-12)
    assert c.Re_G == pytest.approx(84.47655836456161, rel=1e-12)
    assert c.wetting_fraction == pytest.approx(0.6445310518902228, rel=1e-12)
    assert 0 < c.effective_area_m2_m3 <= c.packing_area_m2_m3


def test_synthetic_henry_mass_transfer_baseline(report):
    mt = report.transfer_results["SYN_H"]
    assert mt.equilibrium_model == "henry_pc"
    assert mt.equilibrium_slope_m == pytest.approx(2.6739130434782608, rel=1e-12)
    assert mt.absorption_factor == pytest.approx(2.4903604051669634, rel=1e-10)
    assert mt.HTU_OG_m == pytest.approx(0.4926624918720292, rel=1e-10)
    assert mt.NTU_OG == pytest.approx(4.871489182950441, rel=1e-10)


def test_synthetic_linear_m_mass_transfer_baseline(report):
    mt = report.transfer_results["SYN_M"]
    assert mt.equilibrium_model == "linear_m"
    assert mt.equilibrium_slope_m == pytest.approx(0.85, rel=1e-14)
    assert mt.absorption_factor == pytest.approx(7.834126082750294, rel=1e-10)
    assert mt.HTU_OG_m == pytest.approx(0.3882571142953412, rel=1e-10)
    assert mt.NTU_OG == pytest.approx(6.181470761600409, rel=1e-10)


def test_two_component_countercurrent_solver_baseline(report):
    h = report.solver_results.components["SYN_H"]
    m = report.solver_results.components["SYN_M"]
    assert h.gas_outlet_y == pytest.approx(6.629670031869219e-05, rel=1e-8, abs=1e-12)
    assert h.removal_fraction == pytest.approx(0.966851649840654, rel=1e-8)
    assert m.gas_outlet_y == pytest.approx(2.090478523719668e-05, rel=1e-8, abs=1e-12)
    assert m.removal_fraction == pytest.approx(0.9790952147628034, rel=1e-8)
    for result in (h, m):
        assert abs(result.diagnostics.boundary_error_x) <= 1e-10
        assert result.diagnostics.relative_mass_balance_error <= 1e-10


def test_nonzero_synthetic_liquid_inlet_loading_is_preserved(report):
    m = report.solver_results.components["SYN_M"]
    assert m.liquid_inlet_x == pytest.approx(2.0e-5)
    assert m.liquid_bottom_x == pytest.approx(1.6703321226685844e-4, rel=1e-8)
    assert m.liquid_bottom_x > m.liquid_inlet_x


def test_generic_units_reconstruct_synthetic_multicomponent_outlet(report):
    b = report.gas_balance
    assert b.inlet.total_ppmv == pytest.approx(3000.0)
    assert b.outlet.total_ppmv == pytest.approx(87.20148555588887, rel=1e-9)
    assert b.inlet.total_mgVOC_Nm3 == pytest.approx(9904.537416196956, rel=1e-10)
    assert b.outlet.total_mgVOC_Nm3 == pytest.approx(276.9718509851437, rel=1e-9)
    assert b.total_captured_kg_h == pytest.approx(2.4656759126844934, rel=1e-9)
    # Different component removals mean outlet composition is not allowed to be
    # reconstructed from the inlet 2:1 molar split.
    inlet_ratio = b.inlet.components["SYN_H"].y / b.inlet.components["SYN_M"].y
    outlet_ratio = b.outlet.components["SYN_H"].y / b.outlet.components["SYN_M"].y
    assert inlet_ratio == pytest.approx(2.0)
    assert outlet_ratio != pytest.approx(inlet_ratio, rel=1e-3)


def test_generic_hydraulics_synthetic_baseline(report):
    h = report.hydraulics
    assert h.pressure_drop.wet_pressure_drop_Pa_m == pytest.approx(8.067534208188976, rel=1e-10)
    assert h.flooding.flood_velocity_m_s == pytest.approx(2.20158583922877, rel=1e-9)
    assert h.flooding.flooding_percent == pytest.approx(9.125496926107699, rel=1e-9)
    assert h.flooding.gpdc_valid
    assert h.flooding.hydraulic_regime == "UNDERLOADED / HIGH CAPACITY MARGIN"


def test_full_synthetic_generic_gate_and_name_independence(report):
    assert report.core_name_independence_pass
    assert report.legacy_identifier_hits == {}
    assert report.numerical_health_pass
    assert len(report.pre_applicability.blocks) == 0
    assert len(report.post_applicability.blocks) == 0
    assert report.pass_gate
