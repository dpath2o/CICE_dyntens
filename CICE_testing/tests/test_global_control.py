"""Preparation isolation and G0 exact-comparison behaviour."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
from netCDF4 import Dataset

from CICE_testing.core.types import WorkflowSpec
from CICE_testing.workflows.global_control import GlobalControlWorkflow, NAMES, INPUT, check_completion, nonempty_path, required_history_fields
from CICE_testing.workflows.restart import set_entry, entry

ROOT = Path(__file__).resolve().parents[2]


def prepared(tmp_path):
    repo = tmp_path/'repo'
    template = repo/'global_tests/G0/dyntens01'
    shutil.copytree(ROOT/'global_tests/G0/dyntens01', template)
    (repo/'tools').mkdir()
    shutil.copy2(ROOT/'tools/compare_dyntens_runs.py', repo/'tools')
    text = (template/'ice_in').read_text()
    for key in ('grid_file', 'kmt_file', 'atm_data_dir', 'ocn_data_dir'):
        path = tmp_path/key
        path.touch()
        text = set_entry(text, key, repr(str(path)))
    (template/'ice_in').write_text(text)
    source = tmp_path/INPUT
    with Dataset(source, 'w') as ds:
        for dim, size in [('ncat', 5), ('nj', 1080), ('ni', 1440)]:
            ds.createDimension(dim, size)
        ds.createVariable('aicen', 'f8', ('ncat', 'nj', 'ni'))
        for key, value in dict(myear=2000, mmonth=9, mday=1, msec=0, istep1=100).items():
            ds.setncattr(key, value)
    workflow = GlobalControlWorkflow(WorkflowSpec(repo, tmp_path/'runs'))
    workflow.prepare(source)
    return workflow, template


def outputs(workflow):
    for name in NAMES:
        case, run = workflow.spec.repo/'global_tests/G0'/name, workflow.spec.runs/name
        shutil.copy2(case/'ice_in', run/'ice_in')
        (run/'cice').write_bytes(b'identical executable')
        (run/'mpi_exit_status.txt').write_text('0\n')
        (run/'cice.runlog.test').write_text('MPI launch log; diagnostics in ice_diag.d\n')
        (run/'ice_diag.d').write_text('CICE COMPLETED SUCCESSFULLY\n')
        for filename in ['iceh_ic.2000-09-01-00000.nc', 'iceh.2000-09-01.nc', 'iceh.2000-09-02.nc']:
            with Dataset(run/'history'/filename, 'w') as ds:
                ds.createDimension('nj', 1080)
                ds.createDimension('ni', 1440)
                for key in ('aice', 'hi', 'uvel', 'vvel'):
                    ds.createVariable(key, 'f8', ())[:] = 1.
        for day in (2, 3):
            with Dataset(run/'restart'/f'iced.2000-09-{day:02d}-00000.nc', 'w') as ds:
                for key, value in dict(myear=2000, mmonth=9, mday=day, msec=0, istep1=100+48*(day-1)).items():
                    ds.setncattr(key, value)
                # Identical under-normalised FSD must not fail the G0 identity check.
                ds.createVariable('fsd_sum', 'f8', ())[:] = .999999967


def test_preserves_physics_and_corrects_launch_paths(tmp_path):
    workflow, template = prepared(tmp_path)
    old = (template/'ice_in').read_text()
    for name in NAMES:
        case = workflow.spec.repo/'global_tests/G0'/name
        text = (case/'ice_in').read_text()
        for key in ('Ktens', 'ktherm', 'atm_data_type', 'ocn_data_type', 'wave_spec_type', 'tr_fsd', 'nx_global'):
            assert entry(text, key) == entry(old, key)
        launch = (case/'cice.run').read_text()
        assert str(case) in launch and '/home/581/da1339/AFIM' not in launch
        assert launch.count('storage=') == 1
    with pytest.raises(ValueError, match='refusing existing'):
        workflow.prepare(tmp_path/INPUT)


def test_identity_accepts_matching_fsd_departures_but_rejects_physical_change(tmp_path):
    workflow, _ = prepared(tmp_path)
    outputs(workflow)
    workflow.analyse()
    with Dataset(workflow.spec.runs/NAMES[1]/'history/iceh.2000-09-01.nc', 'r+') as ds:
        ds['hi'][:] = 2.
    with pytest.raises(ValueError, match='numerical values differ'):
        workflow.analyse()


def test_matching_wrong_clock_is_rejected(tmp_path):
    workflow, _ = prepared(tmp_path)
    outputs(workflow)
    for name in NAMES:
        with Dataset(workflow.spec.runs/name/'restart/iced.2000-09-03-00000.nc', 'r+') as ds:
            ds.istep1 = 100
    with pytest.raises(ValueError, match='incorrect restart clock'):
        workflow.analyse()


def test_completion_uses_configured_destination_and_rejects_retries(tmp_path):
    (tmp_path/'cice.runlog.one').write_text('CICE COMPLETED SUCCESSFULLY')
    (tmp_path/'ice_diag.d').write_text('incomplete')
    text = "diag_type = 'file'\ndiag_file = 'ice_diag.d'\n"
    with pytest.raises(ValueError, match='model completion missing'):
        check_completion(tmp_path, text)
    (tmp_path/'ice_diag.d').write_text('CICE COMPLETED SUCCESSFULLY')
    check_completion(tmp_path, text)
    check_completion(tmp_path, "diag_type = 'stdout'\n")
    (tmp_path/'cice.runlog.two').write_text('CICE COMPLETED SUCCESSFULLY')
    with pytest.raises(ValueError, match='retries'):
        check_completion(tmp_path, text)


def test_empty_run_argument_is_rejected():
    import argparse
    with pytest.raises(argparse.ArgumentTypeError, match='path is empty'):
        nonempty_path('')


def test_thermal_history_requirements_follow_recorded_switches():
    text = "f_hs = 'x'\nf_Tsfc = 'x'\n"
    assert required_history_fields(text) == ['aice', 'hi', 'uvel', 'vvel']
    text = set_entry(text, 'f_Tsfc', "'d'")
    assert required_history_fields(text) == ['aice', 'hi', 'uvel', 'vvel', 'Tsfc']
