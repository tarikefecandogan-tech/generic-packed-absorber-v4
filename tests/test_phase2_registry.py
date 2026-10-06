"""Phase 2 registry/lookup tests.

No mass-transfer or hydraulic calculations are performed here.
"""
from __future__ import annotations

import pytest

from generic_absorber_v4 import (
    AbsorberDataRegistry,
    CarrierGasSpec,
    DataProvenance,
    DuplicateRegistrationError,
    EquilibriumPair,
    GasTransportPair,
    LiquidTransportPair,
    MissingPairDataError,
    SoluteSpec,
    SolventSpec,
    UnknownEntityError,
    build_reference_registry,
    locked_reference_data,
)
from generic_absorber_v4.models import ConfidenceClass


def test_reference_registry_inventory_matches_phase1_bundle():
    bundle = locked_reference_data()
    registry = build_reference_registry()
    assert registry.reference_id == bundle.reference_id
    assert registry.solutes == bundle.solutes
    assert registry.carriers == bundle.carriers
    assert registry.solvents == bundle.solvents
    assert registry.packings == bundle.packings
    assert registry.gas_transport_pairs == bundle.gas_transport_pairs
    assert registry.liquid_transport_pairs == bundle.liquid_transport_pairs
    assert registry.equilibrium_pairs == bundle.equilibrium_pairs


def test_exact_reference_pair_lookup():
    registry = build_reference_registry()
    assert registry.require_gas_transport_pair("ACN", "air").D_ref_m2_s == 1.0e-5
    assert registry.require_liquid_transport_pair("ACN", "water").D_ref_m2_s == 1.0e-9
    assert registry.require_equilibrium_pair("ACN", "water").model == "henry_pc"
    assert registry.require_gas_transport_pair("VAc", "air").D_ref_m2_s == 0.9e-5


def test_missing_pair_is_explicit_and_has_no_fallback():
    registry = build_reference_registry()
    # Add a real entity identity but deliberately no pair data.
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    assert registry.find_gas_transport_pair("X", "air") is None
    with pytest.raises(MissingPairDataError) as exc:
        registry.require_gas_transport_pair("X", "air")
    assert exc.value.pair_type == "gas_transport"
    assert exc.value.key == ("X", "air")
    assert "No fallback value was used" in str(exc.value)


def test_availability_report_marks_complete_reference_case_ready():
    registry = build_reference_registry()
    report = registry.availability("ACN", "air", "water")
    assert report.status.value == "READY"
    assert report.missing == ()


def test_availability_report_marks_partial_pair_incomplete():
    registry = build_reference_registry()
    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    registry.register_gas_transport_pair(
        GasTransportPair(solute_id="X", carrier_id="air", D_ref_m2_s=1.2e-5)
    )
    report = registry.availability("X", "air", "water")
    assert report.status.value == "INCOMPLETE"
    assert report.gas_transport_available is True
    assert report.missing == ("liquid_transport", "equilibrium")


def test_duplicate_registration_is_rejected_unless_replace_is_explicit():
    registry = build_reference_registry()
    with pytest.raises(DuplicateRegistrationError):
        registry.register_solute(registry.get_solute("ACN"))
    registry.register_solute(registry.get_solute("ACN"), replace=True)


def test_pair_registration_validates_foreign_keys():
    registry = build_reference_registry()
    with pytest.raises(UnknownEntityError):
        registry.register_gas_transport_pair(
            GasTransportPair(solute_id="NOT_REGISTERED", carrier_id="air", D_ref_m2_s=1e-5)
        )
    with pytest.raises(UnknownEntityError):
        registry.register_liquid_transport_pair(
            LiquidTransportPair(solute_id="ACN", solvent_id="not_registered", D_ref_m2_s=1e-9)
        )


def test_custom_complete_pair_can_be_registered_without_touching_reference_data():
    registry = build_reference_registry()
    p = DataProvenance(
        source="unit-test synthetic data",
        method="explicit user value",
        confidence=ConfidenceClass.A,
    )
    registry.register_solute(
        SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050, carbon_atoms=1)
    )
    registry.register_gas_transport_pair(
        GasTransportPair(
            solute_id="X", carrier_id="air", D_ref_m2_s=1.2e-5, provenance=p
        )
    )
    registry.register_liquid_transport_pair(
        LiquidTransportPair(
            solute_id="X", solvent_id="water", D_ref_m2_s=1.1e-9, provenance=p
        )
    )
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id="X",
            solvent_id="water",
            model="linear_m",
            m_y_over_x=2.0,
            provenance=p,
        )
    )
    assert registry.availability("X", "air", "water").status.value == "READY"
    assert locked_reference_data().solutes.keys() == {"ACN", "VAc"}
