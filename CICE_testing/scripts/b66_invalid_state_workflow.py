#!/usr/bin/env python3
"""Workflow entry point for CICE_testing.workflows.invalid_state."""
from pathlib import Path
import sys
if sys.version_info < (3, 10):
    raise SystemExit("CICE_testing requires Python 3.10+; activate your analysis environment first.")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from CICE_testing.workflows.invalid_state import *  # Preserve existing helper imports.

if __name__ == "__main__":
    main()
