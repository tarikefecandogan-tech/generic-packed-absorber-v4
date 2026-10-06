"""Phase 4 generic Onda/two-film mass-transfer regression tests."""
from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ComponentPropertyOverrides,
    InvalidMassTransferInput,
    SoluteSpec,
    build_reference_registry,
    build_reference_resolver,
    calculate_common_onda_state,
    calculate_component_mass_transfer,
    evaluate_component_from_resolver,
)
from generic_absorber_v4.resolver import PropertyResolver


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


def test_common_onda_state_matches_locked_v3_baseline():
    r = build_reference_resolver()
    reg = build_reference_registry()
    resolved = r.resolve_component_properties("ACN", "air", "water", T, P)
    common = calculate_common_onda_state(
        reference_operating(),
        reg.get_packing("25mm_metal_pall_ring"),
        resolved.carrier,
        resolved.solvent,
    )

    assert common.area_m2 == pytest.approx(0.19634954084936207, rel=1e-12)
    assert common.gas_molar_flow_mol_s == pytest.approx(1.3479875317121093, rel=1e-12)
    assert common.liquid_molar_flow_mol_s == pytest.approx(38.54812347734912, rel=1e-12)
    assert common.gas_molar_flux_mol_m2_s == pytest.approx(6.865244124743207, rel=1e-12)
    assert common.liquid_molar_flux_mol_m2_s == pytest.approx(196.32398074677934, rel=1e-12)
    assert common.gas_mass_flux_kg_m2_s == pytest.approx(0.19909207961755299, rel=1e-12)
    assert common.liquid_mass_flux_kg_m2_s == pytest.approx(3.53677651315323, rel=1e-12)
    assert common.Re_L == pytest.approx(17.47311987323168, rel=1e-12)
    assert common.Re_G == pytest.approx(51.51822401515305, rel=1e-12)
    assert common.Fr_L == pytest.approx(2.715156150626979e-4, rel=1e-12)
    assert common.We_L == pytest.approx(8.164012046442508e-4, rel=1e-12)
    assert common.effective_area_m2_m3 == pytest.approx(108.8616313828827, rel=1e-12)
    assert common.wetting_fraction == pytest.approx(0.5134982612400127, rel=1e-12)


def test_acn_mass_transfer_matches_locked_v3_baseline():
    common, result = evaluate_component_from_resolver(
        resolver=build_reference_resolver(),
        registry=build_reference_registry(),
        solute_id="ACN",
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=reference_operating(),
    )

    assert result.henry_effective_Pa_m3_mol == pytest.approx(1.0361313639640817, rel=1e-10)
    assert result.equilibrium_slope_m == pytest.approx(0.5663795710741079, rel=1e-10)
    assert result.Sc_L == pytest.approx(956.8804057824822, rel=1e-10)
    assert result.Sc_G == pytest.approx(1.5223678410752755, rel=1e-10)
    assert result.k_L == pytest.approx(7.11620147627118e-5, rel=1e-10)
    assert result.k_G == pytest.approx(2.92160381730706e-6, rel=1e-10)
    assert result.K_G == pytest.approx(2.802392662477365e-6, rel=1e-10)
    assert result.absorption_factor == pytest.approx(50.49051331523841, rel=1e-10)
    assert result.HTU_OG_m == pytest.approx(0.2220933460636276, rel=1e-10)
    assert result.NTU_OG == pytest.approx(6.303655759227084, rel=1e-10)
    assert common.effective_area_m2_m3 == pytest.approx(108.8616313828827, rel=1e-12)


def test_vac_mass_transfer_matches_locked_v3_baseline():
    _, result = evaluate_component_from_resolver(
        resolver=build_reference_resolver(),
        registry=build_reference_registry(),
        solute_id="VAc",
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        operating=reference_operating(),
    )

    assert result.henry_effective_Pa_m3_mol == pytest.approx(44.41319462729456, rel=1e-10)
    assert result.equilibrium_slope_m == pytest.approx(24.27754529773116, rel=1e-10)
    assert result.Sc_L == pytest.approx(1063.2004508694247, rel=1e-10)
    assert result.Sc_G == pytest.approx(1.6915198234169726, rel=1e-10)
    assert result.k_L == pytest.approx(6.751021486100878e-5, rel=1e-10)
    assert result.k_G == pytest.approx(2.7234307051966124e-6, rel=1e-10)
    assert result.K_G == pytest.approx(9.75554905395585e-7, rel=1e-10)
    assert result.absorption_factor == pytest.approx(1.1779113136890638, rel=1e-10)
    assert result.HTU_OG_m == pytest.approx(0.6379884514458747, rel=1e-10)
    assert result.NTU_OG == pytest.approx(2.194397087952261, rel=1e-10)


def test_resistance_fractions_close_exactly_to_unity():
    for sid in ("ACN", "VAc"):
        _, result = evaluate_component_from_resolver(
            resolver=build_reference_resolver(),
            registry=build_reference_registry(),
            solute_id=sid,
            carrier_id="air",
            solvent_id="water",
            packing_id="25mm_metal_pall_ring",
            operating=reference_operating(),
        )
        assert result.gas_resistance_fraction + result.liquid_resistance_fraction == pytest.approx(1.0, abs=1e-14)


def test_linear_m_override_reconstructs_same_two_film_basis():
    # For the same m, converting back to an equivalent Hpc must reproduce the
    # Henry-mode KG exactly on the locked coefficient basis.
    registry = build_reference_registry()
    resolver = PropertyResolver(registry)
    op = reference_operating()
    normal = resolver.resolve_component_properties("ACN", "air", "water", T, P)
    common = calculate_common_onda_state(op, registry.get_packing("25mm_metal_pall_ring"), normal.carrier, normal.solvent)
    henry_result = calculate_component_mass_transfer(common, normal)

    linear = resolver.resolve_component_properties(
        "ACN", "air", "water", T, P,
        component_overrides=ComponentPropertyOverrides(linear_m_y_over_x=henry_result.equilibrium_slope_m),
    )
    linear_result = calculate_component_mass_transfer(common, linear)

    assert linear_result.K_G == pytest.approx(henry_result.K_G, rel=1e-12)
    assert linear_result.absorption_factor == pytest.approx(henry_result.absorption_factor, rel=1e-12)
    assert linear_result.HTU_OG_m == pytest.approx(henry_result.HTU_OG_m, rel=1e-12)


def test_generic_core_has_no_reference_chemical_dependency():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    resolver = PropertyResolver(registry)
    resolved = resolver.resolve_component_properties(
        "X", "air", "water", T, P,
        component_overrides=ComponentPropertyOverrides(
            gas_diffusivity_m2_s=1.2e-5,
            liquid_diffusivity_m2_s=8.0e-10,
            linear_m_y_over_x=2.5,
        ),
    )
    common = calculate_common_onda_state(
        reference_operating(),
        registry.get_packing("25mm_metal_pall_ring"),
        resolved.carrier,
        resolved.solvent,
    )
    result = calculate_component_mass_transfer(common, resolved)

    assert result.solute_id == "X"
    assert result.K_G > 0
    assert result.HTU_OG_m > 0
    assert result.NTU_OG > 0


def test_common_state_is_component_independent_for_same_bulk_case():
    r = build_reference_resolver()
    reg = build_reference_registry()
    op = reference_operating()
    acn = r.resolve_component_properties("ACN", "air", "water", T, P)
    vac = r.resolve_component_properties("VAc", "air", "water", T, P)
    p = reg.get_packing("25mm_metal_pall_ring")
    c1 = calculate_common_onda_state(op, p, acn.carrier, acn.solvent)
    c2 = calculate_common_onda_state(op, p, vac.carrier, vac.solvent)
    assert c1 == c2


def test_invalid_operating_input_is_rejected_before_onda_calculation():
    with pytest.raises(InvalidMassTransferInput):
        AbsorberOperatingPoint(
            diameter_m=0.0,
            packed_height_m=1.4,
            gas_actual_m3_h=117.53,
            liquid_mass_kg_h=2500.0,
            temperature_K=T,
            pressure_Pa=P,
        )
