"""Standalone Phase 10 synthetic generic-chemistry gate."""
from generic_absorber_v4 import run_synthetic_generic_case

report = run_synthetic_generic_case()
assert report.pass_gate
assert report.core_name_independence_pass
assert report.numerical_health_pass
assert len(report.pre_applicability.blocks) == 0
assert len(report.post_applicability.blocks) == 0
assert len(report.solver_results.components) == 2

print(f"SYNTHETIC_CASE_ID = {report.case_id}")
print(f"PRE_STATUS = {report.pre_applicability.status.value}")
print(f"POST_STATUS = {report.post_applicability.status.value}")
print(f"CORE_NAME_INDEPENDENCE = {'PASS' if report.core_name_independence_pass else 'FAIL'}")
for sid, result in report.solver_results.components.items():
    mt = report.transfer_results[sid]
    print(
        f"{sid}: model={mt.equilibrium_model}, y_out={result.gas_outlet_y:.12g}, "
        f"removal={100.0*result.removal_fraction:.6f}%, "
        f"mass_balance_rel_error={result.diagnostics.relative_mass_balance_error:.3e}"
    )
print(f"FLOODING_PERCENT = {report.hydraulics.flooding.flooding_percent:.6f}")
print(f"OUTLET_TOTAL_PPMV = {report.gas_balance.outlet.total_ppmv:.9f}")
print("PHASE10_SYNTHETIC_GENERIC_GATE = PASS")
