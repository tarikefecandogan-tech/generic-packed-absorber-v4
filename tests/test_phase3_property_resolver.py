"""Phase 3 property resolver tests.

These tests verify source precedence and locked V3 operating-point property
parity.  No Onda, ODE, pressure-drop, or flooding calculation is performed.
"""
from __future__ import annotations

import math
import pytest

from generic_absorber_v4 import (
    ComponentPropertyOverrides,
    CorrelationEstimate,
    EquilibriumPair,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    SoluteSpec,
    UnsupportedPropertyModelError,
    build_reference_registry,
    build_reference_resolver,
)

T = 22.0 + 273.15
P = 101325.0


def test_reference_bulk_fluid_properties_match_locked_v3_baseline():
    r = build_reference_resolver()
    air = r.resolve_carrier_state("air", T, P)
    water = r.resolve_solvent_state("water", T)

    assert air.density.value == pytest.approx(1.19739554421, rel=1e-10)
    assert air.viscosity.value == pytest.approx(1.82287646955e-5, rel=1e-10)
    assert water.density.value == pytest.approx(997.800320317, rel=1e-10)
    assert water.viscosity.value == pytest.approx(9.54775575395e-4, rel=1e-10)
    assert water.surface_tension.value == pytest.approx(0.0724322704793, rel=1e-10)
    assert air.viscosity.tier == ResolutionTier.DATABASE
    assert water.density.tier == ResolutionTier.DATABASE


def test_reference_pair_properties_match_locked_values_and_henry_temperature_relation():
    r = build_reference_resolver()
    acn = r.resolve_component_properties("ACN", "air", "water", T, P)
    vac = r.resolve_component_properties("VAc", "air", "water", T, P)

    assert acn.gas_diffusivity.value == 1.0e-5
    assert acn.liquid_diffusivity.value == 1.0e-9
    assert acn.equilibrium.henry_Pa_m3_mol.value == pytest.approx(1.03613136396, rel=1e-10)

    assert vac.gas_diffusivity.value == 0.9e-5
    assert vac.liquid_diffusivity.value == 0.9e-9
    assert vac.equilibrium.henry_Pa_m3_mol.value == pytest.approx(44.4131946273, rel=1e-10)

    assert acn.gas_diffusivity.tier == ResolutionTier.DATABASE
    assert acn.liquid_diffusivity.tier == ResolutionTier.DATABASE
    assert acn.equilibrium.active_property.tier == ResolutionTier.DATABASE


def test_user_override_has_priority_over_database_without_mutating_registry():
    registry = build_reference_registry()
    r = PropertyResolver(registry)
    resolved = r.resolve_component_properties(
        "ACN",
        "air",
        "water",
        T,
        P,
        component_overrides=ComponentPropertyOverrides(
            gas_diffusivity_m2_s=2.0e-5,
            liquid_diffusivity_m2_s=2.0e-9,
            henry_Pa_m3_mol=9.9,
        ),
    )
    assert resolved.gas_diffusivity.value == 2.0e-5
    assert resolved.liquid_diffusivity.value == 2.0e-9
    assert resolved.equilibrium.henry_Pa_m3_mol.value == 9.9
    assert resolved.gas_diffusivity.tier == ResolutionTier.USER_OVERRIDE
    assert resolved.liquid_diffusivity.tier == ResolutionTier.USER_OVERRIDE
    assert resolved.equilibrium.active_property.tier == ResolutionTier.USER_OVERRIDE

    # Registered reference data remain untouched.
    assert registry.require_gas_transport_pair("ACN", "air").D_ref_m2_s == 1.0e-5
    assert registry.require_liquid_transport_pair("ACN", "water").D_ref_m2_s == 1.0e-9


def test_database_has_priority_over_estimator_hook():
    def gas_estimator(solute, carrier, T_K, P_Pa):
        return CorrelationEstimate(8.8e-5, "synthetic gas estimator")

    def liquid_estimator(solute, solvent, T_K):
        return CorrelationEstimate(7.7e-9, "synthetic liquid estimator")

    r = PropertyResolver(
        build_reference_registry(),
        gas_diffusivity_estimator=gas_estimator,
        liquid_diffusivity_estimator=liquid_estimator,
    )
    assert r.resolve_gas_diffusivity("ACN", "air", T, P).value == 1.0e-5
    assert r.resolve_liquid_diffusivity("ACN", "water", T).value == 1.0e-9
    assert r.resolve_gas_diffusivity("ACN", "air", T, P).tier == ResolutionTier.DATABASE


def test_correlation_estimator_is_used_only_when_pair_is_missing():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))

    def gas_estimator(solute, carrier, T_K, P_Pa):
        assert solute.id == "X"
        return CorrelationEstimate(1.23e-5, "synthetic Fuller hook")

    def liquid_estimator(solute, solvent, T_K):
        assert solute.id == "X"
        return CorrelationEstimate(4.56e-10, "synthetic Wilke-Chang hook")

    r = PropertyResolver(
        registry,
        gas_diffusivity_estimator=gas_estimator,
        liquid_diffusivity_estimator=liquid_estimator,
    )
    dg = r.resolve_gas_diffusivity("X", "air", T, P)
    dl = r.resolve_liquid_diffusivity("X", "water", T)
    assert dg.value == 1.23e-5
    assert dl.value == 4.56e-10
    assert dg.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dl.tier == ResolutionTier.CORRELATION_ESTIMATE
    assert dg.estimated is True and dl.estimated is True


def test_missing_property_is_blocked_when_no_override_database_or_estimator_exists():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    r = PropertyResolver(registry)
    with pytest.raises(MissingPropertyError):
        r.resolve_gas_diffusivity("X", "air", T, P)
    with pytest.raises(MissingPropertyError):
        r.resolve_liquid_diffusivity("X", "water", T)
    with pytest.raises(MissingPropertyError):
        r.resolve_equilibrium("X", "water", T)


def test_unsupported_equilibrium_physics_is_explicitly_blocked():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    registry.register_equilibrium_pair(
        EquilibriumPair(solute_id="X", solvent_id="water", model="reactive")
    )
    r = PropertyResolver(registry)
    with pytest.raises(UnsupportedPropertyModelError):
        r.resolve_equilibrium("X", "water", T)


def test_linear_m_user_override_switches_equilibrium_model_without_database_mutation():
    r = build_reference_resolver()
    eq = r.resolve_equilibrium("ACN", "water", T, linear_m_override=1.25)
    assert eq.model == "linear_m"
    assert eq.linear_m_y_over_x.value == 1.25
    assert eq.linear_m_y_over_x.tier == ResolutionTier.USER_OVERRIDE
    # A normal resolve still returns the registered Henry relation.
    assert r.resolve_equilibrium("ACN", "water", T).model == "henry_pc"
