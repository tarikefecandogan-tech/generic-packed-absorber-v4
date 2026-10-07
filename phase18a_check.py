from pathlib import Path
import tempfile

from generic_absorber_v4 import (
    build_phase18a_database,
    build_phase18a_source_registry,
    compare_registry_to_sqlite,
)

with tempfile.TemporaryDirectory() as td:
    repo = build_phase18a_database(Path(td) / "absorber.db")
    report = compare_registry_to_sqlite(build_phase18a_source_registry(), repo)
    assert report.pass_gate
    assert report.sqlite_integrity == "ok"
    assert report.foreign_key_violations == ()
    print("PHASE18A_DATABASE_MIGRATION_GATE = PASS")
    print("INVENTORY =", repo.inventory())
