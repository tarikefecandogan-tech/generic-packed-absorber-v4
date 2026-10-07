"""Phase 10 synthetic generic-chemistry validation harness.

This module deliberately defines a chemistry that does not exist in the locked
V3 reference database.  Its purpose is architecture verification, not chemical
prediction.  The synthetic case exercises the complete generic chain using:

* two fictional solutes (one Henry, one direct-linear equilibrium model),
* a fictional constant-property carrier gas,
* a fictional constant-property solvent,
* a fictional random packing,
* independent counter-current ODE solves,
* generic reporting/unit conversion,
* generic hydraulics and applicability checks.

No ACN/VAc/Air/Water data are used by this case.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from pathlib import Path
from typing import Mapping, Tuple

from .applicability import (
    ApplicabilityCase,
    ApplicabilityReport,
    assess_post_applicability,
    assess_pre_applicability,
)
from .countercurrent import (
    ComponentBoundaryConditions,
    IndependentSolutesResult,
    solve_independent_solutes,
)
from .hydraulics import HydraulicResult, calculate_hydraulics
from .mass_transfer import (
    AbsorberOperatingPoint,
    CommonOndaState,
    ComponentMassTransferResult,
    calculate_common_onda_state,
    calculate_component_mass_transfer,
)
from .models import (
    CarrierGasSpec,
    ConfidenceClass,
    DataProvenance,
    EquilibriumPair,
    GasTransportPair,
    LiquidTransportPair,
    PackingSpec,
    SoluteSpec,
    SolventSpec,
)
from .registry import AbsorberDataRegistry
from .resolver import PropertyResolver, ResolvedComponentProperties
from .units import GasStreamBalance, gas_stream_balance


SYNTHETIC_CASE_ID = "SYNTHETIC_GENERIC_CASE_2026_10_06"
SYNTHETIC_SOLUTES: Tuple[str, str] = ("SYN_H", "SYN_M")
SYNTHETIC_CARRIER_ID = "carrier_x"
SYNTHETIC_SOLVENT_ID = "solvent_q"
SYNTHETIC_PACKING_ID = "packing_z"

SYNTHETIC_PROVENANCE = DataProvenance(
    source="Phase 10 synthetic verification fixture",
    method="fictional deterministic engineering test data",
    confidence=ConfidenceClass.B,
    reference_temperature_K=303.15,
    reference_pressure_Pa=120000.0,
    validity_note=(
        "Synthetic values exist only to verify generic software behavior; "
        "they must not be interpreted as real chemical-property data."
    ),
)


@dataclass(frozen=True)
class SyntheticGenericReport:
    case_id: str
    registry: AbsorberDataRegistry
    resolver: PropertyResolver
    operating: AbsorberOperatingPoint
    resolved_components: Mapping[str, ResolvedComponentProperties]
    common: CommonOndaState
    transfer_results: Mapping[str, ComponentMassTransferResult]
    solver_results: IndependentSolutesResult
    hydraulics: HydraulicResult
    gas_balance: GasStreamBalance
    pre_applicability: ApplicabilityReport
    post_applicability: ApplicabilityReport
    legacy_identifier_hits: Mapping[str, Tuple[str, ...]]

    @property
    def core_name_independence_pass(self) -> bool:
        return not any(self.legacy_identifier_hits.values())

    @property
    def numerical_health_pass(self) -> bool:
        return all(
            abs(result.diagnostics.boundary_error_x) <= 1e-8
            and result.diagnostics.relative_mass_balance_error <= 1e-7
            and math.isfinite(result.gas_outlet_y)
            and 0.0 <= result.gas_outlet_y < 1.0
            and 0.0 <= result.liquid_bottom_x < 1.0
            for result in self.solver_results.components.values()
        )

    @property
    def pass_gate(self) -> bool:
        return (
            self.core_name_independence_pass
            and self.numerical_health_pass
            and len(self.pre_applicability.blocks) == 0
            and len(self.post_applicability.blocks) == 0
            and len(self.solver_results.components) == 2
            and self.hydraulics.flooding.gpdc_valid
        )


def build_synthetic_registry() -> AbsorberDataRegistry:
    """Create a registry containing only fictional Phase 10 entities."""

    registry = AbsorberDataRegistry(reference_id=SYNTHETIC_CASE_ID)

    registry.register_solute(
        SoluteSpec(
            id="SYN_H",
            name="Synthetic Henry Solute",
            MW_kg_mol=0.064,
            carbon_atoms=2,
            formula="X2Y4",
        )
    )
    registry.register_solute(
        SoluteSpec(
            id="SYN_M",
            name="Synthetic Linear Solute",
            MW_kg_mol=0.094,
            carbon_atoms=5,
            formula="X5Z2",
        )
    )

    registry.register_carrier(
        CarrierGasSpec(
            id=SYNTHETIC_CARRIER_ID,
            name="Synthetic Carrier X",
            MW_kg_mol=0.031,
            viscosity_model="constant",
            mu_Pa_s=1.95e-5,
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_solvent(
        SolventSpec(
            id=SYNTHETIC_SOLVENT_ID,
            name="Synthetic Solvent Q",
            MW_kg_mol=0.046,
            property_model="constant",
            rho_kg_m3=820.0,
            mu_Pa_s=1.45e-3,
            sigma_N_m=0.026,
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_packing(
        PackingSpec(
            id=SYNTHETIC_PACKING_ID,
            name="Synthetic Random Packing Z",
            packing_class="random",
            area_m2_m3=180.0,
            nominal_size_m=0.032,
            void_fraction=0.950,
            critical_surface_tension_N_m=0.035,
            pressure_drop_psi=1.05,
            packing_factor_ft_inv=35.0,
            packing_factor_basis="empirical",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )

    # Explicit reference states are supplied so Phase 10 does not inherit the
    # legacy V3 diffusivity-reference-state warning.
    registry.register_gas_transport_pair(
        GasTransportPair(
            solute_id="SYN_H",
            carrier_id=SYNTHETIC_CARRIER_ID,
            D_ref_m2_s=1.15e-5,
            T_ref_K=303.15,
            P_ref_Pa=120000.0,
            model="fixed_reference",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_gas_transport_pair(
        GasTransportPair(
            solute_id="SYN_M",
            carrier_id=SYNTHETIC_CARRIER_ID,
            D_ref_m2_s=0.85e-5,
            T_ref_K=303.15,
            P_ref_Pa=120000.0,
            model="fixed_reference",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_liquid_transport_pair(
        LiquidTransportPair(
            solute_id="SYN_H",
            solvent_id=SYNTHETIC_SOLVENT_ID,
            D_ref_m2_s=1.20e-9,
            T_ref_K=303.15,
            model="fixed_reference",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_liquid_transport_pair(
        LiquidTransportPair(
            solute_id="SYN_M",
            solvent_id=SYNTHETIC_SOLVENT_ID,
            D_ref_m2_s=0.70e-9,
            T_ref_K=303.15,
            model="fixed_reference",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )

    # Exercise both supported Phase 4 equilibrium pathways.
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id="SYN_H",
            solvent_id=SYNTHETIC_SOLVENT_ID,
            model="henry_pc",
            H_ref_Pa_m3_mol=18.0,
            T_ref_K=303.15,
            temperature_coefficient_K=0.0,
            validity_temperature_min_K=290.0,
            validity_temperature_max_K=320.0,
            validity_note="Synthetic Phase 10 Henry fixture.",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id="SYN_M",
            solvent_id=SYNTHETIC_SOLVENT_ID,
            model="linear_m",
            m_y_over_x=0.85,
            validity_temperature_min_K=290.0,
            validity_temperature_max_K=320.0,
            validity_note="Synthetic Phase 10 direct-linear fixture.",
            provenance=SYNTHETIC_PROVENANCE,
        )
    )
    return registry


def synthetic_operating_point() -> AbsorberOperatingPoint:
    return AbsorberOperatingPoint(
        diameter_m=0.65,
        packed_height_m=2.40,
        gas_actual_m3_h=240.0,
        liquid_mass_kg_h=3500.0,
        temperature_K=303.15,
        pressure_Pa=120000.0,
    )


def synthetic_boundaries() -> Mapping[str, ComponentBoundaryConditions]:
    # Total gas solute fraction = 0.0030, comfortably within the dilute green zone.
    return {
        "SYN_H": ComponentBoundaryConditions(gas_inlet_y=0.0020, liquid_inlet_x=0.0),
        "SYN_M": ComponentBoundaryConditions(gas_inlet_y=0.0010, liquid_inlet_x=2.0e-5),
    }


def audit_core_for_legacy_identifiers() -> Mapping[str, Tuple[str, ...]]:
    """Assert that generic physics modules contain no legacy chemical names.

    This is a software-architecture check, not a scientific validation.  The
    database/reference modules are intentionally excluded because legacy names
    are expected there.
    """

    package_dir = Path(__file__).resolve().parent
    filenames = (
        "mass_transfer.py",
        "countercurrent.py",
        "hydraulics.py",
        "units.py",
        "applicability.py",
    )
    forbidden = ("ACN", "VAc", "water", "air")
    patterns = {token: re.compile(rf"\b{re.escape(token)}\b") for token in forbidden}
    hits: dict[str, Tuple[str, ...]] = {}
    for filename in filenames:
        text = (package_dir / filename).read_text(encoding="utf-8")
        file_hits = tuple(token for token, pattern in patterns.items() if pattern.search(text))
        if file_hits:
            hits[filename] = file_hits
    return hits


def run_synthetic_generic_case() -> SyntheticGenericReport:
    """Run the full Phase 1–8 chain on chemistry absent from the reference DB."""

    registry = build_synthetic_registry()
    resolver = PropertyResolver(registry)
    operating = synthetic_operating_point()
    boundaries = synthetic_boundaries()
    packing = registry.get_packing(SYNTHETIC_PACKING_ID)

    case = ApplicabilityCase(
        operating=operating,
        solute_ids=SYNTHETIC_SOLUTES,
        carrier_id=SYNTHETIC_CARRIER_ID,
        solvent_id=SYNTHETIC_SOLVENT_ID,
        packing_id=SYNTHETIC_PACKING_ID,
        gas_inlet_y={sid: boundaries[sid].gas_inlet_y for sid in SYNTHETIC_SOLUTES},
        liquid_inlet_x={sid: boundaries[sid].liquid_inlet_x for sid in SYNTHETIC_SOLUTES},
    )
    pre = assess_pre_applicability(registry, case)

    resolved: dict[str, ResolvedComponentProperties] = {}
    transfers: dict[str, ComponentMassTransferResult] = {}
    common: CommonOndaState | None = None
    for sid in SYNTHETIC_SOLUTES:
        rp = resolver.resolve_component_properties(
            sid,
            SYNTHETIC_CARRIER_ID,
            SYNTHETIC_SOLVENT_ID,
            operating.temperature_K,
            operating.pressure_Pa,
        )
        resolved[sid] = rp
        if common is None:
            common = calculate_common_onda_state(
                operating, packing, rp.carrier, rp.solvent
            )
        transfers[sid] = calculate_component_mass_transfer(common, rp)

    assert common is not None
    solved = solve_independent_solutes(common, transfers, boundaries)
    first = resolved[SYNTHETIC_SOLUTES[0]]
    hydraulics = calculate_hydraulics(common, packing, first.carrier, first.solvent)

    y_in = {sid: boundaries[sid].gas_inlet_y for sid in SYNTHETIC_SOLUTES}
    y_out = {sid: solved.components[sid].gas_outlet_y for sid in SYNTHETIC_SOLUTES}
    gas_balance = gas_stream_balance(
        y_in,
        y_out,
        registry.solutes,
        gas_molar_flow_mol_s=common.gas_molar_flow_mol_s,
    )

    post = assess_post_applicability(
        pre,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        packing=packing,
    )

    return SyntheticGenericReport(
        case_id=SYNTHETIC_CASE_ID,
        registry=registry,
        resolver=resolver,
        operating=operating,
        resolved_components=resolved,
        common=common,
        transfer_results=transfers,
        solver_results=solved,
        hydraulics=hydraulics,
        gas_balance=gas_balance,
        pre_applicability=pre,
        post_applicability=post,
        legacy_identifier_hits=audit_core_for_legacy_identifiers(),
    )
