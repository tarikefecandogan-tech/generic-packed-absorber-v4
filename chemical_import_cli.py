#!/usr/bin/env python3
"""Explicit operator CLI for Phase 18F chemical-database imports.

Examples:
  python chemical_import_cli.py package.json
  python chemical_import_cli.py package.json --commit
  python chemical_import_cli.py package.json --commit --allow-replace

Dry-run is the default. Production Streamlit intentionally does not expose a
write button; committing database changes is an explicit operator action.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys

from generic_absorber_v4 import ChemicalImportValidationError, import_chemical_package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("package", type=Path)
    parser.add_argument("--database", type=Path, default=Path("database/absorber_database_v18g.db"))
    parser.add_argument("--commit", action="store_true", help="Actually write the package. Default is dry-run.")
    parser.add_argument("--allow-replace", action="store_true", help="Explicitly allow replacement of existing entity/pair keys.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create the pre-import backup when committing.")
    args = parser.parse_args()

    try:
        result = import_chemical_package(
            args.database,
            args.package,
            dry_run=not args.commit,
            allow_replace=args.allow_replace,
            create_backup=not args.no_backup,
        )
    except ChemicalImportValidationError as exc:
        print("VALIDATION = BLOCKED")
        for issue in exc.report.issues:
            print(f"[{issue.severity.value}] {issue.code} @ {issue.location}: {issue.message}")
        return 2

    print("VALIDATION = PASS")
    print(f"package_id = {result.validation.package_id}")
    print(f"dry_run = {result.dry_run}")
    print(f"committed = {result.committed}")
    print(f"integrity = {result.database_integrity}")
    print(f"foreign_key_violations = {len(result.foreign_key_violations)}")
    print(f"planned_delta = {result.validation.planned_delta}")
    if result.backup_path:
        print(f"backup = {result.backup_path}")
    for issue in result.validation.issues:
        print(f"[{issue.severity.value}] {issue.code} @ {issue.location}: {issue.message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
