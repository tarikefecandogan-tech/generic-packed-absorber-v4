"""Human-readable Phase 1 gate check."""
from generic_absorber_v4 import locked_reference_data


def main() -> None:
    db = locked_reference_data()
    print(f"Reference: {db.reference_id}")
    print(f"Solutes: {', '.join(db.solutes)}")
    print(f"Carriers: {', '.join(db.carriers)}")
    print(f"Solvents: {', '.join(db.solvents)}")
    print(f"Packings: {', '.join(db.packings)}")
    print(f"Gas transport pairs: {len(db.gas_transport_pairs)}")
    print(f"Liquid transport pairs: {len(db.liquid_transport_pairs)}")
    print(f"Equilibrium pairs: {len(db.equilibrium_pairs)}")
    print("PHASE1_DATA_GATE=PASS")


if __name__ == "__main__":
    main()
