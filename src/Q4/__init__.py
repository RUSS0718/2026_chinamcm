"""Integer-grid geometry and search seams for Q4."""

from .geometry import EXTERNAL_DATA_MANIFEST_HASH, DEFAULT_MODULES, GEOMETRY_THICKNESSES, bbox, modules_for_geometry, polygon_area, rotate_normalized
from .model import Q4Block, Q4Evaluation, Q4Instance, evaluate_layout, formal_audit_match
from .search import ExactResult, solve_exact
from .sa import SAResult, row_layout, solve_sa

__all__ = [
    "DEFAULT_MODULES",
    "EXTERNAL_DATA_MANIFEST_HASH",
    "GEOMETRY_THICKNESSES",
    "Q4Block",
    "Q4Evaluation",
    "Q4Instance",
    "ExactResult",
    "SAResult",
    "bbox",
    "modules_for_geometry",
    "evaluate_layout",
    "formal_audit_match",
    "polygon_area",
    "rotate_normalized",
    "solve_exact",
    "row_layout",
    "solve_sa",
]
