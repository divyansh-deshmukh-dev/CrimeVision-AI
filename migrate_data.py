"""
migrate_data.py — Root CLI entry point for CrimeVision AI data migration.

Usage:
  # Dry-run inspection
  python migrate_data.py --dry-run

  # Apply migration of demo cases into target database & storage
  python migrate_data.py
"""

from storage.migrate_data import main

if __name__ == "__main__":
    main()
