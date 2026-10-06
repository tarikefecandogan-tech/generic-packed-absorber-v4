"""Standalone Phase 9 full V3 parity gate."""
from generic_absorber_v4 import reference_chain_health, run_full_v3_parity

report = run_full_v3_parity()
health = reference_chain_health()

assert report.passed
assert report.failed_count == 0
assert health["phase8_pre_status"] == "READY"
assert health["phase8_final_status"] == "READY_WITH_WARNINGS"

print(f"REFERENCE_ID = {report.reference_id}")
print(f"REFERENCE_SOURCE_SHA256 = {report.reference_source_sha256}")
for section, metrics in report.sections.items():
    passed = sum(m.passed for m in metrics)
    print(f"{section}: {passed}/{len(metrics)} PASS")
print(f"TOTAL_PARITY_METRICS = {report.passed_count}/{report.total_count} PASS")
print(f"PHASE8_FINAL_STATUS = {health['phase8_final_status']}")
print("PHASE9_FULL_V3_PARITY_GATE = PASS")
