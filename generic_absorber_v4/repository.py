"""Phase 18C — repository abstraction for engineering data backends.

The simulation layer must depend on an engineering-data contract, not on SQLite
or any other persistence implementation.  This module therefore contains only
backend-neutral repository adapters and registry-resolution logic.

Backends currently supported through the same contract:
* verified Python registry factory;
* SQLite Phase-18B database through a loader adapter.

No physics is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

from .registry import AbsorberDataRegistry

PHASE18C_REPOSITORY_ID = "PHASE18C_REPOSITORY_ABSTRACTION_2026_10_07"


class RepositoryKind(str, Enum):
    PYTHON_REGISTRY = "PYTHON_REGISTRY"
    SQLITE = "SQLITE"
    DIRECT_REGISTRY = "DIRECT_REGISTRY"
    DEFAULT_REGISTRY = "DEFAULT_REGISTRY"


@dataclass(frozen=True)
class RepositoryDescriptor:
    backend_id: str
    kind: RepositoryKind
    label: str
    source: str
    schema_version: Optional[str] = None
    read_only: bool = True


@runtime_checkable
class AbsorberDataRepository(Protocol):
    @property
    def descriptor(self) -> RepositoryDescriptor:
        ...

    def load_registry(self) -> AbsorberDataRegistry:
        ...


@dataclass(frozen=True)
class PythonRegistryRepository:
    registry_factory: Callable[[], AbsorberDataRegistry]
    backend_id: str = "python_registry_phase17"
    label: str = "Verified Python Registry"

    @property
    def descriptor(self) -> RepositoryDescriptor:
        return RepositoryDescriptor(
            backend_id=self.backend_id,
            kind=RepositoryKind.PYTHON_REGISTRY,
            label=self.label,
            source="generic_absorber_v4.simulation.build_phase14_registry",
            schema_version=None,
            read_only=True,
        )

    def load_registry(self) -> AbsorberDataRegistry:
        registry = self.registry_factory()
        if not isinstance(registry, AbsorberDataRegistry):
            raise TypeError("registry_factory must return AbsorberDataRegistry.")
        return registry


@dataclass(frozen=True)
class RegistryLoaderRepository:
    """Adapter for any backend exposing a callable that reconstructs a registry."""

    loader: Callable[[], AbsorberDataRegistry]
    _descriptor: RepositoryDescriptor

    @property
    def descriptor(self) -> RepositoryDescriptor:
        return self._descriptor

    def load_registry(self) -> AbsorberDataRegistry:
        registry = self.loader()
        if not isinstance(registry, AbsorberDataRegistry):
            raise TypeError("Repository loader must return AbsorberDataRegistry.")
        return registry


def build_python_registry_repository() -> PythonRegistryRepository:
    """Build the verified in-code engineering-data backend.

    Import is intentionally lazy to keep the repository contract independent of
    the simulation module at import time.
    """
    from .simulation import build_phase14_registry

    return PythonRegistryRepository(build_phase14_registry)


def build_sqlite_v18b_repository(database_path: str | Path) -> RegistryLoaderRepository:
    """Adapt the Phase-18B SQLite database to the common repository contract."""
    from .database_v18b import SQLiteAbsorberRepositoryV18B

    path = Path(database_path)
    repo = SQLiteAbsorberRepositoryV18B(path)
    metadata = repo.metadata()
    return RegistryLoaderRepository(
        loader=repo.load_registry,
        _descriptor=RepositoryDescriptor(
            backend_id="sqlite_v18b",
            kind=RepositoryKind.SQLITE,
            label="SQLite Engineering Database v18B",
            source=str(path),
            schema_version=metadata.get("schema_version"),
            read_only=True,
        ),
    )


def resolve_registry_source(
    *,
    registry: Optional[AbsorberDataRegistry],
    repository: Optional[AbsorberDataRepository],
    default_registry_factory: Callable[[], AbsorberDataRegistry],
) -> tuple[AbsorberDataRegistry, RepositoryDescriptor]:
    """Resolve exactly one canonical registry and report its backend identity."""
    if registry is not None and repository is not None:
        raise ValueError("Pass either registry= or repository=, not both.")

    if repository is not None:
        loaded = repository.load_registry()
        return loaded, repository.descriptor

    if registry is not None:
        return registry, RepositoryDescriptor(
            backend_id="direct_registry",
            kind=RepositoryKind.DIRECT_REGISTRY,
            label="Direct AbsorberDataRegistry",
            source=registry.reference_id or "in-memory registry",
            read_only=True,
        )

    loaded = default_registry_factory()
    return loaded, RepositoryDescriptor(
        backend_id="default_python_registry",
        kind=RepositoryKind.DEFAULT_REGISTRY,
        label="Default Verified Python Registry",
        source="generic_absorber_v4.simulation.build_phase14_registry",
        read_only=True,
    )
