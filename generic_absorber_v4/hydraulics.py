"""V4 Phase 6 generic packed-column hydraulics.

This module intentionally preserves the locked V3 screening hydraulics while
removing chemical-name hard-coding.  It consumes a common operating state,
resolved carrier/solvent properties, and packing metadata.

Phase 6 scope
-------------
- liquid holdup screening correlation
- dry and wet packed-bed pressure drop
- empirical/literature packing-factor use with geometric fallback
- GPDC flooding-velocity root solve
- percent flood and hydraulic regime
- Kister-Gill flooding pressure-drop diagnostic

Important limitations
---------------------
The pressure-drop expression is a screening model, not a vendor-rated packed-
bed hydraulic model.  GPDC is used only inside its explicit F_LV correlation
range.  Foaming, entrainment, distributors, supports, demisters, fouling and
maldistribution are not modeled here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import brentq

from .mass_transfer import (
    AbsorberOperatingPoint,
    CommonOndaState,
    calculate_common_onda_state,
)
from .models import PackingSpec
from .resolver import (
    CarrierPropertyOverrides,
    PropertyResolver,
    ResolvedCarrierState,
    ResolvedSolventState,
    SolventPropertyOverrides,
)

G_ACCEL = 9.81
FT_PER_M = 3.280839895
PA_PER_INH2O = 249.08891
M_PER_FT = 0.3048
MBAR_PER_PA = 0.01
GPDC_FLV_MIN = 0.01
GPDC_FLV_MAX = 8.0


class HydraulicsError(RuntimeError):
    """Base exception for Phase 6 hydraulic calculations."""


class InvalidHydraulicInput(HydraulicsError):
    """Raised when a required hydraulic input is nonphysical."""


class GPDCFloodingSolveError(HydraulicsError):
    """Raised when no valid GPDC flood-velocity root can be found."""


@dataclass(frozen=True)
class PackingFactorResult:
    packing_factor_ft_inv: float
    basis: str
    estimated: bool


@dataclass(frozen=True)
class PressureDropResult:
    Re_L_hydraulic: float
    liquid_holdup_fraction: float
    dry_pressure_drop_Pa_m: float
    wet_pressure_drop_Pa_m: float
    wet_pressure_drop_mbar_m: float
    total_pressure_drop_Pa: float
    total_pressure_drop_mbar: float


@dataclass(frozen=True)
class FloodingResult:
    gas_superficial_velocity_m_s: float
    flood_velocity_m_s: float
    gas_mass_flux_kg_m2_s: float
    flood_gas_mass_flux_kg_m2_s: float
    liquid_mass_flux_kg_m2_s: float
    F_LV_flood: float
    CP_flood: float
    packing_factor_ft_inv: float
    packing_factor_basis: str
    packing_factor_estimated: bool
    liquid_kinematic_viscosity_cSt: float
    F_oper: float
    F_flood: float
    flooding_fraction: float
    flooding_percent: float
    hydraulic_regime: str
    flood_pressure_drop_inH2O_ft: float
    flood_pressure_drop_Pa_m: float
    flood_pressure_drop_mbar_m: float
    gpdc_valid: bool


@dataclass(frozen=True)
class HydraulicResult:
    pressure_drop: PressureDropResult
    flooding: FloodingResult
    pressure_drop_ratio_to_flood: float



def _positive(name: str, value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        raise InvalidHydraulicInput(f"{name} must be finite and positive.")
    return float(value)



def resolve_packing_factor(packing: PackingSpec) -> PackingFactorResult:
    """Return V3-compatible GPDC packing factor information.

    Registered empirical/literature values are preferred.  When none exists,
    the legacy geometric fallback a/eps^3 is converted from 1/m to 1/ft.
    """

    if packing.packing_factor_ft_inv is not None:
        return PackingFactorResult(
            packing_factor_ft_inv=_positive(
                "packing factor", packing.packing_factor_ft_inv
            ),
            basis=packing.packing_factor_basis,
            estimated=False,
        )

    area = _positive("packing specific area", packing.area_m2_m3)
    eps = _positive("packing void fraction", packing.void_fraction)
    Fp_m_inv = area / max(eps, 1e-12) ** 3
    return PackingFactorResult(
        packing_factor_ft_inv=Fp_m_inv / FT_PER_M,
        basis="geometric a/eps^3 fallback",
        estimated=True,
    )



def gpdc_flood_curve_cp(F_LV: float) -> float:
    """Locked V3 cubic fit to the GPDC flood curve."""

    if not math.isfinite(F_LV) or F_LV <= 0:
        raise InvalidHydraulicInput("F_LV must be finite and positive.")
    x = math.log10(F_LV)
    return 0.0394 * x**3 + 0.0552 * x**2 - 0.7634 * x + 0.7863



def calculate_pressure_drop(
    common: CommonOndaState,
    packing: PackingSpec,
    carrier: ResolvedCarrierState,
    solvent: ResolvedSolventState,
) -> PressureDropResult:
    """Calculate the locked V3 packed-bed pressure-drop screening model."""

    a = _positive("packing specific area", packing.area_m2_m3)
    eps = _positive("packing void fraction", packing.void_fraction)
    psi = _positive("packing pressure-drop psi", packing.pressure_drop_psi)
    rho_L = _positive("solvent density", solvent.density.value)
    mu_L = _positive("solvent viscosity", solvent.viscosity.value)
    rho_G = _positive("carrier density", carrier.density.value)
    U_G = _positive("gas superficial velocity", common.gas_superficial_velocity_m_s)
    Lp = _positive("liquid mass flux", common.liquid_mass_flux_kg_m2_s)

    Re_L = Lp / (a * mu_L)
    h_L = max(
        1e-6,
        min(
            (12.0 * mu_L * (Lp / rho_L) * a**2 / (G_ACCEL * rho_L))
            ** (1.0 / 3.0),
            0.90 * eps,
        ),
    )
    dP_dry = psi * (a / max(eps, 1e-12) ** 3) * (rho_G * U_G**2 / 2.0)
    dP_wet = dP_dry * (eps / max(eps - h_L, 1e-12)) ** 3

    return PressureDropResult(
        Re_L_hydraulic=Re_L,
        liquid_holdup_fraction=h_L,
        dry_pressure_drop_Pa_m=dP_dry,
        wet_pressure_drop_Pa_m=dP_wet,
        wet_pressure_drop_mbar_m=dP_wet * MBAR_PER_PA,
        total_pressure_drop_Pa=dP_wet * common.packed_height_m,
        total_pressure_drop_mbar=dP_wet * common.packed_height_m * MBAR_PER_PA,
    )



def _hydraulic_regime(flooding_percent: float) -> str:
    if flooding_percent < 40.0:
        return "UNDERLOADED / HIGH CAPACITY MARGIN"
    if flooding_percent < 60.0:
        return "LOW-MODERATE HYDRAULIC LOADING"
    if flooding_percent < 80.0:
        return "NORMAL DESIGN REGION"
    if flooding_percent < 90.0:
        return "HIGH HYDRAULIC LOADING"
    if flooding_percent < 100.0:
        return "NEAR FLOODING"
    return "FLOODING PREDICTED"



def calculate_flooding(
    common: CommonOndaState,
    packing: PackingSpec,
    carrier: ResolvedCarrierState,
    solvent: ResolvedSolventState,
) -> FloodingResult:
    """Solve the V3-compatible GPDC flooding velocity for generic fluids."""

    rho_L = _positive("solvent density", solvent.density.value)
    mu_L = _positive("solvent viscosity", solvent.viscosity.value)
    rho_G = _positive("carrier density", carrier.density.value)
    U_oper = _positive("gas superficial velocity", common.gas_superficial_velocity_m_s)
    Lp = _positive("liquid mass flux", common.liquid_mass_flux_kg_m2_s)
    Gp_oper = _positive("gas mass flux", common.gas_mass_flux_kg_m2_s)

    if rho_L <= rho_G:
        raise InvalidHydraulicInput(
            "GPDC flooding calculation requires solvent density greater than carrier density."
        )

    fp = resolve_packing_factor(packing)
    Fp_ft = fp.packing_factor_ft_inv
    nu_cSt = (mu_L / rho_L) * 1e6

    # This is algebraically the V3 F_LV numerator expressed in terms of U.
    K_flv = (Lp / rho_G) * math.sqrt(rho_G / rho_L)
    U_lo = max(1e-4, K_flv / GPDC_FLV_MAX)
    U_hi = min(50.0, max(U_lo * 1.01, K_flv / GPDC_FLV_MIN))

    def residual(U_flood_m_s: float) -> float:
        G_flood = rho_G * U_flood_m_s
        F_LV = (Lp / G_flood) * math.sqrt(rho_G / rho_L)
        CP_corr = gpdc_flood_curve_cp(F_LV)
        U_flood_ft_s = U_flood_m_s * FT_PER_M
        C_s = U_flood_ft_s * math.sqrt(rho_G / max(rho_L - rho_G, 1e-30))
        CP_trial = C_s * math.sqrt(Fp_ft) * nu_cSt**0.05
        return CP_trial - CP_corr

    grid = np.geomspace(U_lo, U_hi, 400)
    valid_pairs: list[tuple[float, float]] = []
    prev_u = float(grid[0])
    prev_f = residual(prev_u)
    for raw_u in grid[1:]:
        u = float(raw_u)
        f = residual(u)
        if np.isfinite(prev_f) and np.isfinite(f) and prev_f * f <= 0:
            mid = math.sqrt(prev_u * u)
            F_mid = K_flv / mid
            if GPDC_FLV_MIN <= F_mid <= GPDC_FLV_MAX:
                valid_pairs.append((prev_u, u))
        prev_u, prev_f = u, f

    if not valid_pairs:
        raise GPDCFloodingSolveError(
            "No valid GPDC flood-velocity root found in the correlation range."
        )

    bracket = valid_pairs[-1]
    U_flood = brentq(
        residual,
        bracket[0],
        bracket[1],
        xtol=1e-10,
        rtol=1e-10,
    )
    Gp_flood = rho_G * U_flood
    F_LV_flood = (Lp / Gp_flood) * math.sqrt(rho_G / rho_L)
    CP_flood = gpdc_flood_curve_cp(F_LV_flood)
    flooding_fraction = U_oper / max(U_flood, 1e-30)
    flooding_percent = 100.0 * flooding_fraction
    F_oper = U_oper * math.sqrt(rho_G)
    F_flood = U_flood * math.sqrt(rho_G)

    dP_flood_inH2O_ft = 0.115 * Fp_ft**0.7
    dP_flood_Pa_m = dP_flood_inH2O_ft * PA_PER_INH2O / M_PER_FT
    dP_flood_mbar_m = dP_flood_Pa_m * MBAR_PER_PA

    return FloodingResult(
        gas_superficial_velocity_m_s=U_oper,
        flood_velocity_m_s=U_flood,
        gas_mass_flux_kg_m2_s=Gp_oper,
        flood_gas_mass_flux_kg_m2_s=Gp_flood,
        liquid_mass_flux_kg_m2_s=Lp,
        F_LV_flood=F_LV_flood,
        CP_flood=CP_flood,
        packing_factor_ft_inv=Fp_ft,
        packing_factor_basis=fp.basis,
        packing_factor_estimated=fp.estimated,
        liquid_kinematic_viscosity_cSt=nu_cSt,
        F_oper=F_oper,
        F_flood=F_flood,
        flooding_fraction=flooding_fraction,
        flooding_percent=flooding_percent,
        hydraulic_regime=_hydraulic_regime(flooding_percent),
        flood_pressure_drop_inH2O_ft=dP_flood_inH2O_ft,
        flood_pressure_drop_Pa_m=dP_flood_Pa_m,
        flood_pressure_drop_mbar_m=dP_flood_mbar_m,
        gpdc_valid=GPDC_FLV_MIN <= F_LV_flood <= GPDC_FLV_MAX,
    )



def calculate_hydraulics(
    common: CommonOndaState,
    packing: PackingSpec,
    carrier: ResolvedCarrierState,
    solvent: ResolvedSolventState,
) -> HydraulicResult:
    """Calculate pressure drop + flooding as one generic hydraulic result."""

    pressure_drop = calculate_pressure_drop(common, packing, carrier, solvent)
    flooding = calculate_flooding(common, packing, carrier, solvent)
    ratio = (
        pressure_drop.wet_pressure_drop_mbar_m
        / flooding.flood_pressure_drop_mbar_m
        if flooding.flood_pressure_drop_mbar_m > 0
        else float("nan")
    )
    return HydraulicResult(
        pressure_drop=pressure_drop,
        flooding=flooding,
        pressure_drop_ratio_to_flood=ratio,
    )



def evaluate_hydraulics_from_resolver(
    *,
    resolver: PropertyResolver,
    registry,
    carrier_id: str,
    solvent_id: str,
    packing_id: str,
    operating: AbsorberOperatingPoint,
    carrier_overrides: CarrierPropertyOverrides | None = None,
    solvent_overrides: SolventPropertyOverrides | None = None,
) -> tuple[CommonOndaState, HydraulicResult]:
    """Resolve fluid state and evaluate hydraulics without selecting a solute.

    The helper intentionally uses only carrier, solvent, packing and operating
    data.  Dilute-solute identity therefore cannot affect Phase 6 hydraulics.
    """

    carrier = resolver.resolve_carrier_state(
        carrier_id,
        operating.temperature_K,
        operating.pressure_Pa,
        overrides=carrier_overrides,
    )
    solvent = resolver.resolve_solvent_state(
        solvent_id,
        operating.temperature_K,
        overrides=solvent_overrides,
    )
    packing = registry.get_packing(packing_id)
    common = calculate_common_onda_state(operating, packing, carrier, solvent)
    return common, calculate_hydraulics(common, packing, carrier, solvent)
