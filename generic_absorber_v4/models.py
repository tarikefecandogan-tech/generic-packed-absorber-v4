"""V4 Phase 1 canonical data objects.

This module is deliberately data-only.  It contains no Onda, ODE, GPDC,
pressure-drop, unit-conversion, or property-resolution calculations.

All numerical fields use canonical SI units unless the field name explicitly
states another conventional unit (for example ``packing_factor_ft_inv``).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional


class ConfidenceClass(str, Enum):
    """Provenance / data-confidence category defined by the V4 specification."""

    A = "A"  # user-verified / experimental
    B = "B"  # trusted literature / database
    C = "C"  # engineering correlation estimate
    D = "D"  # screening assumption / placeholder


@dataclass(frozen=True)
class DataProvenance:
    source: str
    method: str
    confidence: ConfidenceClass
    reference_temperature_K: Optional[float] = None
    reference_pressure_Pa: Optional[float] = None
    validity_note: str = ""

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("DataProvenance.source cannot be empty.")
        if not self.method.strip():
            raise ValueError("DataProvenance.method cannot be empty.")
        if self.reference_temperature_K is not None and self.reference_temperature_K <= 0:
            raise ValueError("Reference temperature must be positive when supplied.")
        if self.reference_pressure_Pa is not None and self.reference_pressure_Pa <= 0:
            raise ValueError("Reference pressure must be positive when supplied.")


@dataclass(frozen=True)
class SoluteSpec:
    id: str
    name: str
    MW_kg_mol: float
    carbon_atoms: int = 0
    formula: Optional[str] = None
    cas_number: Optional[str] = None
    fuller_diffusion_volume: Optional[float] = None
    boiling_molar_volume_cm3_mol: Optional[float] = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Solute id and name are required.")
        if self.MW_kg_mol <= 0:
            raise ValueError("Solute molecular weight must be positive.")
        if self.carbon_atoms < 0:
            raise ValueError("carbon_atoms cannot be negative.")


@dataclass(frozen=True)
class CarrierGasSpec:
    id: str
    name: str
    MW_kg_mol: float
    viscosity_model: Literal["sutherland", "constant"]
    mu_Pa_s: Optional[float] = None
    mu_ref_Pa_s: Optional[float] = None
    T_ref_K: Optional[float] = None
    sutherland_S_K: Optional[float] = None
    fuller_diffusion_volume: Optional[float] = None
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Carrier id and name are required.")
        if self.MW_kg_mol <= 0:
            raise ValueError("Carrier molecular weight must be positive.")
        if self.viscosity_model == "constant":
            if self.mu_Pa_s is None or self.mu_Pa_s <= 0:
                raise ValueError("Constant-viscosity carrier requires positive mu_Pa_s.")
        elif self.viscosity_model == "sutherland":
            required = (self.mu_ref_Pa_s, self.T_ref_K, self.sutherland_S_K)
            if any(v is None or v <= 0 for v in required):
                raise ValueError(
                    "Sutherland carrier requires positive mu_ref_Pa_s, T_ref_K, and sutherland_S_K."
                )


@dataclass(frozen=True)
class SolventSpec:
    id: str
    name: str
    MW_kg_mol: float
    property_model: Literal["correlation", "constant", "pseudo_solvent"]
    property_model_id: Optional[str] = None
    rho_kg_m3: Optional[float] = None
    mu_Pa_s: Optional[float] = None
    sigma_N_m: Optional[float] = None
    wilke_chang_association_factor: Optional[float] = None
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Solvent id and name are required.")
        if self.MW_kg_mol <= 0:
            raise ValueError("Solvent molecular weight must be positive.")
        if self.property_model == "correlation":
            if not self.property_model_id:
                raise ValueError("Correlation solvent requires property_model_id.")
        else:
            vals = (self.rho_kg_m3, self.mu_Pa_s, self.sigma_N_m)
            if any(v is None or v <= 0 for v in vals):
                raise ValueError(
                    "Constant/pseudo solvent requires positive rho_kg_m3, mu_Pa_s, and sigma_N_m."
                )


@dataclass(frozen=True)
class PackingSpec:
    id: str
    name: str
    packing_class: Literal["random"]
    area_m2_m3: float
    nominal_size_m: float
    void_fraction: float
    critical_surface_tension_N_m: float
    pressure_drop_psi: float
    packing_factor_ft_inv: Optional[float] = None
    packing_factor_basis: Literal["empirical", "literature", "geometric_fallback"] = "geometric_fallback"
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip():
            raise ValueError("Packing id and name are required.")
        if self.area_m2_m3 <= 0 or self.nominal_size_m <= 0:
            raise ValueError("Packing area and nominal size must be positive.")
        if not 0 < self.void_fraction < 1:
            raise ValueError("Packing void fraction must be between 0 and 1.")
        if self.critical_surface_tension_N_m <= 0 or self.pressure_drop_psi <= 0:
            raise ValueError("Packing surface tension and pressure-drop psi must be positive.")
        if self.packing_factor_ft_inv is not None and self.packing_factor_ft_inv <= 0:
            raise ValueError("Packing factor must be positive when supplied.")


@dataclass(frozen=True)
class GasTransportPair:
    """Gas-phase solute diffusivity for a specific solute–carrier pair."""

    solute_id: str
    carrier_id: str
    D_ref_m2_s: float
    T_ref_K: Optional[float] = None
    P_ref_Pa: Optional[float] = None
    model: Literal["fixed_reference", "fuller"] = "fixed_reference"
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if self.D_ref_m2_s <= 0:
            raise ValueError("Gas diffusivity must be positive.")
        if self.T_ref_K is not None and self.T_ref_K <= 0:
            raise ValueError("Gas diffusivity reference temperature must be positive when supplied.")
        if self.P_ref_Pa is not None and self.P_ref_Pa <= 0:
            raise ValueError("Gas diffusivity reference pressure must be positive when supplied.")


@dataclass(frozen=True)
class LiquidTransportPair:
    """Liquid-phase solute diffusivity for a specific solute–solvent pair."""

    solute_id: str
    solvent_id: str
    D_ref_m2_s: float
    T_ref_K: Optional[float] = None
    model: Literal["fixed_reference", "wilke_chang"] = "fixed_reference"
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if self.D_ref_m2_s <= 0:
            raise ValueError("Liquid diffusivity must be positive.")
        if self.T_ref_K is not None and self.T_ref_K <= 0:
            raise ValueError("Liquid diffusivity reference temperature must be positive when supplied.")


EquilibriumModelType = Literal[
    "henry_pc",
    "linear_m",
    "tabulated",
    "reactive",
    "nonideal_unsupported",
    "no_data",
]


@dataclass(frozen=True)
class EquilibriumPair:
    """Equilibrium definition belonging to one solute–solvent pair.

    V4.0 calculations will initially support ``henry_pc`` and ``linear_m``.
    Other model labels exist now so the data layer can explicitly represent
    unsupported physics instead of silently falling back to Henry's law.
    """

    solute_id: str
    solvent_id: str
    model: EquilibriumModelType
    H_ref_Pa_m3_mol: Optional[float] = None
    T_ref_K: Optional[float] = None
    temperature_coefficient_K: Optional[float] = None
    m_y_over_x: Optional[float] = None
    validity_temperature_min_K: Optional[float] = None
    validity_temperature_max_K: Optional[float] = None
    validity_note: str = ""
    provenance: Optional[DataProvenance] = None

    def __post_init__(self) -> None:
        if self.model == "henry_pc":
            if self.H_ref_Pa_m3_mol is None or self.H_ref_Pa_m3_mol <= 0:
                raise ValueError("Henry equilibrium requires positive H_ref_Pa_m3_mol.")
            if self.T_ref_K is None or self.T_ref_K <= 0:
                raise ValueError("Henry equilibrium requires positive T_ref_K.")
            if self.temperature_coefficient_K is None:
                raise ValueError("Henry equilibrium requires temperature_coefficient_K (0 is allowed).")
        elif self.model == "linear_m":
            if self.m_y_over_x is None or self.m_y_over_x <= 0:
                raise ValueError("Linear equilibrium requires positive m_y_over_x.")
        if (
            self.validity_temperature_min_K is not None
            and self.validity_temperature_max_K is not None
            and self.validity_temperature_min_K >= self.validity_temperature_max_K
        ):
            raise ValueError("Equilibrium validity Tmin must be below Tmax.")
