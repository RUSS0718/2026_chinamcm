from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Mapping

from .geometry import bbox, polygon_area, rotate_normalized
from .model import Q4Evaluation, Q4Instance, evaluate_layout, formal_audit_match


@dataclass(frozen=True)
class ExactResult:
    status: str
    complete: bool
    layout: dict | None
    evaluation: Q4Evaluation | None
    lower_bound: int
    upper_bound: int | None
    domain_upper_area: int
    containers_checked: int
    placements_tested: int
    runtime: float
    formal_audit_match: bool
    audit: dict
    domain: dict
    domain_evaluation: Q4Evaluation | None = None
    domain_audit: dict = field(default_factory=dict)
    domain_audit_match: bool = False

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "complete": self.complete,
            "layout": self.evaluation.as_dict()["layout"] if self.evaluation else {},
            "evaluation": self.evaluation.as_dict() if self.evaluation else {},
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
            "domain_upper_area": self.domain_upper_area,
            "containers_checked": self.containers_checked,
            "placements_tested": self.placements_tested,
            "runtime": self.runtime,
            "formal_audit_match": self.formal_audit_match,
            "audit": self.audit,
            "domain": self.domain,
            "domain_evaluation": self.domain_evaluation.as_dict() if self.domain_evaluation else {},
            "domain_audit": self.domain_audit,
            "domain_audit_match": self.domain_audit_match,
        }


class _SearchTimeout(Exception):
    pass


def _inside(polygon: tuple[tuple[int, int], ...], x: float, y: float) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y):
            crossing = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing:
                inside = not inside
    return inside


def _cells(polygon: tuple[tuple[int, int], ...]) -> frozenset[tuple[int, int]]:
    width, height = bbox(polygon)
    min_x = min(x for x, _ in polygon)
    min_y = min(y for _, y in polygon)
    cells = frozenset(
        (x, y)
        for x in range(min_x, min_x + width)
        for y in range(min_y, min_y + height)
        if _inside(polygon, x + 0.5, y + 0.5)
    )
    if len(cells) != polygon_area(polygon):
        raise ValueError("integer cell discretization does not preserve polygon area")
    return cells


def _container_sizes(instance: Q4Instance, upper_area: int) -> list[tuple[int, int]]:
    min_width = max(min(bbox(rotate_normalized(block.polygon, rotation))[0] for rotation in (0, 90, 180, 270)) for block in instance.blocks.values())
    min_height = max(min(bbox(rotate_normalized(block.polygon, rotation))[1] for rotation in (0, 90, 180, 270)) for block in instance.blocks.values())
    max_width = upper_area // min_height
    max_height = upper_area // min_width
    return sorted(
        (
            (width, height)
            for width in range(min_width, max_width + 1)
            for height in range(min_height, max_height + 1)
            if instance.module_area <= width * height <= upper_area
        ),
        key=lambda item: (item[0] * item[1], item[0], item[1]),
    )


def _row_layout(instance: Q4Instance) -> dict[str, tuple[int, int, int]]:
    layout: dict[str, tuple[int, int, int]] = {}
    x = 0
    for name in sorted(instance.blocks):
        layout[name] = (x, 0, 0)
        x += bbox(instance.blocks[name].polygon)[0]
    return layout


def solve_exact(
    instance: Q4Instance | None = None,
    *,
    upper_area: int = 36,
    time_limit: float | None = None,
    domain: tuple[int, int] | None = None,
) -> ExactResult:
    instance = instance or Q4Instance.default()
    if not isinstance(upper_area, int):
        raise ValueError("upper_area must be an integer")
    if upper_area < instance.module_area:
        raise ValueError("upper_area must be at least module_area")
    if time_limit is not None and time_limit < 0:
        raise ValueError("time_limit must be non-negative")
    if domain is not None and (not isinstance(domain, tuple) or len(domain) != 2 or any(not isinstance(value, int) or value <= 0 for value in domain)):
        raise ValueError("domain dimensions must be positive integers")
    started = time.perf_counter()
    module_area = instance.module_area
    containers = _container_sizes(instance, upper_area)
    if domain is not None:
        containers = [item for item in containers if item[0] <= domain[0] and item[1] <= domain[1]]
    declared_domain = {
        "grid_step": 1,
        "rotations": [0, 90, 180, 270],
        "search_domain": "integer_translation_grid",
        "area_lower_bound": module_area,
        "area_upper_bound": upper_area,
        "width_range": [min(width for width, _ in containers), max(width for width, _ in containers)] if containers else [],
        "height_range": [min(height for _, height in containers), max(height for _, height in containers)] if containers else [],
        "containers_total": len(containers),
    }
    if domain is not None:
        declared_domain["declared_outline"] = list(domain)
    placements_tested = 0
    containers_checked = 0

    best_layout = None
    best_evaluation = None
    best_audit: dict = {}
    best_domain_evaluation: Q4Evaluation | None = None
    best_domain_audit: dict = {}
    best_domain_match = False
    row = _row_layout(instance)
    row_objective = evaluate_layout(instance, row)
    row_bounded = evaluate_layout(instance, row, domain) if domain else row_objective
    if row_objective.legal and row_bounded.legal and row_objective.area <= upper_area:
        best_layout = row
        best_evaluation = row_objective
        best_domain_evaluation = row_bounded if domain else None
        from src._internal.audit import audit_layout

        best_audit = audit_layout(instance, row)
        if domain:
            best_domain_audit = audit_layout(instance, row, (0, 0, *domain))
            best_domain_match = formal_audit_match(instance, row, domain)
    if time_limit is not None and time_limit <= 0:
        matched = formal_audit_match(instance, best_layout) if best_layout is not None else False
        return ExactResult("timeout", False, best_layout, best_evaluation, module_area, best_evaluation.area if best_evaluation else None, upper_area, 0, 0, 0.0, matched, best_audit, {**declared_domain, "containers_checked": 0}, best_domain_evaluation, best_domain_audit, best_domain_match)

    ordered = tuple(sorted(instance.blocks, key=lambda name: (-instance.blocks[name].polygon.__len__(), name)))

    def timed_out() -> bool:
        return time_limit is not None and time.perf_counter() - started >= time_limit

    def find_layout(width: int, height: int):
        occupied: set[tuple[int, int]] = set()
        layout: dict[str, tuple[int, int, int]] = {}

        def dfs(index: int):
            nonlocal placements_tested
            if timed_out():
                raise _SearchTimeout
            if index == len(ordered):
                return dict(layout)
            name = ordered[index]
            block = instance.blocks[name]
            for rotation in (0, 90, 180, 270):
                local = rotate_normalized(block.polygon, rotation)
                block_width, block_height = bbox(local)
                cells = _cells(local)
                for y in range(height - block_height + 1):
                    for x in range(width - block_width + 1):
                        placements_tested += 1
                        translated = {(x + px, y + py) for px, py in cells}
                        if translated & occupied:
                            continue
                        layout[name] = (x, y, rotation)
                        occupied.update(translated)
                        found = dfs(index + 1)
                        if found is not None:
                            return found
                        for cell in translated:
                            occupied.remove(cell)
                        layout.pop(name)
            return None

        return dfs(0)

    try:
        lower_bound = module_area
        for index, (width, height) in enumerate(containers):
            lower_bound = width * height
            layout = find_layout(width, height)
            containers_checked += 1
            if layout is None:
                if index + 1 < len(containers):
                    lower_bound = containers[index + 1][0] * containers[index + 1][1]
                continue
            objective = evaluate_layout(instance, layout)
            bounded = evaluate_layout(instance, layout, domain) if domain else objective
            if not objective.legal or not bounded.legal or objective.area > upper_area:
                raise AssertionError("exact search produced an illegal layout")
            matched = formal_audit_match(instance, layout)
            if not matched:
                raise AssertionError("formal evaluator and independent audit disagree")
            bounded_match = formal_audit_match(instance, layout, domain) if domain else False
            if domain and not bounded_match:
                raise AssertionError("declared-domain evaluator and independent audit disagree")
            from src._internal.audit import audit_layout

            return ExactResult(
                "optimal",
                True,
                layout,
                objective,
                objective.area,
                objective.area,
                upper_area,
                containers_checked,
                placements_tested,
                time.perf_counter() - started,
                True,
                audit_layout(instance, layout),
                {**declared_domain, "containers_checked": containers_checked},
                bounded if domain else None,
                audit_layout(instance, layout, (0, 0, *domain)) if domain else {},
                bounded_match,
            )
    except _SearchTimeout:
        matched = formal_audit_match(instance, best_layout) if best_layout is not None else False
        return ExactResult("timeout", False, best_layout, best_evaluation, lower_bound, best_evaluation.area if best_evaluation else None, upper_area, containers_checked, placements_tested, time.perf_counter() - started, matched, best_audit, {**declared_domain, "containers_checked": containers_checked}, best_domain_evaluation, best_domain_audit, best_domain_match)

    return ExactResult("no_feasible", True, None, None, lower_bound, None, upper_area, containers_checked, placements_tested, time.perf_counter() - started, False, {}, {**declared_domain, "containers_checked": containers_checked})
