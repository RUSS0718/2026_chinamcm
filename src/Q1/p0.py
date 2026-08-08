"""Independent P0 baselines for Question 1 rectangle packing.

Q1-G is a deterministic bottom-left construction.  Q1-SP uses a genuine
sequence pair and simulated annealing; it intentionally does not reuse the
B*-Tree representation or decoder.
"""

from __future__ import annotations

import math
import random
import time

from .._internal.audit import audit_layout
from .._internal.evaluator import evaluate
from .._internal.parser import Block, Instance
from .p1_p2 import PackedLayout, Q1SearchConfig, SearchResult


def _size(block: Block, rotation: int) -> tuple[float, float]:
    return (block.width, block.height) if rotation == 0 else (block.height, block.width)


def _packed(layout: dict[str, tuple[float, float, int]], blocks: dict[str, Block]) -> PackedLayout:
    width = max((x + _size(blocks[name], rotation)[0] for name, (x, y, rotation) in layout.items()), default=0.0)
    height = max((y + _size(blocks[name], rotation)[1] for name, (x, y, rotation) in layout.items()), default=0.0)
    area = width * height
    aspect = max(width, height) / min(width, height) if min(width, height) else math.inf
    return PackedLayout(layout, width, height, area, aspect)


def bottom_left(instance: Instance, deadline: float | None = None) -> PackedLayout:
    """Place largest rectangles first at the lowest feasible corner."""
    layout: dict[str, tuple[float, float, int]] = {}
    ordered = sorted(instance.blocks.values(), key=lambda block: (-block.width * block.height, block.name))
    for block in ordered:
        if deadline is not None and time.perf_counter() >= deadline:
            raise TimeoutError("bottom-left time budget exhausted")
        x_candidates = {0.0}
        y_candidates = {0.0}
        for name, (x, y, rotation) in layout.items():
            width, height = _size(instance.blocks[name], rotation)
            x_candidates.add(x + width)
            y_candidates.add(y + height)
        choices: list[tuple[tuple[float, float, int], tuple[float, float, int]]] = []
        for rotation in (0, 90):
            width, height = _size(block, rotation)
            for y in sorted(y_candidates):
                for x in sorted(x_candidates):
                    if deadline is not None and time.perf_counter() >= deadline:
                        raise TimeoutError("bottom-left time budget exhausted")
                    overlaps = False
                    for name, (other_x, other_y, other_rotation) in layout.items():
                        other_w, other_h = _size(instance.blocks[name], other_rotation)
                        if x < other_x + other_w and other_x < x + width and y < other_y + other_h and other_y < y + height:
                            overlaps = True
                            break
                    if not overlaps:
                        choices.append(((y, x, rotation), (x, y, rotation)))
        if not choices:
            raise RuntimeError(f"bottom-left failed to place {block.name}")
        layout[block.name] = min(choices)[1]
    return _packed(layout, instance.blocks)


def decode_sequence_pair(
    positive: tuple[str, ...], negative: tuple[str, ...], rotations: dict[str, int], blocks: dict[str, Block]
) -> PackedLayout:
    """Decode a sequence pair through horizontal and vertical DAG constraints."""
    if set(positive) != set(blocks) or set(negative) != set(blocks) or len(positive) != len(blocks) or len(negative) != len(blocks):
        raise ValueError("sequence pair must contain every block exactly once")
    negative_position = {name: index for index, name in enumerate(negative)}
    horizontal: dict[str, list[tuple[str, float]]] = {name: [] for name in positive}
    vertical: dict[str, list[tuple[str, float]]] = {name: [] for name in positive}
    for left_index, first in enumerate(positive):
        for second in positive[left_index + 1:]:
            if negative_position[first] < negative_position[second]:
                horizontal[first].append((second, _size(blocks[first], rotations[first])[0]))
            else:
                vertical[second].append((first, _size(blocks[second], rotations[second])[1]))

    def longest_paths(edges: dict[str, list[tuple[str, float]]], order: tuple[str, ...]) -> dict[str, float]:
        coordinates = {name: 0.0 for name in order}
        for name in order:
            for successor, offset in edges[name]:
                coordinates[successor] = max(coordinates[successor], coordinates[name] + offset)
        return coordinates

    x = longest_paths(horizontal, positive)
    y = longest_paths(vertical, tuple(reversed(positive)))
    return _packed({name: (x[name], y[name], rotations[name]) for name in positive}, blocks)


def _mutate_pair(
    positive: tuple[str, ...], negative: tuple[str, ...], rotations: dict[str, int], rng: random.Random
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, int]]:
    next_positive, next_negative, next_rotations = list(positive), list(negative), dict(rotations)
    operation = rng.randrange(3)
    if operation == 0:
        target = next_positive
        first, second = rng.sample(range(len(target)), 2)
        target[first], target[second] = target[second], target[first]
    elif operation == 1:
        first, second = rng.sample(range(len(next_negative)), 2)
        next_negative[first], next_negative[second] = next_negative[second], next_negative[first]
    else:
        name = rng.choice(next_positive)
        next_rotations[name] ^= 90
    return tuple(next_positive), tuple(next_negative), next_rotations


def sequence_pair_sa(instance: Instance, config: Q1SearchConfig, seed: int) -> SearchResult:
    if not instance.blocks:
        return SearchResult("no_feasible", None, error="no HardBlock records")
    if config.max_evaluations <= 0 or config.restarts <= 0 or config.time_limit < 0:
        raise ValueError("max_evaluations and restarts must be positive; time_limit must be non-negative")
    start = time.perf_counter()
    rng = random.Random(seed)
    names = tuple(instance.blocks)
    best: PackedLayout | None = None
    evaluations = proposals = accepted = restarts_completed = 0
    timed_out = False
    try:
        for _ in range(config.restarts):
            if evaluations >= config.max_evaluations or time.perf_counter() - start >= config.time_limit:
                timed_out = evaluations < config.max_evaluations
                break
            positive = list(names)
            negative = list(names)
            rng.shuffle(positive)
            rng.shuffle(negative)
            rotations = {name: rng.choice((0, 90)) for name in names}
            current = decode_sequence_pair(tuple(positive), tuple(negative), rotations, instance.blocks)
            evaluations += 1
            if best is None or current.rank < best.rank:
                best = current
            temperature = max(current.area, 1.0) * 0.1
            while evaluations < config.max_evaluations:
                if time.perf_counter() - start >= config.time_limit:
                    timed_out = True
                    break
                trial_positive, trial_negative, trial_rotations = _mutate_pair(tuple(positive), tuple(negative), rotations, rng)
                proposal = decode_sequence_pair(trial_positive, trial_negative, trial_rotations, instance.blocks)
                evaluations += 1
                proposals += 1
                delta = proposal.area - current.area
                if proposal.area == current.area:
                    delta = proposal.aspect_ratio - current.aspect_ratio
                if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 1e-12)):
                    positive, negative, rotations, current = list(trial_positive), list(trial_negative), trial_rotations, proposal
                    accepted += 1
                if proposal.rank < best.rank:
                    best = proposal
                temperature *= 0.95
            restarts_completed += 1
            if timed_out:
                break
    except Exception as exc:
        runtime = time.perf_counter() - start
        return SearchResult("crash", best, evaluations=evaluations, proposals=proposals, accepted=accepted, restarts_completed=restarts_completed, runtime=runtime, error=f"{type(exc).__name__}: {exc}")
    runtime = time.perf_counter() - start
    status = "timeout" if timed_out else "success"
    formal = evaluate(instance, best.layout).as_dict() if best is not None else {}
    audit = audit_layout(instance, best.layout) if best is not None else {}
    return SearchResult(status, best, formal, audit, evaluations, proposals, accepted, 0, restarts_completed, runtime)


def search_p0(instance: Instance, config: Q1SearchConfig, seed: int) -> SearchResult:
    if config.candidate == "Q1-G":
        start = time.perf_counter()
        if config.max_evaluations <= 0 or config.restarts <= 0 or config.time_limit < 0:
            raise ValueError("max_evaluations and restarts must be positive; time_limit must be non-negative")
        try:
            best = bottom_left(instance, start + config.time_limit)
            formal = evaluate(instance, best.layout).as_dict()
            audit = audit_layout(instance, best.layout)
            return SearchResult("success", best, formal, audit, evaluations=1, restarts_completed=1, runtime=time.perf_counter() - start)
        except TimeoutError as exc:
            return SearchResult("timeout", None, runtime=time.perf_counter() - start, error=str(exc))
        except Exception as exc:
            return SearchResult("crash", None, runtime=time.perf_counter() - start, error=f"{type(exc).__name__}: {exc}")
    if config.candidate == "Q1-SP":
        return sequence_pair_sa(instance, config, seed)
    raise ValueError(f"unsupported P0 candidate: {config.candidate}")
