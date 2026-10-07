"""Phase 11 validation fixture for built-in diffusivity estimators."""
from __future__ import annotations

from dataclasses import dataclass

from .models import CarrierGasSpec, EquilibriumPair, SoluteSpec, SolventSpec
from .registry import build_reference_registry
from .resolver import (
    ComponentPropertyOverrides,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
)

PHASE11_ESTIMATION_CASE_ID = "PHASE11_ESTIMATION_FIXTURE_2026_10_07"
ESTIMATION_SOLUTE_ID = "EST_X"
ESTIMATION_CARRIER_ID = "est_carrier"
ESTIMATION_SOLVENT_ID = "est_solvent"


@dataclass(frozen=True)
class Phase11EstimationReport:
    estimated_DG_m2_s: float
    estimated_DL_m2_s: float
    gas_tier: str
    liquid_tier: str
    gas_confidence: str
    liquid_confidence: str
    reference_database_priority_pass: bool
    override_priority_pass: bool
    missing_input_block_pass: bool

    @property
    def pass_gate(self) -> bool:
        return all((
            self.estimated_DG_m2_s > 0,
            self.estimated_DL_m2_s > 0,
            self.gas_tier == "CORRELATION_ESTIMATE",
            self.liquid_tier == "CORRELATION_ESTIMATE",
            self.gas_confidence == "C",
            self.liquid_confidence == "C",
            self.reference_database_priority_pass,
            self.override_priority_pass,
            self.missing_input_block_pass,
        ))


def build_phase11_estimation_registry():
    """Create a synthetic Phase 11 registry with estimator inputs but no DG/DL pairs.

    The locked V3 reference Air/Water records are intentionally *not* enriched
    with invented correlation metadata.  Phase 11 keeps the reference dataset
    immutable and demonstrates estimation on separate synthetic pure-component
    objects.
    """
    registry = build_reference_registry()
    registry.register_solute(
        SoluteSpec(
            id=ESTIMATION_SOLUTE_ID,
            name="Phase 11 Estimation Solute X",
            MW_kg_mol=0.078,
            carbon_atoms=6,
            formula="E6X",
            fuller_diffusion_volume=65.0,
            boiling_molar_volume_cm3_mol=100.0,
        )
    )
    registry.register_carrier(
        CarrierGasSpec(
            id=ESTIMATION_CARRIER_ID,
            name="Phase 11 Estimation Carrier",
            MW_kg_mol=0.029,
            viscosity_model="constant",
            mu_Pa_s=1.85e-5,
            fuller_diffusion_volume=20.1,
        )
    )
    registry.register_solvent(
        SolventSpec(
            id=ESTIMATION_SOLVENT_ID,
            name="Phase 11 Estimation Solvent",
            MW_kg_mol=18.015e-3,
            property_model="constant",
            rho_kg_m3=997.0,
            mu_Pa_s=0.0008904389816146542,
            sigma_N_m=0.072,
            wilke_chang_association_factor=2.6,
        )
    )
    # Equilibrium is supplied so complete component-property resolution can be
    # demonstrated. No gas/liquid transport pair is registered.
    registry.register_equilibrium_pair(
        EquilibriumPair(
            solute_id=ESTIMATION_SOLUTE_ID,
            solvent_id=ESTIMATION_SOLVENT_ID,
            model="linear_m",
            m_y_over_x=1.20,
            validity_note="Synthetic Phase 11 equilibrium fixture; not real chemistry.",
        )
    )
    return registry


def run_phase11_estimation_gate() -> Phase11EstimationReport:
    T_K = 298.15
    P_Pa = 101325.0
    registry = build_phase11_estimation_registry()
    resolver = PropertyResolver(registry)

    resolved = resolver.resolve_component_properties(
        ESTIMATION_SOLUTE_ID, ESTIMATION_CARRIER_ID, ESTIMATION_SOLVENT_ID, T_K, P_Pa
    )

    # Existing registered V3 pair values must retain priority over the newly
    # available built-in estimator mechanism.
    acn = resolver.resolve_component_properties("ACN", "air", "water", T_K, P_Pa)
    reference_database_priority_pass = (
        acn.gas_diffusivity.tier == ResolutionTier.DATABASE
        and acn.liquid_diffusivity.tier == ResolutionTier.DATABASE
        and acn.gas_diffusivity.value == 1.0e-5
        and acn.liquid_diffusivity.value == 1.0e-9
    )

    override = resolver.resolve_component_properties(
        ESTIMATION_SOLUTE_ID,
        ESTIMATION_CARRIER_ID,
        ESTIMATION_SOLVENT_ID,
        T_K,
        P_Pa,
        component_overrides=ComponentPropertyOverrides(
            gas_diffusivity_m2_s=2.2e-5,
            liquid_diffusivity_m2_s=2.2e-9,
        ),
    )
    override_priority_pass = (
        override.gas_diffusivity.tier == ResolutionTier.USER_OVERRIDE
        and override.liquid_diffusivity.tier == ResolutionTier.USER_OVERRIDE
        and override.gas_diffusivity.value == 2.2e-5
        and override.liquid_diffusivity.value == 2.2e-9
    )

    # Missing pure-component estimator inputs must still block resolution.
    missing_registry = build_reference_registry()
    missing_registry.register_solute(
        SoluteSpec(id="NO_EST_DATA", name="No estimator data", MW_kg_mol=0.050)
    )
    missing = PropertyResolver(missing_registry)
    blocked_g = blocked_l = False
    try:
        missing.resolve_gas_diffusivity("NO_EST_DATA", "air", T_K, P_Pa)
    except MissingPropertyError:
        blocked_g = True
    try:
        missing.resolve_liquid_diffusivity("NO_EST_DATA", "water", T_K)
    except MissingPropertyError:
        blocked_l = True

    return Phase11EstimationReport(
        estimated_DG_m2_s=resolved.gas_diffusivity.value,
        estimated_DL_m2_s=resolved.liquid_diffusivity.value,
        gas_tier=resolved.gas_diffusivity.tier.value,
        liquid_tier=resolved.liquid_diffusivity.tier.value,
        gas_confidence=resolved.gas_diffusivity.confidence.value,
        liquid_confidence=resolved.liquid_diffusivity.confidence.value,
        reference_database_priority_pass=reference_database_priority_pass,
        override_priority_pass=override_priority_pass,
        missing_input_block_pass=blocked_g and blocked_l,
    )
