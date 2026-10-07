"""Phase 18C/18D — repository abstraction and controlled primary-backend cut-over.

The physics and simulation layers consume a backend-neutral engineering-data
repository contract. Phase 18C proved that the verified Python registry and the
Phase-18B SQLite engineering database reconstruct the same canonical registry.
Phase 18D made SQLite the *product-facing primary read source* while retaining
an explicit, auditable Python-registry fallback/reference backend. Phase 18G advances
the default packaged data snapshot to the verified expanded v18G database while
keeping the proven Phase-18B.1 SQL schema.

No transport, equilibrium, ODE or hydraulic physics is implemented here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

from .registry import AbsorberDataRegistry

PHASE18C_REPOSITORY_ID = "PHASE18C_REPOSITORY_ABSTRACTION_2026_10_07"
PHASE18D_CUTOVER_ID = "PHASE18D_SQLITE_PRIMARY_CUTOVER_2026_10_07"
DEFAULT_SQLITE_FILENAME = "absorber_database_v18g.db"


class RepositoryKind(str, Enum):
    PYTHON_REGISTRY = "PYTHON_REGISTRY"
    SQLITE = "SQLITE"
    DIRECT_REGISTRY = "DIRECT_REGISTRY"
    DEFAULT_REGISTRY = "DEFAULT_REGISTRY"  # retained for API compatibility
    CONTROLLED_FALLBACK = "CONTROLLED_FALLBACK"


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


class PrimaryRepositoryUnavailableError(RuntimeError):
    """Raised when the configured primary SQLite backend cannot be used."""


@dataclass(frozen=True)
class CutoverDecision:
    """Auditable result of selecting the product-facing engineering-data backend."""

    cutover_id: str
    requested_primary: str
    active_backend_id: str
    active_kind: RepositoryKind
    active_label: str
    database_path: str
    sqlite_integrity: str
    foreign_key_violations: int
    fallback_allowed: bool
    fallback_used: bool
    fallback_reason: str = ""

    @property
    def pass_gate(self) -> bool:
        if self.fallback_used:
            return self.fallback_allowed and bool(self.fallback_reason)
        return (
            self.active_kind == RepositoryKind.SQLITE
            and self.sqlite_integrity.lower() == "ok"
            and self.foreign_key_violations == 0
        )


def default_sqlite_database_path() -> Path:
    """Return the packaged current primary SQLite database path (Phase 18G data snapshot).

    repository.py lives in ``generic_absorber_v4`` while the database directory
    is kept at the project/repository root next to that package.
    """
    return Path(__file__).resolve().parent.parent / "database" / DEFAULT_SQLITE_FILENAME


def build_python_registry_repository() -> PythonRegistryRepository:
    """Build the verified in-code engineering-data reference backend."""
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


def build_sqlite_v18g_repository(database_path: str | Path) -> RegistryLoaderRepository:
    """Adapt the Phase-18G expanded SQLite snapshot to the common repository contract.

    Phase 18G intentionally retains the proven Phase-18B.1 SQL schema; the
    distinction is the data snapshot/content, not a new physical-property schema.
    """
    from .database_v18b import SQLiteAbsorberRepositoryV18B

    path = Path(database_path)
    repo = SQLiteAbsorberRepositoryV18B(path)
    metadata = repo.metadata()
    return RegistryLoaderRepository(
        loader=repo.load_registry,
        _descriptor=RepositoryDescriptor(
            backend_id="sqlite_v18g",
            kind=RepositoryKind.SQLITE,
            label="SQLite Engineering Database v18G",
            source=str(path),
            schema_version=metadata.get("schema_version"),
            read_only=True,
        ),
    )


def _database_is_phase18g(database_path: Path) -> bool:
    """Identify the expanded snapshot without coupling the physics layer to it."""
    try:
        from .database_v18b import SQLiteAbsorberRepositoryV18B
        md = SQLiteAbsorberRepositoryV18B(database_path).metadata()
        return bool(md.get("verified_expansion_batch")) or md.get("data_snapshot_id", "").startswith("PHASE18G_")
    except Exception:
        return database_path.name == "absorber_database_v18g.db"


def _validate_sqlite_backend(database_path: Path) -> tuple[str, int]:
    """Validate the SQLite file before it becomes the primary read source."""
    from .database_v18b import PHASE18B_SCHEMA_VERSION, SQLiteAbsorberRepositoryV18B

    if not database_path.exists():
        raise FileNotFoundError(f"Primary SQLite engineering database not found: {database_path}")
    if not database_path.is_file():
        raise PrimaryRepositoryUnavailableError(
            f"Primary SQLite engineering database path is not a file: {database_path}"
        )

    raw = SQLiteAbsorberRepositoryV18B(database_path)
    integrity = raw.integrity_check()
    fk_violations = len(raw.foreign_key_violations())
    metadata = raw.metadata()
    schema = metadata.get("schema_version")

    if integrity.lower() != "ok":
        raise PrimaryRepositoryUnavailableError(
            f"SQLite integrity_check failed for {database_path}: {integrity}"
        )
    if fk_violations:
        raise PrimaryRepositoryUnavailableError(
            f"SQLite foreign-key check found {fk_violations} violation(s) in {database_path}."
        )
    if schema != PHASE18B_SCHEMA_VERSION:
        raise PrimaryRepositoryUnavailableError(
            f"SQLite schema mismatch: expected {PHASE18B_SCHEMA_VERSION}, found {schema!r}."
        )

    # Force a complete registry reconstruction before declaring the database fit
    # to be the primary read source. This catches missing/corrupt domain rows.
    rebuilt = raw.load_registry()
    if not isinstance(rebuilt, AbsorberDataRegistry):
        raise PrimaryRepositoryUnavailableError("SQLite backend did not reconstruct AbsorberDataRegistry.")

    return integrity, fk_violations


def _build_controlled_python_fallback(reason: str) -> RegistryLoaderRepository:
    """Create an explicit fallback backend; never disguise fallback as SQLite."""
    py = build_python_registry_repository()
    return RegistryLoaderRepository(
        loader=py.load_registry,
        _descriptor=RepositoryDescriptor(
            backend_id="python_registry_controlled_fallback",
            kind=RepositoryKind.CONTROLLED_FALLBACK,
            label="Verified Python Registry — CONTROLLED FALLBACK",
            source=(
                "generic_absorber_v4.simulation.build_phase14_registry; "
                f"fallback_reason={reason}"
            ),
            schema_version=None,
            read_only=True,
        ),
    )


def select_primary_data_repository(
    database_path: str | Path | None = None,
    *,
    allow_python_fallback: bool = True,
) -> tuple[AbsorberDataRepository, CutoverDecision]:
    """Select SQLite as the product primary backend with an explicit fallback policy.

    The function validates SQLite integrity, foreign keys, schema version and a
    complete registry reconstruction *before* returning it as primary. If this
    validation fails and fallback is allowed, a specially labelled Python
    fallback repository is returned together with the exact failure reason.

    No silent fallback occurs: callers can inspect ``CutoverDecision`` and the
    result repository descriptor always identifies the active backend.
    """
    path = Path(database_path) if database_path is not None else default_sqlite_database_path()
    requested_primary = "SQLite Engineering Database v18G" if _database_is_phase18g(path) else "SQLite Engineering Database v18B"

    try:
        integrity, fk_violations = _validate_sqlite_backend(path)
        repo = build_sqlite_v18g_repository(path) if _database_is_phase18g(path) else build_sqlite_v18b_repository(path)
        decision = CutoverDecision(
            cutover_id=PHASE18D_CUTOVER_ID,
            requested_primary=requested_primary,
            active_backend_id=repo.descriptor.backend_id,
            active_kind=repo.descriptor.kind,
            active_label=repo.descriptor.label,
            database_path=str(path),
            sqlite_integrity=integrity,
            foreign_key_violations=fk_violations,
            fallback_allowed=allow_python_fallback,
            fallback_used=False,
            fallback_reason="",
        )
        return repo, decision
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        if not allow_python_fallback:
            raise PrimaryRepositoryUnavailableError(
                f"SQLite primary backend unavailable and fallback disabled. {reason}"
            ) from exc
        repo = _build_controlled_python_fallback(reason)
        decision = CutoverDecision(
            cutover_id=PHASE18D_CUTOVER_ID,
            requested_primary=requested_primary,
            active_backend_id=repo.descriptor.backend_id,
            active_kind=repo.descriptor.kind,
            active_label=repo.descriptor.label,
            database_path=str(path),
            sqlite_integrity="UNAVAILABLE",
            foreign_key_violations=-1,
            fallback_allowed=True,
            fallback_used=True,
            fallback_reason=reason,
        )
        return repo, decision


def resolve_registry_source(
    *,
    registry: Optional[AbsorberDataRegistry],
    repository: Optional[AbsorberDataRepository],
    default_registry_factory: Callable[[], AbsorberDataRegistry],
) -> tuple[AbsorberDataRegistry, RepositoryDescriptor]:
    """Resolve exactly one canonical registry and report its backend identity.

    The no-argument library/API path intentionally remains backward compatible
    with the verified Python registry. Phase 18D performs the production cut-over
    through the product-facing primary repository selector. This separation lets
    existing API consumers opt into the cut-over deliberately while Streamlit
    uses SQLite by default.
    """
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

    # Backward-compatible Python API default. Product/UI default is selected by
    # select_primary_data_repository() and passed explicitly as repository=.
    loaded = default_registry_factory()
    return loaded, RepositoryDescriptor(
        backend_id="default_python_registry",
        kind=RepositoryKind.DEFAULT_REGISTRY,
        label="Default Verified Python Registry",
        source="generic_absorber_v4.simulation.build_phase14_registry",
        read_only=True,
    )
