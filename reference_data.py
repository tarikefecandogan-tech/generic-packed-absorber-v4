"""Locked Phase 1 data snapshot for REF_SCRUBBER_2026_10_06.

Only the existing ACN + VAc / Water / Air reference chemistry and the selected
25 mm Metal Pall Ring are present here.  New chemistry is intentionally excluded
until later V4 phases.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

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

P_N = 101325.0
T_HENRY_REF = 298.15

REFERENCE_ID = "REF_SCRUBBER_2026_10_06"
REFERENCE_SOURCE = "scrubber_model.py / ScrubberSimulationV34 locked 2026-10-06"

LEGACY_PROVENANCE = DataProvenance(
    source=REFERENCE_SOURCE,
    method="locked_reference_compatibility",
    confidence=ConfidenceClass.B,
    validity_note=(
        "Copied without re-estimation from the locked V3 reference engine. "
        "Scientific source verification is a later database-quality task."
    ),
)

AIR_PROVENANCE = DataProvenance(
    source=REFERENCE_SOURCE,
    method="Sutherland viscosity parameters preserved from V3 reference",
    confidence=ConfidenceClass.B,
)

WATER_PROVENANCE = DataProvenance(
    source=REFERENCE_SOURCE,
    method="Existing V3 temperature-dependent water property correlations",
    confidence=ConfidenceClass.B,
)

PACKING_PROVENANCE = DataProvenance(
    source=REFERENCE_SOURCE,
    method="Existing V3 packing dataset; empirical GPDC packing factor retained",
    confidence=ConfidenceClass.B,
)

SOLUTES: Dict[str, SoluteSpec] = {
    "ACN": SoluteSpec(
        id="ACN",
        name="Acrylonitrile",
        MW_kg_mol=53.06e-3,
        carbon_atoms=3,
        formula="C3H3N",
    ),
    "VAc": SoluteSpec(
        id="VAc",
        name="Vinyl acetate",
        MW_kg_mol=86.09e-3,
        carbon_atoms=4,
        formula="C4H6O2",
    ),
}

CARRIERS: Dict[str, CarrierGasSpec] = {
    "air": CarrierGasSpec(
        id="air",
        name="Air",
        MW_kg_mol=0.029,
        viscosity_model="sutherland",
        mu_ref_Pa_s=1.716e-5,
        T_ref_K=273.15,
        sutherland_S_K=110.4,
        provenance=AIR_PROVENANCE,
    )
}

SOLVENTS: Dict[str, SolventSpec] = {
    "water": SolventSpec(
        id="water",
        name="Water",
        MW_kg_mol=18.015e-3,
        property_model="correlation",
        property_model_id="legacy_v3_water",
        provenance=WATER_PROVENANCE,
    )
}

PACKINGS: Dict[str, PackingSpec] = {
    "25mm_metal_pall_ring": PackingSpec(
        id="25mm_metal_pall_ring",
        name="25mm Metal Pall Ring",
        packing_class="random",
        area_m2_m3=212.0,
        nominal_size_m=0.025,
        void_fraction=0.962,
        critical_surface_tension_N_m=0.075,
        pressure_drop_psi=1.20,
        packing_factor_ft_inv=48.0,
        packing_factor_basis="empirical",
        provenance=PACKING_PROVENANCE,
    )
}

GAS_TRANSPORT_PAIRS: Dict[Tuple[str, str], GasTransportPair] = {
    ("ACN", "air"): GasTransportPair(
        solute_id="ACN",
        carrier_id="air",
        D_ref_m2_s=1.0e-5,
        T_ref_K=None,
        P_ref_Pa=None,
        model="fixed_reference",
        provenance=LEGACY_PROVENANCE,
    ),
    ("VAc", "air"): GasTransportPair(
        solute_id="VAc",
        carrier_id="air",
        D_ref_m2_s=0.9e-5,
        T_ref_K=None,
        P_ref_Pa=None,
        model="fixed_reference",
        provenance=LEGACY_PROVENANCE,
    ),
}

LIQUID_TRANSPORT_PAIRS: Dict[Tuple[str, str], LiquidTransportPair] = {
    ("ACN", "water"): LiquidTransportPair(
        solute_id="ACN",
        solvent_id="water",
        D_ref_m2_s=1.0e-9,
        T_ref_K=None,
        model="fixed_reference",
        provenance=LEGACY_PROVENANCE,
    ),
    ("VAc", "water"): LiquidTransportPair(
        solute_id="VAc",
        solvent_id="water",
        D_ref_m2_s=0.9e-9,
        T_ref_K=None,
        model="fixed_reference",
        provenance=LEGACY_PROVENANCE,
    ),
}

EQUILIBRIUM_PAIRS: Dict[Tuple[str, str], EquilibriumPair] = {
    ("ACN", "water"): EquilibriumPair(
        solute_id="ACN",
        solvent_id="water",
        model="henry_pc",
        H_ref_Pa_m3_mol=1.18e-5 * P_N,
        T_ref_K=T_HENRY_REF,
        temperature_coefficient_K=4200.0,
        validity_note="Locked V3 reference pair; source-quality review deferred to later database phase.",
        provenance=LEGACY_PROVENANCE,
    ),
    ("VAc", "water"): EquilibriumPair(
        solute_id="VAc",
        solvent_id="water",
        model="henry_pc",
        H_ref_Pa_m3_mol=5.11e-4 * P_N,
        T_ref_K=T_HENRY_REF,
        temperature_coefficient_K=4500.0,
        validity_note="Locked V3 reference pair; source-quality review deferred to later database phase.",
        provenance=LEGACY_PROVENANCE,
    ),
}


@dataclass(frozen=True)
class ReferenceDataBundle:
    reference_id: str
    solutes: Dict[str, SoluteSpec]
    carriers: Dict[str, CarrierGasSpec]
    solvents: Dict[str, SolventSpec]
    packings: Dict[str, PackingSpec]
    gas_transport_pairs: Dict[Tuple[str, str], GasTransportPair]
    liquid_transport_pairs: Dict[Tuple[str, str], LiquidTransportPair]
    equilibrium_pairs: Dict[Tuple[str, str], EquilibriumPair]


def locked_reference_data() -> ReferenceDataBundle:
    """Return defensive copies of the locked V3-compatible Phase 1 dataset."""
    return ReferenceDataBundle(
        reference_id=REFERENCE_ID,
        solutes=dict(SOLUTES),
        carriers=dict(CARRIERS),
        solvents=dict(SOLVENTS),
        packings=dict(PACKINGS),
        gas_transport_pairs=dict(GAS_TRANSPORT_PAIRS),
        liquid_transport_pairs=dict(LIQUID_TRANSPORT_PAIRS),
        equilibrium_pairs=dict(EQUILIBRIUM_PAIRS),
    )
