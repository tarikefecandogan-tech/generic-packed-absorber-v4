"""Phase 11 engineering property-estimation correlations.

The functions in this module are intentionally small, explicit and unit-aware.
They estimate only transport properties that are missing from the registered
binary-pair database.  They never overwrite database values.

Implemented in V4 Phase 11
--------------------------
* Fuller–Schettler–Giddings gas-phase binary diffusivity estimate.
* Wilke–Chang dilute liquid-phase diffusivity estimate.

These are screening / engineering estimates, not substitutes for validated
binary experimental data.  The resolver marks results as Confidence C.
"""
from __future__ import annotations

import math
from dataclasses import dataclass


class CorrelationInputError(ValueError):
    """Raised when an estimator lacks required pure-component inputs."""


@dataclass(frozen=True)
class CorrelationCalculation:
    value_m2_s: float
    method: str
    equation_basis: str
    note: str

    def __post_init__(self) -> None:
        if not math.isfinite(self.value_m2_s) or self.value_m2_s <= 0:
            raise ValueError("Estimated diffusivity must be finite and positive.")


def fuller_gas_diffusivity_m2_s(
    *,
    T_K: float,
    P_Pa: float,
    solute_MW_kg_mol: float,
    carrier_MW_kg_mol: float,
    solute_diffusion_volume: float,
    carrier_diffusion_volume: float,
) -> CorrelationCalculation:
    """Estimate binary gas diffusivity using the Fuller correlation.

    Equation basis used here::

        D_AB [cm²/s] = 0.001 * T^1.75 * sqrt(1/M_A + 1/M_B)
                       / (P_atm * (V_A^(1/3) + V_B^(1/3))²)

    Molecular weights are in g/mol and Fuller diffusion volumes are the
    conventional dimensionless atomic-volume sums.  The result is converted
    from cm²/s to m²/s.
    """
    vals = {
        "T_K": T_K,
        "P_Pa": P_Pa,
        "solute_MW_kg_mol": solute_MW_kg_mol,
        "carrier_MW_kg_mol": carrier_MW_kg_mol,
        "solute_diffusion_volume": solute_diffusion_volume,
        "carrier_diffusion_volume": carrier_diffusion_volume,
    }
    for name, value in vals.items():
        if value is None or not math.isfinite(float(value)) or float(value) <= 0:
            raise CorrelationInputError(f"Fuller requires positive {name}.")

    M_A = solute_MW_kg_mol * 1000.0  # g/mol
    M_B = carrier_MW_kg_mol * 1000.0  # g/mol
    P_atm = P_Pa / 101325.0
    volume_term = (
        solute_diffusion_volume ** (1.0 / 3.0)
        + carrier_diffusion_volume ** (1.0 / 3.0)
    ) ** 2
    D_cm2_s = (
        0.001
        * T_K ** 1.75
        * math.sqrt(1.0 / M_A + 1.0 / M_B)
        / (P_atm * volume_term)
    )
    D_m2_s = D_cm2_s * 1.0e-4
    return CorrelationCalculation(
        value_m2_s=D_m2_s,
        method="Fuller–Schettler–Giddings gas diffusivity correlation",
        equation_basis=(
            "D[cm²/s]=0.001*T^1.75*sqrt(1/MA+1/MB)/"
            "(P_atm*(VA^(1/3)+VB^(1/3))^2)"
        ),
        note=(
            f"Estimated at T={T_K:g} K, P={P_Pa:g} Pa using Fuller volumes "
            f"VA={solute_diffusion_volume:g}, VB={carrier_diffusion_volume:g}."
        ),
    )


def wilke_chang_liquid_diffusivity_m2_s(
    *,
    T_K: float,
    solvent_mu_Pa_s: float,
    solvent_MW_kg_mol: float,
    solvent_association_factor: float,
    solute_boiling_molar_volume_cm3_mol: float,
) -> CorrelationCalculation:
    """Estimate dilute liquid diffusivity using Wilke–Chang.

    Equation basis used here::

        D_AB [cm²/s] = 7.4e-8 * sqrt(phi_B * M_B) * T
                       / (mu_B[cP] * V_A^0.6)

    ``M_B`` is solvent molecular weight in g/mol, ``mu_B`` is solvent
    viscosity in cP, ``V_A`` is solute molar volume at its normal boiling
    point in cm³/mol, and ``phi_B`` is the solvent association factor.
    """
    vals = {
        "T_K": T_K,
        "solvent_mu_Pa_s": solvent_mu_Pa_s,
        "solvent_MW_kg_mol": solvent_MW_kg_mol,
        "solvent_association_factor": solvent_association_factor,
        "solute_boiling_molar_volume_cm3_mol": solute_boiling_molar_volume_cm3_mol,
    }
    for name, value in vals.items():
        if value is None or not math.isfinite(float(value)) or float(value) <= 0:
            raise CorrelationInputError(f"Wilke–Chang requires positive {name}.")

    M_B = solvent_MW_kg_mol * 1000.0  # g/mol
    mu_cP = solvent_mu_Pa_s * 1000.0  # Pa s -> cP
    V_A = solute_boiling_molar_volume_cm3_mol
    phi = solvent_association_factor
    D_cm2_s = (
        7.4e-8
        * math.sqrt(phi * M_B)
        * T_K
        / (mu_cP * V_A ** 0.6)
    )
    D_m2_s = D_cm2_s * 1.0e-4
    return CorrelationCalculation(
        value_m2_s=D_m2_s,
        method="Wilke–Chang dilute liquid diffusivity correlation",
        equation_basis=(
            "D[cm²/s]=7.4e-8*sqrt(phiB*MB)*T/(muB[cP]*VA^0.6)"
        ),
        note=(
            f"Estimated at T={T_K:g} K using phi={phi:g}, solvent MW={M_B:g} g/mol, "
            f"mu={mu_cP:g} cP and solute boiling molar volume={V_A:g} cm³/mol."
        ),
    )
