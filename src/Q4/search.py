from __future__ import annotations

import time
from dataclasses import dataclass
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
) -> ExactResult:
    instance = instance or Q4Instance.default()
    if not isinstance(upper_area, int):
        raise ValueError("upper_area must be an integer")
    if upper_area < instance.module_area:
        raise ValueError("upper_area must be at least module_area")
    if time_limit is not None and time_limit < 0:
        raise ValueError("time_limit must be non-negative")
    started = time.perf_counter()
    module_area = instance.module_area
    containers = _container_sizes(instance, upper_area)
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
    placements_tested = 0
    containers_checked = 0

    best_layout = None
    best_evaluation = None
    best_audit: dict = {}
    row = _row_layout(instance)
    row_evaluation = evaluate_layout(instance, row)
    if row_evaluation.legal and row_evaluation.area <= upper_area:
        best_layout = row
        best_evaluation = row_evaluation
        from src._internal.audit import audit_layout

        best_audit = audit_layout(instance, row)
    if time_limit is not None and time_limit <= 0:
        matched = formal_audit_match(instance, best_layout) if best_layout is not None else False
        return ExactResult("timeout", False, best_layout, best_evaluation, module_area, best_evaluation.area if best_evaluation else None, upper_area, 0, 0, 0.0, matched, best_audit, {**declared_domain, "containers_checked": 0})

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
            evaluation = evaluate_layout(instance, layout, (width, height))
            if not evaluation.legal:
                raise AssertionError("exact search produced an illegal layout")
            matched = formal_audit_match(instance, layout, (width, height))
            if not matched:
                raise AssertionError("formal evaluator and independent audit disagree")
            from src._internal.audit import audit_layout

            return ExactResult(
                "optimal",
                True,
                layout,
                evaluation,
                evaluation.area,
                evaluation.area,
                upper_area,
                containers_checked,
                placements_tested,
                time.perf_counter() - started,
                True,
                audit_layout(instance, layout, (0, 0, width, height)),
                {**declared_domain, "containers_checked": containers_checked},
            )
    except _SearchTimeout:
        matched = formal_audit_match(instance, best_layout) if best_layout is not None else False
        return ExactResult("timeout", False, best_layout, best_evaluation, lower_bound, best_evaluation.area if best_evaluation else None, upper_area, containers_checked, placements_tested, time.perf_counter() - started, matched, best_audit, {**declared_domain, "containers_checked": containers_checked})

    return ExactResult("no_feasible", True, None, None, lower_bound, None, upper_area, containers_checked, placements_tested, time.perf_counter() - started, False, {}, {**declared_domain, "containers_checked": containers_checked})
