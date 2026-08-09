"""Outer dead-space search and final HPWL optimization for Question 3."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Any, Callable

from ..Q2.common import Q2SearchConfig, SearchResult
from ..Q2.p0 import search_p0
from ..Q2.p1_p2 import search_p1_p2
from .._internal.parser import Instance
from .common import (
    Q3Result,
    Q3SearchConfig,
    SeedAttempt,
    ThresholdAttempt,
    outline_side,
    ratio_key,
    rounded_midpoint,
    validate_config,
)


ProgressCallback = Callable[[dict[str, Any]], None]


def _inner_config(config: Q3SearchConfig, dead_space_ratio: float, final: bool = False) -> Q2SearchConfig:
    return Q2SearchConfig(
        candidate=config.inner_candidate,
        adaptive_constraints=(
            config.adaptive_constraints
            if config.adaptive_constraints is not None
            else config.inner_candidate != "Q2-SP"
        ),
        hypergraph_init=(
            config.hypergraph_init
            if config.hypergraph_init is not None
            else config.inner_candidate == "Q2-HG"
        ),
        sa_schedule="classic" if config.inner_candidate == "Q2-SP" else "fast",
        max_evaluations=config.final_max_evaluations if final else config.max_evaluations,
        time_limit=config.final_time_limit if final else config.time_limit,
        restarts=config.final_restarts if final else config.restarts,
        dead_space_ratio=dead_space_ratio,
    )


def _run_inner(instance: Instance, config: Q2SearchConfig, seed: int, warm_state: object | None = None) -> SearchResult:
    if config.candidate == "Q2-SP":
        return search_p0(instance, config, seed)
    return search_p1_p2(instance, config, seed, initial_state=warm_state)


def _run_seed_attempt(task: tuple[Instance, Q2SearchConfig, int, str]) -> SeedAttempt:
    instance, config, seed, mode = task
    return SeedAttempt(seed, mode, _run_inner(instance, config, seed))


def _run_seed_attempts(
    instance: Instance,
    config: Q2SearchConfig,
    seeds: tuple[int, ...],
    workers: int,
    mode: str,
    *,
    candidate: str | None = None,
    dead_space_ratio: float | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[SeedAttempt]:
    tasks = [(instance, config, seed, mode) for seed in seeds]
    attempts: list[SeedAttempt] = []

    def record(index: int, attempt: SeedAttempt) -> None:
        if progress_callback is None:
            return
        progress_callback({
            "event": "seed_complete",
            "candidate": candidate,
            "phase": "final" if mode == "final_cold" else "threshold",
            "mode": mode,
            "dead_space_ratio": dead_space_ratio,
            "seed": attempt.seed,
            "seed_index": index + 1,
            "seed_total": len(seeds),
            **attempt.as_dict(),
        })

    if workers == 1:
        for index, task in enumerate(tasks):
            attempt = _run_seed_attempt(task)
            attempts.append(attempt)
            record(index, attempt)
        return attempts
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for index, attempt in enumerate(executor.map(_run_seed_attempt, tasks)):
            attempts.append(attempt)
            record(index, attempt)
    return attempts


def _run_cold_attempts(
    instance: Instance,
    config: Q2SearchConfig,
    seeds: tuple[int, ...],
    workers: int,
    *,
    candidate: str | None = None,
    dead_space_ratio: float | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[SeedAttempt]:
    return _run_seed_attempts(
        instance,
        config,
        seeds,
        workers,
        "cold",
        candidate=candidate,
        dead_space_ratio=dead_space_ratio,
        progress_callback=progress_callback,
    )


def _run_final_attempts(
    instance: Instance,
    config: Q2SearchConfig,
    seeds: tuple[int, ...],
    workers: int,
    *,
    candidate: str | None = None,
    dead_space_ratio: float | None = None,
    progress_callback: ProgressCallback | None = None,
) -> list[SeedAttempt]:
    return _run_seed_attempts(
        instance,
        config,
        seeds,
        workers,
        "final_cold",
        candidate=candidate,
        dead_space_ratio=dead_space_ratio,
        progress_callback=progress_callback,
    )


def _threshold_attempt(
    instance: Instance,
    config: Q3SearchConfig,
    dead_space_ratio: float,
    warm_state: object | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ThresholdAttempt:
    ratio = ratio_key(dead_space_ratio)
    inner = _inner_config(config, ratio)
    seed_attempts: list[SeedAttempt] = []
    if (
        config.candidate == "Q3-CONT-R"
        and config.continuous_compression
        and warm_state is not None
        and config.inner_candidate != "Q2-SP"
    ):
        warm_seed = config.seeds[0]
        warm_attempt = SeedAttempt(warm_seed, "warm", _run_inner(instance, inner, warm_seed, warm_state))
        seed_attempts.append(warm_attempt)
        if progress_callback is not None:
            progress_callback({
                "event": "seed_complete",
                "candidate": config.candidate,
                "phase": "threshold",
                "mode": "warm",
                "dead_space_ratio": ratio,
                "seed": warm_attempt.seed,
                "seed_index": 1,
                "seed_total": 1,
                **warm_attempt.as_dict(),
            })
    seed_attempts.extend(_run_cold_attempts(
        instance,
        inner,
        config.seeds,
        config.workers,
        candidate=config.candidate,
        dead_space_ratio=ratio,
        progress_callback=progress_callback,
    ))
    return ThresholdAttempt(ratio, outline_side(instance, ratio), seed_attempts)


def _decision(attempt: ThresholdAttempt, config: Q3SearchConfig) -> bool:
    if config.decision_rule == "any":
        return bool(attempt.cold_legal_attempts)
    return attempt.success_rate >= config.robust_min_success_rate


def _best_warm_state(attempt: ThresholdAttempt) -> object | None:
    best = attempt.best_legal
    return best.result.best_state if best is not None else None


def _ratios_linear(config: Q3SearchConfig) -> list[float]:
    ratios = [ratio_key(config.upper_ratio)]
    current = config.upper_ratio
    while current - config.precision > config.lower_ratio:
        current = ratio_key(current - config.precision)
        ratios.append(current)
    if ratios[-1] != ratio_key(config.lower_ratio):
        ratios.append(ratio_key(config.lower_ratio))
    return ratios


def _threshold_search(
    instance: Instance,
    config: Q3SearchConfig,
    progress_callback: ProgressCallback | None = None,
) -> list[ThresholdAttempt]:
    attempts: list[ThresholdAttempt] = []
    by_ratio: dict[float, ThresholdAttempt] = {}

    def attempt(ratio: float, warm_state: object | None = None) -> ThresholdAttempt:
        key = ratio_key(ratio)
        if key not in by_ratio:
            current = _threshold_attempt(instance, config, key, warm_state, progress_callback)
            by_ratio[key] = current
            attempts.append(current)
            if progress_callback is not None:
                progress_callback({
                    "event": "threshold_complete",
                    "candidate": config.candidate,
                    "phase": "threshold",
                    "dead_space_ratio": current.dead_space_ratio,
                    "outline_side": current.outline_side,
                    "cold_runs": len(current.cold_attempts),
                    "cold_legal_runs": len(current.cold_legal_attempts),
                    "cold_success_rate": current.success_rate,
                    "robust": current.success_rate >= config.robust_min_success_rate,
                })
        return by_ratio[key]

    upper = attempt(config.upper_ratio)
    if config.candidate == "Q3-LIN":
        for ratio in _ratios_linear(config)[1:]:
            attempt(ratio)
        return attempts

    if not _decision(upper, config):
        return attempts
    warm_state = (
        _best_warm_state(upper)
        if config.candidate == "Q3-CONT-R" and config.continuous_compression
        else None
    )
    lower = attempt(config.lower_ratio, warm_state)
    if _decision(lower, config):
        return attempts
    low, high = config.lower_ratio, config.upper_ratio
    while high - low > config.precision:
        midpoint = rounded_midpoint(low, high, config.precision)
        if midpoint == high:
            break
        current = attempt(midpoint, warm_state)
        if _decision(current, config):
            high = midpoint
            if config.candidate == "Q3-CONT-R" and config.continuous_compression:
                warm_state = _best_warm_state(current)
        else:
            low = midpoint
    return attempts


def _minimum_ratio(attempts: list[ThresholdAttempt], config: Q3SearchConfig, robust: bool) -> float | None:
    candidates = []
    for attempt in attempts:
        if robust:
            accepted = attempt.success_rate >= config.robust_min_success_rate
        else:
            accepted = bool(attempt.cold_legal_attempts)
        if accepted:
            candidates.append(attempt.dead_space_ratio)
    return min(candidates) if candidates else None


def _final_attempts(
    instance: Instance,
    config: Q3SearchConfig,
    selected_ratio: float | None,
    progress_callback: ProgressCallback | None = None,
) -> list[SeedAttempt]:
    if selected_ratio is None:
        return []
    inner = _inner_config(config, selected_ratio, final=True)
    attempts = _run_final_attempts(
        instance,
        inner,
        config.final_seeds,
        config.workers,
        candidate=config.candidate,
        dead_space_ratio=selected_ratio,
        progress_callback=progress_callback,
    )
    if progress_callback is not None:
        progress_callback({
            "event": "final_complete",
            "candidate": config.candidate,
            "phase": "final",
            "dead_space_ratio": selected_ratio,
            "final_runs": len(attempts),
            "final_legal_runs": sum(
                attempt.result.status != "crash" and attempt.result.audit_metrics.get("legal") is True
                for attempt in attempts
            ),
        })
    return attempts


def solve_q3(
    instance: Instance,
    config: Q3SearchConfig,
    *,
    progress_callback: ProgressCallback | None = None,
) -> Q3Result:
    """Search a documented heuristic boundary, then re-optimize HPWL there.

    A failed inner run means only that its finite budget did not find a layout.
    It is never returned as a mathematical proof of infeasibility.
    """
    validate_config(config)
    attempts = _threshold_search(instance, config, progress_callback)
    d_best = _minimum_ratio(attempts, config, robust=False)
    d_robust = _minimum_ratio(attempts, config, robust=True)
    selected = d_robust if config.decision_rule == "robust" else d_best
    return Q3Result(
        attempts,
        d_best,
        d_robust,
        selected,
        _final_attempts(instance, config, selected, progress_callback),
    )
