"""Q2-BT and Q2-HG using the Question 1 B*-Tree representation."""

from __future__ import annotations

import random
import time

from ..Q1.p1_p2 import BTreeState, PackedLayout, pack_btree
from .._internal.parser import Instance
from .common import (
    Q2Layout,
    Q2SearchConfig,
    SearchResult,
    accept,
    assess,
    audit_best,
    constraint_penalty,
    checkpoint_targets,
    record_checkpoint,
    fast_temperature,
    finalize,
    initial_temperature,
    layout_signature,
    restart_evaluation_limits,
    search_delta,
    shelf_layout_with_order,
    square_side,
    validate_config,
)


def _random_state(names: tuple[str, ...], rng: random.Random) -> BTreeState:
    return BTreeState.complete(names, rng)


def _fixed_outline_state(
    instance: Instance, side: float, preferred_order: list[str] | None = None
) -> BTreeState | None:
    placement = shelf_layout_with_order(instance, side, preferred_order)
    if placement is None:
        return None
    rows: dict[float, list[str]] = {}
    for name, (_x, y, _rotation) in placement.items():
        rows.setdefault(y, []).append(name)
    if preferred_order is None:
        rank = None
    else:
        rank = {name: position for position, name in enumerate(preferred_order)}
    ordered_rows = [
        sorted(
            rows[y],
            key=(
                (lambda name: (placement[name][0], name))
                if rank is None
                else (lambda name: (rank[name], name))
            ),
        )
        for y in sorted(rows)
    ]
    labels = [name for row in ordered_rows for name in row]
    index = {name: position for position, name in enumerate(labels)}
    left: list[int | None] = [None] * len(labels)
    right: list[int | None] = [None] * len(labels)
    parent: list[int | None] = [None] * len(labels)
    rotations = [placement[name][2] for name in labels]
    for row in ordered_rows:
        for first, second in zip(row, row[1:]):
            first_index, second_index = index[first], index[second]
            left[first_index] = second_index
            parent[second_index] = first_index
    for lower, upper in zip(ordered_rows, ordered_rows[1:]):
        lower_index, upper_index = index[lower[0]], index[upper[0]]
        right[lower_index] = upper_index
        parent[upper_index] = lower_index
    state = BTreeState(labels, left, right, parent, rotations, 0)
    state.validate()
    return state


def _hypergraph_order(instance: Instance, rng: random.Random) -> list[str]:
    names = tuple(instance.blocks)
    adjacency = {name: {} for name in names}
    degree = {name: 0.0 for name in names}
    for net in instance.nets:
        blocks = [pin for pin in net.pins if pin in instance.blocks]
        if not blocks:
            continue
        weight = 1.0 / max(len(blocks) - 1, 1)
        for name in blocks:
            degree[name] += 1.0
            for other in blocks:
                if other != name:
                    adjacency[name][other] = adjacency[name].get(other, 0.0) + weight
    remaining = set(names)
    order: list[str] = []
    while remaining:
        if not order:
            best_score = max((degree[name] for name in remaining), default=0.0)
            choices = sorted(name for name in remaining if degree[name] == best_score)
        else:
            scores = {
                name: sum(adjacency[name].get(placed, 0.0) for placed in order) + 0.01 * degree[name]
                for name in remaining
            }
            best_score = max(scores.values())
            choices = sorted(name for name in remaining if scores[name] == best_score)
        chosen = rng.choice(choices)
        order.append(chosen)
        remaining.remove(chosen)
    return order


def _initial_state(
    instance: Instance,
    config: Q2SearchConfig,
    rng: random.Random,
    side: float,
    restart: int,
    initial_state: BTreeState | None = None,
) -> tuple[BTreeState, dict[str, tuple[float, float, int]] | None]:
    names = tuple(instance.blocks)
    if restart == 0 and initial_state is not None:
        if set(initial_state.labels) != set(names):
            raise ValueError("warm-start state does not match instance blocks")
        return initial_state.clone(), None
    if config.initialization_mode == "shelf":
        if config.hypergraph_init:
            preferred_order = _hypergraph_order(instance, rng)
        else:
            preferred_order = list(names)
            rng.shuffle(preferred_order)
        fixed = _fixed_outline_state(instance, side, preferred_order)
        if fixed is not None:
            shelf = shelf_layout_with_order(instance, side, preferred_order)
            if shelf is not None:
                return fixed, shelf
    state = _random_state(names, rng)
    return state, None


def _shelf_packed(instance: Instance, layout: dict[str, tuple[float, float, int]]) -> PackedLayout:
    """Build the packed-layout wrapper for a legal fixed-shelf placement.

    The B*-Tree state is retained for subsequent mutations, while the first
    evaluated layout is the actual shelf placement.  This keeps the P2 ON/OFF
    initialization comparison scoped to the intended within-row order rather
    than letting the B*-Tree contour decoder silently change row membership.
    """
    right = []
    top = []
    for name, (x, y, rotation) in layout.items():
        block = instance.blocks[name]
        width, height = (block.width, block.height) if rotation % 180 == 0 else (block.height, block.width)
        right.append(x + width)
        top.append(y + height)
    width = max(right, default=0.0)
    height = max(top, default=0.0)
    area = width * height
    aspect = max(width, height) / min(width, height) if min(width, height) else float("inf")
    return PackedLayout(layout, width, height, area, aspect)


def _mutate(state: BTreeState, rng: random.Random) -> None:
    operation = rng.randrange(3)
    if operation == 0:
        state.rotate_random(rng)
    elif operation == 1:
        state.move_random(rng)
    else:
        state.swap_random(rng)


def _calibrate(
    instance: Instance,
    state: BTreeState,
    current: Q2Layout,
    config: Q2SearchConfig,
    rng: random.Random,
    side: float,
    start: float,
    evaluations: int,
    evaluation_limit: int,
) -> tuple[float, int, bool]:
    uphill: list[float] = []
    sample = current
    target = config.calibration_samples or len(instance.blocks)
    timed_out = False
    for sample_index in range(target):
        if evaluations >= evaluation_limit or time.perf_counter() - start >= config.time_limit:
            timed_out = time.perf_counter() - start >= config.time_limit
            break
        trial = state.clone()
        _mutate(trial, rng)
        proposal = assess(instance, pack_btree(trial, instance.blocks), side)
        evaluations += 1
        delta = search_delta(sample, proposal, constraint_penalty(config, sample_index, sample.legal))
        if delta > 0:
            uphill.append(delta)
        sample = proposal
    average = sum(uphill) / len(uphill) if uphill else 0.01
    return average, evaluations, timed_out


def search_p1_p2(
    instance: Instance,
    config: Q2SearchConfig,
    seed: int,
    initial_state: BTreeState | None = None,
) -> SearchResult:
    if config.candidate not in {"Q2-BT", "Q2-HG"}:
        raise ValueError(f"unsupported Q2 B*-Tree candidate: {config.candidate}")
    validate_config(config)
    if config.sa_schedule != "fast":
        raise ValueError("Q2-BT and Q2-HG are fixed to the Fast-SA schedule")
    if not instance.blocks:
        return SearchResult("no_feasible", None, error="no HardBlock records")

    start = time.perf_counter()
    master_rng = random.Random(seed)
    side = square_side(instance, config.dead_space_ratio)
    best_feasible: Q2Layout | None = None
    best_infeasible: Q2Layout | None = None
    best_feasible_state: BTreeState | None = None
    best_infeasible_state: BTreeState | None = None
    evaluations = proposals = accepted_count = restarts_completed = 0
    first_feasible_evaluation = None
    first_feasible_time = None
    timed_out = False
    error = None
    restart_initial_hpwl: list[float] = []
    restart_initial_legal: list[bool] = []
    restart_initial_signatures: list[str] = []
    restart_init_seeds: list[int] = []
    restart_search_seeds: list[int] = []
    checkpoint_targets_by_percent = checkpoint_targets(config.max_evaluations)
    checkpoint_evaluations: dict[int, int] = {}
    checkpoint_best_hpwl: dict[int, float | None] = {}

    try:
        limits = restart_evaluation_limits(config.max_evaluations, config.restarts)
        for restart in range(config.restarts):
            evaluation_limit = limits[restart]
            if evaluations >= evaluation_limit:
                break
            if time.perf_counter() - start >= config.time_limit:
                timed_out = True
                break
            init_seed = master_rng.getrandbits(64)
            search_seed = master_rng.getrandbits(64)
            init_rng = random.Random(init_seed)
            search_rng = random.Random(search_seed)
            restart_init_seeds.append(init_seed)
            restart_search_seeds.append(search_seed)
            state, shelf_layout = _initial_state(instance, config, init_rng, side, restart, initial_state)
            initial_packed = _shelf_packed(instance, shelf_layout) if shelf_layout is not None else pack_btree(state, instance.blocks)
            current = assess(instance, initial_packed, side)
            evaluations += 1
            restart_initial_hpwl.append(current.hpwl)
            restart_initial_legal.append(current.legal)
            restart_initial_signatures.append(layout_signature(current.layout))
            if current.legal:
                if best_feasible is None or current.rank < best_feasible.rank:
                    best_feasible = current
                    best_feasible_state = state.clone()
                if first_feasible_evaluation is None:
                    first_feasible_evaluation = evaluations
                    first_feasible_time = time.perf_counter() - start
            elif best_infeasible is None or current.rank < best_infeasible.rank:
                best_infeasible = current
                best_infeasible_state = state.clone()
            record_checkpoint(
                checkpoint_targets_by_percent, evaluations, best_feasible,
                checkpoint_evaluations, checkpoint_best_hpwl,
            )

            avg_delta, evaluations, calibration_timeout = _calibrate(
                instance, state, current, config, search_rng, side, start, evaluations, evaluation_limit
            )
            record_checkpoint(
                checkpoint_targets_by_percent, evaluations, best_feasible,
                checkpoint_evaluations, checkpoint_best_hpwl,
            )
            if calibration_timeout:
                timed_out = True
                restarts_completed += 1
                break
            t1 = initial_temperature(avg_delta, config.initial_acceptance)
            iteration = 0
            while evaluations < evaluation_limit:
                if time.perf_counter() - start >= config.time_limit:
                    timed_out = True
                    break
                iteration += 1
                proposal_state = state.clone()
                _mutate(proposal_state, search_rng)
                proposal = assess(instance, pack_btree(proposal_state, instance.blocks), side)
                evaluations += 1
                proposals += 1
                if proposal.legal:
                    if first_feasible_evaluation is None:
                        first_feasible_evaluation = evaluations
                        first_feasible_time = time.perf_counter() - start
                    if best_feasible is None or proposal.rank < best_feasible.rank:
                        best_feasible = proposal
                        best_feasible_state = proposal_state.clone()
                elif best_infeasible is None or proposal.rank < best_infeasible.rank:
                    best_infeasible = proposal
                    best_infeasible_state = proposal_state.clone()
                record_checkpoint(
                    checkpoint_targets_by_percent, evaluations, best_feasible,
                    checkpoint_evaluations, checkpoint_best_hpwl,
                )
                penalty = constraint_penalty(config, iteration, best_feasible is not None)
                temperature = fast_temperature(iteration, t1, avg_delta, config.fast_sa_c, config.fast_sa_k)
                if accept(current, proposal, temperature, penalty, search_rng):
                    state = proposal_state
                    current = proposal
                    accepted_count += 1
            restarts_completed += 1
            if timed_out:
                break
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    runtime = time.perf_counter() - start
    best = finalize(instance, best_feasible or best_infeasible, side)
    if error:
        status = "crash"
    elif best_feasible is None or best is None or not best.legal:
        status = "no_feasible"
    elif timed_out:
        status = "timeout"
    else:
        status = "success"
    return SearchResult(
        status=status,
        best=best,
        audit_metrics=audit_best(instance, best, side),
        evaluations=evaluations,
        proposals=proposals,
        accepted=accepted_count,
        restarts_completed=restarts_completed,
        first_feasible_evaluation=first_feasible_evaluation,
        first_feasible_time=first_feasible_time,
        runtime=runtime,
        error=error,
        restart_initial_hpwl=restart_initial_hpwl,
        restart_initial_legal=restart_initial_legal,
        restart_initial_signatures=restart_initial_signatures,
        restart_init_seeds=restart_init_seeds,
        restart_search_seeds=restart_search_seeds,
        best_state=best_feasible_state or best_infeasible_state,
        checkpoint_evaluations=checkpoint_evaluations,
        checkpoint_best_hpwl=checkpoint_best_hpwl,
    )
