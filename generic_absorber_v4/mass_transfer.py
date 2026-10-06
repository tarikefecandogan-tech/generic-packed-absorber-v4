"""V4 Phase 4 generic Onda + two-film mass-transfer core.

This module is deliberately limited to the *coefficient layer* of the absorber.
It accepts already-resolved physical properties and a packing specification,
then calculates common Onda hydrodynamic groups and per-solute transfer
coefficients/diagnostics.

Phase 4 scope
-------------
- common column area / actual-flow fluxes
- Onda Re/Fr/We groups
- Onda effective wetted area
- per-solute ScL / ScG
- Onda kL / kG
- Henry/linear equilibrium slope m
- V3-compatible overall gas-side KG
- absorption factor A
- HTU_OG / NTU_OG
- film-resistance fractions

Explicitly NOT in Phase 4
-------------------------
- counter-current ODE / shooting method
- outlet concentration
- required height root solve
- pressure drop / GPDC flooding
- automatic diffusivity-estimation correlations

The numerical equations intentionally preserve the locked V3 reference basis so
that the first V4 acceptance gate is exact regression parity rather than a
physics revision.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .models import PackingSpec
from .resolver import (
    ResolvedCarrierState,
    ResolvedComponentProperties,
    ResolvedSolventState,
)

R = 8.314462618  # J/(mol K)
G_ACCEL = 9.81   # m/s²; locked V3 value


class MassTransferError(RuntimeError):
    """Base exception for Phase 4 coefficient calculations."""


class InvalidMassTransferInput(MassTransferError):
    """Raised when resolved values cannot form a physical Onda calculation."""


@dataclass(frozen=True)
class AbsorberOperatingPoint:
    """Canonical operating values required by the Phase 4 mass-transfer core.

    Gas flow is the *actual* volumetric flow at operating T/P.  Flow-reference
    conversion belongs to the unit/input layer, not this physics module.
    """

    diameter_m: float
    packed_height_m: float
    gas_actual_m3_h: float
    liquid_mass_kg_h: float
    temperature_K: float
    pressure_Pa: float

    def __post_init__(self) -> None:
        for label, value in (
            ("diameter_m", self.diameter_m),
            ("packed_height_m", self.packed_height_m),
            ("gas_actual_m3_h", self.gas_actual_m3_h),
            ("liquid_mass_kg_h", self.liquid_mass_kg_h),
            ("temperature_K", self.temperature_K),
            ("pressure_Pa", self.pressure_Pa),
        ):
            if not math.isfinite(value) or value <= 0:
                raise InvalidMassTransferInput(f"{label} must be finite and positive.")


@dataclass(frozen=True)
class CommonOndaState:
    """Quantities that are common to every dilute solute in one column case."""

    area_m2: float
    gas_molar_flow_mol_s: float
    liquid_molar_flow_mol_s: float
    gas_molar_flux_mol_m2_s: float
    liquid_molar_flux_mol_m2_s: float
    gas_mass_flux_kg_m2_s: float
    liquid_mass_flux_kg_m2_s: float
    gas_superficial_velocity_m_s: float
    Re_L: float
    Re_G: float
    Fr_L: float
    We_L: float
    effective_area_m2_m3: float
    wetting_fraction: float
    packing_area_m2_m3: float
    nominal_size_m: float
    pressure_Pa: float
    temperature_K: float
    packed_height_m: float


@dataclass(frozen=True)
class ComponentMassTransferResult:
    """Per-solute Onda/two-film coefficients and engineering diagnostics."""

    solute_id: str
    equilibrium_model: str
    gas_diffusivity_m2_s: float
    liquid_diffusivity_m2_s: float
    henry_effective_Pa_m3_mol: float
    equilibrium_slope_m: float
    Sc_L: float
    Sc_G: float
    k_L: float
    k_G: float
    K_G: float
    absorption_factor: float
    HTU_OG_m: float
    NTU_OG: float
    gas_resistance_fraction: float
    liquid_resistance_fraction: float



def _positive(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise InvalidMassTransferInput(f"{name} must be finite and positive.")
    return float(value)



def calculate_common_onda_state(
    operating: AbsorberOperatingPoint,
    packing: PackingSpec,
    carrier: ResolvedCarrierState,
    solvent: ResolvedSolventState,
) -> CommonOndaState:
    """Calculate V3-compatible common Onda quantities once per absorber case."""

    D = _positive("column diameter", operating.diameter_m)
    Z = _positive("packed height", operating.packed_height_m)
    Q_h = _positive("actual gas flow", operating.gas_actual_m3_h)
    L_h = _positive("liquid mass flow", operating.liquid_mass_kg_h)
    T = _positive("temperature", operating.temperature_K)
    P = _positive("pressure", operating.pressure_Pa)

    rho_G = _positive("carrier density", carrier.density.value)
    mu_G = _positive("carrier viscosity", carrier.viscosity.value)
    rho_L = _positive("solvent density", solvent.density.value)
    mu_L = _positive("solvent viscosity", solvent.viscosity.value)
    sigma_L = _positive("solvent surface tension", solvent.surface_tension.value)
    MW_L = _positive("solvent molecular weight", solvent.MW.value)

    a_t = _positive("packing specific area", packing.area_m2_m3)
    d_p = _positive("packing nominal size", packing.nominal_size_m)
    sigma_c = _positive("packing critical surface tension", packing.critical_surface_tension_N_m)

    area = math.pi * D**2 / 4.0
    Q_s = Q_h / 3600.0
    liquid_kg_s = L_h / 3600.0

    # Preserve the V3 definitions exactly.
    gas_molar_flow = Q_h * P / (R * T) / 3600.0
    liquid_molar_flow = L_h / MW_L / 3600.0
    gas_molar_flux = gas_molar_flow / area
    liquid_molar_flux = liquid_molar_flow / area
    gas_mass_flux = Q_h * rho_G / 3600.0 / area
    liquid_mass_flux = L_h / 3600.0 / area
    gas_velocity = Q_s / area

    Re_L = liquid_mass_flux / (a_t * mu_L)
    Re_G = gas_mass_flux / (a_t * mu_G)
    Fr_L = liquid_mass_flux**2 * a_t / (rho_L**2 * G_ACCEL)
    We_L = liquid_mass_flux**2 / (rho_L * sigma_L * a_t)

    for label, value in (("Re_L", Re_L), ("Re_G", Re_G), ("Fr_L", Fr_L), ("We_L", We_L)):
        if not math.isfinite(value) or value <= 0:
            raise InvalidMassTransferInput(f"{label} is non-positive or non-finite.")

    wet_exp = (
        -1.45
        * (sigma_c / sigma_L) ** 0.75
        * max(Re_L, 1e-30) ** 0.10
        * max(Fr_L, 1e-30) ** (-0.05)
        * max(We_L, 1e-30) ** 0.20
    )
    # This is the exact numerical guard used by the locked V3 engine.
    a_e = max(1e-8, min(a_t * (1.0 - math.exp(wet_exp)), a_t))
    wetting_fraction = a_e / a_t

    return CommonOndaState(
        area_m2=area,
        gas_molar_flow_mol_s=gas_molar_flow,
        liquid_molar_flow_mol_s=liquid_molar_flow,
        gas_molar_flux_mol_m2_s=gas_molar_flux,
        liquid_molar_flux_mol_m2_s=liquid_molar_flux,
        gas_mass_flux_kg_m2_s=gas_mass_flux,
        liquid_mass_flux_kg_m2_s=liquid_mass_flux,
        gas_superficial_velocity_m_s=gas_velocity,
        Re_L=Re_L,
        Re_G=Re_G,
        Fr_L=Fr_L,
        We_L=We_L,
        effective_area_m2_m3=a_e,
        wetting_fraction=wetting_fraction,
        packing_area_m2_m3=a_t,
        nominal_size_m=d_p,
        pressure_Pa=P,
        temperature_K=T,
        packed_height_m=Z,
    )



def calculate_component_mass_transfer(
    common: CommonOndaState,
    component: ResolvedComponentProperties,
) -> ComponentMassTransferResult:
    """Calculate one solute's Onda/two-film coefficients from resolved data.

    The function contains no chemical-name branching.  It can therefore be
    used with any future solute/carrier/solvent combination that the resolver
    can fully resolve.
    """

    rho_G = _positive("carrier density", component.carrier.density.value)
    mu_G = _positive("carrier viscosity", component.carrier.viscosity.value)
    rho_L = _positive("solvent density", component.solvent.density.value)
    mu_L = _positive("solvent viscosity", component.solvent.viscosity.value)
    MW_L = _positive("solvent molecular weight", component.solvent.MW.value)
    D_L = _positive("liquid diffusivity", component.liquid_diffusivity.value)
    D_G = _positive("gas diffusivity", component.gas_diffusivity.value)

    a_t = _positive("packing specific area", common.packing_area_m2_m3)
    d_p = _positive("packing nominal size", common.nominal_size_m)
    a_e = _positive("effective wetted area", common.effective_area_m2_m3)
    P = _positive("pressure", common.pressure_Pa)
    T = _positive("temperature", common.temperature_K)

    Sc_L = mu_L / (rho_L * D_L)
    k_L = (
        0.0051
        * (mu_L * G_ACCEL / rho_L) ** (1.0 / 3.0)
        * (common.liquid_mass_flux_kg_m2_s / (a_e * mu_L)) ** (2.0 / 3.0)
        * Sc_L ** (-0.5)
        * (a_t * d_p) ** 0.4
    )

    Sc_G = mu_G / (rho_G * D_G)
    k_G = (
        5.23
        * (a_t * D_G / (R * T))
        * common.Re_G ** 0.7
        * Sc_G ** (1.0 / 3.0)
        * (a_t * d_p) ** (-2.0)
    )

    eq = component.equilibrium
    if eq.model == "henry_pc":
        if eq.henry_Pa_m3_mol is None:
            raise InvalidMassTransferInput("Resolved Henry equilibrium has no Henry value.")
        H_effective = _positive("Henry constant", eq.henry_Pa_m3_mol.value)
        m = H_effective * (rho_L / MW_L) / P
    elif eq.model == "linear_m":
        if eq.linear_m_y_over_x is None:
            raise InvalidMassTransferInput("Resolved linear equilibrium has no m value.")
        m = _positive("linear equilibrium slope", eq.linear_m_y_over_x.value)
        # Convert the canonical y*=m x definition to the Hpc resistance basis
        # used by the locked V3 two-film KG formulation.
        H_effective = m * MW_L * P / rho_L
    else:
        raise InvalidMassTransferInput(
            f"Phase 4 mass-transfer core does not support equilibrium model '{eq.model}'."
        )

    K_G = 1.0 / (1.0 / k_G + H_effective / k_L)
    absorption_factor = common.liquid_molar_flow_mol_s / max(
        m * common.gas_molar_flow_mol_s, 1e-30
    )
    HTU_OG = common.gas_molar_flux_mol_m2_s / max(K_G * a_e * P, 1e-30)
    NTU_OG = common.packed_height_m / max(HTU_OG, 1e-30)

    total_resistance = 1.0 / K_G
    gas_resistance_fraction = (1.0 / k_G) / total_resistance
    liquid_resistance_fraction = (H_effective / k_L) / total_resistance

    result_values = {
        "Sc_L": Sc_L,
        "Sc_G": Sc_G,
        "k_L": k_L,
        "k_G": k_G,
        "K_G": K_G,
        "m": m,
        "absorption_factor": absorption_factor,
        "HTU_OG": HTU_OG,
        "NTU_OG": NTU_OG,
        "gas_resistance_fraction": gas_resistance_fraction,
        "liquid_resistance_fraction": liquid_resistance_fraction,
    }
    for label, value in result_values.items():
        if not math.isfinite(value) or value <= 0:
            raise InvalidMassTransferInput(f"Calculated {label} is non-positive or non-finite.")

    if abs((gas_resistance_fraction + liquid_resistance_fraction) - 1.0) > 1e-10:
        raise MassTransferError("Film resistance fractions failed the internal unity check.")

    return ComponentMassTransferResult(
        solute_id=component.solute_id,
        equilibrium_model=eq.model,
        gas_diffusivity_m2_s=D_G,
        liquid_diffusivity_m2_s=D_L,
        henry_effective_Pa_m3_mol=H_effective,
        equilibrium_slope_m=m,
        Sc_L=Sc_L,
        Sc_G=Sc_G,
        k_L=k_L,
        k_G=k_G,
        K_G=K_G,
        absorption_factor=absorption_factor,
        HTU_OG_m=HTU_OG,
        NTU_OG=NTU_OG,
        gas_resistance_fraction=gas_resistance_fraction,
        liquid_resistance_fraction=liquid_resistance_fraction,
    )



def evaluate_component_from_resolver(
    *,
    resolver,
    registry,
    solute_id: str,
    carrier_id: str,
    solvent_id: str,
    packing_id: str,
    operating: AbsorberOperatingPoint,
    component_overrides=None,
    carrier_overrides=None,
    solvent_overrides=None,
) -> tuple[CommonOndaState, ComponentMassTransferResult]:
    """Thin orchestration helper for UI/tests; core equations remain name-free."""

    resolved = resolver.resolve_component_properties(
        solute_id,
        carrier_id,
        solvent_id,
        operating.temperature_K,
        operating.pressure_Pa,
        component_overrides=component_overrides,
        carrier_overrides=carrier_overrides,
        solvent_overrides=solvent_overrides,
    )
    packing = registry.get_packing(packing_id)
    common = calculate_common_onda_state(
        operating, packing, resolved.carrier, resolved.solvent
    )
    result = calculate_component_mass_transfer(common, resolved)
    return common, result
