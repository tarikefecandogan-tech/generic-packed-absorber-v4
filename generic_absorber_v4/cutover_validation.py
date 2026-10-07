"""Phase 18D — controlled SQLite-primary cut-over validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from .repository import (
    AbsorberDataRepository,
    CutoverDecision,
    RepositoryKind,
    build_python_registry_repository,
    select_primary_data_repository,
)
from .repository_validation import RepositoryParityReport, run_phase18c_repository_parity

PHASE18D_VALIDATION_ID = "PHASE18D_PRIMARY_CUTOVER_VALIDATION_2026_10_07"


@dataclass(frozen=True)
class Phase18DCutoverReport:
    validation_id: str
    decision: CutoverDecision
    parity: RepositoryParityReport
    default_is_sqlite: bool
    fallback_test_passed: bool
    strict_failure_test_passed: bool

    @property
    def pass_gate(self) -> bool:
        return (
            self.decision.pass_gate
            and self.default_is_sqlite
            and self.parity.pass_gate
            and self.fallback_test_passed
            and self.strict_failure_test_passed
        )


def _validate_missing_database_policy(tmp_missing_path: Path) -> Tuple[bool, bool]:
    repo, decision = select_primary_data_repository(
        tmp_missing_path, allow_python_fallback=True
    )
    fallback_ok = (
        decision.fallback_used
        and decision.active_kind == RepositoryKind.CONTROLLED_FALLBACK
        and repo.descriptor.kind == RepositoryKind.CONTROLLED_FALLBACK
        and bool(decision.fallback_reason)
        and repo.load_registry().inventory_counts()["solutes"] >= 1
    )

    strict_ok = False
    try:
        select_primary_data_repository(tmp_missing_path, allow_python_fallback=False)
    except Exception:
        strict_ok = True

    return fallback_ok, strict_ok


def run_phase18d_cutover_gate(
    database_path: str | Path,
    *,
    missing_database_probe: str | Path | None = None,
) -> Phase18DCutoverReport:
    """Validate SQLite-primary selection, parity and explicit fallback behavior."""
    path = Path(database_path)
    primary_repo, decision = select_primary_data_repository(
        path, allow_python_fallback=True
    )
    python_repo = build_python_registry_repository()
    parity = run_phase18c_repository_parity(python_repo, primary_repo)

    probe = (
        Path(missing_database_probe)
        if missing_database_probe is not None
        else path.parent / "__phase18d_missing_database_probe__.db"
    )
    if probe.exists():
        probe.unlink()
    fallback_ok, strict_ok = _validate_missing_database_policy(probe)

    return Phase18DCutoverReport(
        validation_id=PHASE18D_VALIDATION_ID,
        decision=decision,
        parity=parity,
        default_is_sqlite=(
            decision.active_kind == RepositoryKind.SQLITE
            and not decision.fallback_used
        ),
        fallback_test_passed=fallback_ok,
        strict_failure_test_passed=strict_ok,
    )
