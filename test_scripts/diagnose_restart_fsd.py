#!/usr/bin/env python3
"""Compatibility entry point for CICE_testing.validation.fsd."""
from pathlib import Path
import sys
if sys.version_info < (3, 10):
    raise SystemExit("CICE_testing requires Python 3.10+; activate your analysis environment first.")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from CICE_testing.validation.fsd import *  # Preserve existing helper imports.

if __name__ == "__main__":
    main()
