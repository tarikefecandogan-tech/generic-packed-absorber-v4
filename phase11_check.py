from generic_absorber_v4 import run_phase11_estimation_gate

r = run_phase11_estimation_gate()
print("PHASE11_PROPERTY_ESTIMATION_GATE =", "PASS" if r.pass_gate else "FAIL")
print(f"DG_Fuller = {r.estimated_DG_m2_s:.12e} m2/s")
print(f"DL_WilkeChang = {r.estimated_DL_m2_s:.12e} m2/s")
print("DB_PRIORITY =", "PASS" if r.reference_database_priority_pass else "FAIL")
print("OVERRIDE_PRIORITY =", "PASS" if r.override_priority_pass else "FAIL")
print("MISSING_INPUT_BLOCK =", "PASS" if r.missing_input_block_pass else "FAIL")
raise SystemExit(0 if r.pass_gate else 1)
