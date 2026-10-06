"""Object interfaces to the audited diagnostic functions."""
from pathlib import Path
from netCDF4 import Dataset
from ..core.types import CandidateSpec, SpatialSpec
from . import candidates, spatial, fsd


class CandidateValidator:
    """Diagnostic-only candidates; applied coefficients must remain at control values."""
    def __init__(self, spec=CandidateSpec()):
        self.spec = spec

    def check(self, path, control=None):
        with Dataset(path) as ds:
            candidates.check_dataset(ds, self.spec.ktens, self.spec.gmin, self.spec.atol)
            if control is not None:
                with Dataset(control) as ref:
                    candidates.compare_history(ds, ref)


class SpatialValidator:
    def __init__(self, spec: SpatialSpec):
        self.spec = spec

    def check(self, path):
        return spatial.check_file(Path(path), self.spec)

    def compare(self, run, reference, atol=0.0, rtol=0.0):
        return spatial.compare_runs(Path(run), Path(reference), atol, rtol)


class RestartFSDDiagnostic:
    """Descriptive diagnosis, never a successful-validation gate by itself."""
    def __init__(self, grid_history):
        self.grid_history = Path(grid_history)
        self.grid = fsd.read_grid(self.grid_history)
        self.longitude = fsd.read_longitude(self.grid_history, self.grid[0])

    def diagnose(self, restart):
        detail = {}
        result = fsd.diagnose(Path(restart), self.grid, detail=detail, lon=self.longitude)
        return result, detail

    def report(self, restart):
        result, detail = self.diagnose(restart)
        fsd.report(restart, result, detail)
        return result, detail
