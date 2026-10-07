from pathlib import Path
from generic_absorber_v4 import run_phase18g_verified_batch_gate

ROOT = Path(__file__).resolve().parent
DB = ROOT / "database" / "absorber_database_v18g.db"
r = run_phase18g_verified_batch_gate(DB)
print("PHASE18G_FIRST_VERIFIED_CHEMICAL_BATCH_GATE =", "PASS" if r.pass_gate else "FAIL")
print("integrity=", r.integrity)
print("foreign_key_violations=", r.foreign_key_violations)
print("inventory_solutes=", r.inventory_solutes)
print("inventory_equilibrium_pairs=", r.inventory_equilibrium_pairs)
print("identity_ok=", r.identity_ok)
print("henry_ok=", r.henry_ok)
print("transport_estimated_c=", r.transport_estimated_c)
print("water_coverage_estimated=", r.water_coverage_estimated)
print("acrylonitrile_coverage_missing=", r.acrylonitrile_coverage_missing)
print("no_new_fixed_transport_pairs=", r.no_new_fixed_transport_pairs)
print("provenance_field_split_ok=", r.provenance_field_split_ok)
for f in r.fixture_results:
    print(f"{f.solute_id}: outlet={f.outlet_ppmv:.6g} ppmv, removal={100*f.removal_fraction:.6g}%, A={f.absorption_factor:.6g}, HTU={f.HTU_OG_m:.6g} m, MB={f.mass_balance_error:.3e}, readiness={f.readiness}")
raise SystemExit(0 if r.pass_gate else 1)
