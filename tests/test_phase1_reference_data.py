"""Phase 1 integrity tests.

These tests do NOT run Onda, ODE, GPDC, pressure drop, or any other solver.
They only verify that the new V4 data objects preserve the locked V3 reference
constants exactly and that binary data live on the correct pair keys.
"""
from __future__ import annotations

import math

from generic_absorber_v4 import locked_reference_data


P_N = 101325.0


def test_reference_inventory_is_intentionally_small():
    db = locked_reference_data()
    assert set(db.solutes) == {"ACN", "VAc"}
    assert set(db.carriers) == {"air"}
    assert set(db.solvents) == {"water"}
    assert set(db.packings) == {"25mm_metal_pall_ring"}


def test_pure_component_reference_values():
    db = locked_reference_data()
    assert db.solutes["ACN"].MW_kg_mol == 53.06e-3
    assert db.solutes["ACN"].carbon_atoms == 3
    assert db.solutes["VAc"].MW_kg_mol == 86.09e-3
    assert db.solutes["VAc"].carbon_atoms == 4

    air = db.carriers["air"]
    assert air.MW_kg_mol == 0.029
    assert air.mu_ref_Pa_s == 1.716e-5
    assert air.T_ref_K == 273.15
    assert air.sutherland_S_K == 110.4

    water = db.solvents["water"]
    assert water.MW_kg_mol == 18.015e-3
    assert water.property_model_id == "legacy_v3_water"


def test_packing_reference_values():
    p = locked_reference_data().packings["25mm_metal_pall_ring"]
    assert p.name == "25mm Metal Pall Ring"
    assert p.area_m2_m3 == 212.0
    assert p.nominal_size_m == 0.025
    assert p.void_fraction == 0.962
    assert p.critical_surface_tension_N_m == 0.075
    assert p.pressure_drop_psi == 1.20
    assert p.packing_factor_ft_inv == 48.0
    assert p.packing_factor_basis == "empirical"


def test_transport_data_are_pair_based():
    db = locked_reference_data()
    assert set(db.gas_transport_pairs) == {("ACN", "air"), ("VAc", "air")}
    assert set(db.liquid_transport_pairs) == {("ACN", "water"), ("VAc", "water")}

    assert db.gas_transport_pairs[("ACN", "air")].D_ref_m2_s == 1.0e-5
    assert db.gas_transport_pairs[("VAc", "air")].D_ref_m2_s == 0.9e-5
    assert db.liquid_transport_pairs[("ACN", "water")].D_ref_m2_s == 1.0e-9
    assert db.liquid_transport_pairs[("VAc", "water")].D_ref_m2_s == 0.9e-9


def test_equilibrium_data_are_solute_solvent_pair_based():
    db = locked_reference_data()
    assert set(db.equilibrium_pairs) == {("ACN", "water"), ("VAc", "water")}

    acn = db.equilibrium_pairs[("ACN", "water")]
    vac = db.equilibrium_pairs[("VAc", "water")]

    assert acn.model == "henry_pc"
    assert vac.model == "henry_pc"
    assert math.isclose(acn.H_ref_Pa_m3_mol, 1.18e-5 * P_N, rel_tol=0.0, abs_tol=0.0)
    assert math.isclose(vac.H_ref_Pa_m3_mol, 5.11e-4 * P_N, rel_tol=0.0, abs_tol=0.0)
    assert acn.T_ref_K == 298.15
    assert vac.T_ref_K == 298.15
    assert acn.temperature_coefficient_K == 4200.0
    assert vac.temperature_coefficient_K == 4500.0


def test_reference_bundle_is_copy_safe():
    a = locked_reference_data()
    b = locked_reference_data()
    a.solutes.pop("ACN")
    assert "ACN" in b.solutes


def test_legacy_fixed_diffusivities_do_not_invent_reference_conditions():
    db = locked_reference_data()
    for pair in db.gas_transport_pairs.values():
        assert pair.model == "fixed_reference"
        assert pair.T_ref_K is None
        assert pair.P_ref_Pa is None
    for pair in db.liquid_transport_pairs.values():
        assert pair.model == "fixed_reference"
        assert pair.T_ref_K is None
