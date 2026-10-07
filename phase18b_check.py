from pathlib import Path
import tempfile

from generic_absorber_v4 import (
    build_phase18a_source_registry,
    build_phase18b_database,
    compare_registry_to_phase18b_sqlite,
)

with tempfile.TemporaryDirectory() as td:
    repo = build_phase18b_database(Path(td) / "absorber_v18b.db")
    report = compare_registry_to_phase18b_sqlite(build_phase18a_source_registry(), repo)
    assert report.pass_gate
    assert report.sqlite_integrity == "ok"
    assert report.foreign_key_violations == ()
    assert report.coverage.unresolved_source_metadata == 0
    print("PHASE18B_STRUCTURED_PROVENANCE_GATE = PASS")
    print("COVERAGE =", report.coverage)
