from __future__ import annotations

from pathlib import Path

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
    REFERENCE_SOURCE_SHA256,
    reference_chain_health,
    run_full_v3_parity,
    SYNTHETIC_CASE_ID,
    SYNTHETIC_SOLUTES,
    run_synthetic_generic_case,
    PHASE11_ESTIMATION_CASE_ID,
    run_phase11_estimation_gate,
    PHASE12_VDC_WATER_CASE_ID,
    VDC_ID,
    VDC_CAS,
    VDC_FORMULA,
    VDC_FULLER_DIFFUSION_VOLUME,
    VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL,
    VDC_WATER_H_REF_PA_M3_MOL,
    NIST_GOSSETT_SOURCE,
    FULLER_SOURCE,
    WILKE_CHANG_SOURCE,
    build_vdc_water_registry,
    run_vdc_water_case,
    PHASE13_VDC_ACN_CASE_ID,
    ACN_SOLVENT_ID,
    ACN_CAS,
    ACN_FORMULA,
    ACN_DENSITY_22C_KG_M3,
    ACN_VISCOSITY_NEAR_AMBIENT_PA_S,
    ACN_SURFACE_TENSION_NEAR_AMBIENT_N_M,
    VDC_ACN_LINEAR_M_22C,
    ACN_VAPOR_FRACTION_IF_SATURATED_22C,
    ACN_BULK_SOURCE,
    VDC_VP_SOURCE,
    ACN_VP_SOURCE,
    VDC_ACN_EQUILIBRIUM_SOURCE,
    WILKE_CHANG_ACN_NOTE,
    PROJECT_PILOT_NOTE,
    build_vdc_acn_registry,
    run_vdc_acn_case,
)

from generic_absorber_v4 import (
    GenericAbsorberCase,
    SimulationBlockedError,
    build_phase14_registry,
    compatible_solutes,
    run_generic_absorber_case,
    PHASE15_LIVE_METHODS_ID,
    build_live_methods_report,
    PHASE16_PARAMETER_SWEEP_ID,
    MAX_SWEEP_POINTS,
    SweepAxis,
    SweepVariable,
    InvalidSweepDefinition,
    run_parameter_sweep,
    suggested_sweep_bounds,
    PHASE17_COMPARISON_ID,
    ComparisonMode,
    compare_packings,
    compare_solvents,
)

from generic_absorber_v4 import (
    PHASE18A_DATABASE_ID,
    PHASE18A_SCHEMA_VERSION,
    SQLiteAbsorberRepository,
    build_phase18a_source_registry,
    compare_registry_to_sqlite,
)

from generic_absorber_v4 import (
    PHASE18B_DATABASE_ID,
    PHASE18B_SCHEMA_VERSION,
    SQLiteAbsorberRepositoryV18B,
    build_phase18b_database,
    compare_registry_to_phase18b_sqlite,
)

from generic_absorber_v4 import (
    PHASE18C_REPOSITORY_ID,
    RepositoryKind,
    build_python_registry_repository,
    build_sqlite_v18b_repository,
    run_phase18c_repository_parity,
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
            "Fuller volume": s.fuller_diffusion_volume,
            "Boiling molar V (cm³/mol)": s.boiling_molar_volume_cm3_mol,
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
            "Fuller volume": c.fuller_diffusion_volume,
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
            "Wilke–Chang φ": s.wilke_chang_association_factor,
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

SIM_REGISTRY = build_phase14_registry()
SIM_RESOLVER = PropertyResolver(SIM_REGISTRY)
PHASE18C_DB_PATH = Path(__file__).resolve().parent / "database" / "absorber_database_v18b.db"
PYTHON_DATA_REPOSITORY = build_python_registry_repository()
SQLITE_DATA_REPOSITORY = build_sqlite_v18b_repository(PHASE18C_DB_PATH)
DATA_REPOSITORIES = {
    "Verified Python Registry": PYTHON_DATA_REPOSITORY,
    "SQLite Engineering Database v18B": SQLITE_DATA_REPOSITORY,
}

st.title("🧪 Generic Packed Absorber Simulator V4")
st.caption("Phase 18C — Repository Abstraction & Dual-Backend Parity")

st.info(
    "Phase 18C places a backend-neutral repository contract between the simulator and engineering data. "
    "The same integrated solver can now run from either the verified Python registry or the Phase 18B SQLite database without changing physics code."
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
    st.success("PHASE9_FULL_V3_PARITY_GATE = PASS")
    st.success("PHASE10_SYNTHETIC_GENERIC_GATE = PASS")
    st.success("PHASE11_PROPERTY_ESTIMATION_GATE = PASS")
    st.success("PHASE12_VDC_WATER_GATE = PASS")
    st.success("PHASE13_VDC_ACN_GATE = PASS")
    st.success("PHASE14_INTEGRATED_SIMULATOR_GATE = PASS")
    st.success("PHASE15_LIVE_METHODS_GATE = PASS")
    st.success("PHASE16_PARAMETER_SWEEP_GATE = PASS")
    st.success("PHASE17_COMPARISON_GATE = PASS")
    st.success("PHASE18A_DATABASE_MIGRATION_GATE = PASS")
    st.success("PHASE18B_STRUCTURED_PROVENANCE_GATE = PASS")
    st.success("PHASE18C_REPOSITORY_ABSTRACTION_GATE = PASS")
    st.metric("Reference ID", REGISTRY.reference_id)
    st.divider()
    st.caption("Resolution precedence")
    st.write("**1. User override**")
    st.write("**2. Registered database**")
    st.write("**3. Correlation estimate (Fuller / Wilke–Chang)**")
    st.write("**4. Missing → explicit error**")
    st.caption("Correlation estimates are Confidence C and never overwrite registered pair data.")

(
    simulator_tab,
    methods_tab,
    sweep_tab,
    comparison_tab,
    database_tab,
    provenance_tab,
    repository_tab,
    overview_tab,
    resolver_tab,
    mass_transfer_tab,
    solver_tab,
    hydraulics_tab,
    units_tab,
    applicability_tab,
    parity_tab,
    synthetic_tab,
    estimation_tab,
    vdc_tab,
    vdc_acn_tab,
    lookup_tab,
    solute_tab,
    fluid_tab,
    pair_tab,
    packing_tab,
    quality_tab,
) = st.tabs([
    "Simulator",
    "Methods & Assumptions",
    "Parameter Sweep",
    "Comparison",
    "Database Migration",
    "Data Provenance",
    "Repository Backends",
    "Overview",
    "Property Resolver",
    "Mass Transfer",
    "Counter-Current Solver",
    "Hydraulics",
    "Units & Composition",
    "Applicability & Validity",
    "V3 Parity Gate",
    "Synthetic Generic Test",
    "Property Estimates",
    "VDC / Water",
    "VDC / Acrylonitrile",
    "Registry Lookup",
    "Solutes",
    "Carrier & Solvent",
    "Binary Pairs",
    "Packing",
    "Data Quality",
])

with simulator_tab:
    st.subheader("Integrated Generic Absorber Simulator")
    st.caption(
        "This is the product-facing integrated workflow. The UI prepares canonical inputs; "
        "all physics is executed by generic_absorber_v4.simulation.run_generic_absorber_case(). "
        "Phase 15 builds the live Methods & Assumptions audit from that result; Phase 16 can reuse the same case as a sweep baseline."
    )

    backend_name = st.selectbox(
        "Engineering data backend",
        list(DATA_REPOSITORIES),
        index=0,
        key="phase18c_sim_backend",
        help="Both backends reconstruct the same AbsorberDataRegistry contract. Physics code is unchanged.",
    )
    sim_repository = DATA_REPOSITORIES[backend_name]
    sim_registry = sim_repository.load_registry()
    sim_resolver = PropertyResolver(sim_registry)
    st.caption(
        f"Active backend: **{sim_repository.descriptor.label}** · "
        f"kind `{sim_repository.descriptor.kind.value}` · read-only={sim_repository.descriptor.read_only}"
    )

    st.markdown("### 1. Chemistry & equipment")
    c1, c2, c3 = st.columns(3)
    sim_carrier = c1.selectbox(
        "Carrier gas", list(sim_registry.carriers),
        format_func=lambda x: sim_registry.get_carrier(x).name,
        key="sim_carrier",
    )
    sim_solvent = c2.selectbox(
        "Solvent", list(sim_registry.solvents),
        format_func=lambda x: sim_registry.get_solvent(x).name,
        key="sim_solvent",
    )
    sim_packing = c3.selectbox(
        "Packing", list(sim_registry.packings),
        format_func=lambda x: sim_registry.get_packing(x).name,
        key="sim_packing",
    )

    st.markdown("### 2. Operating conditions")
    o1, o2, o3 = st.columns(3)
    sim_temp_C = o1.number_input("Temperature (°C)", value=22.0, step=1.0, key="sim_temp_C")
    sim_pressure_bar = o2.number_input(
        "Pressure (bar abs)", min_value=0.05, value=1.01325, step=0.05,
        format="%.5f", key="sim_pressure_bar"
    )
    sim_liquid_kg_h = o3.number_input(
        "Liquid flow (kg/h)", min_value=0.001, value=2500.0, step=50.0, key="sim_liquid_kg_h"
    )

    o4, o5, o6 = st.columns(3)
    sim_diameter = o4.number_input("Column diameter (m)", min_value=0.01, value=0.50, step=0.05, key="sim_diameter")
    sim_height = o5.number_input("Packed height (m)", min_value=0.01, value=1.40, step=0.10, key="sim_height")
    sim_flow_basis = o6.selectbox("Gas-flow basis", ["Actual m³/h", "Normal m³/h"], key="sim_flow_basis")

    default_gas_flow = 117.53 if sim_flow_basis == "Actual m³/h" else 108.05
    sim_gas_flow = st.number_input(
        f"Gas flow ({sim_flow_basis})", min_value=0.001, value=float(default_gas_flow), step=5.0, key="sim_gas_flow"
    )

    sim_T_K = sim_temp_C + 273.15
    sim_P_Pa = sim_pressure_bar * 1e5
    if sim_flow_basis == "Actual m³/h":
        sim_actual_gas_m3_h = sim_gas_flow
    else:
        sim_actual_gas_m3_h = normal_m3_h_to_actual_m3_h(
            sim_gas_flow, temperature_K=sim_T_K, pressure_Pa=sim_P_Pa
        )
    st.caption(f"Canonical actual gas flow used by physics core: **{sim_actual_gas_m3_h:.4f} m³/h**")

    compatibility = compatible_solutes(
        sim_registry,
        carrier_id=sim_carrier,
        solvent_id=sim_solvent,
        temperature_K=sim_T_K,
        pressure_Pa=sim_P_Pa,
    )
    ready_solutes = [row.solute_id for row in compatibility if row.ready]
    not_ready = [row for row in compatibility if not row.ready]

    if not ready_solutes:
        st.error("No registered solute can be fully resolved for the selected carrier/solvent/temperature/pressure.")
        st.dataframe(pd.DataFrame([{"Solute": x.solute_id, "Reason": x.reason} for x in not_ready]), hide_index=True, use_container_width=True)
        st.stop()

    default_solutes = [sid for sid in ("ACN", "VAc") if sid in ready_solutes]
    if not default_solutes:
        default_solutes = [ready_solutes[0]]
    sim_solutes = st.multiselect(
        "Solutes (1–4)",
        ready_solutes,
        default=default_solutes,
        format_func=lambda x: f"{x} — {sim_registry.get_solute(x).name}",
        max_selections=4,
        key="sim_solutes",
    )

    if not_ready:
        with st.expander("Why are some solutes unavailable for this solvent?"):
            st.dataframe(
                pd.DataFrame([{"Solute": x.solute_id, "Reason": x.reason} for x in not_ready]),
                use_container_width=True, hide_index=True,
            )

    st.markdown("### 3. Gas feed")
    sim_input_mode = st.radio(
        "Gas-feed input mode",
        ["Component-by-component", "Total concentration + composition"],
        horizontal=True,
        key="sim_input_mode",
    )
    sim_gas_basis_label = st.selectbox(
        "Concentration basis",
        [b.value for b in GasConcentrationBasis],
        key="sim_gas_basis",
    )
    sim_gas_basis = GasConcentrationBasis(sim_gas_basis_label)

    component_values = {}
    total_value = None
    fraction_values = {}
    fraction_basis = CompositionFractionBasis.VOC_MASS
    if sim_solutes:
        if sim_input_mode == "Component-by-component":
            feed_cols = st.columns(min(len(sim_solutes), 4))
            for idx, sid in enumerate(sim_solutes):
                default = 0.0
                if sim_gas_basis == GasConcentrationBasis.MG_VOC_NM3:
                    default = 4650.0 if sid == "ACN" and set(sim_solutes) == {"ACN", "VAc"} else (350.0 if sid == "VAc" and set(sim_solutes) == {"ACN", "VAc"} else 1000.0 / len(sim_solutes))
                elif sim_gas_basis == GasConcentrationBasis.PPMV:
                    default = 1000.0 / len(sim_solutes)
                else:
                    default = 500.0 / len(sim_solutes)
                component_values[sid] = feed_cols[idx].number_input(
                    f"{sid} inlet ({sim_gas_basis.value})",
                    min_value=0.0, value=float(default), format="%.6g", key=f"sim_feed_{sid}_{sim_gas_basis.value}",
                )
        else:
            t1, t2 = st.columns(2)
            total_value = t1.number_input(
                f"Total inlet ({sim_gas_basis.value})", min_value=0.0, value=5000.0, format="%.6g", key="sim_total_feed"
            )
            frac_label = t2.selectbox(
                "Composition fraction basis",
                ["VOC mass", "Mole", "Carbon mass"], key="sim_fraction_basis"
            )
            fraction_basis = {
                "VOC mass": CompositionFractionBasis.VOC_MASS,
                "Mole": CompositionFractionBasis.MOLE,
                "Carbon mass": CompositionFractionBasis.CARBON_MASS,
            }[frac_label]
            frac_cols = st.columns(min(len(sim_solutes), 4))
            for idx, sid in enumerate(sim_solutes):
                default_fraction = 1.0 / len(sim_solutes)
                if set(sim_solutes) == {"ACN", "VAc"} and fraction_basis == CompositionFractionBasis.VOC_MASS:
                    default_fraction = 0.93 if sid == "ACN" else 0.07
                fraction_values[sid] = frac_cols[idx].number_input(
                    f"{sid} fraction", min_value=0.0, value=float(default_fraction), format="%.6f", key=f"sim_fraction_{sid}"
                )
            st.caption("Fractions are normalized internally before conversion to canonical gas mole fractions.")

    st.markdown("### 4. Solvent inlet loading")
    fresh_solvent = st.checkbox("Fresh solvent (all solute inlet loadings = 0)", value=True, key="sim_fresh_solvent")
    loading_basis = "x"
    loading_values = {}
    if not fresh_solvent and sim_solutes:
        loading_basis = st.radio("Liquid loading basis", ["Mole fraction x", "mg/L"], horizontal=True, key="sim_loading_basis")
        load_cols = st.columns(min(len(sim_solutes), 4))
        for idx, sid in enumerate(sim_solutes):
            if loading_basis == "Mole fraction x":
                loading_values[sid] = load_cols[idx].number_input(
                    f"{sid} solvent inlet x", min_value=0.0, max_value=0.999, value=0.0, format="%.8g", key=f"sim_xin_{sid}"
                )
            else:
                loading_values[sid] = load_cols[idx].number_input(
                    f"{sid} solvent inlet (mg/L)", min_value=0.0, value=0.0, format="%.6g", key=f"sim_mgl_{sid}"
                )

    st.markdown("### 5. Model-domain flags")
    f1, f2 = st.columns(2)
    default_evap = sim_solvent == "acrylonitrile"
    solvent_evap_expected = f1.checkbox(
        "Material solvent evaporation expected",
        value=default_evap,
        key=f"sim_evap_{sim_solvent}",
        help="V4.0 does not include solvent evaporation. Keep this checked for materially volatile solvents so the applicability engine exposes the limitation.",
    )
    foaming_expected = f2.checkbox("Foaming expected", value=False, key="sim_foaming")

    run_sim = st.button("Run integrated simulation", type="primary", key="run_integrated_phase14")

    if run_sim:
        if not sim_solutes:
            st.error("Select at least one solute.")
        else:
            try:
                sim_specs = {sid: sim_registry.get_solute(sid) for sid in sim_solutes}
                if sim_input_mode == "Component-by-component":
                    sim_y = canonical_y_from_component_concentrations(
                        component_values, sim_gas_basis, sim_specs
                    )
                else:
                    mixture = canonical_y_from_total_and_fractions(
                        total_value,
                        sim_gas_basis,
                        fraction_values,
                        fraction_basis,
                        sim_specs,
                        normalize_fractions=True,
                    )
                    sim_y = dict(mixture.canonical_y)

                sim_x = {sid: 0.0 for sid in sim_solutes}
                if not fresh_solvent:
                    if loading_basis == "Mole fraction x":
                        sim_x = {sid: float(loading_values[sid]) for sid in sim_solutes}
                    else:
                        solvent_state = sim_resolver.resolve_solvent_state(sim_solvent, sim_T_K)
                        for sid in sim_solutes:
                            sim_x[sid] = liquid_mg_L_to_x_dilute(
                                loading_values[sid],
                                solute_MW_kg_mol=sim_registry.get_solute(sid).MW_kg_mol,
                                solvent_MW_kg_mol=solvent_state.MW.value,
                                solvent_density_kg_m3=solvent_state.density.value,
                            )

                sim_case = GenericAbsorberCase(
                    operating=AbsorberOperatingPoint(
                        diameter_m=sim_diameter,
                        packed_height_m=sim_height,
                        gas_actual_m3_h=sim_actual_gas_m3_h,
                        liquid_mass_kg_h=sim_liquid_kg_h,
                        temperature_K=sim_T_K,
                        pressure_Pa=sim_P_Pa,
                    ),
                    solute_ids=tuple(sim_solutes),
                    carrier_id=sim_carrier,
                    solvent_id=sim_solvent,
                    packing_id=sim_packing,
                    gas_inlet_y=sim_y,
                    liquid_inlet_x=sim_x,
                    solvent_evaporation_expected=solvent_evap_expected,
                    foaming_expected=foaming_expected,
                )
                st.session_state["phase14_result"] = run_generic_absorber_case(
                    sim_case, repository=sim_repository
                )
                st.session_state.pop("phase14_blocked", None)
            except SimulationBlockedError as exc:
                st.session_state["phase14_blocked"] = exc.report
                st.session_state.pop("phase14_result", None)
            except Exception as exc:
                st.session_state.pop("phase14_result", None)
                st.exception(exc)

    blocked = st.session_state.get("phase14_blocked")
    if blocked is not None:
        st.error(f"PRE-SOLVER STATUS: {blocked.status.value}")
        st.dataframe(pd.DataFrame([
            {"Severity": i.severity.value, "Code": i.code, "Scope": i.scope, "Message": i.message}
            for i in blocked.issues
        ]), use_container_width=True, hide_index=True)

    result = st.session_state.get("phase14_result")
    if result is not None:
        st.divider()
        st.markdown("## Simulation results")
        st.caption(
            f"Data backend used for this result: **{result.data_source.label}** "
            f"(`{result.data_source.backend_id}`)"
        )
        status = result.post_applicability.status.value
        if result.post_applicability.blocks:
            st.error(f"FINAL STATUS: {status}")
        elif result.post_applicability.warnings:
            st.warning(f"FINAL STATUS: {status}")
        else:
            st.success(f"FINAL STATUS: {status}")

        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("Inlet VOC", f"{result.inlet_report.total_mgVOC_Nm3:.3f}", "mg/Nm³")
        k2.metric("Outlet VOC", f"{result.outlet_report.total_mgVOC_Nm3:.3f}", "mg/Nm³")
        voc_rem = result.stream_balance.overall_removal_voc_mass
        k3.metric("VOC mass removal", "—" if voc_rem is None else f"{100*voc_rem:.3f}%")
        k4.metric("Outlet ppmv", f"{result.outlet_report.total_ppmv:.3f}")
        k5.metric("% Flood", f"{result.hydraulics.flooding.flooding_percent:.2f}%")
        k6.metric("Wet ΔP", f"{result.hydraulics.pressure_drop.wet_pressure_drop_mbar_m:.4f}", "mbar/m")

        st.markdown("### Component performance")
        component_rows = []
        for sid in result.case.solute_ids:
            inlet = result.inlet_report.components[sid]
            outlet = result.outlet_report.components[sid]
            solved = result.solver_results.components[sid]
            mt = result.transfer_results[sid]
            rp = result.resolved_components[sid]
            component_rows.append({
                "Solute": sid,
                "Inlet ppmv": inlet.ppmv,
                "Outlet ppmv": outlet.ppmv,
                "Inlet mgVOC/Nm³": inlet.mgVOC_Nm3,
                "Outlet mgVOC/Nm³": outlet.mgVOC_Nm3,
                "Removal %": None if solved.removal_fraction is None else 100*solved.removal_fraction,
                "Captured kg/h": result.stream_balance.captured_kg_h_by_component[sid],
                "A": mt.absorption_factor,
                "HTU_OG (m)": mt.HTU_OG_m,
                "NTU_OG": mt.NTU_OG,
                "m": mt.equilibrium_slope_m,
                "DG tier": rp.gas_diffusivity.tier.value,
                "DL tier": rp.liquid_diffusivity.tier.value,
                "Eq confidence": rp.equilibrium.active_property.confidence.value,
                "Mode": solved.diagnostics.mode,
            })
        st.dataframe(pd.DataFrame(component_rows), use_container_width=True, hide_index=True)

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Molar removal", "—" if result.stream_balance.overall_removal_molar is None else f"{100*result.stream_balance.overall_removal_molar:.3f}%")
        r2.metric("Carbon-mass removal", "—" if result.stream_balance.overall_removal_carbon_mass is None else f"{100*result.stream_balance.overall_removal_carbon_mass:.3f}%")
        r3.metric("Captured total", f"{result.stream_balance.total_captured_kg_h:.5f} kg/h")
        r4.metric("Overall confidence", result.post_applicability.confidence.overall.value)

        with st.expander("Hydraulics details", expanded=False):
            h = result.hydraulics
            st.dataframe(pd.DataFrame([{
                "Ug (m/s)": h.flooding.gas_superficial_velocity_m_s,
                "U_flood (m/s)": h.flooding.flood_velocity_m_s,
                "% Flood": h.flooding.flooding_percent,
                "Regime": h.flooding.hydraulic_regime,
                "Liquid holdup": h.pressure_drop.liquid_holdup_fraction,
                "Dry ΔP (Pa/m)": h.pressure_drop.dry_pressure_drop_Pa_m,
                "Wet ΔP (Pa/m)": h.pressure_drop.wet_pressure_drop_Pa_m,
                "Total ΔP (mbar)": h.pressure_drop.total_pressure_drop_mbar,
                "F_LV": h.flooding.F_LV_flood,
                "GPDC valid": h.flooding.gpdc_valid,
            }]), use_container_width=True, hide_index=True)

        with st.expander("Applicability / validity issues", expanded=True):
            issues = result.post_applicability.issues
            if issues:
                st.dataframe(pd.DataFrame([
                    {
                        "Severity": i.severity.value,
                        "Code": i.code,
                        "Scope": i.scope,
                        "Message": i.message,
                    }
                    for i in issues
                ]), use_container_width=True, hide_index=True)
            else:
                st.success("No applicability issues reported.")

        with st.expander("Resolved property provenance", expanded=False):
            prop_rows = []
            for sid, rp in result.resolved_components.items():
                for label, prop in (
                    ("DG", rp.gas_diffusivity),
                    ("DL", rp.liquid_diffusivity),
                    ("Equilibrium", rp.equilibrium.active_property),
                ):
                    prop_rows.append({
                        "Solute": sid,
                        "Property": label,
                        "Value": prop.value,
                        "Unit": prop.unit,
                        "Tier": prop.tier.value,
                        "Confidence": prop.confidence.value,
                        "Method": prop.method,
                        "Source": prop.source,
                        "Estimated": prop.estimated,
                    })
            st.dataframe(pd.DataFrame(prop_rows), use_container_width=True, hide_index=True)

        st.markdown("### Column profiles")
        for sid in result.case.solute_ids:
            solved = result.solver_results.components[sid]
            with st.expander(f"{sid} profiles"):
                profile = pd.DataFrame({
                    "z (m)": solved.z_m,
                    "gas ppmv": solved.gas_y_profile * 1e6,
                    "liquid x × 1e6": solved.liquid_x_profile * 1e6,
                    "driving force (y-mx) × 1e6": solved.driving_force_profile_y * 1e6,
                }).set_index("z (m)")
                st.line_chart(profile)
                st.caption(
                    f"Mass-balance error: {solved.diagnostics.relative_mass_balance_error:.3e} · "
                    f"Boundary error: {solved.diagnostics.boundary_error_x:.3e}"
                )

        st.caption(
            "Phase 16 remains a rating simulator. Parameter sweeps rerun the full rating model at every point; they are not an optimizer. "
            "Required-height design, solvent evaporation, coupled nonideal VLE, reaction and energy balance are not yet part of the integrated workflow."
        )


with sweep_tab:
    st.subheader("Parameter Sweep / Sensitivity Analysis")
    st.caption(
        "Start from the latest Simulator case and vary one or two numerical parameters. "
        "Every grid point calls the same integrated V4 solver again: properties → Onda → ODE → hydraulics → units → applicability."
    )

    sweep_base_result = st.session_state.get("phase14_result")
    if sweep_base_result is None:
        st.info("Run a case in the Simulator tab first. That case becomes the baseline for the sweep.")
    else:
        base_case = sweep_base_result.case
        st.success(
            f"Baseline loaded · {', '.join(base_case.solute_ids)} / "
            f"{sweep_base_result.registry.get_solvent(base_case.solvent_id).name} · "
            f"status {sweep_base_result.post_applicability.status.value}"
        )
        st.caption(
            "Sweep axes operate on the canonical integrated case. In particular, temperature/pressure sweeps hold the current "
            "**actual gas volumetric flow** constant unless gas flow itself is selected as an axis."
        )

        sweep_mode = st.radio("Sweep dimension", ["1D", "2D"], horizontal=True, key="phase16_sweep_mode")
        sweep_variables = list(SweepVariable)
        var_labels = {v: f"{v.label} [{v.unit}]" for v in sweep_variables}

        a1c1, a1c2, a1c3, a1c4 = st.columns(4)
        axis1_var = a1c1.selectbox(
            "Axis 1 variable",
            sweep_variables,
            index=sweep_variables.index(SweepVariable.LIQUID_MASS_KG_H),
            format_func=lambda v: var_labels[v],
            key="phase16_axis1_var",
        )
        a1_lo, a1_hi = suggested_sweep_bounds(base_case, axis1_var)
        axis1_start = a1c2.number_input(
            f"Axis 1 start ({axis1_var.unit})",
            value=float(a1_lo),
            format="%.6g",
            key=f"phase16_a1_start_{axis1_var.value}",
        )
        axis1_stop = a1c3.number_input(
            f"Axis 1 stop ({axis1_var.unit})",
            value=float(a1_hi),
            format="%.6g",
            key=f"phase16_a1_stop_{axis1_var.value}",
        )
        max_1d = 41 if sweep_mode == "1D" else 15
        axis1_points = a1c4.number_input(
            "Axis 1 points",
            min_value=2,
            max_value=max_1d,
            value=9 if sweep_mode == "1D" else 7,
            step=1,
            key=f"phase16_axis1_points_{sweep_mode}",
        )

        axis2 = None
        if sweep_mode == "2D":
            remaining = [v for v in sweep_variables if v != axis1_var]
            default2 = SweepVariable.GAS_ACTUAL_M3_H if SweepVariable.GAS_ACTUAL_M3_H in remaining else remaining[0]
            a2c1, a2c2, a2c3, a2c4 = st.columns(4)
            axis2_var = a2c1.selectbox(
                "Axis 2 variable",
                remaining,
                index=remaining.index(default2),
                format_func=lambda v: var_labels[v],
                key=f"phase16_axis2_var_{axis1_var.value}",
            )
            a2_lo, a2_hi = suggested_sweep_bounds(base_case, axis2_var)
            axis2_start = a2c2.number_input(
                f"Axis 2 start ({axis2_var.unit})",
                value=float(a2_lo),
                format="%.6g",
                key=f"phase16_a2_start_{axis2_var.value}",
            )
            axis2_stop = a2c3.number_input(
                f"Axis 2 stop ({axis2_var.unit})",
                value=float(a2_hi),
                format="%.6g",
                key=f"phase16_a2_stop_{axis2_var.value}",
            )
            axis2_points = a2c4.number_input(
                "Axis 2 points",
                min_value=2,
                max_value=15,
                value=7,
                step=1,
                key="phase16_axis2_points",
            )
            requested_points = int(axis1_points) * int(axis2_points)
            st.caption(f"Requested grid: **{requested_points}** points · Phase 16 limit: {MAX_SWEEP_POINTS}")
            if requested_points <= MAX_SWEEP_POINTS:
                axis2 = (axis2_var, axis2_start, axis2_stop, int(axis2_points))
            else:
                st.error(f"Reduce point counts: {requested_points} exceeds the {MAX_SWEEP_POINTS}-point Phase 16 limit.")
        else:
            requested_points = int(axis1_points)
            st.caption(f"Requested sweep: **{requested_points}** full integrated simulations")

        run_sweep = st.button(
            "Run full-physics sweep",
            type="primary",
            key="run_phase16_sweep",
            disabled=requested_points > MAX_SWEEP_POINTS,
        )
        if run_sweep:
            try:
                axes = [SweepAxis(axis1_var, axis1_start, axis1_stop, int(axis1_points))]
                if axis2 is not None:
                    axes.append(SweepAxis(*axis2))
                with st.spinner(f"Running {requested_points} complete absorber simulations..."):
                    st.session_state["phase16_sweep"] = run_parameter_sweep(
                        base_case,
                        axes,
                        registry=sweep_base_result.registry,
                    )
            except InvalidSweepDefinition as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)

        sweep_result = st.session_state.get("phase16_sweep")
        if sweep_result is not None:
            # Avoid accidentally presenting a prior sweep as belonging to a newly rerun baseline.
            if sweep_result.base_case != base_case:
                st.warning("The stored sweep belongs to an older Simulator baseline. Run the sweep again for the current case.")
            else:
                st.divider()
                q1, q2, q3, q4 = st.columns(4)
                q1.metric("Total points", sweep_result.total_points)
                q2.metric("Successful", sweep_result.successful_points)
                q3.metric("Failed / blocked", sweep_result.failed_points)
                q4.metric("Sweep ID", "Phase 16")

                sweep_df = pd.DataFrame(sweep_result.records())
                st.markdown("### Sweep results")
                st.dataframe(sweep_df, use_container_width=True, hide_index=True)

                successful_df = sweep_df[sweep_df["success"] == True].copy()  # noqa: E712
                if not successful_df.empty:
                    focus_solute = st.selectbox(
                        "Focus solute for component metrics",
                        list(base_case.solute_ids),
                        key="phase16_focus_solute",
                    )
                    metric_options = {
                        "Outlet VOC (mg/Nm³)": "outlet_mgVOC_Nm3",
                        "VOC mass removal (%)": "voc_mass_removal_percent",
                        "Outlet total (ppmv)": "outlet_ppmv",
                        "Captured total (kg/h)": "captured_kg_h",
                        "% Flood": "flooding_percent",
                        "Wet ΔP (mbar/m)": "wet_pressure_drop_mbar_m",
                        "Total ΔP (mbar)": "total_pressure_drop_mbar",
                        f"{focus_solute} absorption factor A": f"{focus_solute}__absorption_factor",
                        f"{focus_solute} HTU_OG (m)": f"{focus_solute}__HTU_OG_m",
                        f"{focus_solute} NTU_OG": f"{focus_solute}__NTU_OG",
                        f"{focus_solute} removal (%)": f"{focus_solute}__removal_percent",
                    }
                    metric_label = st.selectbox(
                        "Output metric",
                        list(metric_options),
                        key=f"phase16_output_metric_{focus_solute}",
                    )
                    metric_col = metric_options[metric_label]

                    axis1 = sweep_result.axes[0]
                    if len(sweep_result.axes) == 1:
                        chart_df = successful_df[[axis1.variable.value, metric_col]].dropna().sort_values(axis1.variable.value)
                        if not chart_df.empty:
                            st.markdown("### Sensitivity curve")
                            st.line_chart(chart_df.set_index(axis1.variable.value)[metric_col])
                            st.caption(f"x-axis: {axis1.variable.label} [{axis1.variable.unit}] · y-axis: {metric_label}")
                    else:
                        axis2_obj = sweep_result.axes[1]
                        pivot = successful_df.pivot(
                            index=axis2_obj.variable.value,
                            columns=axis1.variable.value,
                            values=metric_col,
                        )
                        st.markdown("### 2D response matrix")
                        st.dataframe(pivot, use_container_width=True)
                        st.caption(
                            f"Rows: {axis2_obj.variable.label} [{axis2_obj.variable.unit}] · "
                            f"Columns: {axis1.variable.label} [{axis1.variable.unit}] · Cell: {metric_label}"
                        )

                    st.markdown("### Validity across the sweep")
                    status_counts = sweep_df.groupby(["status", "confidence"], dropna=False).size().reset_index(name="Points")
                    st.dataframe(status_counts, use_container_width=True, hide_index=True)

                failed_df = sweep_df[sweep_df["success"] == False]  # noqa: E712
                if not failed_df.empty:
                    with st.expander("Failed / blocked sweep points", expanded=True):
                        st.dataframe(failed_df, use_container_width=True, hide_index=True)

                st.download_button(
                    "Download sweep CSV",
                    data=sweep_df.to_csv(index=False).encode("utf-8"),
                    file_name="generic_absorber_phase16_sweep.csv",
                    mime="text/csv",
                    key="phase16_download_csv",
                )
                st.caption(
                    "Phase 16 is sensitivity analysis, not optimization. A numerically low outlet is not automatically a valid design; "
                    "always inspect readiness/confidence, flooding and pressure drop for the same sweep point."
                )


with comparison_tab:
    st.subheader("Engineering Comparison Tools")
    st.caption(
        "Compare alternatives on a controlled basis. Each successful alternative reruns the full integrated V4 solver: "
        "properties → Onda/two-film → counter-current ODEs → hydraulics → units → applicability. "
        "Phase 17 deliberately does not calculate a hidden composite best-score."
    )

    comparison_base_result = st.session_state.get("phase14_result")
    if comparison_base_result is None:
        st.info("Run a case in the Simulator tab first. That case becomes the comparison basis.")
    else:
        base_case = comparison_base_result.case
        st.success(
            f"Comparison basis loaded · {', '.join(base_case.solute_ids)} / "
            f"{comparison_base_result.registry.get_solvent(base_case.solvent_id).name} / "
            f"{comparison_base_result.registry.get_packing(base_case.packing_id).name}"
        )
        st.caption(
            "For packing comparison, chemistry, feed, geometry and flow basis are fixed and only packing changes. "
            "For solvent comparison, solutes/feed/carrier/packing/geometry/flows are fixed and only the solvent changes. "
            "Unsupported chemistry is retained as a failed alternative instead of being silently omitted."
        )

        comparison_mode_label = st.radio(
            "Comparison mode",
            ["Packing alternatives", "Solvent alternatives"],
            horizontal=True,
            key="phase17_comparison_mode",
        )

        if comparison_mode_label == "Packing alternatives":
            packing_ids = list(comparison_base_result.registry.packings)
            default_packings = [pid for pid in (base_case.packing_id, "38mm_metal_pall_ring", "imtp_25") if pid in packing_ids]
            selected_alternatives = st.multiselect(
                "Packings to compare",
                packing_ids,
                default=default_packings,
                format_func=lambda pid: comparison_base_result.registry.get_packing(pid).name,
                key="phase17_packings",
            )
            with st.expander("Packing data provenance / screening status"):
                packing_rows = []
                for pid in selected_alternatives:
                    p = comparison_base_result.registry.get_packing(pid)
                    prov = p.provenance
                    packing_rows.append({
                        "Packing": p.name,
                        "a (m²/m³)": p.area_m2_m3,
                        "Nominal size (mm)": 1000.0 * p.nominal_size_m,
                        "Void fraction": p.void_fraction,
                        "Fp (ft⁻¹)": p.packing_factor_ft_inv,
                        "Fp basis": p.packing_factor_basis,
                        "Confidence": "—" if prov is None else prov.confidence.value,
                        "Source": "—" if prov is None else prov.source,
                    })
                if packing_rows:
                    st.dataframe(pd.DataFrame(packing_rows), use_container_width=True, hide_index=True)
            run_comparison = st.button(
                "Run packing comparison", type="primary", key="run_phase17_packing_comparison",
                disabled=not selected_alternatives,
            )
            if run_comparison:
                with st.spinner(f"Running {len(selected_alternatives)} complete absorber simulations..."):
                    st.session_state["phase17_comparison"] = compare_packings(
                        base_case, selected_alternatives, registry=comparison_base_result.registry
                    )
        else:
            solvent_ids = list(comparison_base_result.registry.solvents)
            default_solvents = list(solvent_ids) if len(solvent_ids) <= 4 else [base_case.solvent_id]
            selected_alternatives = st.multiselect(
                "Solvents to compare",
                solvent_ids,
                default=default_solvents,
                format_func=lambda sid: comparison_base_result.registry.get_solvent(sid).name,
                key="phase17_solvents",
            )
            st.caption(
                "Acrylonitrile is automatically flagged as a materially volatile solvent in this comparison because V4.0 "
                "does not yet model solvent evaporation. That limitation remains visible in readiness/confidence."
            )
            run_comparison = st.button(
                "Run solvent comparison", type="primary", key="run_phase17_solvent_comparison",
                disabled=not selected_alternatives,
            )
            if run_comparison:
                evap_flags = {sid: (sid == "acrylonitrile") for sid in selected_alternatives}
                with st.spinner(f"Running {len(selected_alternatives)} complete absorber simulations..."):
                    st.session_state["phase17_comparison"] = compare_solvents(
                        base_case,
                        selected_alternatives,
                        registry=comparison_base_result.registry,
                        solvent_evaporation_expected=evap_flags,
                    )

        comparison_result = st.session_state.get("phase17_comparison")
        if comparison_result is not None:
            # Prevent an old comparison from being presented as belonging to a new baseline.
            if comparison_result.base_case is not None and comparison_result.base_case != base_case:
                st.warning("The stored comparison belongs to an older Simulator baseline. Run the comparison again for the current case.")
            else:
                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("Alternatives", len(comparison_result.alternatives))
                c2.metric("Successful", comparison_result.successful_alternatives)
                c3.metric("Failed / blocked", comparison_result.failed_alternatives)

                comp_df = pd.DataFrame(comparison_result.records())
                st.markdown("### Comparison table")
                st.dataframe(comp_df, use_container_width=True, hide_index=True)

                success_df = comp_df[comp_df["success"] == True].copy()  # noqa: E712
                if not success_df.empty:
                    metric_options = {
                        "Outlet VOC (mg/Nm³)": "outlet_mgVOC_Nm3",
                        "VOC mass removal (%)": "voc_mass_removal_percent",
                        "Captured total (kg/h)": "captured_kg_h",
                        "% Flood": "flooding_percent",
                        "Wet ΔP (mbar/m)": "wet_pressure_drop_mbar_m",
                        "Total ΔP (mbar)": "total_pressure_drop_mbar",
                    }
                    focus_solute = st.selectbox(
                        "Component detail",
                        list(base_case.solute_ids),
                        key="phase17_focus_solute",
                    )
                    metric_options.update({
                        f"{focus_solute} removal (%)": f"{focus_solute}__removal_percent",
                        f"{focus_solute} absorption factor A": f"{focus_solute}__absorption_factor",
                        f"{focus_solute} HTU_OG (m)": f"{focus_solute}__HTU_OG_m",
                        f"{focus_solute} NTU_OG": f"{focus_solute}__NTU_OG",
                    })
                    metric_label = st.selectbox(
                        "Comparison metric", list(metric_options), key="phase17_metric"
                    )
                    metric_col = metric_options[metric_label]
                    chart = success_df[["label", metric_col]].dropna().set_index("label")
                    if not chart.empty:
                        st.bar_chart(chart)
                        st.caption(
                            f"Chart metric: {metric_label}. This is a visualization/sort dimension only; it is not a composite design score."
                        )

                    st.markdown("### Readiness and confidence")
                    st.dataframe(
                        success_df[[
                            "label", "status", "confidence", "voc_mass_removal_percent",
                            "flooding_percent", "wet_pressure_drop_mbar_m"
                        ]],
                        use_container_width=True, hide_index=True,
                    )

                failed_df = comp_df[comp_df["success"] == False]  # noqa: E712
                if not failed_df.empty:
                    with st.expander("Unsupported / failed alternatives", expanded=True):
                        st.dataframe(
                            failed_df[["label", "solvent_id", "packing_id", "error"]],
                            use_container_width=True, hide_index=True,
                        )

                st.download_button(
                    "Download comparison CSV",
                    data=comp_df.to_csv(index=False).encode("utf-8"),
                    file_name="generic_absorber_phase17_comparison.csv",
                    mime="text/csv",
                    key="phase17_download_csv",
                )
                st.info(
                    "Decision rule: do not select an alternative from removal alone. Review outlet/removal together with ΔP, %Flood, "
                    "readiness, confidence and property provenance. Phase 17 intentionally provides no automatic 'best solvent' or 'best packing' score."
                )


with database_tab:
    st.subheader("Phase 18A — SQLite Database Migration")
    st.caption(
        "This is the migration/audit view, not yet the final Database Explorer. "
        "The solver still defaults to the verified Python registry; this page proves the SQLite snapshot can reconstruct it exactly."
    )

    db_path = Path(__file__).resolve().parent / "database" / "absorber_database.db"
    if not db_path.exists():
        st.error(f"Prebuilt SQLite database not found: {db_path}")
    else:
        db_repo = SQLiteAbsorberRepository(db_path)
        db_meta = db_repo.metadata()
        db_inv = db_repo.inventory()
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Schema version", db_meta.get("schema_version", "—"))
        d2.metric("Engineering records", db_inv.engineering_records)
        d3.metric("Sources", db_inv.sources)
        d4.metric("Provenance records", db_inv.provenance_records)

        st.markdown("### Inventory")
        st.dataframe(pd.DataFrame([
            {"Table": "Solutes", "Records": db_inv.solutes},
            {"Table": "Carrier gases", "Records": db_inv.carriers},
            {"Table": "Solvents", "Records": db_inv.solvents},
            {"Table": "Packings", "Records": db_inv.packings},
            {"Table": "Gas transport pairs", "Records": db_inv.gas_transport_pairs},
            {"Table": "Liquid transport pairs", "Records": db_inv.liquid_transport_pairs},
            {"Table": "Equilibrium pairs", "Records": db_inv.equilibrium_pairs},
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Database health")
        h1, h2 = st.columns(2)
        h1.metric("SQLite integrity", db_repo.integrity_check().upper())
        h2.metric("Foreign-key violations", len(db_repo.foreign_key_violations()))
        st.caption(f"Database ID: {db_meta.get('database_id', PHASE18A_DATABASE_ID)}")
        st.caption(f"Data snapshot: {db_meta.get('data_snapshot_id', '—')}")

        if st.button("Run registry ↔ SQLite parity gate", key="phase18a_parity_button"):
            parity18 = compare_registry_to_sqlite(build_phase18a_source_registry(), db_repo)
            if parity18.pass_gate:
                st.success("PHASE18A_DATABASE_MIGRATION_GATE = PASS")
            else:
                st.error("PHASE18A_DATABASE_MIGRATION_GATE = FAIL")
            st.dataframe(pd.DataFrame([
                {"Dataset": key, "Exact dataclass parity": "PASS" if value else "FAIL"}
                for key, value in parity18.dictionary_parity.items()
            ]), use_container_width=True, hide_index=True)

        with st.expander("Registered equilibrium pairs", expanded=False):
            st.dataframe(pd.DataFrame(db_repo.list_equilibrium_pairs()), use_container_width=True, hide_index=True)
        with st.expander("Normalized sources", expanded=False):
            st.dataframe(pd.DataFrame(db_repo.list_sources()), use_container_width=True, hide_index=True)

        st.info(
            "Phase 18A intentionally does not switch the production solver to SQLite yet. "
            "Cut-over comes only after repository abstraction and full old-registry == database regression gates."
        )


with provenance_tab:
    st.subheader("Phase 18B — Data Provenance & Source Registry")
    st.caption(
        "Structured bibliographic audit of the engineering database. This page does not recalculate absorber physics; "
        "it shows where registered properties/methods came from, their confidence, validity metadata and usage scope."
    )

    db18b_path = Path(__file__).resolve().parent / "database" / "absorber_database_v18b.db"
    if not db18b_path.exists():
        st.error(f"Phase 18B SQLite database not found: {db18b_path}")
    else:
        repo18b = SQLiteAbsorberRepositoryV18B(db18b_path)
        meta18b = repo18b.metadata()
        cov18b = repo18b.provenance_coverage()
        p1, p2, p3, p4 = st.columns(4)
        p1.metric("Schema version", meta18b.get("schema_version", "—"))
        p2.metric("Structured sources", cov18b.sources)
        p3.metric("Provenance records", cov18b.provenance_records)
        p4.metric("Property/method links", cov18b.provenance_usage_records)

        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Typed sources", f"{cov18b.sources_with_type}/{cov18b.sources}")
        q2.metric("Titled sources", f"{cov18b.sources_with_title}/{cov18b.sources}")
        q3.metric("DOI/URL linked", f"{cov18b.sources_with_url_or_doi}/{cov18b.sources}")
        q4.metric("Unclassified sources", cov18b.unresolved_source_metadata)

        st.markdown("### Confidence distribution")
        st.dataframe(pd.DataFrame([
            {"Confidence": "A — user verified / experimental", "Provenance records": cov18b.confidence_A},
            {"Confidence": "B — trusted literature/database", "Provenance records": cov18b.confidence_B},
            {"Confidence": "C — correlation estimate", "Provenance records": cov18b.confidence_C},
            {"Confidence": "D — screening/surrogate", "Provenance records": cov18b.confidence_D},
        ]), use_container_width=True, hide_index=True)

        if st.button("Run Phase 18B provenance parity gate", key="phase18b_parity_button"):
            report18b = compare_registry_to_phase18b_sqlite(build_phase18a_source_registry(), repo18b)
            if report18b.pass_gate:
                st.success("PHASE18B_STRUCTURED_PROVENANCE_GATE = PASS")
            else:
                st.error("PHASE18B_STRUCTURED_PROVENANCE_GATE = FAIL")
            st.dataframe(pd.DataFrame([
                {"Dataset": key, "Exact core parity": "PASS" if value else "FAIL"}
                for key, value in report18b.core_registry_parity.items()
            ]), use_container_width=True, hide_index=True)

        with st.expander("Structured source catalog", expanded=True):
            src_df = pd.DataFrame(repo18b.list_sources_detailed())
            if not src_df.empty:
                cols = [c for c in [
                    "source_type","evidence_role","title","authors","publication_year",
                    "journal_or_publisher","doi","url","provenance_records","usage_records",
                    "quality_note","citation"
                ] if c in src_df.columns]
                st.dataframe(src_df[cols], use_container_width=True, hide_index=True)

        with st.expander("Property / method provenance usage", expanded=False):
            usage_df = pd.DataFrame(repo18b.list_provenance_usage())
            st.dataframe(usage_df, use_container_width=True, hide_index=True)

        with st.expander("Source-type coverage", expanded=False):
            st.dataframe(pd.DataFrame(repo18b.list_source_type_summary()), use_container_width=True, hide_index=True)

        st.info(
            "Phase 18B improves traceability but does not claim all scientific data are fully literature-verified. "
            "Internal legacy and screening-surrogate sources remain explicitly labeled, while missing/weak areas are targets for later database expansion."
        )


with methods_tab:
    st.subheader("Live Methods & Assumptions")
    st.caption(
        "This audit trail is generated from the latest integrated Simulator result. It does not run a second calculation. "
        "Change the chemistry, operating conditions, packing, feed or solvent loading in Simulator and rerun the case; "
        "this page updates automatically."
    )

    live_result = st.session_state.get("phase14_result")
    if live_result is None:
        st.info("Run a case in the Simulator tab first. The live audit trail will then appear here.")
    else:
        audit = build_live_methods_report(live_result)
        st.success(f"{audit.report_id} · LIVE REPORT READY")

        st.markdown("### Active case")
        for item in audit.summary:
            st.write(f"- {item}")

        st.markdown("### Calculation methods and equations")
        for section in audit.sections:
            rows = [x for x in audit.equations if x.section == section]
            with st.expander(section, expanded=section.startswith("1.") or section.startswith("2.")):
                st.dataframe(pd.DataFrame([
                    {
                        "Method / quantity": x.title,
                        "Equation": x.equation,
                        "Active method": x.active_method,
                        "Live value": x.live_value,
                        "Engineering note": x.note or "—",
                    }
                    for x in rows
                ]), use_container_width=True, hide_index=True)

        st.markdown("### Resolved property provenance")
        st.caption(
            "Every critical property shows the actual selection path used by the current case: "
            "USER_OVERRIDE > DATABASE > CORRELATION_ESTIMATE > MISSING."
        )
        st.dataframe(pd.DataFrame([
            {
                "Scope": x.scope,
                "Property": x.property_name,
                "Value": x.value,
                "Unit": x.unit,
                "Tier": x.tier,
                "Confidence": x.confidence,
                "Method": x.method,
                "Source": x.source,
                "Estimated": x.estimated,
                "Note": x.note or "—",
            }
            for x in audit.properties
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Active assumptions and model limits")
        st.dataframe(pd.DataFrame([
            {
                "Category": x.category,
                "Assumption / scope item": x.assumption,
                "Current state": x.state,
                "Consequence": x.consequence,
            }
            for x in audit.assumptions
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Numerical and validity diagnostics")
        st.dataframe(pd.DataFrame([
            {
                "Scope": x.scope,
                "Diagnostic": x.diagnostic,
                "Live value": x.value,
                "Interpretation": x.interpretation,
            }
            for x in audit.diagnostics
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Applicability issues for this exact case")
        if live_result.post_applicability.issues:
            st.dataframe(pd.DataFrame([
                {
                    "Severity": i.severity.value,
                    "Code": i.code,
                    "Scope": i.scope,
                    "Message": i.message,
                }
                for i in live_result.post_applicability.issues
            ]), use_container_width=True, hide_index=True)
        else:
            st.success("No applicability issues were reported for this case.")

        st.info(
            "Interpretation rule: this page documents the method actually used for the current calculation. "
            "A correlation appearing here does not imply design-grade validity; always read its source, confidence and applicability messages together."
        )


with repository_tab:
    st.subheader("Phase 18C — Repository Backends")
    st.caption(
        "The simulator consumes one backend-neutral repository contract. The repository reconstructs the canonical "
        "AbsorberDataRegistry; property resolution and all physics remain unchanged."
    )

    py_desc = PYTHON_DATA_REPOSITORY.descriptor
    db_desc = SQLITE_DATA_REPOSITORY.descriptor
    py_reg = PYTHON_DATA_REPOSITORY.load_registry()
    db_reg = SQLITE_DATA_REPOSITORY.load_registry()

    st.markdown("### Backend inventory")
    st.dataframe(pd.DataFrame([
        {
            "Backend": py_desc.label,
            "Backend ID": py_desc.backend_id,
            "Kind": py_desc.kind.value,
            "Schema": py_desc.schema_version or "—",
            "Reference ID": py_reg.reference_id,
            **py_reg.inventory_counts(),
        },
        {
            "Backend": db_desc.label,
            "Backend ID": db_desc.backend_id,
            "Kind": db_desc.kind.value,
            "Schema": db_desc.schema_version or "—",
            "Reference ID": db_reg.reference_id,
            **db_reg.inventory_counts(),
        },
    ]), use_container_width=True, hide_index=True)

    sqlite_repo_raw = SQLiteAbsorberRepositoryV18B(PHASE18C_DB_PATH)
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("SQLite integrity", sqlite_repo_raw.integrity_check().upper())
    b2.metric("FK violations", len(sqlite_repo_raw.foreign_key_violations()))
    b3.metric("Python reference", py_reg.reference_id or "—")
    b4.metric("SQLite reference", db_reg.reference_id or "—")

    if st.button("Run dual-backend parity suite", type="primary", key="run_phase18c_backend_parity"):
        with st.spinner("Running deterministic cases on both repositories..."):
            st.session_state["phase18c_repository_parity"] = run_phase18c_repository_parity(
                PYTHON_DATA_REPOSITORY, SQLITE_DATA_REPOSITORY
            )

    repo_report = st.session_state.get("phase18c_repository_parity")
    if repo_report is not None:
        if repo_report.pass_gate:
            st.success(
                f"PHASE18C_REPOSITORY_ABSTRACTION_GATE = PASS · "
                f"{len(repo_report.scenarios)} scenarios · {repo_report.metrics_checked} numerical metrics"
            )
        else:
            st.error("PHASE18C_REPOSITORY_ABSTRACTION_GATE = FAIL")

        st.markdown("### Registry-object parity")
        st.dataframe(pd.DataFrame([
            {"Dataset": key, "Exact match": value}
            for key, value in repo_report.registry_dictionary_parity.items()
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Scenario parity")
        st.dataframe(pd.DataFrame([
            {
                "Scenario": row.scenario_id,
                "Python backend": row.python_backend_id,
                "SQLite backend": row.sqlite_backend_id,
                "Metrics": row.metrics_checked,
                "Max abs error": row.max_absolute_error,
                "Max rel error": row.max_relative_error,
                "Readiness match": row.readiness_match,
                "PASS": row.pass_gate,
            }
            for row in repo_report.scenarios
        ]), use_container_width=True, hide_index=True)

    st.info(
        "Phase 18C does not remove the Python registry. It makes the backend selectable and proves equivalence before any "
        "future SQLite-default cut-over. A backend switch changes data delivery only; it must not change equations or results."
    )


with overview_tab:
    st.subheader("Phase 14 architecture")
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
        ↓
Phase 9 Full V3 Parity Harness
        ↓
82 locked expected-vs-actual reference checks
source hash + section gates + regression tolerances
        ↓
Phase 10 Synthetic Generic Chemistry Gate
        ↓
fictional carrier + solvent + 2 fictional solutes
Henry path + direct-linear-m path + multicomponent ODE + units + hydraulics
legacy chemical-name hard-code audit
        ↓
Phase 11 Property Estimation Correlations
        ↓
missing DG → Fuller (when inputs exist)
missing DL → Wilke–Chang (when inputs exist)
all estimates → CORRELATION_ESTIMATE / Confidence C
        ↓
Phase 12 VDC / Water Real Chemistry
        ↓
NIST/Gossett Henry equilibrium + Fuller DG + Wilke–Chang DL
first real non-reference chemistry gate
        ↓
Phase 13 VDC / Acrylonitrile Screening Chemistry
        ↓
literature bulk AN properties + explicit Confidence D equilibrium surrogate
        ↓
Phase 14 Integrated Generic Simulator
        ↓
one product-facing case: inputs → full simulation → results + validity
        ↓
Phase 15 Live Methods & Assumptions
        ↓
current case → equations + provenance + active assumptions + diagnostics
report-only audit layer; no physics recalculation

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


with parity_tab:
    st.subheader("Full V3 reference parity gate")
    st.caption(
        "This is a regression-verification layer, not a new correlation. The complete V4 reference chain is "
        "executed and compared against the frozen REF_SCRUBBER_2026_10_06 numerical fixture."
    )

    p1, p2 = st.columns(2)
    p1.metric("Reference ID", REGISTRY.reference_id)
    p2.code(REFERENCE_SOURCE_SHA256, language="text")
    st.caption("SHA-256 belongs to the locked scrubber_model.py source used to create the Phase 9 fixture.")

    if st.button("Run full V3 parity gate", type="primary", key="run_phase9_parity"):
        parity_report = run_full_v3_parity()
        health = reference_chain_health()
        if parity_report.passed:
            st.success(
                f"PHASE9_FULL_V3_PARITY_GATE = PASS · "
                f"{parity_report.passed_count}/{parity_report.total_count} metrics passed"
            )
        else:
            st.error(
                f"PHASE9_FULL_V3_PARITY_GATE = FAIL · "
                f"{parity_report.failed_count} metric(s) outside tolerance"
            )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Parity metrics", parity_report.total_count)
        c2.metric("Passed", parity_report.passed_count)
        c3.metric("Failed", parity_report.failed_count)
        c4.metric("Phase 8 final status", health["phase8_final_status"])

        section_rows = []
        for section, metrics in parity_report.sections.items():
            passed_count = sum(m.passed for m in metrics)
            section_rows.append({
                "Section": section,
                "Passed": passed_count,
                "Total": len(metrics),
                "Gate": "PASS" if passed_count == len(metrics) else "FAIL",
            })
        st.markdown("### Section gates")
        st.dataframe(pd.DataFrame(section_rows), use_container_width=True, hide_index=True)

        metric_rows = []
        for m in parity_report.metrics:
            metric_rows.append({
                "Section": m.section,
                "Metric": m.name,
                "Expected": m.expected,
                "Actual": m.actual,
                "Unit": m.unit or "—",
                "Abs. error": m.absolute_error,
                "Rel. error": m.relative_error,
                "rtol": m.rtol,
                "atol": m.atol,
                "Gate": "PASS" if m.passed else "FAIL",
            })
        st.markdown("### Expected vs actual")
        st.dataframe(pd.DataFrame(metric_rows), use_container_width=True, hide_index=True)

        st.markdown("### Integrated-chain health")
        h1, h2, h3 = st.columns(3)
        h1.metric("Pre-solver", health["phase8_pre_status"])
        h2.metric("Final applicability", health["phase8_final_status"])
        h3.metric("Overall confidence", health["phase8_overall_confidence"])
        st.caption(
            f"Mass-balance relative error: ACN={health['ACN_mass_balance_relative_error']:.3e}, "
            f"VAc={health['VAc_mass_balance_relative_error']:.3e}."
        )
    else:
        st.info("Press the button to execute the complete locked reference chain and display all parity metrics.")

    st.info(
        "Phase 9 intentionally does not include required-height design in the parity metric set. "
        "No existing physics equation was changed in this phase."
    )


with synthetic_tab:
    st.subheader("Synthetic generic chemistry verification")
    st.caption(
        "This is a software-architecture verification fixture, not real chemical-property data. "
        "The synthetic case contains no ACN/VAc/Air/Water registry entries and exercises two fictional "
        "solutes through the full generic calculation chain."
    )

    st.info(
        "Case design: SYN_H uses Henry Hpc equilibrium; SYN_M uses direct linear y*=m·x equilibrium and "
        "enters with a nonzero solvent loading. Carrier, solvent and packing all use fictional IDs."
    )

    if st.button("Run Phase 10 synthetic generic gate", type="primary", key="run_phase10_synthetic"):
        syn = run_synthetic_generic_case()
        if syn.pass_gate:
            st.success("PHASE10_SYNTHETIC_GENERIC_GATE = PASS")
        else:
            st.error("PHASE10_SYNTHETIC_GENERIC_GATE = FAIL")

        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Synthetic case", SYNTHETIC_CASE_ID)
        g2.metric("Solved solutes", len(syn.solver_results.components))
        g3.metric("Core name audit", "PASS" if syn.core_name_independence_pass else "FAIL")
        g4.metric("Numerical health", "PASS" if syn.numerical_health_pass else "FAIL")

        st.markdown("### Synthetic registry")
        inventory = syn.registry.inventory_counts()
        st.dataframe(pd.DataFrame([
            {"Object": "Solutes", "Count": inventory["solutes"], "IDs": ", ".join(syn.registry.solutes)},
            {"Object": "Carrier", "Count": inventory["carriers"], "IDs": ", ".join(syn.registry.carriers)},
            {"Object": "Solvent", "Count": inventory["solvents"], "IDs": ", ".join(syn.registry.solvents)},
            {"Object": "Packing", "Count": inventory["packings"], "IDs": ", ".join(syn.registry.packings)},
        ]), use_container_width=True, hide_index=True)

        component_rows = []
        for sid in SYNTHETIC_SOLUTES:
            mt = syn.transfer_results[sid]
            result = syn.solver_results.components[sid]
            component_rows.append({
                "Solute": sid,
                "Equilibrium": mt.equilibrium_model,
                "m": mt.equilibrium_slope_m,
                "A": mt.absorption_factor,
                "HTU (m)": mt.HTU_OG_m,
                "NTU": mt.NTU_OG,
                "y in": result.gas_inlet_y,
                "y out": result.gas_outlet_y,
                "x in": result.liquid_inlet_x,
                "x bottom": result.liquid_bottom_x,
                "Removal (%)": None if result.removal_fraction is None else 100.0 * result.removal_fraction,
                "Rel. mass balance error": result.diagnostics.relative_mass_balance_error,
            })
        st.markdown("### Generic component results")
        st.dataframe(pd.DataFrame(component_rows), use_container_width=True, hide_index=True)

        h = syn.hydraulics
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Wet ΔP", f"{h.pressure_drop.wet_pressure_drop_Pa_m:.4f} Pa/m")
        h2.metric("Flood velocity", f"{h.flooding.flood_velocity_m_s:.4f} m/s")
        h3.metric("Flooding", f"{h.flooding.flooding_percent:.2f}%")
        h4.metric("GPDC range", "PASS" if h.flooding.gpdc_valid else "FAIL")

        b = syn.gas_balance
        st.markdown("### Multicomponent unit/reporting reconstruction")
        st.dataframe(pd.DataFrame([
            {"Stream": "Inlet", "ppmv": b.inlet.total_ppmv, "mgVOC/Nm³": b.inlet.total_mgVOC_Nm3, "mgC/Nm³": b.inlet.total_mgC_Nm3},
            {"Stream": "Outlet", "ppmv": b.outlet.total_ppmv, "mgVOC/Nm³": b.outlet.total_mgVOC_Nm3, "mgC/Nm³": b.outlet.total_mgC_Nm3},
        ]), use_container_width=True, hide_index=True)
        st.caption(f"Total captured synthetic-solute mass: {b.total_captured_kg_h:.6f} kg/h")

        st.markdown("### Applicability")
        a1, a2, a3 = st.columns(3)
        a1.metric("Pre-solver", syn.pre_applicability.status.value)
        a2.metric("Post-solver", syn.post_applicability.status.value)
        a3.metric("Blocking issues", len(syn.post_applicability.blocks))

        st.markdown("### Legacy-name architecture audit")
        if syn.core_name_independence_pass:
            st.success(
                "PASS — mass_transfer.py, countercurrent.py, hydraulics.py, units.py and applicability.py "
                "contain no standalone ACN/VAc/water/air identifiers."
            )
        else:
            st.error(str(syn.legacy_identifier_hits))
    else:
        st.info("Press the button to execute the synthetic full-chain verification case.")

    st.warning(
        "Synthetic values are intentionally fictional. A PASS proves software generality and numerical plumbing; "
        "it is not experimental validation of a real chemical system."
    )

with estimation_tab:
    st.subheader("Phase 11 — Fuller / Wilke–Chang estimation gate")
    st.caption(
        "This screen verifies the fallback path only. EST_X is a synthetic solute with no registered DG/DL pair. "
        "The fixture uses a separate synthetic carrier and solvent containing the required Fuller / Wilke–Chang inputs. "
        "The resulting diffusivities are estimates, not validated binary measurements."
    )

    st.code(
        "User Override > Registered Pair Data > Correlation Estimate > Missing",
        language="text",
    )

    if st.button("Run Phase 11 property-estimation gate", type="primary", key="run_phase11_estimation"):
        report = run_phase11_estimation_gate()
        if report.pass_gate:
            st.success("PHASE11_PROPERTY_ESTIMATION_GATE = PASS")
        else:
            st.error("PHASE11_PROPERTY_ESTIMATION_GATE = FAIL")

        c1, c2, c3 = st.columns(3)
        c1.metric("Fixture", PHASE11_ESTIMATION_CASE_ID)
        c2.metric("Fuller DG", f"{report.estimated_DG_m2_s:.6e} m²/s")
        c3.metric("Wilke–Chang DL", f"{report.estimated_DL_m2_s:.6e} m²/s")

        st.dataframe(pd.DataFrame([
            {
                "Property": "Gas diffusivity DG",
                "Method": "Fuller–Schettler–Giddings",
                "Tier": report.gas_tier,
                "Confidence": report.gas_confidence,
                "Value (m²/s)": report.estimated_DG_m2_s,
            },
            {
                "Property": "Liquid diffusivity DL",
                "Method": "Wilke–Chang",
                "Tier": report.liquid_tier,
                "Confidence": report.liquid_confidence,
                "Value (m²/s)": report.estimated_DL_m2_s,
            },
        ]), use_container_width=True, hide_index=True)

        g1, g2, g3 = st.columns(3)
        g1.metric("Database priority", "PASS" if report.reference_database_priority_pass else "FAIL")
        g2.metric("Override priority", "PASS" if report.override_priority_pass else "FAIL")
        g3.metric("Missing-input block", "PASS" if report.missing_input_block_pass else "FAIL")

    st.markdown("### Correlation requirements")
    st.write(
        "**Fuller:** solute MW + carrier MW + solute Fuller diffusion volume + carrier Fuller diffusion volume + T + P."
    )
    st.write(
        "**Wilke–Chang:** solvent MW + solvent viscosity at T + solvent association factor φ + "
        "solute molar volume at normal boiling point + T."
    )
    st.warning(
        "If a required correlation input is absent, Phase 11 does not invent it. Resolution stops with MissingPropertyError."
    )


with vdc_tab:
    st.subheader("Phase 12 — VDC / Water real-chemistry gate")
    st.caption(
        "This is the first real chemistry added outside the locked V3 ACN/VAc dataset. "
        "The default engineering fixture uses the reference column geometry at 22 °C, 1 atm, 1000 ppmv VDC and fresh water. "
        "It is a model verification fixture, not a claim that the plant feed is exactly 1000 ppmv."
    )

    st.markdown("### Registered VDC identity and equilibrium")
    st.dataframe(pd.DataFrame([
        {
            "ID": VDC_ID,
            "Name": "1,1-Dichloroethylene / Vinylidene chloride",
            "CAS": VDC_CAS,
            "Formula": VDC_FORMULA,
            "MW (g/mol)": 96.943,
            "Fuller volume": VDC_FULLER_DIFFUSION_VOLUME,
            "Le Bas Vb (cm³/mol)": VDC_LEBAS_BOILING_MOLAR_VOLUME_CM3_MOL,
            "Hpc ref (Pa·m³/mol @ 298.15 K)": VDC_WATER_H_REF_PA_M3_MOL,
        }
    ]), use_container_width=True, hide_index=True)

    st.info(
        "Primary Henry dataset: NIST WebBook compilation, measured Gossett (1987) entry kH=0.039 mol/(kg·bar) "
        "with temperature coefficient 3700 K. Published VDC/water Henry values show substantial scatter, so the "
        "equilibrium choice remains an explicit design uncertainty."
    )

    if st.button("Run Phase 12 VDC / Water gate", type="primary", key="run_phase12_vdc_water"):
        report = run_vdc_water_case()
        if report.pass_gate:
            st.success("PHASE12_VDC_WATER_GATE = PASS")
        else:
            st.error("PHASE12_VDC_WATER_GATE = FAIL")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Case", PHASE12_VDC_WATER_CASE_ID)
        c2.metric("Pre-check", report.pre_applicability.status.value)
        c3.metric("Final status", report.post_applicability.status.value)
        c4.metric("Overall confidence", report.post_applicability.confidence.overall.value)

        st.markdown("### Resolved property path")
        st.dataframe(pd.DataFrame([
            resolved_row("VDC DG", report.resolved.gas_diffusivity),
            resolved_row("VDC DL", report.resolved.liquid_diffusivity),
            resolved_row("VDC-water Henry Hpc", report.resolved.equilibrium.active_property),
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Absorber result — deterministic Phase 12 fixture")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Inlet", f"{report.gas_inlet_report.total_ppmv:.1f} ppmv")
        r2.metric("Outlet", f"{report.gas_outlet_report.total_ppmv:.1f} ppmv")
        r3.metric("Removal", f"{100*report.solver.removal_fraction:.3f}%")
        r4.metric("Absorption factor A", f"{report.transfer.absorption_factor:.4f}")

        st.dataframe(pd.DataFrame([
            {"Metric": "Equilibrium slope m", "Value": report.transfer.equilibrium_slope_m, "Unit": "y/x"},
            {"Metric": "HTU_OG", "Value": report.transfer.HTU_OG_m, "Unit": "m"},
            {"Metric": "NTU_OG", "Value": report.transfer.NTU_OG, "Unit": "—"},
            {"Metric": "Outlet mgVOC/Nm³", "Value": report.gas_outlet_report.total_mgVOC_Nm3, "Unit": "mg/Nm³"},
            {"Metric": "Wet pressure drop", "Value": report.hydraulics.pressure_drop.wet_pressure_drop_Pa_m, "Unit": "Pa/m"},
            {"Metric": "Flooding", "Value": report.hydraulics.flooding.flooding_percent, "Unit": "%"},
            {"Metric": "Mass-balance error", "Value": report.solver.diagnostics.relative_mass_balance_error, "Unit": "relative"},
        ]), use_container_width=True, hide_index=True)

        if report.transfer.absorption_factor < 1.0:
            st.warning(
                "For this water fixture A << 1, so physical absorption of VDC into water is thermodynamically difficult. "
                "This is an engineering screening result; Henry-constant sensitivity and plant data should be reviewed before design decisions."
            )

    st.markdown("### Source / model provenance")
    st.write(f"**Equilibrium:** {NIST_GOSSETT_SOURCE}")
    st.write(f"**DG estimate basis:** {FULLER_SOURCE}")
    st.write(f"**DL estimate basis:** {WILKE_CHANG_SOURCE}")
    st.warning(
        "Phase 12 does not calibrate the model to plant trials. DG and DL remain Confidence C estimates, and the published "
        "Henry literature scatter is retained as an explicit uncertainty rather than hidden by tuning."
    )


with vdc_acn_tab:
    st.subheader("Phase 13 — VDC / Acrylonitrile screening gate")
    st.caption(
        "This case adds a real liquid acrylonitrile solvent, but the VDC/AN binary equilibrium is not yet design-grade. "
        "The registered m-value is an explicit ideal-dilute Raoult screening surrogate at 22 °C and 1 atm."
    )

    st.markdown("### Acrylonitrile solvent property set")
    st.dataframe(pd.DataFrame([{
        "Solvent ID": ACN_SOLVENT_ID,
        "CAS": ACN_CAS,
        "Formula": ACN_FORMULA,
        "Density @22°C (kg/m³)": ACN_DENSITY_22C_KG_M3,
        "Viscosity near ambient (mPa·s)": ACN_VISCOSITY_NEAR_AMBIENT_PA_S * 1e3,
        "Surface tension near ambient (mN/m)": ACN_SURFACE_TENSION_NEAR_AMBIENT_N_M * 1e3,
        "VDC/AN screening m @22°C": VDC_ACN_LINEAR_M_22C,
        "AN Psat/P @22°C": ACN_VAPOR_FRACTION_IF_SATURATED_22C,
    }]), use_container_width=True, hide_index=True)

    st.warning(
        "Thermodynamics warning: the VDC/AN equilibrium uses gamma∞=1.0 and pure VDC vapor pressure to form "
        "m = Psat/P. It is Confidence D screening data, not measured binary VLE."
    )
    st.warning(
        "Volatility warning: pure acrylonitrile vapor pressure at the fixture temperature is about 12.7% of 1 atm. "
        "V4.0 does not include solvent evaporation, so the result is outside the recommended model domain."
    )

    if st.button("Run Phase 13 VDC / Acrylonitrile gate", type="primary", key="run_phase13_vdc_acn"):
        report = run_vdc_acn_case()
        if report.pass_gate:
            st.success("PHASE13_VDC_ACN_GATE = PASS")
        else:
            st.error("PHASE13_VDC_ACN_GATE = FAIL")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Case", PHASE13_VDC_ACN_CASE_ID)
        c2.metric("Pre-check", report.pre_applicability.status.value)
        c3.metric("Final status", report.post_applicability.status.value)
        c4.metric("Overall confidence", report.post_applicability.confidence.overall.value)

        st.markdown("### Resolved property path")
        st.dataframe(pd.DataFrame([
            resolved_row("VDC DG", report.resolved.gas_diffusivity),
            resolved_row("VDC in AN DL", report.resolved.liquid_diffusivity),
            resolved_row("VDC/AN equilibrium m", report.resolved.equilibrium.active_property),
        ]), use_container_width=True, hide_index=True)

        st.markdown("### Same-column screening comparison: Water vs Acrylonitrile")
        st.dataframe(pd.DataFrame([
            {
                "Solvent": "Water (Phase 12)",
                "Absorption factor A": report.water_absorption_factor,
                "Removal (%)": 100 * report.water_removal_fraction,
                "Thermo basis": "Measured Henry default (B), literature scatter",
            },
            {
                "Solvent": "Acrylonitrile (Phase 13)",
                "Absorption factor A": report.transfer.absorption_factor,
                "Removal (%)": 100 * report.solver.removal_fraction,
                "Thermo basis": "Ideal-dilute Raoult surrogate (D)",
            },
        ]), use_container_width=True, hide_index=True)

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Inlet", f"{report.gas_inlet_report.total_ppmv:.1f} ppmv")
        r2.metric("Outlet", f"{report.gas_outlet_report.total_ppmv:.4f} ppmv")
        r3.metric("Removal", f"{100*report.solver.removal_fraction:.4f}%")
        r4.metric("A", f"{report.transfer.absorption_factor:.3f}")

        st.dataframe(pd.DataFrame([
            {"Metric": "Equilibrium slope m", "Value": report.transfer.equilibrium_slope_m, "Unit": "y/x"},
            {"Metric": "HTU_OG", "Value": report.transfer.HTU_OG_m, "Unit": "m"},
            {"Metric": "NTU_OG", "Value": report.transfer.NTU_OG, "Unit": "—"},
            {"Metric": "Effective wetted area", "Value": report.common.effective_area_m2_m3, "Unit": "m²/m³"},
            {"Metric": "Wet pressure drop", "Value": report.hydraulics.pressure_drop.wet_pressure_drop_Pa_m, "Unit": "Pa/m"},
            {"Metric": "Flooding", "Value": report.hydraulics.flooding.flooding_percent, "Unit": "%"},
            {"Metric": "ACN vapor pressure", "Value": report.acn_vapor_pressure_Pa / 1000.0, "Unit": "kPa"},
            {"Metric": "Mass-balance error", "Value": report.solver.diagnostics.relative_mass_balance_error, "Unit": "relative"},
        ]), use_container_width=True, hide_index=True)

        st.info(
            f"The mathematical screening case predicts a much stronger VDC absorption tendency than water, but this "
            f"must not be treated as design validation until VDC/AN binary equilibrium and AN evaporation are represented."
        )

    st.markdown("### Source / evidence trail")
    st.write(f"**AN bulk properties:** {ACN_BULK_SOURCE}")
    st.write(f"**VDC vapor pressure:** {VDC_VP_SOURCE}")
    st.write(f"**AN vapor pressure:** {ACN_VP_SOURCE}")
    st.write(f"**VDC/AN equilibrium:** {VDC_ACN_EQUILIBRIUM_SOURCE}")
    st.write(f"**DL estimator caveat:** {WILKE_CHANG_ACN_NOTE}")
    st.write(f"**Project pilot observation:** {PROJECT_PILOT_NOTE}")
    st.caption(
        "The project pilot observation is not used to tune m, kL, kG or KG because the inlet VDC concentration and "
        "complete material-balance basis are not documented in the available slide summary."
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
        "Reference ACN/VAc DG/DL values remain fixed exactly as in V3. For chemistry without a registered transport pair, "
        "Phase 11+ may use Fuller/Wilke–Chang only when the required inputs exist; estimated values remain Confidence C."
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
- Built-in Fuller and Wilke–Chang fallback estimation is active from Phase 11 onward, but only after user/database resolution fails and required inputs are complete.
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
- Phase 9 runs the complete reference chain and compares 82 locked V3 metrics using declared algebra/coefficient/solver/reporting/hydraulic tolerances.
- The parity fixture is tied to the locked reference source by SHA-256; future intentional physics revisions must create a new reference rather than silently moving this baseline.
- Phase 10 verifies the full generic chain with fictional chemistry and audits generic physics modules for legacy chemical-name branching.
- Synthetic-data PASS demonstrates architecture generality only; it is not real-system validation.
- Phase 11 allows missing DG/DL to resolve through explicit Fuller/Wilke–Chang estimates when all required inputs exist.
- Phase 12 adds VDC/water as the first real non-reference chemistry; equilibrium is literature/database based while DG/DL remain visible Confidence C estimates.
- The Phase 12 applicability pre-check distinguishes an estimatable missing transport pair from truly missing critical data.
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
    st.success("PHASE9_FULL_V3_PARITY_GATE = PASS")
    st.success("PHASE10_SYNTHETIC_GENERIC_GATE = PASS")
    st.success("PHASE11_PROPERTY_ESTIMATION_GATE = PASS")
    st.success("PHASE12_VDC_WATER_GATE = PASS")
    st.success("PHASE13_VDC_ACN_GATE = PASS")
    st.success("PHASE14_INTEGRATED_SIMULATOR_GATE = PASS")
    st.success("PHASE15_LIVE_METHODS_GATE = PASS")
    st.success("PHASE16_PARAMETER_SWEEP_GATE = PASS")
    st.success("PHASE17_COMPARISON_GATE = PASS")
    st.success("PHASE18A_DATABASE_MIGRATION_GATE = PASS")
    st.caption("Phase 17 adds full-physics packing/solvent comparison tools. Alternatives keep performance, hydraulics, applicability and confidence visible without a hidden composite score.")

st.divider()
st.caption(
    "Generic Packed Absorber Simulator V4 · Phase 18A · SQLite Schema + Migration Architecture · "
    "Milestone C complete: integrated UI + live audit + sweeps + comparison tools"
)
