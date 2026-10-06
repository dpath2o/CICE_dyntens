#!/usr/bin/env python3
"""Workflow entry point for CICE_testing.workflows.feedback."""
from pathlib import Path
import sys
if sys.version_info < (3, 10):
    raise SystemExit('CICE_testing requires Python 3.10+; activate your analysis environment.')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from CICE_testing.workflows.feedback import main

if __name__ == '__main__':
    main()
