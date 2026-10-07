from generic_absorber_v4 import run_vdc_acn_case

r = run_vdc_acn_case()
assert r.pass_gate
print("PHASE13_VDC_ACN_GATE = PASS")
print(f"m = {r.transfer.equilibrium_slope_m:.12g}")
print(f"A = {r.transfer.absorption_factor:.12g}")
print(f"HTU_OG = {r.transfer.HTU_OG_m:.12g} m")
print(f"NTU_OG = {r.transfer.NTU_OG:.12g}")
print(f"outlet = {r.gas_outlet_report.total_ppmv:.12g} ppmv")
print(f"removal = {100*r.solver.removal_fraction:.12g} %")
print(f"water removal = {100*r.water_removal_fraction:.12g} %")
print(f"improvement factor = {r.removal_improvement_factor_vs_water:.12g}")
print(f"ACN vapor pressure = {r.acn_vapor_pressure_Pa:.12g} Pa")
print(f"wet dP = {r.hydraulics.pressure_drop.wet_pressure_drop_Pa_m:.12g} Pa/m")
print(f"flood = {r.hydraulics.flooding.flooding_percent:.12g} %")
print(f"status = {r.post_applicability.status.value}")
print(f"confidence = {r.post_applicability.confidence.overall.value}")
