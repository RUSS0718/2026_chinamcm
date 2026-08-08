"""Integer-grid geometry and search seams for Q4."""

from .geometry import DEFAULT_MODULES, bbox, polygon_area, rotate_normalized
from .model import Q4Block, Q4Evaluation, Q4Instance, evaluate_layout, formal_audit_match
from .search import ExactResult, solve_exact
from .sa import SAResult, row_layout, solve_sa

__all__ = [
    "DEFAULT_MODULES",
    "Q4Block",
    "Q4Evaluation",
    "Q4Instance",
    "ExactResult",
    "SAResult",
    "bbox",
    "evaluate_layout",
    "formal_audit_match",
    "polygon_area",
    "rotate_normalized",
    "solve_exact",
    "row_layout",
    "solve_sa",
]
