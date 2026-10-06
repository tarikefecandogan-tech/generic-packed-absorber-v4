"""V4 Phase 2 registry / lookup layer.

This module makes the Phase 1 data objects usable as an explicit engineering
registry.  It deliberately performs no Onda, ODE, GPDC, pressure-drop,
unit-conversion, property-estimation, or equilibrium calculations.

Core Phase 2 policy
-------------------
* Pair data are keyed by the exact chemical IDs carried by the data objects.
* Missing critical pair data raise an explicit error by default.
* Duplicate registration is rejected unless ``replace=True`` is requested.
* Pair registration validates its foreign keys (solute/carrier/solvent IDs).
* No fallback to another chemical pair is ever performed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, Optional, Tuple

from .models import (
    CarrierGasSpec,
    EquilibriumPair,
    GasTransportPair,
    LiquidTransportPair,
    PackingSpec,
    SoluteSpec,
    SolventSpec,
)
from .reference_data import ReferenceDataBundle, locked_reference_data


class RegistryError(RuntimeError):
    """Base class for Phase 2 registry errors."""


class DuplicateRegistrationError(RegistryError):
    """Raised when a key is registered twice without explicit replacement."""


class UnknownEntityError(RegistryError):
    """Raised when a pair references an unregistered pure component."""


class MissingPairDataError(RegistryError):
    """Raised when requested pair data do not exist in the registry."""

    def __init__(self, pair_type: str, key: Tuple[str, str]):
        self.pair_type = pair_type
        self.key = key
        super().__init__(
            f"{pair_type} data not available for pair {key[0]} / {key[1]}. "
            "No fallback value was used."
        )


class RegistryReadiness(str, Enum):
    READY = "READY"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class PairAvailability:
    """Availability summary for one solute/carrier/solvent combination.

    This is a data-readiness report only.  It does not decide whether the
    underlying physics/correlation is applicable; that belongs to the later
    applicability engine.
    """

    solute_id: str
    carrier_id: str
    solvent_id: str
    gas_transport_available: bool
    liquid_transport_available: bool
    equilibrium_available: bool

    @property
    def status(self) -> RegistryReadiness:
        if (
            self.gas_transport_available
            and self.liquid_transport_available
            and self.equilibrium_available
        ):
            return RegistryReadiness.READY
        return RegistryReadiness.INCOMPLETE

    @property
    def missing(self) -> Tuple[str, ...]:
        items = []
        if not self.gas_transport_available:
            items.append("gas_transport")
        if not self.liquid_transport_available:
            items.append("liquid_transport")
        if not self.equilibrium_available:
            items.append("equilibrium")
        return tuple(items)


class AbsorberDataRegistry:
    """Mutable registry around the immutable Phase 1 data objects."""

    def __init__(self, *, reference_id: Optional[str] = None) -> None:
        self.reference_id = reference_id
        self._solutes: Dict[str, SoluteSpec] = {}
        self._carriers: Dict[str, CarrierGasSpec] = {}
        self._solvents: Dict[str, SolventSpec] = {}
        self._packings: Dict[str, PackingSpec] = {}
        self._gas_pairs: Dict[Tuple[str, str], GasTransportPair] = {}
        self._liquid_pairs: Dict[Tuple[str, str], LiquidTransportPair] = {}
        self._equilibrium_pairs: Dict[Tuple[str, str], EquilibriumPair] = {}

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    @classmethod
    def from_bundle(cls, bundle: ReferenceDataBundle) -> "AbsorberDataRegistry":
        registry = cls(reference_id=bundle.reference_id)
        for item in bundle.solutes.values():
            registry.register_solute(item)
        for item in bundle.carriers.values():
            registry.register_carrier(item)
        for item in bundle.solvents.values():
            registry.register_solvent(item)
        for item in bundle.packings.values():
            registry.register_packing(item)
        for item in bundle.gas_transport_pairs.values():
            registry.register_gas_transport_pair(item)
        for item in bundle.liquid_transport_pairs.values():
            registry.register_liquid_transport_pair(item)
        for item in bundle.equilibrium_pairs.values():
            registry.register_equilibrium_pair(item)
        return registry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _require_id(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _register(mapping: dict, key, value, *, replace: bool, label: str) -> None:
        if key in mapping and not replace:
            raise DuplicateRegistrationError(
                f"{label} '{key}' is already registered. Use replace=True for an explicit overwrite."
            )
        mapping[key] = value

    def _ensure_solute(self, solute_id: str) -> str:
        key = self._require_id(solute_id, "solute_id")
        if key not in self._solutes:
            raise UnknownEntityError(f"Unknown solute_id '{key}'. Register the solute first.")
        return key

    def _ensure_carrier(self, carrier_id: str) -> str:
        key = self._require_id(carrier_id, "carrier_id")
        if key not in self._carriers:
            raise UnknownEntityError(f"Unknown carrier_id '{key}'. Register the carrier first.")
        return key

    def _ensure_solvent(self, solvent_id: str) -> str:
        key = self._require_id(solvent_id, "solvent_id")
        if key not in self._solvents:
            raise UnknownEntityError(f"Unknown solvent_id '{key}'. Register the solvent first.")
        return key

    # ------------------------------------------------------------------
    # Pure-component registration / lookup
    # ------------------------------------------------------------------
    def register_solute(self, item: SoluteSpec, *, replace: bool = False) -> None:
        self._register(self._solutes, item.id, item, replace=replace, label="Solute")

    def register_carrier(self, item: CarrierGasSpec, *, replace: bool = False) -> None:
        self._register(self._carriers, item.id, item, replace=replace, label="Carrier")

    def register_solvent(self, item: SolventSpec, *, replace: bool = False) -> None:
        self._register(self._solvents, item.id, item, replace=replace, label="Solvent")

    def register_packing(self, item: PackingSpec, *, replace: bool = False) -> None:
        self._register(self._packings, item.id, item, replace=replace, label="Packing")

    def get_solute(self, solute_id: str) -> SoluteSpec:
        key = self._require_id(solute_id, "solute_id")
        try:
            return self._solutes[key]
        except KeyError as exc:
            raise UnknownEntityError(f"Unknown solute_id '{key}'.") from exc

    def get_carrier(self, carrier_id: str) -> CarrierGasSpec:
        key = self._require_id(carrier_id, "carrier_id")
        try:
            return self._carriers[key]
        except KeyError as exc:
            raise UnknownEntityError(f"Unknown carrier_id '{key}'.") from exc

    def get_solvent(self, solvent_id: str) -> SolventSpec:
        key = self._require_id(solvent_id, "solvent_id")
        try:
            return self._solvents[key]
        except KeyError as exc:
            raise UnknownEntityError(f"Unknown solvent_id '{key}'.") from exc

    def get_packing(self, packing_id: str) -> PackingSpec:
        key = self._require_id(packing_id, "packing_id")
        try:
            return self._packings[key]
        except KeyError as exc:
            raise UnknownEntityError(f"Unknown packing_id '{key}'.") from exc

    # ------------------------------------------------------------------
    # Pair registration
    # ------------------------------------------------------------------
    def register_gas_transport_pair(
        self, item: GasTransportPair, *, replace: bool = False
    ) -> None:
        solute_id = self._ensure_solute(item.solute_id)
        carrier_id = self._ensure_carrier(item.carrier_id)
        key = (solute_id, carrier_id)
        self._register(
            self._gas_pairs, key, item, replace=replace, label="Gas transport pair"
        )

    def register_liquid_transport_pair(
        self, item: LiquidTransportPair, *, replace: bool = False
    ) -> None:
        solute_id = self._ensure_solute(item.solute_id)
        solvent_id = self._ensure_solvent(item.solvent_id)
        key = (solute_id, solvent_id)
        self._register(
            self._liquid_pairs, key, item, replace=replace, label="Liquid transport pair"
        )

    def register_equilibrium_pair(
        self, item: EquilibriumPair, *, replace: bool = False
    ) -> None:
        solute_id = self._ensure_solute(item.solute_id)
        solvent_id = self._ensure_solvent(item.solvent_id)
        key = (solute_id, solvent_id)
        self._register(
            self._equilibrium_pairs, key, item, replace=replace, label="Equilibrium pair"
        )

    # ------------------------------------------------------------------
    # Pair lookup — exact match, explicit missing-data behavior
    # ------------------------------------------------------------------
    def find_gas_transport_pair(
        self, solute_id: str, carrier_id: str
    ) -> Optional[GasTransportPair]:
        return self._gas_pairs.get((solute_id.strip(), carrier_id.strip()))

    def find_liquid_transport_pair(
        self, solute_id: str, solvent_id: str
    ) -> Optional[LiquidTransportPair]:
        return self._liquid_pairs.get((solute_id.strip(), solvent_id.strip()))

    def find_equilibrium_pair(
        self, solute_id: str, solvent_id: str
    ) -> Optional[EquilibriumPair]:
        return self._equilibrium_pairs.get((solute_id.strip(), solvent_id.strip()))

    def require_gas_transport_pair(self, solute_id: str, carrier_id: str) -> GasTransportPair:
        key = (self._require_id(solute_id, "solute_id"), self._require_id(carrier_id, "carrier_id"))
        pair = self._gas_pairs.get(key)
        if pair is None:
            raise MissingPairDataError("gas_transport", key)
        return pair

    def require_liquid_transport_pair(self, solute_id: str, solvent_id: str) -> LiquidTransportPair:
        key = (self._require_id(solute_id, "solute_id"), self._require_id(solvent_id, "solvent_id"))
        pair = self._liquid_pairs.get(key)
        if pair is None:
            raise MissingPairDataError("liquid_transport", key)
        return pair

    def require_equilibrium_pair(self, solute_id: str, solvent_id: str) -> EquilibriumPair:
        key = (self._require_id(solute_id, "solute_id"), self._require_id(solvent_id, "solvent_id"))
        pair = self._equilibrium_pairs.get(key)
        if pair is None:
            raise MissingPairDataError("equilibrium", key)
        return pair

    # ------------------------------------------------------------------
    # Availability / inventory
    # ------------------------------------------------------------------
    def availability(self, solute_id: str, carrier_id: str, solvent_id: str) -> PairAvailability:
        # Pure entities must exist; availability should not silently accept typos.
        solute_key = self._ensure_solute(solute_id)
        carrier_key = self._ensure_carrier(carrier_id)
        solvent_key = self._ensure_solvent(solvent_id)
        return PairAvailability(
            solute_id=solute_key,
            carrier_id=carrier_key,
            solvent_id=solvent_key,
            gas_transport_available=(solute_key, carrier_key) in self._gas_pairs,
            liquid_transport_available=(solute_key, solvent_key) in self._liquid_pairs,
            equilibrium_available=(solute_key, solvent_key) in self._equilibrium_pairs,
        )

    @property
    def solutes(self) -> Dict[str, SoluteSpec]:
        return dict(self._solutes)

    @property
    def carriers(self) -> Dict[str, CarrierGasSpec]:
        return dict(self._carriers)

    @property
    def solvents(self) -> Dict[str, SolventSpec]:
        return dict(self._solvents)

    @property
    def packings(self) -> Dict[str, PackingSpec]:
        return dict(self._packings)

    @property
    def gas_transport_pairs(self) -> Dict[Tuple[str, str], GasTransportPair]:
        return dict(self._gas_pairs)

    @property
    def liquid_transport_pairs(self) -> Dict[Tuple[str, str], LiquidTransportPair]:
        return dict(self._liquid_pairs)

    @property
    def equilibrium_pairs(self) -> Dict[Tuple[str, str], EquilibriumPair]:
        return dict(self._equilibrium_pairs)

    def inventory_counts(self) -> Dict[str, int]:
        return {
            "solutes": len(self._solutes),
            "carriers": len(self._carriers),
            "solvents": len(self._solvents),
            "packings": len(self._packings),
            "gas_transport_pairs": len(self._gas_pairs),
            "liquid_transport_pairs": len(self._liquid_pairs),
            "equilibrium_pairs": len(self._equilibrium_pairs),
        }


def build_reference_registry() -> AbsorberDataRegistry:
    """Build a mutable registry from the locked Phase 1 reference snapshot."""
    return AbsorberDataRegistry.from_bundle(locked_reference_data())
