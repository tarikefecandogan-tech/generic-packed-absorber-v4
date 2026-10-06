"""Generic Packed Absorber Simulator V4 — Phase 2 data registry layer."""

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
from .reference_data import REFERENCE_ID, ReferenceDataBundle, locked_reference_data
from .registry import (
    AbsorberDataRegistry,
    DuplicateRegistrationError,
    MissingPairDataError,
    PairAvailability,
    RegistryError,
    RegistryReadiness,
    UnknownEntityError,
    build_reference_registry,
)

__all__ = [
    "CarrierGasSpec",
    "ConfidenceClass",
    "DataProvenance",
    "EquilibriumPair",
    "GasTransportPair",
    "LiquidTransportPair",
    "PackingSpec",
    "SoluteSpec",
    "SolventSpec",
    "REFERENCE_ID",
    "ReferenceDataBundle",
    "locked_reference_data",
    "AbsorberDataRegistry",
    "RegistryError",
    "DuplicateRegistrationError",
    "UnknownEntityError",
    "MissingPairDataError",
    "PairAvailability",
    "RegistryReadiness",
    "build_reference_registry",
]
