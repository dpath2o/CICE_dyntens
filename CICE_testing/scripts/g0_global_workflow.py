#!/usr/bin/env python3
"""Run the G0 global-control workflow."""
from pathlib import Path
import sys
if sys.version_info < (3, 10):
    raise SystemExit('Activate a Python 3.10+ analysis environment.')
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from CICE_testing.workflows.global_control import main

if __name__ == '__main__':
    main()
