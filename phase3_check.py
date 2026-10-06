"""Small dependency-free Phase 3 gate check."""
from generic_absorber_v4 import (
    ComponentPropertyOverrides,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    SoluteSpec,
    build_reference_registry,
    build_reference_resolver,
)

T = 295.15
P = 101325.0
r = build_reference_resolver()
acn = r.resolve_component_properties("ACN", "air", "water", T, P)
vac = r.resolve_component_properties("VAc", "air", "water", T, P)

assert abs(acn.carrier.density.value - 1.19739554421) < 1e-10
assert abs(acn.solvent.density.value - 997.800320317) < 1e-8
assert abs(acn.gas_diffusivity.value - 1.0e-5) < 1e-20
assert abs(acn.liquid_diffusivity.value - 1.0e-9) < 1e-20
assert abs(acn.equilibrium.henry_Pa_m3_mol.value - 1.03613136396) < 1e-10
assert abs(vac.equilibrium.henry_Pa_m3_mol.value - 44.4131946273) < 1e-8

ovr = r.resolve_component_properties(
    "ACN", "air", "water", T, P,
    component_overrides=ComponentPropertyOverrides(gas_diffusivity_m2_s=2e-5),
)
assert ovr.gas_diffusivity.tier == ResolutionTier.USER_OVERRIDE
assert r.resolve_gas_diffusivity("ACN", "air", T, P).value == 1e-5

reg = build_reference_registry()
reg.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
try:
    PropertyResolver(reg).resolve_gas_diffusivity("X", "air", T, P)
except MissingPropertyError:
    pass
else:
    raise AssertionError("Missing property was not blocked")

print("ACN H(22C):", acn.equilibrium.henry_Pa_m3_mol.value)
print("VAc H(22C):", vac.equilibrium.henry_Pa_m3_mol.value)
print("Air rho(22C):", acn.carrier.density.value)
print("Water rho(22C):", acn.solvent.density.value)
print("override precedence: PASS")
print("missing-property safety: PASS")
print("PHASE3_RESOLVER_GATE=PASS")
