from pathlib import Path
from generic_absorber_v4 import run_phase18e_explorer_gate

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "absorber_database_v18b.db"
report = run_phase18e_explorer_gate(DB)
print("PHASE18E_DATABASE_EXPLORER_GATE =", "PASS" if report.pass_gate else "FAIL")
print("SQLite integrity =", report.integrity)
print("Foreign-key violations =", report.foreign_key_violations)
print("Coverage cells =", report.matrix_cells)
print("Coverage summary =", report.summary)
print("VDC search hits =", report.search_vdc_hits)
print("Database unchanged =", report.database_unchanged)
for key, value in report.expected_reference_statuses.items():
    print(f"{key} = {'PASS' if value else 'FAIL'}")
if not report.pass_gate:
    raise SystemExit(1)
