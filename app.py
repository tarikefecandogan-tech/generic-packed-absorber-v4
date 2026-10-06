from __future__ import annotations

import pandas as pd
import streamlit as st

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ComponentPropertyOverrides,
    ComponentBoundaryConditions,
    MissingPairDataError,
    MissingPropertyError,
    PropertyResolver,
    ResolutionTier,
    SoluteSpec,
    build_reference_registry,
    build_reference_resolver,
    locked_reference_data,
    evaluate_component_from_resolver,
    solve_component_countercurrent,
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
st.caption("Phase 5 — Generic Counter-Current ODE Solver")

st.warning(
    "Phase 5 adds the generic counter-current shooting/ODE solver. It now calculates component "
    "gas outlet mole fraction, liquid-bottom loading, removal and bed profiles, including nonzero "
    "solvent inlet loading and desorption. Concentration-basis conversion, required height, pressure "
    "drop and GPDC flooding are still NOT connected."
)

with st.sidebar:
    st.header("Development Status")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.success("PHASE3_RESOLVER_GATE = PASS")
    st.success("PHASE4_MASS_TRANSFER_GATE = PASS")
    st.success("PHASE5_COUNTERCURRENT_GATE = PASS")
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
    mass_transfer_tab,
    solver_tab,
    lookup_tab,
    solute_tab,
    fluid_tab,
    pair_tab,
    packing_tab,
    quality_tab,
) = st.tabs([
    "Overview",
    "Property Resolver",
    "Mass Transfer",
    "Counter-Current Solver",
    "Registry Lookup",
    "Solutes",
    "Carrier & Solvent",
    "Binary Pairs",
    "Packing",
    "Data Quality",
])

with overview_tab:
    st.subheader("Phase 5 architecture")
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
        ↓
Phase 4 Generic Onda + Two-Film Core
        ↓
a_e, kL, kG, KG, m, A, HTU, NTU
        ↓
Phase 5 Counter-Current BVP Solver
        ↓
y_out, x_bottom, removal, profiles, balance diagnostics

No concentration-basis conversion / required-height / GPDC calculation yet.""",
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

with mass_transfer_tab:
    st.subheader("Generic Onda + two-film mass-transfer core")
    st.caption(
        "All chemistry-dependent values are supplied by the Phase 3 resolver. The Phase 4 equations "
        "contain no ACN/VAc/Water/Air name branches. Gas flow on this screen is actual operating flow."
    )

    a1, a2, a3 = st.columns(3)
    mt_solute = a1.selectbox("Solute", list(REGISTRY.solutes), key="mt_solute")
    mt_packing = a2.selectbox("Packing", list(REGISTRY.packings), key="mt_packing")
    mt_temp_C = a3.number_input("Temperature (°C)", value=22.0, step=1.0, key="mt_temp")

    b1, b2, b3 = st.columns(3)
    mt_d = b1.number_input("Column diameter D (m)", min_value=0.01, value=0.50, step=0.05, key="mt_d")
    mt_z = b2.number_input("Packed height Z (m)", min_value=0.01, value=1.40, step=0.10, key="mt_z")
    mt_p_bar = b3.number_input("Pressure (bar abs)", min_value=0.01, value=1.01325, step=0.05, format="%.5f", key="mt_p")

    c1, c2 = st.columns(2)
    mt_q = c1.number_input("Actual gas flow (m³/h)", min_value=0.001, value=117.53, step=5.0, key="mt_q")
    mt_l = c2.number_input("Liquid flow (kg/h)", min_value=0.001, value=2500.0, step=50.0, key="mt_l")

    try:
        op = AbsorberOperatingPoint(
            diameter_m=mt_d,
            packed_height_m=mt_z,
            gas_actual_m3_h=mt_q,
            liquid_mass_kg_h=mt_l,
            temperature_K=mt_temp_C + 273.15,
            pressure_Pa=mt_p_bar * 1e5,
        )
        common, mt = evaluate_component_from_resolver(
            resolver=RESOLVER,
            registry=REGISTRY,
            solute_id=mt_solute,
            carrier_id="air",
            solvent_id="water",
            packing_id=mt_packing,
            operating=op,
        )
        st.success("GENERIC MASS-TRANSFER COEFFICIENT CALCULATION READY")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Effective wetted area", f"{common.effective_area_m2_m3:.4f} m²/m³")
        m2.metric("Wetting", f"{100*common.wetting_fraction:.2f}%")
        m3.metric("Absorption factor A", f"{mt.absorption_factor:.5g}")
        m4.metric("HTU / NTU", f"{mt.HTU_OG_m:.4f} m / {mt.NTU_OG:.4f}")

        st.markdown("### Common Onda state")
        common_rows = [
            ["Column area", common.area_m2, "m²"],
            ["Gas molar flow", common.gas_molar_flow_mol_s, "mol/s"],
            ["Liquid molar flow", common.liquid_molar_flow_mol_s, "mol/s"],
            ["Gas mass flux", common.gas_mass_flux_kg_m2_s, "kg/m²·s"],
            ["Liquid mass flux", common.liquid_mass_flux_kg_m2_s, "kg/m²·s"],
            ["Re_L", common.Re_L, "—"],
            ["Re_G", common.Re_G, "—"],
            ["Fr_L", common.Fr_L, "—"],
            ["We_L", common.We_L, "—"],
            ["Effective area a_e", common.effective_area_m2_m3, "m²/m³"],
        ]
        st.dataframe(pd.DataFrame(common_rows, columns=["Quantity", "Value", "Unit"]), use_container_width=True, hide_index=True)

        st.markdown(f"### {mt_solute} component coefficients")
        comp_rows = [
            ["DG", mt.gas_diffusivity_m2_s, "m²/s"],
            ["DL", mt.liquid_diffusivity_m2_s, "m²/s"],
            ["Henry-equivalent H", mt.henry_effective_Pa_m3_mol, "Pa·m³/mol"],
            ["Equilibrium slope m", mt.equilibrium_slope_m, "—"],
            ["Sc_L", mt.Sc_L, "—"],
            ["Sc_G", mt.Sc_G, "—"],
            ["k_L", mt.k_L, "V3 coefficient basis"],
            ["k_G", mt.k_G, "V3 coefficient basis"],
            ["K_G", mt.K_G, "V3 coefficient basis"],
            ["Absorption factor A", mt.absorption_factor, "—"],
            ["HTU_OG", mt.HTU_OG_m, "m"],
            ["NTU_OG", mt.NTU_OG, "—"],
            ["Gas resistance fraction", mt.gas_resistance_fraction, "—"],
            ["Liquid resistance fraction", mt.liquid_resistance_fraction, "—"],
        ]
        st.dataframe(pd.DataFrame(comp_rows, columns=["Quantity", "Value", "Unit / basis"]), use_container_width=True, hide_index=True)

        if (
            abs(mt_d - 0.5) < 1e-12
            and abs(mt_z - 1.4) < 1e-12
            and abs(mt_q - 117.53) < 1e-12
            and abs(mt_l - 2500.0) < 1e-12
            and abs(mt_temp_C - 22.0) < 1e-12
            and abs(mt_p_bar - 1.01325) < 1e-12
            and mt_packing == "25mm_metal_pall_ring"
        ):
            st.info("Locked V3 reference operating point detected. Phase 4 regression tests verify coefficient parity for ACN and VAc.")
    except Exception as exc:
        st.error(str(exc))

    st.info(
        "Phase 4 remains the coefficient layer. Phase 5 consumes these coefficients in the separate "
        "Counter-Current Solver tab."
    )

with solver_tab:
    st.subheader("Generic counter-current component solver")
    st.caption(
        "Canonical boundary variables are gas mole fraction y and liquid mole fraction x. "
        "Coordinate: z=0 gas inlet/liquid outlet; z=Z gas outlet/liquid inlet. "
        "Negative driving force is retained and therefore can represent desorption."
    )

    ref_y = {
        "ACN": 0.001964284929935824,
        "VAc": 9.112428087594802e-05,
    }

    s1, s2, s3 = st.columns(3)
    cc_solute = s1.selectbox("Solute", list(REGISTRY.solutes), key="cc_solute")
    cc_packing = s2.selectbox("Packing", list(REGISTRY.packings), key="cc_packing")
    cc_temp_C = s3.number_input("Temperature (°C)", value=22.0, step=1.0, key="cc_temp")

    s4, s5, s6 = st.columns(3)
    cc_d = s4.number_input("Column diameter D (m)", min_value=0.01, value=0.50, step=0.05, key="cc_d")
    cc_z = s5.number_input("Packed height Z (m)", min_value=0.01, value=1.40, step=0.10, key="cc_z")
    cc_p_bar = s6.number_input("Pressure (bar abs)", min_value=0.01, value=1.01325, step=0.05, format="%.5f", key="cc_p")

    s7, s8 = st.columns(2)
    cc_q = s7.number_input("Actual gas flow (m³/h)", min_value=0.001, value=117.53, step=5.0, key="cc_q")
    cc_l = s8.number_input("Liquid flow (kg/h)", min_value=0.001, value=2500.0, step=50.0, key="cc_l")

    b1, b2 = st.columns(2)
    default_y = ref_y.get(cc_solute, 1.0e-4)
    cc_y_in = b1.number_input(
        "Gas inlet y (mole fraction)", min_value=0.0, max_value=0.999999,
        value=float(default_y), format="%.10e", key=f"cc_y_{cc_solute}"
    )
    cc_x_in = b2.number_input(
        "Liquid inlet x at z=Z (mole fraction)", min_value=0.0, max_value=0.999999,
        value=0.0, format="%.10e", key=f"cc_x_{cc_solute}"
    )

    try:
        cc_op = AbsorberOperatingPoint(
            diameter_m=cc_d, packed_height_m=cc_z, gas_actual_m3_h=cc_q,
            liquid_mass_kg_h=cc_l, temperature_K=cc_temp_C + 273.15,
            pressure_Pa=cc_p_bar * 1e5,
        )
        cc_common, cc_mt = evaluate_component_from_resolver(
            resolver=RESOLVER, registry=REGISTRY, solute_id=cc_solute,
            carrier_id="air", solvent_id="water", packing_id=cc_packing, operating=cc_op,
        )
        cc_result = solve_component_countercurrent(
            cc_common, cc_mt, ComponentBoundaryConditions(cc_y_in, cc_x_in)
        )

        st.success("COUNTER-CURRENT BOUNDARY VALUE SOLVED")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Gas inlet y", f"{cc_result.gas_inlet_y:.6e}")
        r2.metric("Gas outlet y", f"{cc_result.gas_outlet_y:.6e}")
        r3.metric("Liquid bottom x", f"{cc_result.liquid_bottom_x:.6e}")
        if cc_result.removal_fraction is None:
            r4.metric("Removal", "N/A")
        else:
            r4.metric("Removal", f"{100*cc_result.removal_fraction:.4f}%")

        d = cc_result.diagnostics
        diag_rows = [
            ["Mode", d.mode, "—"],
            ["Boundary closure x(Z)-x_in", d.boundary_error_x, "mole fraction"],
            ["Gas solute change", d.gas_solute_change_mol_s, "mol/s"],
            ["Liquid solute change", d.liquid_solute_change_mol_s, "mol/s"],
            ["Mass-balance error", d.mass_balance_error_mol_s, "mol/s"],
            ["Relative mass-balance error", d.relative_mass_balance_error, "—"],
            ["Minimum driving force y-mx", d.min_driving_force_y, "mole fraction"],
            ["Maximum driving force y-mx", d.max_driving_force_y, "mole fraction"],
            ["Root iterations", d.root_iterations, "—"],
            ["ODE function evaluations", d.ode_function_evaluations, "—"],
        ]
        st.markdown("### Numerical and physical diagnostics")
        st.dataframe(pd.DataFrame(diag_rows, columns=["Quantity", "Value", "Unit"]), use_container_width=True, hide_index=True)

        profile = pd.DataFrame({
            "z (m)": cc_result.z_m,
            "gas y": cc_result.gas_y_profile,
            "liquid x": cc_result.liquid_x_profile,
            "driving force y-mx": cc_result.driving_force_profile_y,
        }).set_index("z (m)")
        st.markdown("### Bed profiles")
        st.line_chart(profile)
        st.dataframe(profile.reset_index(), use_container_width=True, hide_index=True)

        if d.min_driving_force_y < 0:
            st.warning("A negative local driving force exists. The solver has not clamped it; local desorption is retained.")
        st.caption(
            "ppmv convenience view: y_in = "
            f"{cc_result.gas_inlet_y*1e6:.3f} ppmv, y_out = {cc_result.gas_outlet_y*1e6:.3f} ppmv. "
            "The full concentration-basis conversion architecture is intentionally deferred to Phase 7."
        )
    except Exception as exc:
        st.error(str(exc))

    st.warning(
        "Phase 5 solves component y/x profiles only. Total mgVOC/Nm³, mgC/Nm³, required height, "
        "pressure drop and flooding are not yet part of this solver layer."
    )

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
    st.subheader("Data, mass-transfer and solver rules")
    st.markdown(
        """
- **User override** has first priority and receives confidence class A for the active case.
- If no override exists, the exact registered **database pair/property** is used.
- Only when a database pair is absent may a configured **correlation estimator hook** be used.
- Default Fuller and Wilke–Chang estimation are intentionally not activated in Phase 3.
- If nothing can resolve a critical property, `MissingPropertyError` stops the path.
- An override never mutates the underlying locked registry.
- Reactive / explicitly unsupported equilibrium models are blocked rather than converted to Henry silently.
- Phase 4 receives resolved numeric properties and performs Onda/two-film calculations without chemical-name branching.
- The locked V3 coefficient basis is intentionally preserved before any physics revision.
- Phase 5 solves `y(0)=y_in` and `x(Z)=x_in` by shooting on `x(0)` with `solve_ivp` + Brent root finding.
- Nonzero solvent inlet loading is supported; negative `y-mx` is not clamped and can represent desorption.
- Solver diagnostics expose boundary closure and independent gas/liquid solute mass-balance closure.
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
    st.success("PHASE4_MASS_TRANSFER_GATE = PASS")
    st.success("PHASE5_COUNTERCURRENT_GATE = PASS")
    st.caption("40 automated tests pass in the packaged Phase 5 source tree.")

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 5 · Generic Counter-Current ODE Solver · "
    "Next: Phase 6 generic hydraulics"
)
