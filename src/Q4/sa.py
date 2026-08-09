from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass

from .geometry import bbox, rotate_normalized
from .model import Q4Evaluation, Q4Instance, evaluate_layout, formal_audit_match


def row_layout(instance: Q4Instance) -> dict[str, tuple[int, int, int]]:
    layout: dict[str, tuple[int, int, int]] = {}
    x = 0
    for name in sorted(instance.blocks):
        layout[name] = (x, 0, 0)
        x += bbox(instance.blocks[name].polygon)[0]
    return layout


@dataclass(frozen=True)
class SAResult:
    status: str
    seed: int
    evaluations: int
    runtime: float
    layout: dict[str, tuple[int, int, int]]
    evaluation: Q4Evaluation
    initial_area: int | float
    formal_audit_match: bool
    config: dict
    restarts_completed: int
    audit: dict

    def as_dict(self) -> dict:
        payload = self.evaluation.as_dict()
        payload.update(
            {
                "evaluation": self.evaluation.as_dict(),
                "status": self.status,
                "seed": self.seed,
                "evaluations": self.evaluations,
                "runtime": self.runtime,
                "initial_area": self.initial_area,
                "formal_audit_match": self.formal_audit_match,
                "config": self.config,
                "restarts_completed": self.restarts_completed,
                "audit": self.audit,
            }
        )
        return payload


def solve_sa(
    instance: Q4Instance | None = None,
    *,
    seed: int = 0,
    max_evaluations: int = 1000,
    time_limit: float = 60.0,
    restarts: int = 4,
    domain: tuple[int, int] = (9, 9),
    geometry: str | None = None,
) -> SAResult:
    instance = instance or Q4Instance.default()
    if not isinstance(max_evaluations, int) or max_evaluations <= 0:
        raise ValueError("max_evaluations must be positive")
    if not isinstance(restarts, int) or restarts <= 0:
        raise ValueError("restarts must be positive")
    if not (isinstance(domain, tuple) and len(domain) == 2 and all(isinstance(value, int) and value > 0 for value in domain)):
        raise ValueError("domain dimensions must be positive integers")
    if time_limit < 0:
        raise ValueError("time_limit must be non-negative")
    started = time.perf_counter()
    initial = row_layout(instance)
    initial_eval = evaluate_layout(instance, initial)
    if not initial_eval.legal:
        raise ValueError("row initialization must be legal")
    best_layout = dict(initial)
    best_eval = initial_eval
    evaluations = 0
    rng = random.Random(seed)
    stop = False
    restart_count = max(1, restarts)
    restarts_completed = 0
    for restart in range(restart_count):
        restart_budget = max_evaluations // restart_count + (1 if restart < max_evaluations % restart_count else 0)
        current_layout = dict(initial)
        current_eval = initial_eval
        restart_evaluations = 0
        while restart_evaluations < restart_budget:
            if time_limit >= 0 and time.perf_counter() - started >= time_limit:
                stop = True
                break
            evaluations += 1
            restart_evaluations += 1
            candidate = dict(current_layout)
            name = rng.choice(tuple(sorted(instance.blocks)))
            rotation = rng.choice((0, 90, 180, 270))
            width, height = bbox(rotate_normalized(instance.blocks[name].polygon, rotation))
            max_x = max(0, domain[0] - width)
            max_y = max(0, domain[1] - height)
            candidate[name] = (rng.randint(0, max_x), rng.randint(0, max_y), rotation)
            bounded = evaluate_layout(instance, candidate, domain)
            if not bounded.legal:
                continue
            trial = evaluate_layout(instance, candidate)
            delta = trial.area - current_eval.area
            temperature = max(0.25, initial_eval.area * (1 - restart_evaluations / max(1, restart_budget)))
            if delta <= 0 or rng.random() < math.exp(-delta / temperature):
                current_layout, current_eval = candidate, trial
                if trial.area < best_eval.area:
                    best_layout, best_eval = dict(candidate), trial
        if stop:
            break
        restarts_completed += 1
        if evaluations >= max_evaluations:
            break
    matched = formal_audit_match(instance, best_layout)
    if not matched:
        raise AssertionError("formal evaluator and independent audit disagree")
    from src._internal.audit import audit_layout

    config = {"seed": seed, "max_evaluations": max_evaluations, "time_limit": time_limit, "restarts": restarts, "domain": domain, "temperature_schedule": "per_restart_linear", "grid_step": 1, "rotations": (0, 90, 180, 270), "search_domain": "integer_translation_grid"}
    if geometry is not None:
        config["mode"] = "sa"
        config["geometry"] = geometry
        config["b1_beam_thickness"] = {"G-": 1, "G0": 2, "G+": 3}[geometry]
    return SAResult(
        "timeout" if stop else "success",
        seed,
        evaluations,
        time.perf_counter() - started,
        best_layout,
        best_eval,
        initial_eval.area,
        matched,
        config,
        restarts_completed,
        audit_layout(instance, best_layout),
    )
