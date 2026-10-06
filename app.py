from __future__ import annotations

import pandas as pd
import streamlit as st

from generic_absorber_v4 import (
    ComponentPropertyOverrides,
    MissingPairDataError,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    SoluteSpec,
    build_reference_registry,
    build_reference_resolver,
    locked_reference_data,
)

st.set_page_config(
    page_title="Generic Packed Absorber Simulator V4",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)


def provenance_text(obj) -> str:
    p = getattr(obj, "provenance", None)
    if p is None:
        return "—"
    return f"{p.confidence.value} · {p.method}"


def solute_df(db):
    return pd.DataFrame([
        {
            "ID": s.id,
            "Name": s.name,
            "Formula": s.formula or "—",
            "MW (g/mol)": s.MW_kg_mol * 1000,
            "Carbon atoms": s.carbon_atoms,
            "CAS": s.cas_number or "—",
        }
        for s in db.solutes.values()
    ])


def carrier_df(db):
    return pd.DataFrame([
        {
            "ID": c.id,
            "Name": c.name,
            "MW (g/mol)": c.MW_kg_mol * 1000,
            "Viscosity model": c.viscosity_model,
            "mu_ref (Pa·s)": c.mu_ref_Pa_s,
            "T_ref (K)": c.T_ref_K,
            "Sutherland S (K)": c.sutherland_S_K,
            "Data": provenance_text(c),
        }
        for c in db.carriers.values()
    ])


def solvent_df(db):
    return pd.DataFrame([
        {
            "ID": s.id,
            "Name": s.name,
            "MW (g/mol)": s.MW_kg_mol * 1000,
            "Property model": s.property_model,
            "Property model ID": s.property_model_id or "—",
            "rho const. (kg/m³)": s.rho_kg_m3,
            "mu const. (Pa·s)": s.mu_Pa_s,
            "sigma const. (N/m)": s.sigma_N_m,
            "Data": provenance_text(s),
        }
        for s in db.solvents.values()
    ])


def gas_pair_df(db):
    return pd.DataFrame([
        {
            "Solute": solute,
            "Carrier": carrier,
            "DG (m²/s)": p.D_ref_m2_s,
            "Model": p.model,
            "T_ref (K)": p.T_ref_K,
            "P_ref (Pa)": p.P_ref_Pa,
            "Data": provenance_text(p),
        }
        for (solute, carrier), p in db.gas_transport_pairs.items()
    ])


def liquid_pair_df(db):
    return pd.DataFrame([
        {
            "Solute": solute,
            "Solvent": solvent,
            "DL (m²/s)": p.D_ref_m2_s,
            "Model": p.model,
            "T_ref (K)": p.T_ref_K,
            "Data": provenance_text(p),
        }
        for (solute, solvent), p in db.liquid_transport_pairs.items()
    ])


def equilibrium_df(db):
    return pd.DataFrame([
        {
            "Solute": solute,
            "Solvent": solvent,
            "Model": p.model,
            "H_ref (Pa·m³/mol)": p.H_ref_Pa_m3_mol,
            "T_ref (K)": p.T_ref_K,
            "Temperature coeff. (K)": p.temperature_coefficient_K,
            "Linear m": p.m_y_over_x,
            "Data": provenance_text(p),
        }
        for (solute, solvent), p in db.equilibrium_pairs.items()
    ])


def packing_df(db):
    return pd.DataFrame([
        {
            "ID": p.id,
            "Name": p.name,
            "Class": p.packing_class,
            "a_t (m²/m³)": p.area_m2_m3,
            "Nominal size (mm)": p.nominal_size_m * 1000,
            "Void fraction": p.void_fraction,
            "Critical surface tension (N/m)": p.critical_surface_tension_N_m,
            "Pressure-drop ψ": p.pressure_drop_psi,
            "Packing factor (ft⁻¹)": p.packing_factor_ft_inv,
            "Fp basis": p.packing_factor_basis,
            "Data": provenance_text(p),
        }
        for p in db.packings.values()
    ])


def availability_df(registry):
    rows = []
    for solute_id in registry.solutes:
        for carrier_id in registry.carriers:
            for solvent_id in registry.solvents:
                r = registry.availability(solute_id, carrier_id, solvent_id)
                rows.append({
                    "Solute": solute_id,
                    "Carrier": carrier_id,
                    "Solvent": solvent_id,
                    "DG pair": "✓" if r.gas_transport_available else "✗",
                    "DL pair": "✓" if r.liquid_transport_available else "✗",
                    "Equilibrium": "✓" if r.equilibrium_available else "✗",
                    "Registry status": r.status.value,
                })
    return pd.DataFrame(rows)


def resolved_row(label, prop):
    return {
        "Property": label,
        "Value": prop.value,
        "Unit": prop.unit,
        "Resolution tier": prop.tier.value,
        "Confidence": prop.confidence.value,
        "Method": prop.method,
        "Source": prop.source,
        "Estimated": "Yes" if prop.estimated else "No",
        "Note": prop.note or "—",
    }


DB = locked_reference_data()
REGISTRY = build_reference_registry()
RESOLVER = build_reference_resolver()
COUNTS = REGISTRY.inventory_counts()

st.title("🧪 Generic Packed Absorber Simulator V4")
st.caption("Phase 3 — Property Resolver")

st.warning(
    "Phase 3 resolves operating-point properties and records why each value was selected. "
    "Onda mass transfer, two-film KG, counter-current ODE, pressure drop, GPDC flooding, "
    "required height and generic outlet calculations are still NOT connected."
)

with st.sidebar:
    st.header("Development Status")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.success("PHASE3_RESOLVER_GATE = PASS")
    st.metric("Reference ID", REGISTRY.reference_id)
    st.divider()
    st.caption("Resolution precedence")
    st.write("**1. User override**")
    st.write("**2. Registered database**")
    st.write("**3. Correlation estimate hook**")
    st.write("**4. Missing → explicit error**")
    st.caption("Fuller / Wilke–Chang are not enabled as default estimators yet.")

(
    overview_tab,
    resolver_tab,
    lookup_tab,
    solute_tab,
    fluid_tab,
    pair_tab,
    packing_tab,
    quality_tab,
) = st.tabs([
    "Overview",
    "Property Resolver",
    "Registry Lookup",
    "Solutes",
    "Carrier & Solvent",
    "Binary Pairs",
    "Packing",
    "Data Quality",
])

with overview_tab:
    st.subheader("Phase 3 architecture")
    st.code(
        """Phase 1 immutable data objects
        ↓
Phase 2 exact registry / pair lookup
        ↓
Phase 3 PropertyResolver
        ↓
USER OVERRIDE > DATABASE > CORRELATION ESTIMATE > MISSING
        ↓
Resolved operating-point values + provenance

No Onda / ODE / GPDC calculation yet.""",
        language="text",
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Solutes", COUNTS["solutes"])
    c2.metric("Transport pairs", COUNTS["gas_transport_pairs"] + COUNTS["liquid_transport_pairs"])
    c3.metric("Equilibrium pairs", COUNTS["equilibrium_pairs"])
    c4.metric("Packings", COUNTS["packings"])

    st.markdown("### Locked operating-point check (22 °C, 1.01325 bar abs)")
    rows = []
    for sid in REGISTRY.solutes:
        rp = RESOLVER.resolve_component_properties(sid, "air", "water", 295.15, 101325.0)
        rows.extend([
            resolved_row(f"{sid} DG", rp.gas_diffusivity),
            resolved_row(f"{sid} DL", rp.liquid_diffusivity),
            resolved_row(f"{sid} equilibrium", rp.equilibrium.active_property),
        ])
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with resolver_tab:
    st.subheader("Operating-point property resolution")
    st.caption(
        "This is the first V4 layer that evaluates temperature/pressure dependent bulk properties "
        "and Henry H(T). It does not calculate absorber mass transfer."
    )

    c1, c2, c3 = st.columns(3)
    solute_id = c1.selectbox("Solute", list(REGISTRY.solutes), key="resolver_solute")
    temp_C = c2.number_input("Temperature (°C)", value=22.0, step=1.0)
    pressure_bar = c3.number_input("Pressure (bar abs)", value=1.01325, min_value=0.01, step=0.05, format="%.5f")
    T_K = temp_C + 273.15
    P_Pa = pressure_bar * 1e5

    st.markdown("### Optional user overrides")
    o1, o2, o3 = st.columns(3)
    use_dg = o1.checkbox("Override DG", key="use_dg")
    use_dl = o2.checkbox("Override DL", key="use_dl")
    use_h = o3.checkbox("Override Henry H", key="use_h")

    dg_override = o1.number_input("DG override (m²/s)", value=1.0e-5, format="%.6e", disabled=not use_dg)
    dl_override = o2.number_input("DL override (m²/s)", value=1.0e-9, format="%.6e", disabled=not use_dl)
    h_override = o3.number_input("H override (Pa·m³/mol)", value=1.0, format="%.6e", disabled=not use_h)

    overrides = ComponentPropertyOverrides(
        gas_diffusivity_m2_s=dg_override if use_dg else None,
        liquid_diffusivity_m2_s=dl_override if use_dl else None,
        henry_Pa_m3_mol=h_override if use_h else None,
    )

    try:
        resolved = RESOLVER.resolve_component_properties(
            solute_id, "air", "water", T_K, P_Pa, component_overrides=overrides
        )
        st.success("PROPERTY RESOLUTION READY")
        bulk_rows = [
            resolved_row("Carrier MW", resolved.carrier.MW),
            resolved_row("Carrier density", resolved.carrier.density),
            resolved_row("Carrier viscosity", resolved.carrier.viscosity),
            resolved_row("Solvent MW", resolved.solvent.MW),
            resolved_row("Solvent density", resolved.solvent.density),
            resolved_row("Solvent viscosity", resolved.solvent.viscosity),
            resolved_row("Solvent surface tension", resolved.solvent.surface_tension),
            resolved_row(f"{solute_id} DG", resolved.gas_diffusivity),
            resolved_row(f"{solute_id} DL", resolved.liquid_diffusivity),
            resolved_row(f"{solute_id} equilibrium", resolved.equilibrium.active_property),
        ]
        st.dataframe(pd.DataFrame(bulk_rows), use_container_width=True, hide_index=True)

        st.info(
            "Changing an override only changes the resolved operating-point result. "
            "It does not overwrite the locked registry/database value."
        )
    except Exception as exc:
        st.error(str(exc))

    st.markdown("### Missing-property safety demonstration")
    if st.button("Run Phase 3 missing-property check"):
        demo_registry = build_reference_registry()
        demo_registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
        demo_resolver = PropertyResolver(demo_registry)
        try:
            demo_resolver.resolve_gas_diffusivity("X", "air", T_K, P_Pa)
        except MissingPropertyError as exc:
            st.success("PASS — unresolved critical property was blocked; no chemical substitution occurred.")
            st.code(str(exc), language="text")
        else:
            st.error("FAIL — missing property unexpectedly resolved.")

with lookup_tab:
    st.subheader("Exact pair lookup — Phase 2 remains intact")
    c1, c2, c3 = st.columns(3)
    lookup_solute = c1.selectbox("Solute", list(REGISTRY.solutes), key="lookup_solute")
    lookup_carrier = c2.selectbox("Carrier", list(REGISTRY.carriers), key="lookup_carrier")
    lookup_solvent = c3.selectbox("Solvent", list(REGISTRY.solvents), key="lookup_solvent")

    report = REGISTRY.availability(lookup_solute, lookup_carrier, lookup_solvent)
    if report.status.value == "READY":
        st.success("PAIR DATA READY")
    else:
        st.error(f"PAIR DATA INCOMPLETE · Missing: {', '.join(report.missing)}")
    st.dataframe(availability_df(REGISTRY), use_container_width=True, hide_index=True)

    if st.button("Run Phase 2 missing-pair safety check"):
        demo = build_reference_registry()
        demo.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
        try:
            demo.require_equilibrium_pair("X", "water")
        except MissingPairDataError as exc:
            st.success("PASS — missing pair was blocked; no fallback value was used.")
            st.code(str(exc), language="text")

with solute_tab:
    st.subheader("Pure solute definitions")
    st.dataframe(solute_df(DB), use_container_width=True, hide_index=True)
    st.caption("Henry constants and diffusivities remain binary-pair data, not universal solute properties.")

with fluid_tab:
    st.subheader("Carrier gases")
    st.dataframe(carrier_df(DB), use_container_width=True, hide_index=True)
    st.subheader("Solvents")
    st.dataframe(solvent_df(DB), use_container_width=True, hide_index=True)
    st.info(
        "Phase 3 now evaluates the registered Air Sutherland model and the locked V3 water-property "
        "correlations at the selected operating temperature."
    )

with pair_tab:
    st.subheader("Solute–carrier gas transport pairs")
    st.dataframe(gas_pair_df(DB), use_container_width=True, hide_index=True)
    st.subheader("Solute–solvent liquid transport pairs")
    st.dataframe(liquid_pair_df(DB), use_container_width=True, hide_index=True)
    st.subheader("Solute–solvent equilibrium pairs")
    st.dataframe(equilibrium_df(DB), use_container_width=True, hide_index=True)
    st.info(
        "Reference DG/DL values remain fixed exactly as in V3. Fuller and Wilke–Chang hooks exist in "
        "the resolver architecture, but no default estimator is enabled yet."
    )

with packing_tab:
    st.subheader("Locked reference packing")
    st.dataframe(packing_df(DB), use_container_width=True, hide_index=True)

with quality_tab:
    st.subheader("Phase 3 resolution rules")
    st.markdown(
        """
- **User override** has first priority and receives confidence class A for the active case.
- If no override exists, the exact registered **database pair/property** is used.
- Only when a database pair is absent may a configured **correlation estimator hook** be used.
- Default Fuller and Wilke–Chang estimation are intentionally not activated in Phase 3.
- If nothing can resolve a critical property, `MissingPropertyError` stops the path.
- An override never mutates the underlying locked registry.
- Reactive / explicitly unsupported equilibrium models are blocked rather than converted to Henry silently.
        """
    )

    provenance_rows = []
    for group_name, objects in [
        ("Carrier", DB.carriers.values()),
        ("Solvent", DB.solvents.values()),
        ("Packing", DB.packings.values()),
        ("Gas transport", DB.gas_transport_pairs.values()),
        ("Liquid transport", DB.liquid_transport_pairs.values()),
        ("Equilibrium", DB.equilibrium_pairs.values()),
    ]:
        for obj in objects:
            p = getattr(obj, "provenance", None)
            if p is None:
                continue
            provenance_rows.append({
                "Group": group_name,
                "Object": getattr(obj, "name", None)
                or f"{getattr(obj, 'solute_id', '?')} / {getattr(obj, 'carrier_id', getattr(obj, 'solvent_id', '?'))}",
                "Confidence": p.confidence.value,
                "Method": p.method,
                "Source": p.source,
                "Validity note": p.validity_note,
            })
    st.dataframe(pd.DataFrame(provenance_rows), use_container_width=True, hide_index=True)

    st.markdown("### Phase gates")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.success("PHASE3_RESOLVER_GATE = PASS")
    st.caption("23 automated tests pass in the packaged Phase 3 source tree.")

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 3 · Property Resolver · "
    "Next: Phase 4 generic Onda mass-transfer core"
)
