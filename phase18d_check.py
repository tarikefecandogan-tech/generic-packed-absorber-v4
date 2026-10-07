from pathlib import Path

from generic_absorber_v4 import run_phase18d_cutover_gate

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "database" / "absorber_database_v18b.db"
report = run_phase18d_cutover_gate(DB_PATH)

print("PHASE18D_SQLITE_PRIMARY_CUTOVER_GATE =", "PASS" if report.pass_gate else "FAIL")
print("ACTIVE_BACKEND =", report.decision.active_backend_id)
print("ACTIVE_KIND =", report.decision.active_kind.value)
print("SQLITE_INTEGRITY =", report.decision.sqlite_integrity)
print("FK_VIOLATIONS =", report.decision.foreign_key_violations)
print("FALLBACK_USED =", report.decision.fallback_used)
print("PARITY_SCENARIOS =", len(report.parity.scenarios))
print("PARITY_METRICS =", report.parity.metrics_checked)
print("FALLBACK_POLICY_TEST =", "PASS" if report.fallback_test_passed else "FAIL")
print("STRICT_POLICY_TEST =", "PASS" if report.strict_failure_test_passed else "FAIL")
raise SystemExit(0 if report.pass_gate else 1)
