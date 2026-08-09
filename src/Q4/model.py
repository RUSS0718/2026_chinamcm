from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Mapping

from .geometry import DEFAULT_MODULES, GEOMETRY_THICKNESSES, Polygon, modules_for_geometry, polygon_area, rotate_normalized


@dataclass(frozen=True)
class Q4Block:
    name: str
    polygon: Polygon


@dataclass(frozen=True)
class Q4Instance:
    blocks: dict[str, Q4Block]
    terminals: dict = field(default_factory=dict)
    nets: tuple = ()

    @classmethod
    def default(cls, geometry: str = "G0") -> "Q4Instance":
        return cls({name: Q4Block(name, polygon) for name, polygon in modules_for_geometry(geometry).items()})

    @property
    def geometry(self) -> str:
        for geometry, thickness in GEOMETRY_THICKNESSES.items():
            if self.blocks.get("b1", Q4Block("b1", DEFAULT_MODULES["b1"])).polygon == modules_for_geometry(geometry)["b1"]:
                return geometry
        return "custom"

    @property
    def module_area(self) -> int:
        return sum(polygon_area(block.polygon) for block in self.blocks.values())


@dataclass(frozen=True)
class Q4Evaluation:
    legal: bool
    width: int | float
    height: int | float
    area: int | float
    module_area: int | float
    deadspace: int | float
    dead_space_ratio: float
    aspect_ratio: float
    rho: float
    polygons: dict[str, Polygon]
    layout: dict[str, tuple[int | float, int | float, int]]

    def as_dict(self) -> dict:
        return {
            "legal": self.legal,
            "W": self.width,
            "H": self.height,
            "area": self.area,
            "module_area": self.module_area,
            "deadspace": self.deadspace,
            "dead_space_ratio": self.dead_space_ratio,
            "aspect_ratio": self.aspect_ratio,
            "rho": self.rho,
            "HPWL": 0,
            "square_side": max(self.width, self.height),
            "layout": {
                name: {"x": x, "y": y, "rotation": rotation}
                for name, (x, y, rotation) in sorted(self.layout.items())
            },
        }


def _intersection_area(first: Polygon, second: Polygon) -> Fraction:
    ys = sorted({y for polygon in (first, second) for _, y in polygon})
    total = Fraction(0)

    def intervals(polygon: Polygon, y: Fraction) -> list[tuple[Fraction, Fraction]]:
        crossings: list[Fraction] = []
        for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
            if y1 == y2 or not min(y1, y2) < y < max(y1, y2):
                continue
            x = Fraction(x1) + Fraction(y - y1, y2 - y1) * (x2 - x1)
            crossings.append(x)
        crossings.sort()
        return list(zip(crossings[::2], crossings[1::2]))

    for low, high in zip(ys, ys[1:]):
        if low == high:
            continue
        y = Fraction(low + high, 2)
        for left_a, right_a in intervals(first, y):
            for left_b, right_b in intervals(second, y):
                total += max(Fraction(0), min(right_a, right_b) - max(left_a, left_b)) * (high - low)
    return total


def evaluate_layout(
    instance: Q4Instance,
    layout: Mapping[str, tuple[int | float, int | float, int]],
    outline: tuple[int | float, int | float] | None = None,
) -> Q4Evaluation:
    if set(layout) != set(instance.blocks):
        raise ValueError("layout names must match instance blocks")
    polygons: dict[str, Polygon] = {}
    for name, block in instance.blocks.items():
        x, y, rotation = layout[name]
        local = rotate_normalized(block.polygon, rotation)
        polygons[name] = tuple((x + px, y + py) for px, py in local)

    names = tuple(polygons)
    legal = True
    for index, first in enumerate(names):
        for second in names[index + 1 :]:
            if _intersection_area(polygons[first], polygons[second]) > 0:
                legal = False
    min_x = min(x for polygon in polygons.values() for x, _ in polygon)
    min_y = min(y for polygon in polygons.values() for _, y in polygon)
    max_x = max(x for polygon in polygons.values() for x, _ in polygon)
    max_y = max(y for polygon in polygons.values() for _, y in polygon)
    if outline is None:
        width, height = max_x - min_x, max_y - min_y
    else:
        width, height = outline
        legal = legal and min_x >= 0 and min_y >= 0 and max_x <= width and max_y <= height
    area = width * height
    module_area = instance.module_area
    deadspace = area - module_area
    return Q4Evaluation(
        legal,
        width,
        height,
        area,
        module_area,
        deadspace,
        deadspace / module_area if module_area else 0,
        max(width, height) / min(width, height) if min(width, height) else float("inf"),
        deadspace / area if area else 0,
        polygons,
        dict(layout),
    )


def formal_audit_match(
    instance: Q4Instance,
    layout: Mapping[str, tuple[int | float, int | float, int]],
    outline: tuple[int | float, int | float] | None = None,
) -> bool:
    from src._internal.audit import audit_layout

    formal = evaluate_layout(instance, layout, outline).as_dict()
    audited = audit_layout(instance, dict(layout), (0, 0, *outline) if outline else None)
    required = {"legal", "W", "H", "area", "module_area", "dead_space_ratio", "aspect_ratio", "rho", "deadspace", "HPWL", "square_side"}
    if set(audited) != required or any(formal.get(key) != audited[key] for key in required):
        return False
    expected_layout = {
        name: {"x": x, "y": y, "rotation": rotation}
        for name, (x, y, rotation) in sorted(layout.items())
    }
    return formal["layout"] == expected_layout and formal["legal"] == bool(audited["legal"])
