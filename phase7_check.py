"""Standalone Phase 7 gate for the locked reference unit/composition basis."""
from generic_absorber_v4 import (
    CompositionFractionBasis,
    GasConcentrationBasis,
    build_reference_registry,
    canonical_y_from_total_and_fractions,
    gas_stream_balance,
)

reg = build_reference_registry()
feed = canonical_y_from_total_and_fractions(
    5000.0,
    GasConcentrationBasis.MG_VOC_NM3,
    {"ACN": 0.93, "VAc": 0.07},
    CompositionFractionBasis.VOC_MASS,
    reg.solutes,
)
outlet_y = {
    "ACN": 3.991282910574221e-06,
    "VAc": 2.5299699106660017e-05,
}
bal = gas_stream_balance(feed.canonical_y, outlet_y, reg.solutes)

assert abs(feed.report.total_mgVOC_Nm3 - 5000.0) < 1e-9
assert abs(feed.report.total_mgC_Nm3 - 3353.1344673788503) < 1e-9
assert abs(feed.report.total_ppmv - 2055.409210811772) < 1e-9
assert abs(bal.outlet.total_mgVOC_Nm3 - 106.62228136662561) < 1e-9
assert abs(bal.outlet.total_mgC_Nm3 - 60.645957347814814) < 1e-9
assert abs(bal.outlet.total_ppmv - 29.29098201723424) < 1e-9

print("PHASE7_UNITS_COMPOSITION_GATE = PASS")
