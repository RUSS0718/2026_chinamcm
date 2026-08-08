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
    fast_temperature,
    fixed_outline_shelf_layout,
    finalize,
    initial_temperature,
    search_delta,
    square_side,
    validate_config,
)


def _random_state(names: tuple[str, ...], rng: random.Random) -> BTreeState:
    return BTreeState.complete(names, rng)


def _fixed_outline_state(
    instance: Instance, side: float, preferred_order: list[str] | None = None
) -> BTreeState | None:
    placement = fixed_outline_shelf_layout(instance, side)
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


def _initial_state(instance: Instance, config: Q2SearchConfig, rng: random.Random, side: float, restart: int) -> BTreeState:
    names = tuple(instance.blocks)
    if config.hypergraph_init:
        fixed = _fixed_outline_state(instance, side, _hypergraph_order(instance, rng))
        if fixed is not None:
            return fixed
    elif restart == 0:
        fixed = _fixed_outline_state(instance, side)
        if fixed is not None:
            return fixed
    state = _random_state(names, rng)
    return state


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


def search_p1_p2(instance: Instance, config: Q2SearchConfig, seed: int) -> SearchResult:
    if config.candidate not in {"Q2-BT", "Q2-HG"}:
        raise ValueError(f"unsupported Q2 B*-Tree candidate: {config.candidate}")
    validate_config(config)
    if not instance.blocks:
        return SearchResult("no_feasible", None, error="no HardBlock records")

    start = time.perf_counter()
    rng = random.Random(seed)
    side = square_side(instance, config.dead_space_ratio)
    best_feasible: Q2Layout | None = None
    best_infeasible: Q2Layout | None = None
    evaluations = proposals = accepted_count = restarts_completed = 0
    first_feasible_evaluation = None
    first_feasible_time = None
    timed_out = False
    error = None

    try:
        per_restart = (config.max_evaluations + config.restarts - 1) // config.restarts
        for restart in range(config.restarts):
            evaluation_limit = min(config.max_evaluations, (restart + 1) * per_restart)
            if evaluations >= evaluation_limit:
                break
            if time.perf_counter() - start >= config.time_limit:
                timed_out = True
                break
            state = _initial_state(instance, config, random.Random(rng.randrange(2**63)), side, restart)
            current = assess(instance, pack_btree(state, instance.blocks), side)
            evaluations += 1
            if current.legal:
                best_feasible = current if best_feasible is None or current.rank < best_feasible.rank else best_feasible
                if first_feasible_evaluation is None:
                    first_feasible_evaluation = evaluations
                    first_feasible_time = time.perf_counter() - start
            elif best_infeasible is None or current.rank < best_infeasible.rank:
                best_infeasible = current

            avg_delta, evaluations, calibration_timeout = _calibrate(
                instance, state, current, config, rng, side, start, evaluations, evaluation_limit
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
                _mutate(proposal_state, rng)
                proposal = assess(instance, pack_btree(proposal_state, instance.blocks), side)
                evaluations += 1
                proposals += 1
                if proposal.legal:
                    if first_feasible_evaluation is None:
                        first_feasible_evaluation = evaluations
                        first_feasible_time = time.perf_counter() - start
                    if best_feasible is None or proposal.rank < best_feasible.rank:
                        best_feasible = proposal
                elif best_infeasible is None or proposal.rank < best_infeasible.rank:
                    best_infeasible = proposal
                penalty = constraint_penalty(config, iteration, best_feasible is not None)
                temperature = fast_temperature(iteration, t1, avg_delta, config.fast_sa_c, config.fast_sa_k)
                if accept(current, proposal, temperature, penalty, rng):
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
    )
