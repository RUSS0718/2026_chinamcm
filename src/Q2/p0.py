"""Independent Q2 Sequence Pair baseline with fixed-outline SA."""

from __future__ import annotations

import random
import time

from ..Q1.p0 import decode_sequence_pair
from .._internal.parser import Instance
from .common import (
    Q2Layout,
    Q2SearchConfig,
    SearchResult,
    accept,
    assess,
    audit_best,
    fast_temperature,
    fixed_outline_shelf_layout,
    finalize,
    initial_temperature,
    search_delta,
    square_side,
    validate_config,
)


def _fixed_outline_initialization(
    instance: Instance, side: float
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, int]] | None:
    """Build a deterministic shelf layout and encode it as a sequence pair."""
    placement = fixed_outline_shelf_layout(instance, side)
    if placement is None:
        return None

    # In the decoder convention, blocks in an upper shelf precede lower
    # shelves in the positive sequence and follow them in the negative one.
    positive = tuple(sorted(placement, key=lambda name: (-placement[name][1], placement[name][0], name)))
    negative = tuple(sorted(placement, key=lambda name: (placement[name][1], placement[name][0], name)))
    rotations = {name: rotation for name, (_x, _y, rotation) in placement.items()}
    return positive, negative, rotations


def _mutate(
    positive: tuple[str, ...],
    negative: tuple[str, ...],
    rotations: dict[str, int],
    rng: random.Random,
) -> tuple[tuple[str, ...], tuple[str, ...], dict[str, int]]:
    next_positive = list(positive)
    next_negative = list(negative)
    next_rotations = dict(rotations)
    if len(next_positive) == 1:
        name = next_positive[0]
        next_rotations[name] ^= 90
        return tuple(next_positive), tuple(next_negative), next_rotations
    operation = rng.randrange(3)
    if operation == 0:
        first, second = rng.sample(range(len(next_positive)), 2)
        next_positive[first], next_positive[second] = next_positive[second], next_positive[first]
    elif operation == 1:
        first, second = rng.sample(range(len(next_negative)), 2)
        next_negative[first], next_negative[second] = next_negative[second], next_negative[first]
    else:
        name = rng.choice(next_positive)
        next_rotations[name] ^= 90
    return tuple(next_positive), tuple(next_negative), next_rotations


def search_p0(instance: Instance, config: Q2SearchConfig, seed: int) -> SearchResult:
    if config.candidate != "Q2-SP":
        raise ValueError(f"unsupported Q2 P0 candidate: {config.candidate}")
    validate_config(config)
    if not instance.blocks:
        return SearchResult("no_feasible", None, error="no HardBlock records")

    start = time.perf_counter()
    rng = random.Random(seed)
    side = square_side(instance, config.dead_space_ratio)
    names = tuple(instance.blocks)
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
            initialization = _fixed_outline_initialization(instance, side) if restart == 0 else None
            if initialization is None:
                positive = list(names)
                negative = list(names)
                rng.shuffle(positive)
                rng.shuffle(negative)
                rotations = {name: rng.choice((0, 90)) for name in names}
            else:
                initial_positive, initial_negative, rotations = initialization
                positive = list(initial_positive)
                negative = list(initial_negative)
            current = assess(
                instance,
                decode_sequence_pair(tuple(positive), tuple(negative), rotations, instance.blocks),
                side,
            )
            evaluations += 1
            if current.legal:
                best_feasible = current if best_feasible is None or current.rank < best_feasible.rank else best_feasible
                if first_feasible_evaluation is None:
                    first_feasible_evaluation = evaluations
                    first_feasible_time = time.perf_counter() - start
            else:
                best_infeasible = current if best_infeasible is None or current.rank < best_infeasible.rank else best_infeasible

            calibration = config.calibration_samples or len(names)
            uphill: list[float] = []
            sample = current
            for sample_index in range(calibration):
                if evaluations >= evaluation_limit or time.perf_counter() - start >= config.time_limit:
                    timed_out = time.perf_counter() - start >= config.time_limit
                    break
                trial_positive, trial_negative, trial_rotations = _mutate(
                    tuple(positive), tuple(negative), rotations, rng
                )
                proposal = assess(
                    instance,
                    decode_sequence_pair(trial_positive, trial_negative, trial_rotations, instance.blocks),
                    side,
                )
                evaluations += 1
                delta = search_delta(sample, proposal, 10.0)
                if delta > 0:
                    uphill.append(delta)
                sample = proposal
            if timed_out or evaluations >= evaluation_limit:
                restarts_completed += 1
                if timed_out:
                    break
                continue
            avg_delta = sum(uphill) / len(uphill) if uphill else 0.01
            t1 = initial_temperature(avg_delta, config.initial_acceptance)
            iteration = 0
            while evaluations < evaluation_limit:
                if time.perf_counter() - start >= config.time_limit:
                    timed_out = True
                    break
                iteration += 1
                trial_positive, trial_negative, trial_rotations = _mutate(
                    tuple(positive), tuple(negative), rotations, rng
                )
                proposal = assess(
                    instance,
                    decode_sequence_pair(trial_positive, trial_negative, trial_rotations, instance.blocks),
                    side,
                )
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
                temperature = fast_temperature(iteration, t1, avg_delta, config.fast_sa_c, config.fast_sa_k)
                if accept(current, proposal, temperature, 10.0, rng):
                    positive = list(trial_positive)
                    negative = list(trial_negative)
                    rotations = trial_rotations
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
