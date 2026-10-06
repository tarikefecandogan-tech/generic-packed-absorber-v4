"""Phase 6 generic hydraulics regression and behavior tests."""
from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    PackingSpec,
    build_reference_registry,
    build_reference_resolver,
    evaluate_hydraulics_from_resolver,
    resolve_packing_factor,
)

T = 295.15
P = 101325.0


def reference_operating(gas_actual_m3_h: float = 117.53):
    return AbsorberOperatingPoint(
        diameter_m=0.5,
        packed_height_m=1.4,
        gas_actual_m3_h=gas_actual_m3_h,
        liquid_mass_kg_h=2500.0,
        temperature_K=T,
        pressure_Pa=P,
    )


def reference_hydraulics(gas_actual_m3_h: float = 117.53):
    return evaluate_hydraulics_from_resolver(
        resolver=build_reference_resolver(),
        registry=build_reference_registry(),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=reference_operating(gas_actual_m3_h),
    )


def test_pressure_drop_matches_locked_v3_baseline():
    _, result = reference_hydraulics()
    dp = result.pressure_drop

    assert dp.Re_L_hydraulic == pytest.approx(17.47311987323168, rel=1e-12)
    assert dp.liquid_holdup_fraction == pytest.approx(0.05713056691346087, rel=1e-12)
    assert dp.dry_pressure_drop_Pa_m == pytest.approx(4.729685067279156, rel=1e-12)
    assert dp.wet_pressure_drop_Pa_m == pytest.approx(5.683288286702279, rel=1e-12)
    assert dp.wet_pressure_drop_mbar_m == pytest.approx(0.05683288286702279, rel=1e-12)
    assert dp.total_pressure_drop_Pa == pytest.approx(7.95660360138319, rel=1e-12)


def test_gpdc_flooding_matches_locked_v3_baseline():
    _, result = reference_hydraulics()
    fl = result.flooding

    assert fl.flood_velocity_m_s == pytest.approx(2.3208029666997687, rel=1e-10)
    assert fl.flood_gas_mass_flux_kg_m2_s == pytest.approx(2.7789191313105754, rel=1e-10)
    assert fl.F_LV_flood == pytest.approx(0.0440888436630539, rel=1e-10)
    assert fl.CP_flood == pytest.approx(1.8245028673067514, rel=1e-10)
    assert fl.packing_factor_ft_inv == pytest.approx(48.0, rel=1e-12)
    assert fl.liquid_kinematic_viscosity_cSt == pytest.approx(0.9568804057824821, rel=1e-12)
    assert fl.flooding_percent == pytest.approx(7.164371117329295, rel=1e-10)
    assert fl.hydraulic_regime == "UNDERLOADED / HIGH CAPACITY MARGIN"
    assert fl.gpdc_valid is True


def test_kister_gill_diagnostic_and_dp_ratio_match_v3_baseline():
    _, result = reference_hydraulics()
    fl = result.flooding

    assert fl.flood_pressure_drop_inH2O_ft == pytest.approx(1.7280913905215345, rel=1e-12)
    assert fl.flood_pressure_drop_Pa_m == pytest.approx(1412.232286238167, rel=1e-12)
    assert fl.flood_pressure_drop_mbar_m == pytest.approx(14.12232286238167, rel=1e-12)
    assert result.pressure_drop_ratio_to_flood == pytest.approx(0.004024329667353191, rel=1e-10)


def test_reference_packing_uses_empirical_factor_not_fallback():
    reg = build_reference_registry()
    fp = resolve_packing_factor(reg.get_packing("25mm_metal_pall_ring"))
    assert fp.packing_factor_ft_inv == 48.0
    assert fp.estimated is False
    assert fp.basis == "empirical"


def test_missing_packing_factor_uses_visible_geometric_fallback():
    packing = PackingSpec(
        id="synthetic_random",
        name="Synthetic random packing",
        packing_class="random",
        area_m2_m3=180.0,
        nominal_size_m=0.03,
        void_fraction=0.95,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.0,
        packing_factor_ft_inv=None,
        packing_factor_basis="geometric_fallback",
    )
    fp = resolve_packing_factor(packing)
    expected = (180.0 / 0.95**3) / 3.280839895
    assert fp.packing_factor_ft_inv == pytest.approx(expected, rel=1e-12)
    assert fp.estimated is True
    assert "geometric" in fp.basis.lower()


def test_hydraulics_path_does_not_require_solute_identity():
    common, result = reference_hydraulics()
    assert common.gas_superficial_velocity_m_s > 0
    assert result.flooding.flood_velocity_m_s > common.gas_superficial_velocity_m_s


def test_increasing_gas_flow_increases_pressure_drop_and_percent_flood():
    _, low = reference_hydraulics(117.53)
    _, high = reference_hydraulics(235.06)
    assert high.pressure_drop.wet_pressure_drop_Pa_m > low.pressure_drop.wet_pressure_drop_Pa_m
    assert high.flooding.flooding_percent > low.flooding.flooding_percent


def test_reference_flooding_values_are_physically_positive():
    _, result = reference_hydraulics()
    dp = result.pressure_drop
    fl = result.flooding
    assert 0 < dp.liquid_holdup_fraction < 0.962
    assert dp.wet_pressure_drop_Pa_m > dp.dry_pressure_drop_Pa_m > 0
    assert fl.flood_velocity_m_s > 0
    assert 0 < fl.flooding_percent < 100
