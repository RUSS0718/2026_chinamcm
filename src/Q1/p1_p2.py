"""Question 1 P1/P2 B*-Tree packing and Fast-SA search.

The optimizer proposes rectangle layouts; the shared evaluator and the
independent audit remain the authority for the final metrics.  This module
contains no file-system or CLI policy so it can be tested independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import random
import time
from typing import Iterable

from .._internal.audit import audit_layout
from .._internal.evaluator import evaluate
from .._internal.parser import Block, Instance


def _rotated_size(block: Block, rotation: int) -> tuple[float, float]:
    if rotation % 180 == 0:
        return block.width, block.height
    return block.height, block.width


class Contour:
    """Piecewise-constant skyline used by the B*-Tree decoder."""

    def __init__(self) -> None:
        # The right edge is an open-ended zero-height segment.  All module
        # coordinates are non-negative, so no negative sentinel is needed.
        self.segments: list[list[float]] = [[0.0, math.inf, 0.0]]

    def _split(self, x: float) -> None:
        for i, (left, right, height) in enumerate(self.segments):
            if x <= left or x >= right:
                continue
            self.segments[i:i + 1] = [[left, x, height], [x, right, height]]
            return

    def query(self, left: float, right: float) -> float:
        if right <= left:
            return 0.0
        return max(
            (height for start, end, height in self.segments if end > left and start < right),
            default=0.0,
        )

    def raise_interval(self, left: float, right: float, height: float) -> None:
        if right <= left:
            return
        self._split(left)
        self._split(right)
        for segment in self.segments:
            if segment[1] > left and segment[0] < right:
                segment[2] = max(segment[2], height)
        merged: list[list[float]] = []
        for segment in self.segments:
            if merged and merged[-1][2] == segment[2] and merged[-1][1] == segment[0]:
                merged[-1][1] = segment[1]
            else:
                merged.append(segment)
        self.segments = merged


@dataclass
class BTreeState:
    """A mutable ordered binary tree whose nodes carry block labels."""

    labels: list[str]
    left: list[int | None]
    right: list[int | None]
    parent: list[int | None]
    rotations: list[int]
    root: int | None = 0

    @classmethod
    def complete(cls, names: Iterable[str], rng: random.Random) -> "BTreeState":
        labels = list(names)
        rng.shuffle(labels)
        n = len(labels)
        left = [2 * i + 1 if 2 * i + 1 < n else None for i in range(n)]
        right = [2 * i + 2 if 2 * i + 2 < n else None for i in range(n)]
        parent = [((i - 1) // 2 if i else None) for i in range(n)]
        rotations = [rng.choice((0, 90)) for _ in range(n)]
        state = cls(labels, left, right, parent, rotations)
        state.validate()
        return state

    def clone(self) -> "BTreeState":
        return BTreeState(
            self.labels.copy(),
            self.left.copy(),
            self.right.copy(),
            self.parent.copy(),
            self.rotations.copy(),
            self.root,
        )

    def validate(self) -> None:
        n = len(self.labels)
        if not (len(self.left) == len(self.right) == len(self.parent) == len(self.rotations) == n):
            raise ValueError("B*-Tree arrays have inconsistent lengths")
        if n == 0:
            if self.root is not None:
                raise ValueError("empty B*-Tree must have no root")
            return
        if self.root is None or not 0 <= self.root < n or self.parent[self.root] is not None:
            raise ValueError("B*-Tree root is invalid")
        seen: set[int] = set()
        stack = [self.root]
        while stack:
            node = stack.pop()
            if node in seen:
                raise ValueError("B*-Tree contains a cycle")
            seen.add(node)
            for child in (self.left[node], self.right[node]):
                if child is not None:
                    if not 0 <= child < n or self.parent[child] != node:
                        raise ValueError("B*-Tree parent/child relation is inconsistent")
                    stack.append(child)
        if len(seen) != n:
            raise ValueError("B*-Tree does not contain every node")
        if len(set(self.labels)) != n:
            raise ValueError("B*-Tree labels are not unique")
        if any(rotation not in (0, 90) for rotation in self.rotations):
            raise ValueError("Q1 rotations must be 0 or 90 degrees")

    def node_for_label(self, label: str) -> int:
        try:
            return self.labels.index(label)
        except ValueError as exc:
            raise KeyError(label) from exc

    def signature(self) -> tuple:
        return (
            self.root,
            tuple(self.labels),
            tuple(self.left),
            tuple(self.right),
            tuple(self.rotations),
        )

    def rotate_random(self, rng: random.Random) -> None:
        self.rotations[rng.randrange(len(self.rotations))] ^= 90

    def swap_random(self, rng: random.Random) -> None:
        if len(self.labels) < 2:
            return
        first, second = rng.sample(range(len(self.labels)), 2)
        self.labels[first], self.labels[second] = self.labels[second], self.labels[first]
        self.rotations[first], self.rotations[second] = self.rotations[second], self.rotations[first]

    def _attach_subtree(self, parent: int, child: int, side: str) -> None:
        if side == "left":
            if self.left[parent] is not None:
                raise ValueError("left child slot is occupied")
            self.left[parent] = child
        else:
            if self.right[parent] is not None:
                raise ValueError("right child slot is occupied")
            self.right[parent] = child
        self.parent[child] = parent

    def _find_open_slot(self, root: int, prefer_right: bool = True) -> tuple[int, str]:
        order = ("right", "left") if prefer_right else ("left", "right")
        stack = [root]
        while stack:
            node = stack.pop()
            for side in order:
                if (self.right[node] if side == "right" else self.left[node]) is None:
                    return node, side
            for child in (self.right[node], self.left[node]):
                if child is not None:
                    stack.append(child)
        raise ValueError("subtree has no open insertion slot")

    def move_node(self, source: int, target: int, side: str) -> None:
        """Move a node while preserving every other node and tree invariant."""
        n = len(self.labels)
        if n < 2 or source == target or side not in ("left", "right"):
            return
        if not 0 <= source < n or not 0 <= target < n:
            raise IndexError("B*-Tree node out of range")

        source_parent = self.parent[source]
        source_left, source_right = self.left[source], self.right[source]

        # Detach source.  If it has two children, promote the left subtree and
        # attach the right subtree to the first available slot in that subtree.
        replacement = source_left if source_left is not None else source_right
        if source_left is not None and source_right is not None:
            attach_node, attach_side = self._find_open_slot(source_left, prefer_right=True)
            self._attach_subtree(attach_node, source_right, attach_side)
        if source_parent is None:
            self.root = replacement
        else:
            if self.left[source_parent] == source:
                self.left[source_parent] = replacement
            elif self.right[source_parent] == source:
                self.right[source_parent] = replacement
            else:
                raise ValueError("source is not attached to its parent")
        if replacement is not None:
            self.parent[replacement] = source_parent
        self.left[source] = None
        self.right[source] = None
        self.parent[source] = None

        # The source is now a singleton node.  If the selected target slot is
        # occupied, the displaced subtree becomes the corresponding child of
        # source.  This is the standard B*-Tree move operation.
        displaced = self.left[target] if side == "left" else self.right[target]
        if side == "left":
            self.left[target] = source
            self.left[source] = displaced
        else:
            self.right[target] = source
            self.right[source] = displaced
        self.parent[source] = target
        if displaced is not None:
            self.parent[displaced] = source
        self.validate()

    def move_random(self, rng: random.Random) -> None:
        if len(self.labels) < 2:
            return
        source = rng.randrange(len(self.labels))
        target = rng.randrange(len(self.labels) - 1)
        if target >= source:
            target += 1
        self.move_node(source, target, rng.choice(("left", "right")))


@dataclass(frozen=True)
class PackedLayout:
    layout: dict[str, tuple[float, float, int]]
    width: float
    height: float
    area: float
    aspect_ratio: float

    @property
    def rank(self) -> tuple[float, float]:
        return self.area, self.aspect_ratio


def pack_btree(state: BTreeState, blocks: dict[str, Block]) -> PackedLayout:
    """Decode a B*-Tree with a skyline contour."""
    state.validate()
    if state.root is None:
        return PackedLayout({}, 0.0, 0.0, 0.0, math.inf)
    contour = Contour()
    layout: dict[str, tuple[float, float, int]] = {}
    extents: dict[int, tuple[float, float, float, float]] = {}
    order = [state.root]
    while order:
        node = order.pop()
        label = state.labels[node]
        block = blocks[label]
        rotation = state.rotations[node]
        width, height = _rotated_size(block, rotation)
        parent = state.parent[node]
        if parent is None:
            x = 0.0
        elif state.left[parent] == node:
            parent_x, _, parent_w, _ = extents[parent]
            x = parent_x + parent_w
        else:
            parent_x, _, _, _ = extents[parent]
            x = parent_x
        y = contour.query(x, x + width)
        contour.raise_interval(x, x + width, y + height)
        layout[label] = (x, y, rotation)
        extents[node] = (x, y, width, height)
        # Preorder traversal gives each parent a completed contour before its
        # children are placed.  Push right first because the stack is LIFO.
        if state.right[node] is not None:
            order.append(state.right[node])
        if state.left[node] is not None:
            order.append(state.left[node])
    right = []
    top = []
    for label, (x, y, rotation) in layout.items():
        w, h = _rotated_size(blocks[label], rotation)
        right.append(x + w)
        top.append(y + h)
    width, height = max(right, default=0.0), max(top, default=0.0)
    area = width * height
    aspect = max(width, height) / min(width, height) if min(width, height) else math.inf
    return PackedLayout(layout, width, height, area, aspect)


def layout_signature(layout: dict[str, tuple[float, float, int]], blocks: dict[str, Block]) -> tuple:
    """Canonicalize a layout and its 90-degree whole-chip rotation."""
    if not layout:
        return tuple()

    def one(items: dict[str, tuple[float, float, int]], width: float, height: float) -> tuple:
        return tuple(
            (name, items[name][0], items[name][1], items[name][2])
            for name in sorted(items)
        )

    max_x = max(x + _rotated_size(blocks[name], rotation)[0] for name, (x, y, rotation) in layout.items())
    max_y = max(y + _rotated_size(blocks[name], rotation)[1] for name, (x, y, rotation) in layout.items())
    rotated: dict[str, tuple[float, float, int]] = {}
    for name, (x, y, rotation) in layout.items():
        _, height = _rotated_size(blocks[name], rotation)
        rotated[name] = (max_y - (y + height), x, (rotation + 90) % 180)
    return min(one(layout, max_x, max_y), one(rotated, max_y, max_x))


@dataclass(frozen=True)
class Q1SearchConfig:
    candidate: str = "Q1-BT"
    directed_moves: bool = False
    state_dedup: bool = False
    max_evaluations: int = 100_000
    time_limit: float = 60.0
    restarts: int = 4
    initial_acceptance: float = 0.9
    fast_sa_c: float = 100.0
    fast_sa_k: int = 7
    calibration_samples: int | None = None

    def as_dict(self) -> dict:
        return {
            "candidate": self.candidate,
            "directed_moves": self.directed_moves,
            "state_dedup": self.state_dedup,
            "max_evaluations": self.max_evaluations,
            "time_limit": self.time_limit,
            "restarts": self.restarts,
            "initial_acceptance": self.initial_acceptance,
            "fast_sa_c": self.fast_sa_c,
            "fast_sa_k": self.fast_sa_k,
            "calibration_samples": self.calibration_samples,
        }


@dataclass
class SearchResult:
    status: str
    best: PackedLayout | None
    formal_metrics: dict = field(default_factory=dict)
    audit_metrics: dict = field(default_factory=dict)
    evaluations: int = 0
    proposals: int = 0
    accepted: int = 0
    duplicate_rejections: int = 0
    restarts_completed: int = 0
    runtime: float = 0.0
    error: str | None = None

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "formal_metrics": self.formal_metrics,
            "audit_metrics": self.audit_metrics,
            "evaluations": self.evaluations,
            "proposals": self.proposals,
            "accepted": self.accepted,
            "duplicate_rejections": self.duplicate_rejections,
            "restarts_completed": self.restarts_completed,
            "runtime": self.runtime,
            "error": self.error,
        }


def _normal_cost_delta(current: PackedLayout, proposal: PackedLayout, area_norm: float) -> float:
    if proposal.area == current.area:
        return proposal.aspect_ratio - current.aspect_ratio
    return (proposal.area - current.area) / max(area_norm, 1.0)


def _accept(current: PackedLayout, proposal: PackedLayout, temperature: float, area_norm: float, rng: random.Random) -> bool:
    delta = _normal_cost_delta(current, proposal, area_norm)
    if delta <= 0:
        return True
    if temperature <= 0:
        return False
    return rng.random() < math.exp(-delta / temperature)


def _mutate(
    state: BTreeState,
    rng: random.Random,
    blocks: dict[str, Block],
    current: PackedLayout,
    directed: bool,
) -> None:
    if directed and len(state.labels) > 1:
        wide = current.width > current.height * 1.02
        tall = current.height > current.width * 1.02
        if wide or tall:
            boundary: list[str] = []
            for label, (x, y, rotation) in current.layout.items():
                w, h = _rotated_size(blocks[label], rotation)
                if wide and x + w == current.width:
                    boundary.append(label)
                elif tall and y + h == current.height:
                    boundary.append(label)
            if boundary:
                label = rng.choice(boundary)
                node = state.node_for_label(label)
                block = blocks[label]
                width, height = _rotated_size(block, state.rotations[node])
                if (wide and width > height) or (tall and height > width):
                    state.rotations[node] ^= 90
                    return
                target = rng.randrange(len(state.labels) - 1)
                if target >= node:
                    target += 1
                state.move_node(node, target, "right" if wide else "left")
                return
    operation = rng.randrange(3)
    if operation == 0:
        state.rotate_random(rng)
    elif operation == 1:
        state.move_random(rng)
    else:
        state.swap_random(rng)


def _temperature(iteration: int, t1: float, avg_delta: float, c: float, k: int) -> float:
    if iteration <= 1:
        return t1
    if iteration <= k:
        return t1 * avg_delta / max(iteration * c, 1e-12)
    return t1 * avg_delta / iteration


def _initial_temperature(avg_uphill: float, acceptance: float) -> float:
    if avg_uphill <= 0:
        return 1.0
    return avg_uphill / max(-math.log(acceptance), 1e-12)


def search_q1(instance: Instance, config: Q1SearchConfig, seed: int) -> SearchResult:
    """Run a deterministic, budgeted multi-start Q1 search."""
    if not instance.blocks:
        return SearchResult("no_feasible", None, error="no HardBlock records")
    if config.candidate not in {"Q1-BT", "Q1-BT-D"}:
        raise ValueError(f"unsupported Q1 candidate: {config.candidate}")
    if config.max_evaluations <= 0 or config.restarts <= 0:
        raise ValueError("max_evaluations and restarts must be positive")
    start = time.perf_counter()
    rng = random.Random(seed)
    names = tuple(instance.blocks)
    best: PackedLayout | None = None
    evaluations = proposals = accepted = duplicate_rejections = restarts_completed = 0
    timed_out = False
    error: str | None = None

    try:
        for _restart in range(config.restarts):
            if evaluations >= config.max_evaluations:
                break
            if time.perf_counter() - start >= config.time_limit:
                timed_out = True
                break
            state = BTreeState.complete(names, random.Random(rng.randrange(2**63)))
            current = pack_btree(state, instance.blocks)
            evaluations += 1
            if best is None or current.rank < best.rank:
                best = current

            calibration_target = config.calibration_samples or len(names)
            uphill: list[float] = []
            sample_current = current
            for _ in range(calibration_target):
                if evaluations >= config.max_evaluations or time.perf_counter() - start >= config.time_limit:
                    timed_out = time.perf_counter() - start >= config.time_limit
                    break
                trial = state.clone()
                _mutate(trial, rng, instance.blocks, sample_current, False)
                proposal = pack_btree(trial, instance.blocks)
                evaluations += 1
                delta = _normal_cost_delta(sample_current, proposal, max(sample_current.area, 1.0))
                if delta > 0:
                    uphill.append(delta)
                sample_current = proposal
            if timed_out or evaluations >= config.max_evaluations:
                restarts_completed += 1
                continue
            avg_uphill = sum(uphill) / len(uphill) if uphill else 0.01
            t1 = _initial_temperature(avg_uphill, config.initial_acceptance)
            seen: set[tuple] = {layout_signature(current.layout, instance.blocks)} if config.state_dedup else set()
            iteration = 0
            while evaluations < config.max_evaluations:
                if time.perf_counter() - start >= config.time_limit:
                    timed_out = True
                    break
                iteration += 1
                proposal_state = state.clone()
                _mutate(proposal_state, rng, instance.blocks, current, config.directed_moves)
                proposal = pack_btree(proposal_state, instance.blocks)
                evaluations += 1
                proposals += 1
                signature = layout_signature(proposal.layout, instance.blocks)
                if config.state_dedup and signature in seen:
                    duplicate_rejections += 1
                    continue
                if config.state_dedup:
                    seen.add(signature)
                temperature = _temperature(iteration, t1, avg_uphill, config.fast_sa_c, config.fast_sa_k)
                if _accept(current, proposal, temperature, max(current.area, 1.0), rng):
                    state = proposal_state
                    current = proposal
                    accepted += 1
                if best is None or proposal.rank < best.rank:
                    best = proposal
            restarts_completed += 1
            if timed_out:
                break
    except Exception as exc:  # Preserve a crash as a structured run result.
        error = f"{type(exc).__name__}: {exc}"

    runtime = time.perf_counter() - start
    if error:
        status = "crash"
    elif best is None:
        status = "no_feasible"
    elif timed_out:
        status = "timeout"
    else:
        status = "success"

    formal_metrics: dict = {}
    audit_metrics: dict = {}
    if best is not None:
        formal = evaluate(instance, best.layout)
        audit = audit_layout(instance, best.layout)
        formal_metrics = formal.as_dict()
        audit_metrics = audit
    return SearchResult(
        status=status,
        best=best,
        formal_metrics=formal_metrics,
        audit_metrics=audit_metrics,
        evaluations=evaluations,
        proposals=proposals,
        accepted=accepted,
        duplicate_rejections=duplicate_rejections,
        restarts_completed=restarts_completed,
        runtime=runtime,
        error=error,
    )
