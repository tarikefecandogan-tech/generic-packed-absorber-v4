from pathlib import Path
from generic_absorber_v4 import run_phase18f_expansion_gate

DB = Path(__file__).resolve().parent / "database" / "absorber_database_v18b.db"
r = run_phase18f_expansion_gate(DB)
print("PHASE18F_CHEMICAL_EXPANSION_GATE =", "PASS" if r.pass_gate else "FAIL")
print(r)
raise SystemExit(0 if r.pass_gate else 1)
