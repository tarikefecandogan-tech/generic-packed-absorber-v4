"""V4 Phase 3 property-resolution layer.

This module resolves the data registered in Phase 1/2 into operating-point
properties while preserving provenance and the selection path that produced
an engineering value.

Phase 3 precedence
------------------
    USER OVERRIDE > REGISTERED DATABASE VALUE > CORRELATION ESTIMATE > MISSING

Important scope boundary
------------------------
This module performs no Onda mass-transfer calculation, no two-film overall
coefficient calculation, no counter-current ODE solve, and no GPDC/pressure-
drop calculation.  Fuller and Wilke-Chang are intentionally *not* installed as
default estimators yet; Phase 3 only provides safe estimator hooks for the
later estimation-correlation phase.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Callable, Optional

from .models import ConfidenceClass, DataProvenance, EquilibriumPair
from .registry import AbsorberDataRegistry

R = 8.314462618  # J/(mol K)


class PropertyResolutionError(RuntimeError):
    """Base class for Phase 3 property-resolution failures."""


class MissingPropertyError(PropertyResolutionError):
    """Raised when a critical property cannot be resolved by the hierarchy."""

    def __init__(self, property_name: str, key: tuple[str, ...]):
        self.property_name = property_name
        self.key = key
        joined = " / ".join(key)
        super().__init__(
            f"{property_name} could not be resolved for {joined}. "
            "No user override, registered database value, or enabled correlation estimate was available."
        )


class UnsupportedPropertyModelError(PropertyResolutionError):
    """Raised when registered data request physics not supported in Phase 3."""


class InvalidPropertyOverrideError(PropertyResolutionError):
    """Raised when a user override is non-physical or internally ambiguous."""


class ResolutionTier(str, Enum):
    USER_OVERRIDE = "USER_OVERRIDE"
    DATABASE = "DATABASE"
    CORRELATION_ESTIMATE = "CORRELATION_ESTIMATE"


@dataclass(frozen=True)
class ResolvedProperty:
    """One scalar operating-point property with a complete audit trail."""

    name: str
    value: float
    unit: str
    tier: ResolutionTier
    method: str
    source: str
    confidence: ConfidenceClass
    estimated: bool = False
    note: str = ""

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("ResolvedProperty.name cannot be empty.")
        if not math.isfinite(self.value):
            raise ValueError(f"Resolved property {self.name} must be finite.")
        if not self.unit.strip():
            raise ValueError("ResolvedProperty.unit cannot be empty.")


@dataclass(frozen=True)
class CorrelationEstimate:
    """Result returned by an optional Phase 3 estimator hook."""

    value: float
    method: str
    source: str = "engineering correlation"
    note: str = ""

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or self.value <= 0:
            raise ValueError("Correlation estimate must be a finite positive value.")
        if not self.method.strip():
            raise ValueError("Correlation estimate method cannot be empty.")


@dataclass(frozen=True)
class ComponentPropertyOverrides:
    """Optional user-entered operating-point overrides for one solute path."""

    gas_diffusivity_m2_s: Optional[float] = None
    liquid_diffusivity_m2_s: Optional[float] = None
    henry_Pa_m3_mol: Optional[float] = None
    linear_m_y_over_x: Optional[float] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("gas_diffusivity_m2_s", self.gas_diffusivity_m2_s),
            ("liquid_diffusivity_m2_s", self.liquid_diffusivity_m2_s),
            ("henry_Pa_m3_mol", self.henry_Pa_m3_mol),
            ("linear_m_y_over_x", self.linear_m_y_over_x),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise InvalidPropertyOverrideError(f"{label} must be finite and positive.")
        if self.henry_Pa_m3_mol is not None and self.linear_m_y_over_x is not None:
            raise InvalidPropertyOverrideError(
                "Specify either a Henry override or a linear-m override, not both."
            )


@dataclass(frozen=True)
class CarrierPropertyOverrides:
    viscosity_Pa_s: Optional[float] = None
    density_kg_m3: Optional[float] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("viscosity_Pa_s", self.viscosity_Pa_s),
            ("density_kg_m3", self.density_kg_m3),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise InvalidPropertyOverrideError(f"{label} must be finite and positive.")


@dataclass(frozen=True)
class SolventPropertyOverrides:
    density_kg_m3: Optional[float] = None
    viscosity_Pa_s: Optional[float] = None
    surface_tension_N_m: Optional[float] = None

    def __post_init__(self) -> None:
        for label, value in (
            ("density_kg_m3", self.density_kg_m3),
            ("viscosity_Pa_s", self.viscosity_Pa_s),
            ("surface_tension_N_m", self.surface_tension_N_m),
        ):
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise InvalidPropertyOverrideError(f"{label} must be finite and positive.")


@dataclass(frozen=True)
class ResolvedCarrierState:
    carrier_id: str
    MW: ResolvedProperty
    density: ResolvedProperty
    viscosity: ResolvedProperty


@dataclass(frozen=True)
class ResolvedSolventState:
    solvent_id: str
    MW: ResolvedProperty
    density: ResolvedProperty
    viscosity: ResolvedProperty
    surface_tension: ResolvedProperty


@dataclass(frozen=True)
class ResolvedEquilibrium:
    solute_id: str
    solvent_id: str
    model: str
    henry_Pa_m3_mol: Optional[ResolvedProperty] = None
    linear_m_y_over_x: Optional[ResolvedProperty] = None

    @property
    def active_property(self) -> ResolvedProperty:
        if self.model == "henry_pc" and self.henry_Pa_m3_mol is not None:
            return self.henry_Pa_m3_mol
        if self.model == "linear_m" and self.linear_m_y_over_x is not None:
            return self.linear_m_y_over_x
        raise UnsupportedPropertyModelError(
            f"Resolved equilibrium model '{self.model}' has no active supported property."
        )


@dataclass(frozen=True)
class ResolvedComponentProperties:
    solute_id: str
    carrier: ResolvedCarrierState
    solvent: ResolvedSolventState
    gas_diffusivity: ResolvedProperty
    liquid_diffusivity: ResolvedProperty
    equilibrium: ResolvedEquilibrium


GasDiffusivityEstimator = Callable[[object, object, float, float], CorrelationEstimate]
LiquidDiffusivityEstimator = Callable[[object, object, float], CorrelationEstimate]


def _provenance_fields(
    provenance: Optional[DataProvenance],
    *,
    default_source: str,
    default_method: str,
    default_confidence: ConfidenceClass = ConfidenceClass.B,
) -> tuple[str, str, ConfidenceClass, str]:
    if provenance is None:
        return default_source, default_method, default_confidence, ""
    return (
        provenance.source,
        provenance.method,
        provenance.confidence,
        provenance.validity_note,
    )


def _user_property(name: str, value: float, unit: str, *, note: str = "") -> ResolvedProperty:
    return ResolvedProperty(
        name=name,
        value=float(value),
        unit=unit,
        tier=ResolutionTier.USER_OVERRIDE,
        method="explicit user operating-point override",
        source="user override",
        confidence=ConfidenceClass.A,
        estimated=False,
        note=note,
    )


def _database_property(
    name: str,
    value: float,
    unit: str,
    provenance: Optional[DataProvenance],
    *,
    default_method: str,
    note: str = "",
) -> ResolvedProperty:
    source, method, confidence, provenance_note = _provenance_fields(
        provenance,
        default_source="registered V4 database",
        default_method=default_method,
    )
    full_note = "; ".join(x for x in (provenance_note, note) if x)
    return ResolvedProperty(
        name=name,
        value=float(value),
        unit=unit,
        tier=ResolutionTier.DATABASE,
        method=method,
        source=source,
        confidence=confidence,
        estimated=False,
        note=full_note,
    )


def _estimated_property(name: str, estimate: CorrelationEstimate, unit: str) -> ResolvedProperty:
    return ResolvedProperty(
        name=name,
        value=float(estimate.value),
        unit=unit,
        tier=ResolutionTier.CORRELATION_ESTIMATE,
        method=estimate.method,
        source=estimate.source,
        confidence=ConfidenceClass.C,
        estimated=True,
        note=estimate.note,
    )


def _legacy_water_values(T_K: float) -> tuple[float, float, float]:
    """Exact water-property equations used by the locked V3 reference engine."""
    T_C = T_K - 273.15
    if not (-10.0 <= T_C <= 100.0):
        raise UnsupportedPropertyModelError(
            "legacy_v3_water correlation is intended for approximately -10 to 100 °C."
        )

    rho = 1000.0 * (
        1.0
        - ((T_C + 288.9414) / (508929.2 * (T_C + 68.12963)))
        * (T_C - 3.9863) ** 2
    )
    mu = 2.414e-5 * 10.0 ** (247.8 / (T_K - 140.0))
    Tc = 647.096
    tau = max(1e-12, 1.0 - T_K / Tc)
    sigma = 0.2358 * tau ** 1.256 * (1.0 - 0.625 * tau)
    return rho, mu, sigma


class PropertyResolver:
    """Resolve operating-point properties without performing absorber physics."""

    def __init__(
        self,
        registry: AbsorberDataRegistry,
        *,
        gas_diffusivity_estimator: Optional[GasDiffusivityEstimator] = None,
        liquid_diffusivity_estimator: Optional[LiquidDiffusivityEstimator] = None,
    ) -> None:
        self.registry = registry
        self.gas_diffusivity_estimator = gas_diffusivity_estimator
        self.liquid_diffusivity_estimator = liquid_diffusivity_estimator

    @staticmethod
    def _validate_state(T_K: float, P_Pa: float) -> None:
        if not math.isfinite(T_K) or T_K <= 0:
            raise PropertyResolutionError("Temperature must be finite and positive in K.")
        if not math.isfinite(P_Pa) or P_Pa <= 0:
            raise PropertyResolutionError("Pressure must be finite and positive in Pa absolute.")

    def resolve_carrier_state(
        self,
        carrier_id: str,
        T_K: float,
        P_Pa: float,
        *,
        overrides: Optional[CarrierPropertyOverrides] = None,
    ) -> ResolvedCarrierState:
        self._validate_state(T_K, P_Pa)
        overrides = overrides or CarrierPropertyOverrides()
        carrier = self.registry.get_carrier(carrier_id)

        MW = _database_property(
            "carrier molecular weight",
            carrier.MW_kg_mol,
            "kg/mol",
            carrier.provenance,
            default_method="registered carrier molecular weight",
        )

        if overrides.viscosity_Pa_s is not None:
            mu = _user_property("carrier viscosity", overrides.viscosity_Pa_s, "Pa·s")
        elif carrier.viscosity_model == "constant":
            mu = _database_property(
                "carrier viscosity",
                carrier.mu_Pa_s,
                "Pa·s",
                carrier.provenance,
                default_method="registered constant carrier viscosity",
            )
        elif carrier.viscosity_model == "sutherland":
            mu_value = (
                carrier.mu_ref_Pa_s
                * (T_K / carrier.T_ref_K) ** 1.5
                * (carrier.T_ref_K + carrier.sutherland_S_K)
                / (T_K + carrier.sutherland_S_K)
            )
            mu = _database_property(
                "carrier viscosity",
                mu_value,
                "Pa·s",
                carrier.provenance,
                default_method="Sutherland viscosity model from registered parameters",
                note=f"evaluated at T={T_K:g} K",
            )
        else:  # defensive future-proofing
            raise UnsupportedPropertyModelError(
                f"Unsupported carrier viscosity model '{carrier.viscosity_model}'."
            )

        if overrides.density_kg_m3 is not None:
            rho = _user_property("carrier density", overrides.density_kg_m3, "kg/m³")
        else:
            rho_value = P_Pa * carrier.MW_kg_mol / (R * T_K)
            rho = _database_property(
                "carrier density",
                rho_value,
                "kg/m³",
                carrier.provenance,
                default_method="ideal-gas density from registered molecular weight",
                note=f"ideal-gas assumption at T={T_K:g} K and P={P_Pa:g} Pa",
            )

        return ResolvedCarrierState(carrier.id, MW, rho, mu)

    def resolve_solvent_state(
        self,
        solvent_id: str,
        T_K: float,
        *,
        overrides: Optional[SolventPropertyOverrides] = None,
    ) -> ResolvedSolventState:
        if not math.isfinite(T_K) or T_K <= 0:
            raise PropertyResolutionError("Temperature must be finite and positive in K.")
        overrides = overrides or SolventPropertyOverrides()
        solvent = self.registry.get_solvent(solvent_id)

        MW = _database_property(
            "solvent molecular weight",
            solvent.MW_kg_mol,
            "kg/mol",
            solvent.provenance,
            default_method="registered solvent molecular weight",
        )

        if solvent.property_model == "correlation":
            if solvent.property_model_id != "legacy_v3_water":
                raise UnsupportedPropertyModelError(
                    f"Unsupported solvent property model '{solvent.property_model_id}'."
                )
            rho_db, mu_db, sigma_db = _legacy_water_values(T_K)
            model_method = "legacy V3 temperature-dependent water property correlations"
        elif solvent.property_model in ("constant", "pseudo_solvent"):
            rho_db, mu_db, sigma_db = (
                solvent.rho_kg_m3,
                solvent.mu_Pa_s,
                solvent.sigma_N_m,
            )
            model_method = "registered operating-point solvent constants"
        else:
            raise UnsupportedPropertyModelError(
                f"Unsupported solvent property model '{solvent.property_model}'."
            )

        rho = (
            _user_property("solvent density", overrides.density_kg_m3, "kg/m³")
            if overrides.density_kg_m3 is not None
            else _database_property(
                "solvent density", rho_db, "kg/m³", solvent.provenance,
                default_method=model_method, note=f"evaluated at T={T_K:g} K"
            )
        )
        mu = (
            _user_property("solvent viscosity", overrides.viscosity_Pa_s, "Pa·s")
            if overrides.viscosity_Pa_s is not None
            else _database_property(
                "solvent viscosity", mu_db, "Pa·s", solvent.provenance,
                default_method=model_method, note=f"evaluated at T={T_K:g} K"
            )
        )
        sigma = (
            _user_property("solvent surface tension", overrides.surface_tension_N_m, "N/m")
            if overrides.surface_tension_N_m is not None
            else _database_property(
                "solvent surface tension", sigma_db, "N/m", solvent.provenance,
                default_method=model_method, note=f"evaluated at T={T_K:g} K"
            )
        )
        return ResolvedSolventState(solvent.id, MW, rho, mu, sigma)

    def resolve_gas_diffusivity(
        self,
        solute_id: str,
        carrier_id: str,
        T_K: float,
        P_Pa: float,
        *,
        user_override_m2_s: Optional[float] = None,
    ) -> ResolvedProperty:
        self._validate_state(T_K, P_Pa)
        if user_override_m2_s is not None:
            if not math.isfinite(user_override_m2_s) or user_override_m2_s <= 0:
                raise InvalidPropertyOverrideError("Gas diffusivity override must be finite and positive.")
            return _user_property("gas diffusivity", user_override_m2_s, "m²/s")

        pair = self.registry.find_gas_transport_pair(solute_id, carrier_id)
        if pair is not None:
            if pair.model not in ("fixed_reference", "fuller"):
                raise UnsupportedPropertyModelError(
                    f"Unsupported gas transport pair model '{pair.model}'."
                )
            note = ""
            if pair.T_ref_K is None or pair.P_ref_Pa is None:
                note = (
                    "Legacy fixed value retained exactly; original reference temperature/pressure "
                    "were not defined in the locked V3 source."
                )
            return _database_property(
                "gas diffusivity",
                pair.D_ref_m2_s,
                "m²/s",
                pair.provenance,
                default_method=f"registered {pair.model} gas transport pair",
                note=note,
            )

        if self.gas_diffusivity_estimator is not None:
            solute = self.registry.get_solute(solute_id)
            carrier = self.registry.get_carrier(carrier_id)
            estimate = self.gas_diffusivity_estimator(solute, carrier, T_K, P_Pa)
            return _estimated_property("gas diffusivity", estimate, "m²/s")

        raise MissingPropertyError("gas diffusivity", (solute_id, carrier_id))

    def resolve_liquid_diffusivity(
        self,
        solute_id: str,
        solvent_id: str,
        T_K: float,
        *,
        user_override_m2_s: Optional[float] = None,
    ) -> ResolvedProperty:
        if not math.isfinite(T_K) or T_K <= 0:
            raise PropertyResolutionError("Temperature must be finite and positive in K.")
        if user_override_m2_s is not None:
            if not math.isfinite(user_override_m2_s) or user_override_m2_s <= 0:
                raise InvalidPropertyOverrideError("Liquid diffusivity override must be finite and positive.")
            return _user_property("liquid diffusivity", user_override_m2_s, "m²/s")

        pair = self.registry.find_liquid_transport_pair(solute_id, solvent_id)
        if pair is not None:
            if pair.model not in ("fixed_reference", "wilke_chang"):
                raise UnsupportedPropertyModelError(
                    f"Unsupported liquid transport pair model '{pair.model}'."
                )
            note = ""
            if pair.T_ref_K is None:
                note = (
                    "Legacy fixed value retained exactly; original reference temperature "
                    "was not defined in the locked V3 source."
                )
            return _database_property(
                "liquid diffusivity",
                pair.D_ref_m2_s,
                "m²/s",
                pair.provenance,
                default_method=f"registered {pair.model} liquid transport pair",
                note=note,
            )

        if self.liquid_diffusivity_estimator is not None:
            solute = self.registry.get_solute(solute_id)
            solvent = self.registry.get_solvent(solvent_id)
            estimate = self.liquid_diffusivity_estimator(solute, solvent, T_K)
            return _estimated_property("liquid diffusivity", estimate, "m²/s")

        raise MissingPropertyError("liquid diffusivity", (solute_id, solvent_id))

    def resolve_equilibrium(
        self,
        solute_id: str,
        solvent_id: str,
        T_K: float,
        *,
        henry_override_Pa_m3_mol: Optional[float] = None,
        linear_m_override: Optional[float] = None,
    ) -> ResolvedEquilibrium:
        if not math.isfinite(T_K) or T_K <= 0:
            raise PropertyResolutionError("Temperature must be finite and positive in K.")
        if henry_override_Pa_m3_mol is not None and linear_m_override is not None:
            raise InvalidPropertyOverrideError(
                "Specify either a Henry override or linear-m override, not both."
            )
        if henry_override_Pa_m3_mol is not None:
            if not math.isfinite(henry_override_Pa_m3_mol) or henry_override_Pa_m3_mol <= 0:
                raise InvalidPropertyOverrideError("Henry override must be finite and positive.")
            return ResolvedEquilibrium(
                solute_id,
                solvent_id,
                "henry_pc",
                henry_Pa_m3_mol=_user_property(
                    "Henry constant Hpc", henry_override_Pa_m3_mol, "Pa·m³/mol",
                    note=f"user value treated as operating-point H at T={T_K:g} K"
                ),
            )
        if linear_m_override is not None:
            if not math.isfinite(linear_m_override) or linear_m_override <= 0:
                raise InvalidPropertyOverrideError("Linear-m override must be finite and positive.")
            return ResolvedEquilibrium(
                solute_id,
                solvent_id,
                "linear_m",
                linear_m_y_over_x=_user_property(
                    "linear equilibrium slope m", linear_m_override, "dimensionless"
                ),
            )

        pair: Optional[EquilibriumPair] = self.registry.find_equilibrium_pair(solute_id, solvent_id)
        if pair is None:
            raise MissingPropertyError("equilibrium", (solute_id, solvent_id))

        if pair.model == "henry_pc":
            H = pair.H_ref_Pa_m3_mol * math.exp(
                pair.temperature_coefficient_K * (1.0 / pair.T_ref_K - 1.0 / T_K)
            )
            prop = _database_property(
                "Henry constant Hpc",
                H,
                "Pa·m³/mol",
                pair.provenance,
                default_method="registered Henry Hpc temperature relation",
                note=(
                    f"H_ref={pair.H_ref_Pa_m3_mol:g} Pa·m³/mol at {pair.T_ref_K:g} K; "
                    f"evaluated at T={T_K:g} K"
                ),
            )
            return ResolvedEquilibrium(solute_id, solvent_id, "henry_pc", henry_Pa_m3_mol=prop)

        if pair.model == "linear_m":
            prop = _database_property(
                "linear equilibrium slope m",
                pair.m_y_over_x,
                "dimensionless",
                pair.provenance,
                default_method="registered linear equilibrium slope",
            )
            return ResolvedEquilibrium(solute_id, solvent_id, "linear_m", linear_m_y_over_x=prop)

        if pair.model in ("tabulated", "reactive", "nonideal_unsupported", "no_data"):
            raise UnsupportedPropertyModelError(
                f"Equilibrium model '{pair.model}' for {solute_id}/{solvent_id} is not supported by V4 Phase 3."
            )
        raise UnsupportedPropertyModelError(f"Unknown equilibrium model '{pair.model}'.")

    def resolve_component_properties(
        self,
        solute_id: str,
        carrier_id: str,
        solvent_id: str,
        T_K: float,
        P_Pa: float,
        *,
        component_overrides: Optional[ComponentPropertyOverrides] = None,
        carrier_overrides: Optional[CarrierPropertyOverrides] = None,
        solvent_overrides: Optional[SolventPropertyOverrides] = None,
    ) -> ResolvedComponentProperties:
        component_overrides = component_overrides or ComponentPropertyOverrides()
        # Verify the solute identity early so typos are not disguised as missing-pair errors.
        self.registry.get_solute(solute_id)
        carrier = self.resolve_carrier_state(
            carrier_id, T_K, P_Pa, overrides=carrier_overrides
        )
        solvent = self.resolve_solvent_state(
            solvent_id, T_K, overrides=solvent_overrides
        )
        DG = self.resolve_gas_diffusivity(
            solute_id,
            carrier_id,
            T_K,
            P_Pa,
            user_override_m2_s=component_overrides.gas_diffusivity_m2_s,
        )
        DL = self.resolve_liquid_diffusivity(
            solute_id,
            solvent_id,
            T_K,
            user_override_m2_s=component_overrides.liquid_diffusivity_m2_s,
        )
        equilibrium = self.resolve_equilibrium(
            solute_id,
            solvent_id,
            T_K,
            henry_override_Pa_m3_mol=component_overrides.henry_Pa_m3_mol,
            linear_m_override=component_overrides.linear_m_y_over_x,
        )
        return ResolvedComponentProperties(
            solute_id=solute_id,
            carrier=carrier,
            solvent=solvent,
            gas_diffusivity=DG,
            liquid_diffusivity=DL,
            equilibrium=equilibrium,
        )


def build_reference_resolver() -> PropertyResolver:
    """Reference resolver with no default diffusivity estimators enabled."""
    from .registry import build_reference_registry

    return PropertyResolver(build_reference_registry())
