from pathlib import Path
import tempfile

from generic_absorber_v4 import (
    build_phase18b_database,
    build_python_registry_repository,
    build_sqlite_v18b_repository,
    run_phase18c_repository_parity,
)

with tempfile.TemporaryDirectory() as td:
    db_path = Path(td) / "absorber_v18b.db"
    build_phase18b_database(db_path)
    py_repo = build_python_registry_repository()
    db_repo = build_sqlite_v18b_repository(db_path)
    report = run_phase18c_repository_parity(py_repo, db_repo)

print("PHASE18C_REPOSITORY_ABSTRACTION_GATE =", "PASS" if report.pass_gate else "FAIL")
print("SCENARIOS =", len(report.scenarios))
print("METRICS_CHECKED =", report.metrics_checked)
for row in report.scenarios:
    print(row.scenario_id, "PASS" if row.pass_gate else "FAIL", row.metrics_checked, row.max_absolute_error, row.max_relative_error)
raise SystemExit(0 if report.pass_gate else 1)
