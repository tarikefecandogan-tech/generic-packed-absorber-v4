"""Compare Phase 1 reference data directly with the locked V3 source constants.

No simulation is run; this checks data migration only.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

from generic_absorber_v4 import locked_reference_data

DEFAULT_SOURCE = Path(__file__).resolve().parent.parent / "scrubber_model.py"


def load_source(path: Path):
    spec = importlib.util.spec_from_file_location("locked_v3_scrubber_model", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import source: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(source_path: str | None = None) -> None:
    path = Path(source_path) if source_path else DEFAULT_SOURCE
    if not path.exists():
        raise FileNotFoundError(f"Locked V3 source not found: {path}")

    v3 = load_source(path)
    v4 = locked_reference_data()

    # Pure components
    assert v4.solutes["ACN"].MW_kg_mol == v3.VOC["ACN"]["MW"]
    assert v4.solutes["ACN"].carbon_atoms == v3.VOC["ACN"]["nC"]
    assert v4.solutes["VAc"].MW_kg_mol == v3.VOC["VAc"]["MW"]
    assert v4.solutes["VAc"].carbon_atoms == v3.VOC["VAc"]["nC"]
    assert v4.carriers["air"].MW_kg_mol == v3.GAS["MW"]
    assert v4.carriers["air"].mu_ref_Pa_s == v3.GAS["mu_ref"]
    assert v4.carriers["air"].T_ref_K == v3.GAS["T_ref"]
    assert v4.carriers["air"].sutherland_S_K == v3.GAS["S"]
    assert v4.solvents["water"].MW_kg_mol == v3.WATER_MW

    # Packing
    src_p = v3.PACKING_DATA["25mm Metal Pall Ring"]
    dst_p = v4.packings["25mm_metal_pall_ring"]
    assert dst_p.area_m2_m3 == src_p["a"]
    assert dst_p.nominal_size_m == src_p["d"]
    assert dst_p.void_fraction == src_p["epsilon"]
    assert dst_p.critical_surface_tension_N_m == src_p["sigma_c"]
    assert dst_p.pressure_drop_psi == src_p["psi"]
    assert dst_p.packing_factor_ft_inv == src_p["Fp_ft"]

    # Pair transport + equilibrium
    for comp in ("ACN", "VAc"):
        assert v4.gas_transport_pairs[(comp, "air")].D_ref_m2_s == v3.VOC[comp]["DG"]
        assert v4.liquid_transport_pairs[(comp, "water")].D_ref_m2_s == v3.VOC[comp]["DL"]
        eq = v4.equilibrium_pairs[(comp, "water")]
        assert eq.H_ref_Pa_m3_mol == v3.VOC[comp]["H25_atm_m3_mol"] * v3.P_N
        assert eq.temperature_coefficient_K == v3.VOC[comp]["DH_H_over_R"]

    print(f"SOURCE={path}")
    print("PHASE1_V3_SOURCE_MATCH=PASS")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
