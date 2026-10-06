"""Explicit configuration objects, following shuga's specification pattern."""
from dataclasses import dataclass
from pathlib import Path
import math

@dataclass(frozen=True)
class WorkflowSpec:
    repo: Path
    runs: Path
    base_case: Path | None = None

    def __post_init__(self):
        for key in ("repo", "runs", "base_case"):
            value = getattr(self, key)
            if value is not None:
                object.__setattr__(self, key, Path(value).expanduser().resolve())

@dataclass(frozen=True)
class CandidateSpec:
    ktens: float = 0.2
    gmin: float = 0.2
    atol: float = 1e-10

    def __post_init__(self):
        if not all(math.isfinite(x) for x in (self.ktens, self.gmin, self.atol)):
            raise ValueError("coefficients and tolerance must be finite")
        if not (0 <= self.ktens <= 1 and 0 <= self.gmin <= 1 and self.atol >= 0):
            raise ValueError("coefficients must be in [0,1]; tolerance must be nonnegative")

@dataclass(frozen=True)
class SpatialSpec:
    mode: str
    ktens: float
    background: float = 1.0
    band: float = 0.5
    ilo: int = 6
    ihi: int = 7
    wind: str | None = None
    tensile: bool = False
    ic_prefix: str = "iceh_ic"

    def __post_init__(self):
        if self.mode not in ("constant", "box_band"):
            raise ValueError("unsupported spatial mode")
        if not all(math.isfinite(x) and 0 <= x <= 1 for x in (self.ktens, self.background, self.band)):
            raise ValueError("spatial coefficients must be finite in [0,1]")
        if not (1 <= self.ilo <= self.ihi):
            raise ValueError("band indices must be ordered, positive, one-based")
        if self.wind not in (None, "box_tensile", "uniform_east"):
            raise ValueError("unsupported wind")

@dataclass(frozen=True)
class FigureSpec:
    output: Path
    scope: str = "box"
    dpi: int = 180

    def __post_init__(self):
        object.__setattr__(self, "output", Path(self.output).expanduser().resolve())
        if self.scope not in ("box", "global") or self.dpi <= 0:
            raise ValueError("scope must be box/global and dpi positive")
