from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    CompositionFractionBasis,
    GasConcentrationBasis,
    GenericAbsorberCase,
    build_phase14_registry,
    canonical_y_from_total_and_fractions,
    compare_packings,
    compare_solvents,
)

r = build_phase14_registry()
solutes = {sid: r.get_solute(sid) for sid in ("ACN", "VAc")}
feed = canonical_y_from_total_and_fractions(
    5000.0, GasConcentrationBasis.MG_VOC_NM3,
    {"ACN": 0.93, "VAc": 0.07}, CompositionFractionBasis.VOC_MASS, solutes,
)
ref = GenericAbsorberCase(
    operating=AbsorberOperatingPoint(0.5, 1.4, 117.53, 2500.0, 295.15, 101325.0),
    solute_ids=("ACN", "VAc"), carrier_id="air", solvent_id="water",
    packing_id="25mm_metal_pall_ring", gas_inlet_y=feed.canonical_y,
    liquid_inlet_x={"ACN": 0.0, "VAc": 0.0},
)
pack = compare_packings(ref, ["25mm_metal_pall_ring", "38mm_metal_pall_ring", "imtp_25"], registry=r)
assert pack.successful_alternatives == 3

vdc = GenericAbsorberCase(
    operating=ref.operating, solute_ids=("VDC",), carrier_id="air", solvent_id="water",
    packing_id="25mm_metal_pall_ring", gas_inlet_y={"VDC": 1000e-6}, liquid_inlet_x={"VDC": 0.0},
)
solv = compare_solvents(vdc, ["water", "acrylonitrile"], registry=r, solvent_evaporation_expected={"acrylonitrile": True})
assert solv.successful_alternatives == 2
assert solv.alternatives[1].confidence == "SCREENING"
print("PHASE17_COMPARISON_GATE = PASS")
