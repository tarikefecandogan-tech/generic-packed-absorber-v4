"""Human-readable Phase 2 gate check."""
from generic_absorber_v4 import MissingPairDataError, SoluteSpec, build_reference_registry


def main() -> None:
    registry = build_reference_registry()
    counts = registry.inventory_counts()
    print(f"Reference: {registry.reference_id}")
    for key, value in counts.items():
        print(f"{key}: {value}")

    for solute in ("ACN", "VAc"):
        report = registry.availability(solute, "air", "water")
        print(f"{solute}/air/water: {report.status.value}")
        assert report.status.value == "READY"

    registry.register_solute(SoluteSpec(id="X", name="Synthetic X", MW_kg_mol=0.050))
    try:
        registry.require_equilibrium_pair("X", "water")
    except MissingPairDataError as exc:
        print(f"missing-pair safety: PASS ({exc.pair_type})")
    else:
        raise AssertionError("Missing pair did not raise MissingPairDataError")

    print("PHASE2_REGISTRY_GATE=PASS")


if __name__ == "__main__":
    main()
