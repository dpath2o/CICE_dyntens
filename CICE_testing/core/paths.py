"""Model and output locations never depend on where this package is installed."""
from dataclasses import dataclass
from pathlib import Path
import os


def model_repo():
    explicit = os.environ.get("CICE_MODEL_REPO")
    if explicit:
        return Path(explicit).expanduser().resolve()
    current = Path.cwd().resolve()
    for path in (current, *current.parents):
        if (path / "cice.setup").is_file():
            return path
    raise ValueError("provide --repo or CICE_MODEL_REPO outside a CICE checkout")


def run_root():
    return Path(os.environ.get("CICE_TEST_RUNS", "/g/data/gv90/da1339/cice-dirs/runs")).expanduser()

@dataclass(frozen=True)
class TestingPaths:
    output: Path
    scope: str = "box"

    def __post_init__(self):
        object.__setattr__(self, "output", Path(self.output).expanduser().resolve())
        if self.scope not in ("box", "global"):
            raise ValueError("scope must be box or global")

    @property
    def figures(self):
        return self.output / self.scope / "figures"

    @property
    def evidence(self):
        return self.output / self.scope / "evidence"
