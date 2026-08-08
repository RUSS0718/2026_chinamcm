from __future__ import annotations


Point = tuple[int, int]
Polygon = tuple[Point, ...]

DEFAULT_MODULES: dict[str, Polygon] = {
    "b1": ((1, 0), (3, 0), (3, 2), (4, 2), (4, 4), (0, 4), (0, 2), (1, 2)),
    "b2": ((0, 0), (2, 0), (2, 2), (1, 2), (1, 4), (0, 4)),
    "b3": ((0, 0), (2, 0), (2, 1), (0, 1)),
    "b4": ((0, 0), (1, 0), (1, 4), (0, 4)),
}


def polygon_area(polygon: Polygon) -> int:
    return abs(
        sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1])
        )
    ) // 2


def rotate_normalized(polygon: Polygon, rotation: int) -> Polygon:
    if rotation not in (0, 90, 180, 270):
        raise ValueError("rotation must be one of 0, 90, 180, 270")
    if rotation == 0:
        rotated = polygon
    elif rotation == 90:
        rotated = tuple((-y, x) for x, y in polygon)
    elif rotation == 180:
        rotated = tuple((-x, -y) for x, y in polygon)
    else:
        rotated = tuple((y, -x) for x, y in polygon)
    min_x = min(x for x, _ in rotated)
    min_y = min(y for _, y in rotated)
    return tuple((x - min_x, y - min_y) for x, y in rotated)


def bbox(polygon: Polygon) -> tuple[int, int]:
    return (
        max(x for x, _ in polygon) - min(x for x, _ in polygon),
        max(y for _, y in polygon) - min(y for _, y in polygon),
    )
