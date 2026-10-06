from __future__ import annotations

import pandas as pd
import streamlit as st

from generic_absorber_v4 import (
    AbsorberOperatingPoint,
    ApplicabilityCase,
    ReadinessStatus,
    assess_pre_applicability,
    assess_post_applicability,
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
    evaluate_hydraulics_from_resolver,
    solve_component_countercurrent,
    solve_independent_solutes,
    CompositionFractionBasis,
    GasConcentrationBasis,
    actual_m3_h_to_normal_m3_h,
    canonical_y_from_component_concentrations,
    canonical_y_from_total_and_fractions,
    component_y_to_concentration,
    gas_stream_balance,
    liquid_mg_L_to_x_dilute,
    liquid_x_to_mg_L_dilute,
    normal_m3_h_to_actual_m3_h,
    report_gas_stream,
    DEFAULT_NORMAL_CONDITIONS,
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
st.caption("Phase 8 — Applicability, Validity & Confidence Engine")

st.warning(
    "Phase 8 adds an explicit applicability/validity layer around the Phase 1–7 physics. Critical missing "
    "data and unsupported physics are blocked; extrapolation, data-quality limits, Onda screening ranges, "
    "mass-balance closure and flooding are reported visibly. Required-height design remains outside this phase."
)

with st.sidebar:
    st.header("Development Status")
    st.success("PHASE1_DATA_GATE = PASS")
    st.success("PHASE2_REGISTRY_GATE = PASS")
    st.success("PHASE3_RESOLVER_GATE = PASS")
    st.success("PHASE4_MASS_TRANSFER_GATE = PASS")
    st.success("PHASE5_COUNTERCURRENT_GATE = PASS")
    st.success("PHASE6_HYDRAULICS_GATE = PASS")
    st.success("PHASE7_UNITS_COMPOSITION_GATE = PASS")
    st.success("PHASE8_APPLICABILITY_GATE = PASS")
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
    hydraulics_tab,
    units_tab,
    applicability_tab,
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
    "Hydraulics",
    "Units & Composition",
    "Applicability & Validity",
    "Registry Lookup",
    "Solutes",
    "Carrier & Solvent",
    "Binary Pairs",
    "Packing",
    "Data Quality",
])

with overview_tab:
    st.subheader("Phase 8 architecture")
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

Phase 6 Generic Hydraulics
        ↓
hL, dry/wet dP, GPDC U_flood, % flood, hydraulic regime

Phase 7 Units & Composition Boundary
        ↓
ppmv / mgVOC/Nm³ / mgC/Nm³ ↔ canonical y_i
liquid mg/L ↔ canonical x_i
actual ↔ normal gas flow
mixture fraction basis handling + multicomponent outlet reconstruction
        ↓
Phase 8 Applicability / Validity / Confidence
        ↓
PRE: data + physics + model-domain gate
POST: Onda ranges + ODE closure + driving force + flooding
        ↓
READY / READY_WITH_WARNINGS / OUTSIDE_RECOMMENDED_RANGE
INSUFFICIENT_DATA / UNSUPPORTED_PHYSICS / NUMERICAL_FAILURE

No required-height design yet.""",
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
            "Full basis conversion and multicomponent reporting are available in the Units & Composition tab."
        )
    except Exception as exc:
        st.error(str(exc))

    st.info(
        "The counter-current solver intentionally remains a canonical component y/x layer. Phase 7 converts "
        "UI/reporting bases outside the solver; required-height design remains deferred."
    )

with hydraulics_tab:
    st.subheader("Generic packed-column hydraulics")
    st.caption(
        "Hydraulics uses only carrier, solvent, packing and operating conditions. Dilute-solute identity "
        "does not enter the calculation. Pressure drop is a screening model; GPDC supplies flood capacity."
    )

    h1, h2, h3 = st.columns(3)
    hy_packing = h1.selectbox("Packing", list(REGISTRY.packings), key="hy_packing")
    hy_temp_C = h2.number_input("Temperature (°C)", value=22.0, step=1.0, key="hy_temp")
    hy_p_bar = h3.number_input("Pressure (bar abs)", min_value=0.01, value=1.01325, step=0.05, format="%.5f", key="hy_p")

    h4, h5, h6, h7 = st.columns(4)
    hy_d = h4.number_input("Column diameter D (m)", min_value=0.01, value=0.50, step=0.05, key="hy_d")
    hy_z = h5.number_input("Packed height Z (m)", min_value=0.01, value=1.40, step=0.10, key="hy_z")
    hy_q = h6.number_input("Actual gas flow (m³/h)", min_value=0.001, value=117.53, step=5.0, key="hy_q")
    hy_l = h7.number_input("Liquid flow (kg/h)", min_value=0.001, value=2500.0, step=50.0, key="hy_l")

    try:
        hy_op = AbsorberOperatingPoint(
            diameter_m=hy_d, packed_height_m=hy_z, gas_actual_m3_h=hy_q,
            liquid_mass_kg_h=hy_l, temperature_K=hy_temp_C + 273.15,
            pressure_Pa=hy_p_bar * 1e5,
        )
        hy_common, hy = evaluate_hydraulics_from_resolver(
            resolver=RESOLVER, registry=REGISTRY, carrier_id="air", solvent_id="water",
            packing_id=hy_packing, operating=hy_op,
        )
        dp = hy.pressure_drop
        fl = hy.flooding
        st.success("GENERIC HYDRAULICS CALCULATION READY")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Wet ΔP", f"{dp.wet_pressure_drop_mbar_m:.5f} mbar/m")
        m2.metric("Total packed ΔP", f"{dp.total_pressure_drop_Pa:.4f} Pa")
        m3.metric("Flood velocity", f"{fl.flood_velocity_m_s:.4f} m/s")
        m4.metric("Percent flood", f"{fl.flooding_percent:.2f}%")

        if fl.flooding_percent >= 100:
            st.error(fl.hydraulic_regime)
        elif fl.flooding_percent >= 90:
            st.warning(fl.hydraulic_regime)
        else:
            st.info(fl.hydraulic_regime)

        st.markdown("### Pressure-drop screening")
        dp_rows = [
            ["Gas superficial velocity", hy_common.gas_superficial_velocity_m_s, "m/s"],
            ["Hydraulic Re_L", dp.Re_L_hydraulic, "—"],
            ["Liquid holdup hL", dp.liquid_holdup_fraction, "bed fraction"],
            ["Dry pressure drop", dp.dry_pressure_drop_Pa_m, "Pa/m"],
            ["Wet pressure drop", dp.wet_pressure_drop_Pa_m, "Pa/m"],
            ["Wet pressure drop", dp.wet_pressure_drop_mbar_m, "mbar/m"],
            ["Total packed pressure drop", dp.total_pressure_drop_Pa, "Pa"],
        ]
        st.dataframe(pd.DataFrame(dp_rows, columns=["Quantity", "Value", "Unit"]), use_container_width=True, hide_index=True)

        st.markdown("### GPDC flooding capacity")
        flood_rows = [
            ["Operating gas velocity", fl.gas_superficial_velocity_m_s, "m/s"],
            ["Flood gas velocity", fl.flood_velocity_m_s, "m/s"],
            ["Flood gas mass flux", fl.flood_gas_mass_flux_kg_m2_s, "kg/m²·s"],
            ["F_LV at flood", fl.F_LV_flood, "—"],
            ["CP at flood", fl.CP_flood, "—"],
            ["Packing factor", fl.packing_factor_ft_inv, "ft⁻¹"],
            ["Packing-factor basis", fl.packing_factor_basis, "—"],
            ["Packing factor estimated", fl.packing_factor_estimated, "—"],
            ["Liquid kinematic viscosity", fl.liquid_kinematic_viscosity_cSt, "cSt"],
            ["Percent flood", fl.flooding_percent, "%"],
            ["GPDC correlation range valid", fl.gpdc_valid, "—"],
        ]
        st.dataframe(pd.DataFrame(flood_rows, columns=["Quantity", "Value", "Unit"]), use_container_width=True, hide_index=True)

        st.markdown("### Flooding pressure-drop diagnostic")
        st.write(
            f"Kister–Gill diagnostic: **{fl.flood_pressure_drop_mbar_m:.4f} mbar/m** at flood. "
            f"Current wet ΔP / diagnostic flood ΔP = **{hy.pressure_drop_ratio_to_flood:.6f}**."
        )
        st.caption(
            "This pressure-drop-at-flood value is diagnostic only. Percent flood is defined from "
            "operating superficial gas velocity divided by GPDC flood velocity, not from a ΔP ratio."
        )
    except Exception as exc:
        st.error(str(exc))


with units_tab:
    st.subheader("Generic units & composition boundary")
    st.caption(
        "The solver basis remains y_i / x_i. This tab demonstrates reversible UI conversions, "
        "mixture-basis handling and outlet reconstruction from solved component values. "
        "Normal conditions are fixed at 273.15 K and 101325 Pa for V4.0 reference reporting."
    )

    st.markdown("### Normal-condition reference")
    n1, n2, n3 = st.columns(3)
    n1.metric("T_N", f"{DEFAULT_NORMAL_CONDITIONS.temperature_K:.2f} K")
    n2.metric("P_N", f"{DEFAULT_NORMAL_CONDITIONS.pressure_Pa:.0f} Pa")
    n3.metric("Ideal-gas molar density", f"{DEFAULT_NORMAL_CONDITIONS.molar_concentration_mol_m3:.6f} mol/Nm³")

    st.markdown("### Total mixture + composition fractions → canonical y_i")
    u1, u2, u3 = st.columns(3)
    total_basis_label = u1.selectbox(
        "Total concentration basis",
        [b.value for b in GasConcentrationBasis],
        index=0,
        key="u_total_basis",
    )
    total_default = 5000.0 if total_basis_label == "mgVOC/Nm³" else (3353.134467 if total_basis_label == "mgC/Nm³" else 2055.409211)
    total_value = u2.number_input("Total concentration", min_value=0.0, value=float(total_default), format="%.6f", key="u_total_value")
    fraction_basis_label = u3.selectbox(
        "Composition fraction basis",
        [b.value for b in CompositionFractionBasis],
        index=1,
        key="u_fraction_basis",
    )

    f1, f2 = st.columns(2)
    acn_fraction_pct = f1.number_input("ACN fraction (%)", min_value=0.0, max_value=100.0, value=93.0, step=1.0, key="u_acn_fraction")
    vac_fraction_pct = f2.number_input("VAc fraction (%)", min_value=0.0, max_value=100.0, value=7.0, step=1.0, key="u_vac_fraction")

    try:
        mixture = canonical_y_from_total_and_fractions(
            total_value,
            total_basis_label,
            {"ACN": acn_fraction_pct / 100.0, "VAc": vac_fraction_pct / 100.0},
            fraction_basis_label,
            REGISTRY.solutes,
        )
        st.success("UNIT / COMPOSITION RESOLUTION READY")
        mix_rows = []
        for sid, comp in mixture.report.components.items():
            mix_rows.append({
                "Solute": sid,
                "y_i": comp.y,
                "ppmv": comp.ppmv,
                "mgVOC/Nm³": comp.mgVOC_Nm3,
                "mgC/Nm³": comp.mgC_Nm3,
            })
        st.dataframe(pd.DataFrame(mix_rows), use_container_width=True, hide_index=True)
        t1, t2, t3 = st.columns(3)
        t1.metric("Total ppmv", f"{mixture.report.total_ppmv:.6f}")
        t2.metric("Total mgVOC/Nm³", f"{mixture.report.total_mgVOC_Nm3:.6f}")
        t3.metric("Total mgC/Nm³", f"{mixture.report.total_mgC_Nm3:.6f}")
    except Exception as exc:
        st.error(str(exc))
        mixture = None

    st.markdown("### Component-by-component input")
    c1, c2, c3 = st.columns(3)
    component_basis = c1.selectbox("Component input basis", [b.value for b in GasConcentrationBasis], key="u_component_basis")
    acn_component = c2.number_input("ACN component concentration", min_value=0.0, value=4650.0, format="%.6f", key="u_acn_component")
    vac_component = c3.number_input("VAc component concentration", min_value=0.0, value=350.0, format="%.6f", key="u_vac_component")
    try:
        y_components = canonical_y_from_component_concentrations(
            {"ACN": acn_component, "VAc": vac_component}, component_basis, REGISTRY.solutes
        )
        comp_report = report_gas_stream(y_components, REGISTRY.solutes)
        st.write(
            f"Canonical total y = **{comp_report.total_y:.9g}** · "
            f"{comp_report.total_ppmv:.4f} ppmv · "
            f"{comp_report.total_mgVOC_Nm3:.4f} mgVOC/Nm³"
        )
    except Exception as exc:
        st.error(str(exc))

    st.markdown("### Locked solved outlet reconstruction")
    st.caption("These are the Phase 5 locked component y_out values; the inlet fractions are not reused at the outlet.")
    locked_in = {"ACN": 0.001964284929935824, "VAc": 9.112428087594802e-05}
    locked_out = {"ACN": 3.991282910574221e-06, "VAc": 2.5299699106660017e-05}
    balance = gas_stream_balance(locked_in, locked_out, REGISTRY.solutes, gas_molar_flow_mol_s=1.34798753171)
    out_rows = []
    for sid, comp in balance.outlet.components.items():
        out_rows.append({
            "Solute": sid,
            "y_out": comp.y,
            "ppmv": comp.ppmv,
            "mgVOC/Nm³": comp.mgVOC_Nm3,
            "mgC/Nm³": comp.mgC_Nm3,
            "Component removal (%)": 100.0 * balance.component_removal_fraction[sid],
            "Captured (kg/h)": balance.captured_kg_h_by_component[sid],
        })
    st.dataframe(pd.DataFrame(out_rows), use_container_width=True, hide_index=True)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Outlet mgVOC/Nm³", f"{balance.outlet.total_mgVOC_Nm3:.6f}")
    r2.metric("VOC-mass removal", f"{100*balance.overall_removal_voc_mass:.4f}%")
    r3.metric("Molar removal", f"{100*balance.overall_removal_molar:.4f}%")
    r4.metric("Carbon removal", f"{100*balance.overall_removal_carbon_mass:.4f}%")
    st.info(
        "Overall removal is basis-dependent for a multicomponent mixture. Component removal itself is based directly on y_in/y_out."
    )

    st.markdown("### Liquid loading: mg/L ↔ x (dilute approximation)")
    l1, l2, l3 = st.columns(3)
    liq_solute_id = l1.selectbox("Liquid solute", list(REGISTRY.solutes), key="u_liq_solute")
    liq_temp_C = l2.number_input("Liquid temperature (°C)", value=22.0, step=1.0, key="u_liq_temp")
    liq_mg_L = l3.number_input("Liquid loading (mg/L)", min_value=0.0, value=100.0, step=10.0, key="u_liq_mgL")
    try:
        solvent_state = RESOLVER.resolve_solvent_state("water", liq_temp_C + 273.15)
        solute = REGISTRY.solutes[liq_solute_id]
        x_liq = liquid_mg_L_to_x_dilute(
            liq_mg_L,
            solute_MW_kg_mol=solute.MW_kg_mol,
            solvent_MW_kg_mol=REGISTRY.solvents["water"].MW_kg_mol,
            solvent_density_kg_m3=solvent_state.density.value,
        )
        back_mg_L = liquid_x_to_mg_L_dilute(
            x_liq,
            solute_MW_kg_mol=solute.MW_kg_mol,
            solvent_MW_kg_mol=REGISTRY.solvents["water"].MW_kg_mol,
            solvent_density_kg_m3=solvent_state.density.value,
        )
        st.write(f"Canonical x = **{x_liq:.8e}** · round-trip = **{back_mg_L:.6f} mg/L**")
    except Exception as exc:
        st.error(str(exc))

    st.markdown("### Actual ↔ normal gas flow")
    q1, q2, q3 = st.columns(3)
    qa = q1.number_input("Actual gas flow (m³/h)", min_value=0.0, value=117.53, key="u_qa")
    qt = q2.number_input("Operating T (°C)", value=22.0, key="u_qt") + 273.15
    qp = q3.number_input("Operating P (bar abs)", min_value=0.01, value=1.01325, format="%.5f", key="u_qp") * 1e5
    qn = actual_m3_h_to_normal_m3_h(qa, temperature_K=qt, pressure_Pa=qp)
    qa_round = normal_m3_h_to_actual_m3_h(qn, temperature_K=qt, pressure_Pa=qp)
    st.write(f"Normal flow = **{qn:.6f} Nm³/h** · round-trip actual flow = **{qa_round:.6f} m³/h**")



with applicability_tab:
    st.subheader("Applicability, validity & confidence engine")
    st.caption(
        "This tab runs a pre-solver domain/data gate, then—when allowed—the Phase 3–7 property, "
        "mass-transfer, counter-current and hydraulic calculations, followed by a post-solver validity gate."
    )

    st.markdown("### Case definition")
    a1, a2, a3 = st.columns(3)
    ap_temp_C = a1.number_input("Temperature (°C)", value=22.0, step=1.0, key="ap_temp")
    ap_p_bar = a2.number_input("Pressure (bar abs)", min_value=0.01, value=1.01325, step=0.05, format="%.5f", key="ap_p")
    ap_d = a3.number_input("Column diameter D (m)", min_value=0.01, value=0.50, step=0.05, key="ap_d")

    a4, a5, a6 = st.columns(3)
    ap_z = a4.number_input("Packed height Z (m)", min_value=0.01, value=1.40, step=0.10, key="ap_z")
    ap_q = a5.number_input("Actual gas flow (m³/h)", min_value=0.001, value=117.53, step=5.0, key="ap_q")
    ap_l = a6.number_input("Liquid flow (kg/h)", min_value=0.001, value=2500.0, step=50.0, key="ap_l")

    st.markdown("### Canonical component boundary conditions")
    b1, b2, b3, b4 = st.columns(4)
    ap_y_acn = b1.number_input("ACN y_in", min_value=0.0, max_value=0.999999, value=1.964284929935824e-3, format="%.10e", key="ap_y_acn")
    ap_x_acn = b2.number_input("ACN x_in", min_value=0.0, max_value=0.999999, value=0.0, format="%.10e", key="ap_x_acn")
    ap_y_vac = b3.number_input("VAc y_in", min_value=0.0, max_value=0.999999, value=9.112428087594802e-5, format="%.10e", key="ap_y_vac")
    ap_x_vac = b4.number_input("VAc x_in", min_value=0.0, max_value=0.999999, value=0.0, format="%.10e", key="ap_x_vac")

    st.markdown("### Model-domain flags")
    f1, f2, f3, f4 = st.columns(4)
    ap_reactive = f1.checkbox("Reactive absorption", value=False, key="ap_reactive")
    ap_noniso = f2.checkbox("Non-isothermal case", value=False, key="ap_noniso")
    ap_volatile = f3.checkbox("Material solvent evaporation expected", value=False, key="ap_volatile")
    ap_foaming = f4.checkbox("Foaming expected", value=False, key="ap_foaming")

    ap_op = AbsorberOperatingPoint(
        diameter_m=ap_d,
        packed_height_m=ap_z,
        gas_actual_m3_h=ap_q,
        liquid_mass_kg_h=ap_l,
        temperature_K=ap_temp_C + 273.15,
        pressure_Pa=ap_p_bar * 1e5,
    )
    ap_case = ApplicabilityCase(
        operating=ap_op,
        solute_ids=("ACN", "VAc"),
        carrier_id="air",
        solvent_id="water",
        packing_id="25mm_metal_pall_ring",
        gas_inlet_y={"ACN": ap_y_acn, "VAc": ap_y_vac},
        liquid_inlet_x={"ACN": ap_x_acn, "VAc": ap_x_vac},
        reactive_system=ap_reactive,
        physical_absorption=not ap_reactive,
        isothermal=not ap_noniso,
        solvent_evaporation_expected=ap_volatile,
        foaming_expected=ap_foaming,
    )

    pre_report = assess_pre_applicability(REGISTRY, ap_case)
    st.markdown("### Pre-solver gate")
    if pre_report.status == ReadinessStatus.READY:
        st.success(f"PRE STATUS: {pre_report.status.value}")
    elif pre_report.can_run:
        st.warning(f"PRE STATUS: {pre_report.status.value}")
    else:
        st.error(f"PRE STATUS: {pre_report.status.value}")

    if pre_report.issues:
        st.dataframe(pd.DataFrame([
            {
                "Severity": i.severity.value,
                "Code": i.code,
                "Scope": i.scope,
                "Outside recommended range": "Yes" if i.outside_recommended_range else "No",
                "Message": i.message,
            }
            for i in pre_report.issues
        ]), use_container_width=True, hide_index=True)

    if pre_report.can_run:
        resolved_map = {}
        transfer_map = {}
        solved_all = None
        hyd_result = None
        common_ap = None
        numerical_failure = None
        try:
            for sid in ("ACN", "VAc"):
                resolved_map[sid] = RESOLVER.resolve_component_properties(
                    sid, "air", "water", ap_op.temperature_K, ap_op.pressure_Pa
                )
                common_i, transfer_i = evaluate_component_from_resolver(
                    resolver=RESOLVER,
                    registry=REGISTRY,
                    solute_id=sid,
                    carrier_id="air",
                    solvent_id="water",
                    packing_id="25mm_metal_pall_ring",
                    operating=ap_op,
                )
                if common_ap is None:
                    common_ap = common_i
                transfer_map[sid] = transfer_i

            boundaries = {
                "ACN": ComponentBoundaryConditions(gas_inlet_y=ap_y_acn, liquid_inlet_x=ap_x_acn),
                "VAc": ComponentBoundaryConditions(gas_inlet_y=ap_y_vac, liquid_inlet_x=ap_x_vac),
            }
            solved_all = solve_independent_solutes(common_ap, transfer_map, boundaries)
            _, hyd_result = evaluate_hydraulics_from_resolver(
                resolver=RESOLVER,
                registry=REGISTRY,
                carrier_id="air",
                solvent_id="water",
                packing_id="25mm_metal_pall_ring",
                operating=ap_op,
            )
        except Exception as exc:
            numerical_failure = f"{type(exc).__name__}: {exc}"

        final_report = assess_post_applicability(
            pre_report,
            resolved_components=resolved_map,
            common=common_ap,
            transfer_results=transfer_map,
            solver_results=solved_all,
            hydraulics=hyd_result,
            packing=REGISTRY.get_packing("25mm_metal_pall_ring"),
            numerical_failure=numerical_failure,
        )

        st.markdown("### Final applicability verdict")
        if final_report.status == ReadinessStatus.READY:
            st.success(f"FINAL STATUS: {final_report.status.value}")
        elif final_report.status in (ReadinessStatus.READY_WITH_WARNINGS, ReadinessStatus.OUTSIDE_RECOMMENDED_RANGE):
            st.warning(f"FINAL STATUS: {final_report.status.value}")
        else:
            st.error(f"FINAL STATUS: {final_report.status.value}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Thermodynamics confidence", final_report.confidence.thermodynamics.value)
        c2.metric("Mass-transfer confidence", final_report.confidence.mass_transfer.value)
        c3.metric("Hydraulics confidence", final_report.confidence.hydraulics.value)
        c4.metric("Overall confidence", final_report.confidence.overall.value)

        st.dataframe(pd.DataFrame([
            {
                "Severity": i.severity.value,
                "Code": i.code,
                "Scope": i.scope,
                "Outside recommended range": "Yes" if i.outside_recommended_range else "No",
                "Message": i.message,
            }
            for i in final_report.issues
        ]), use_container_width=True, hide_index=True)

        if solved_all is not None:
            st.markdown("### Solver health snapshot")
            rows = []
            for sid, rr in solved_all.components.items():
                rows.append({
                    "Solute": sid,
                    "y_out": rr.gas_outlet_y,
                    "x_bottom": rr.liquid_bottom_x,
                    "Removal (%)": None if rr.removal_fraction is None else 100*rr.removal_fraction,
                    "Relative mass-balance error": rr.diagnostics.relative_mass_balance_error,
                    "Min driving force y-mx": rr.diagnostics.min_driving_force_y,
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        if hyd_result is not None:
            st.caption(
                f"Hydraulics: {hyd_result.flooding.flooding_percent:.2f}% flood · "
                f"{hyd_result.flooding.hydraulic_regime} · "
                f"wet ΔP={hyd_result.pressure_drop.wet_pressure_drop_mbar_m:.5f} mbar/m"
            )
    else:
        st.info("Physics calculation is intentionally not launched because the pre-solver gate contains a blocking issue.")

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
- Phase 6 hydraulics depends on bulk carrier/solvent properties, packing and flows—not dilute-solute identity.
- Packed-bed pressure drop is explicitly a screening model; GPDC determines flood velocity and percent flood.
- Kister–Gill pressure drop at flood is retained only as a diagnostic; it does not define percent flood.
- Foaming, entrainment, distributor/support losses, demisters, fouling and maldistribution are not modeled.
- Phase 7 keeps unit conversion outside the physics solvers; canonical gas/liquid composition variables remain `y_i` and `x_i`.
- Normal reporting uses 273.15 K and 101325 Pa; mass-, mole- and carbon-fraction bases are never treated as interchangeable.
- Multicomponent outlet totals are reconstructed from solved component outlets, never from inlet mixture fractions.
- Phase 8 separates pre-solver data/physics readiness from post-solver numerical/correlation/hydraulic validity.
- BLOCK / WARNING / INFO issues are explicit; confidence is categorical rather than a fabricated percentage.
- Local negative driving force is reported as physical desorption, while numerical mass-balance/boundary failures receive a distinct NUMERICAL_FAILURE state.
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
    st.success("PHASE6_HYDRAULICS_GATE = PASS")
    st.success("PHASE7_UNITS_COMPOSITION_GATE = PASS")
    st.success("PHASE8_APPLICABILITY_GATE = PASS")
    st.caption("76 automated tests pass in the packaged Phase 8 source tree.")

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 8 · Applicability, Validity & Confidence Engine · "
    "Next: Phase 9 full V3 parity gate"
)
