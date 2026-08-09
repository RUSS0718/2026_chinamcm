"""Shared Question 2 objective, result, and search utilities."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
import json
import math
import random

from ..Q1.p1_p2 import PackedLayout
from .._internal.audit import audit_layout
from .._internal.evaluator import evaluate
from .._internal.parser import Instance


DEAD_SPACE_RATIO = 0.15


def square_side(instance: Instance, dead_space_ratio: float = DEAD_SPACE_RATIO) -> float:
    if dead_space_ratio < 0:
        raise ValueError("dead_space_ratio must be non-negative")
    module_area = sum(block.width * block.height for block in instance.blocks.values())
    return math.sqrt(module_area * (1.0 + dead_space_ratio))


def fixed_outline_shelf_layout(instance: Instance, side: float) -> dict[str, tuple[float, float, int]] | None:
    """Construct a deterministic legal shelf layout when this heuristic can fit one."""
    shelves: list[list[float]] = []
    placement: dict[str, tuple[float, float, int]] = {}
    ordered = sorted(
        instance.blocks.values(),
        key=lambda block: (min(block.width, block.height), block.width * block.height, block.name),
        reverse=True,
    )
    for block in ordered:
        choices = []
        for rotation, (width, height) in (
            (0, (block.width, block.height)),
            (90, (block.height, block.width)),
        ):
            for index, (_y, shelf_height, used_width) in enumerate(shelves):
                if height <= shelf_height and used_width + width <= side:
                    choices.append((0, side - used_width - width, shelf_height - height, rotation, index, width, height))
            next_y = sum(shelf[1] for shelf in shelves)
            if width <= side and next_y + height <= side:
                choices.append((1, side - width, 0.0, rotation, len(shelves), width, height))
        if not choices:
            return None
        new_shelf, _remaining, _height_gap, rotation, index, width, height = min(choices)
        if new_shelf:
            y = sum(shelf[1] for shelf in shelves)
            x = 0.0
            shelves.append([y, height, width])
        else:
            y, _shelf_height, x = shelves[index]
            shelves[index][2] += width
        placement[block.name] = (x, y, rotation)
    return placement


def shelf_layout_with_order(
    instance: Instance,
    side: float,
    preferred_order: list[str] | tuple[str, ...] | None = None,
) -> dict[str, tuple[float, float, int]] | None:
    """Re-encode the same legal shelf rows with a different within-row order.

    The row membership, rotation and row heights come from the deterministic
    shelf constructor.  Reordering is therefore a controlled initialization
    change: it cannot change the set of rows or make the initial placement
    illegal.
    """
    placement = fixed_outline_shelf_layout(instance, side)
    if placement is None:
        return None
    rows: dict[float, list[str]] = {}
    for name, (_x, y, _rotation) in placement.items():
        rows.setdefault(y, []).append(name)
    rank = None
    if preferred_order is not None:
        rank = {name: position for position, name in enumerate(preferred_order)}
    reordered: dict[str, tuple[float, float, int]] = {}
    for y in sorted(rows):
        names = rows[y]
        if rank is None:
            names = sorted(names, key=lambda name: (placement[name][0], name))
        else:
            names = sorted(names, key=lambda name: (rank.get(name, len(rank)), name))
        x = 0.0
        for name in names:
            _old_x, _old_y, rotation = placement[name]
            block = instance.blocks[name]
            width = block.width if rotation % 180 == 0 else block.height
            height = block.height if rotation % 180 == 0 else block.width
            reordered[name] = (x, y, rotation)
            x += width
            if height > 0 and y + height > side + 1e-9:
                return None
    return reordered


def layout_signature(layout: dict[str, tuple[float, float, int]]) -> str:
    """Hash row membership, vertical placement and rotations for audit traces."""
    payload = [
        [name, round(float(y), 12), int(rotation)]
        for name, (_x, y, rotation) in sorted(layout.items())
    ]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Q2SearchConfig:
    candidate: str = "Q2-BT"
    adaptive_constraints: bool = True
    hypergraph_init: bool = False
    sa_schedule: str = "fast"
    classic_final_temperature_ratio: float = 1e-3
    initialization_mode: str = "shelf"
    max_evaluations: int = 100_000
    time_limit: float = 60.0
    restarts: int = 4
    dead_space_ratio: float = DEAD_SPACE_RATIO
    initial_acceptance: float = 0.9
    fast_sa_c: float = 100.0
    fast_sa_k: int = 7
    calibration_samples: int | None = None

    def as_dict(self) -> dict:
        return {
            "candidate": self.candidate,
            "adaptive_constraints": self.adaptive_constraints,
            "hypergraph_init": self.hypergraph_init,
            "sa_schedule": self.sa_schedule,
            "classic_final_temperature_ratio": self.classic_final_temperature_ratio,
            "initialization_mode": self.initialization_mode,
            "max_evaluations": self.max_evaluations,
            "time_limit": self.time_limit,
            "restarts": self.restarts,
            "dead_space_ratio": self.dead_space_ratio,
            "coordinate_tolerance": 0.0,
            "initial_acceptance": self.initial_acceptance,
            "fast_sa_c": self.fast_sa_c,
            "fast_sa_k": self.fast_sa_k,
            "calibration_samples": self.calibration_samples,
        }


@dataclass(frozen=True)
class Q2Layout:
    packed: PackedLayout
    legal: bool
    hpwl: float
    overflow: float
    normalized_overflow: float
    formal_metrics: dict

    @property
    def layout(self) -> dict[str, tuple[float, float, int]]:
        return self.packed.layout

    @property
    def rank(self) -> tuple[float, ...]:
        if self.legal:
            return (0.0, self.hpwl)
        return (1.0, self.normalized_overflow, self.hpwl)


@dataclass
class SearchResult:
    status: str
    best: Q2Layout | None
    audit_metrics: dict = field(default_factory=dict)
    evaluations: int = 0
    proposals: int = 0
    accepted: int = 0
    restarts_completed: int = 0
    first_feasible_evaluation: int | None = None
    first_feasible_time: float | None = None
    runtime: float = 0.0
    error: str | None = None
    restart_initial_hpwl: list[float] = field(default_factory=list)
    restart_initial_legal: list[bool] = field(default_factory=list)
    restart_initial_signatures: list[str] = field(default_factory=list)
    restart_init_seeds: list[int] = field(default_factory=list)
    restart_search_seeds: list[int] = field(default_factory=list)
    # Kept only for Q3 continuous-compression warm starts.  It is intentionally
    # not serialized by the Q2 CLI, whose public layout artifact remains stable.
    best_state: object | None = None
    # Solver incumbent (accepted-state search) best-so-far at fixed points of one trajectory.
    checkpoint_evaluations: dict[int, int] = field(default_factory=dict)
    checkpoint_best_hpwl: dict[int, float | None] = field(default_factory=dict)

    @property
    def formal_metrics(self) -> dict:
        return self.best.formal_metrics if self.best is not None else {}


def validate_config(config: Q2SearchConfig) -> None:
    if config.max_evaluations <= 0 or config.restarts <= 0:
        raise ValueError("max_evaluations and restarts must be positive")
    if config.time_limit < 0:
        raise ValueError("time_limit must be non-negative")
    if not 0 < config.initial_acceptance < 1:
        raise ValueError("initial_acceptance must be between zero and one")
    if config.fast_sa_c <= 0 or config.fast_sa_k < 1:
        raise ValueError("Fast-SA parameters must be positive")
    if config.sa_schedule not in {"classic", "fast"}:
        raise ValueError("sa_schedule must be classic or fast")
    if not 0 < config.classic_final_temperature_ratio < 1:
        raise ValueError("classic_final_temperature_ratio must be between zero and one")
    if config.initialization_mode not in {"shelf", "random"}:
        raise ValueError("initialization_mode must be shelf or random")


def checkpoint_targets(max_evaluations: int) -> dict[int, int]:
    """Return fixed trajectory checkpoints (ceil percentage of the budget)."""
    if max_evaluations <= 0:
        raise ValueError("max_evaluations must be positive")
    return {percentage: max(1, (max_evaluations * percentage + 99) // 100) for percentage in (25, 50, 75, 100)}


def record_checkpoint(
    targets: dict[int, int],
    evaluations: int,
    best_feasible: Q2Layout | None,
    checkpoint_evaluations: dict[int, int],
    checkpoint_best_hpwl: dict[int, float | None],
) -> None:
    """Record solver-incumbent best-so-far; calibration only estimates temperature."""
    for percentage, target in targets.items():
        if percentage not in checkpoint_evaluations and evaluations >= target:
            checkpoint_evaluations[percentage] = target
            checkpoint_best_hpwl[percentage] = best_feasible.hpwl if best_feasible is not None else None


def restart_evaluation_limits(max_evaluations: int, restarts: int) -> list[int]:
    """Return cumulative limits whose per-restart budgets sum exactly."""
    base, remainder = divmod(max_evaluations, restarts)
    limits: list[int] = []
    cumulative = 0
    for index in range(restarts):
        cumulative += base + (1 if index < remainder else 0)
        limits.append(cumulative)
    return limits


def assess(instance: Instance, packed: PackedLayout, side: float) -> Q2Layout:
    overflow_x = max(0.0, packed.width - side)
    overflow_y = max(0.0, packed.height - side)
    overflow = overflow_x + overflow_y
    centers = {}
    for name, (x, y, rotation) in packed.layout.items():
        block = instance.blocks[name]
        width, height = (block.width, block.height) if rotation % 180 == 0 else (block.height, block.width)
        centers[name] = (x + width / 2.0, y + height / 2.0)
    hpwl = 0.0
    for net in instance.nets:
        points = [centers[pin] if pin in centers else instance.terminals[pin] for pin in net.pins]
        if points:
            hpwl += max(x for x, _ in points) - min(x for x, _ in points)
            hpwl += max(y for _, y in points) - min(y for _, y in points)
    return Q2Layout(
        packed=packed,
        legal=overflow == 0.0,
        hpwl=hpwl,
        overflow=overflow,
        normalized_overflow=overflow / side if side else math.inf,
        formal_metrics={},
    )


def finalize(instance: Instance, best: Q2Layout | None, side: float) -> Q2Layout | None:
    if best is None:
        return None
    formal = evaluate(instance, best.layout, (0.0, 0.0, side, side)).as_dict()
    return replace(best, legal=bool(formal["legal"]), hpwl=float(formal["HPWL"]), formal_metrics=formal)


def audit_best(instance: Instance, best: Q2Layout | None, side: float) -> dict:
    if best is None:
        return {}
    return audit_layout(instance, best.layout, (0.0, 0.0, side, side))


def search_delta(current: Q2Layout, proposal: Q2Layout, penalty: float) -> float:
    # Feasibility is a hard lexicographic tier.  HPWL is consulted only after
    # both layouts satisfy the fixed square outline, preventing the optimizer
    # from trading a large boundary violation for a small HPWL improvement.
    if current.legal and proposal.legal:
        return (proposal.hpwl - current.hpwl) / max(current.hpwl, proposal.hpwl, 1.0)
    if current.legal and not proposal.legal:
        return 1.0 + proposal.normalized_overflow
    if not current.legal and proposal.legal:
        return -1.0 - current.normalized_overflow
    return penalty * (proposal.normalized_overflow - current.normalized_overflow)


def accept(current: Q2Layout, proposal: Q2Layout, temperature: float, penalty: float, rng: random.Random) -> bool:
    delta = search_delta(current, proposal, penalty)
    if delta <= 0:
        return True
    return temperature > 0 and rng.random() < math.exp(-delta / temperature)


def initial_temperature(avg_uphill: float, acceptance_probability: float) -> float:
    if avg_uphill <= 0:
        return 1.0
    return avg_uphill / max(-math.log(acceptance_probability), 1e-12)


def fast_temperature(iteration: int, t1: float, avg_delta: float, c: float, k: int) -> float:
    if iteration <= 1:
        return t1
    if iteration <= k:
        return t1 * avg_delta / max(iteration * c, 1e-12)
    return t1 * avg_delta / iteration


def classic_temperature(
    iteration: int,
    total_iterations: int,
    t1: float,
    final_ratio: float,
) -> float:
    """Geometric SA cooling over exactly one restart's remaining budget."""
    if total_iterations <= 1:
        return t1
    exponent = max(0, min(iteration - 1, total_iterations - 1)) / (total_iterations - 1)
    return t1 * (final_ratio**exponent)


def constraint_penalty(config: Q2SearchConfig, iteration: int, has_feasible: bool) -> float:
    if not config.adaptive_constraints:
        return 10.0
    if has_feasible:
        return 20.0
    return min(100.0, 5.0 * (1.0 + iteration / 1000.0))
