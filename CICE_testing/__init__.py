"""Reusable CICE validation workflows, independent of the model checkout."""
__version__ = "0.1.0"
from .core.types import WorkflowSpec, CandidateSpec, SpatialSpec, FigureSpec
from .core.paths import TestingPaths

__all__ = ["WorkflowSpec", "CandidateSpec", "SpatialSpec", "FigureSpec", "TestingPaths"]
