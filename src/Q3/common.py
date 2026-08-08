"""Configuration and records for Question 3 threshold searches."""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from ..Q2.common import SearchResult, square_side
from .._internal.parser import Instance


CANDIDATES = ("Q3-LIN", "Q3-BIN", "Q3-CONT-R")
INNER_CANDIDATES = ("Q2-SP", "Q2-BT", "Q2-HG")


@dataclass(frozen=True)
class Q3SearchConfig:
    candidate: str = "Q3-BIN"
    inner_candidate: str = "Q2-HG"
    lower_ratio: float = 0.0
    upper_ratio: float = 0.15
    precision: float = 0.005
    robust_min_success_rate: float = 0.8
    decision_rule: str = "robust"
    seeds: tuple[int, ...] = tuple(range(1101, 1111))
    max_evaluations: int = 30_000
    time_limit: float = 60.0
    restarts: int = 4
    workers: int = 1
    adaptive_constraints: bool | None = None
    hypergraph_init: bool | None = None
    continuous_compression: bool | None = None
    final_seeds: tuple[int, ...] = tuple(range(1101, 1111))
    final_max_evaluations: int = 30_000
    final_time_limit: float = 60.0
    final_restarts: int = 4

    def __post_init__(self) -> None:
        if self.continuous_compression is None:
            object.__setattr__(self, "continuous_compression", self.candidate == "Q3-CONT-R")

    def as_dict(self) -> dict:
        return {
            "candidate": self.candidate,
            "inner_candidate": self.inner_candidate,
            "lower_ratio": self.lower_ratio,
            "upper_ratio": self.upper_ratio,
            "precision": self.precision,
            "robust_min_success_rate": self.robust_min_success_rate,
            "decision_rule": self.decision_rule,
            "seeds": list(self.seeds),
            "max_evaluations": self.max_evaluations,
            "time_limit": self.time_limit,
            "restarts": self.restarts,
            "workers": self.workers,
            "adaptive_constraints": self.adaptive_constraints,
            "hypergraph_init": self.hypergraph_init,
            "continuous_compression": self.continuous_compression,
            "final_seeds": list(self.final_seeds),
            "final_max_evaluations": self.final_max_evaluations,
            "final_time_limit": self.final_time_limit,
            "final_restarts": self.final_restarts,
        }


@dataclass
class SeedAttempt:
    seed: int
    mode: str
    result: SearchResult

    def as_dict(self) -> dict:
        formal = self.result.formal_metrics
        return {
            "seed": self.seed,
            "mode": self.mode,
            "status": self.result.status,
            "legal": self.result.audit_metrics.get("legal"),
            "HPWL": formal.get("HPWL"),
            "runtime": self.result.runtime,
            "evaluations": self.result.evaluations,
            "proposals": self.result.proposals,
            "accepted": self.result.accepted,
            "restarts_completed": self.result.restarts_completed,
            "first_feasible_evaluation": self.result.first_feasible_evaluation,
            "first_feasible_time": self.result.first_feasible_time,
            "formal_audit_match": self.result.formal_metrics == self.result.audit_metrics,
            "error": self.result.error or "",
        }


@dataclass
class ThresholdAttempt:
    dead_space_ratio: float
    outline_side: float
    seed_attempts: list[SeedAttempt] = field(default_factory=list)

    @property
    def cold_attempts(self) -> list[SeedAttempt]:
        return [attempt for attempt in self.seed_attempts if attempt.mode == "cold"]

    @property
    def legal_attempts(self) -> list[SeedAttempt]:
        return [
            attempt
            for attempt in self.seed_attempts
            if attempt.result.status != "crash" and attempt.result.audit_metrics.get("legal") is True
        ]

    @property
    def cold_legal_attempts(self) -> list[SeedAttempt]:
        return [
            attempt
            for attempt in self.cold_attempts
            if attempt.result.status != "crash" and attempt.result.audit_metrics.get("legal") is True
        ]

    @property
    def cold_best_legal(self) -> SeedAttempt | None:
        legal = [
            attempt
            for attempt in self.cold_legal_attempts
            if attempt.result.formal_metrics.get("HPWL") is not None
        ]
        return min(legal, key=lambda attempt: float(attempt.result.formal_metrics["HPWL"])) if legal else None

    @property
    def success_rate(self) -> float:
        return len(self.cold_legal_attempts) / len(self.cold_attempts) if self.cold_attempts else 0.0

    @property
    def best_legal(self) -> SeedAttempt | None:
        legal = [attempt for attempt in self.legal_attempts if attempt.result.formal_metrics.get("HPWL") is not None]
        return min(legal, key=lambda attempt: float(attempt.result.formal_metrics["HPWL"])) if legal else None

    def as_dict(self, robust_min_success_rate: float) -> dict:
        return {
            "dead_space_ratio": self.dead_space_ratio,
            "outline_side": self.outline_side,
            "found_legal": bool(self.cold_legal_attempts),
            "cold_runs": len(self.cold_attempts),
            "cold_legal_runs": len(self.cold_legal_attempts),
            "cold_success_rate": self.success_rate,
            "robust": self.success_rate >= robust_min_success_rate,
            "best_HPWL": self.cold_best_legal.result.formal_metrics["HPWL"] if self.cold_best_legal else None,
            "seed_attempts": [attempt.as_dict() for attempt in self.seed_attempts],
        }


@dataclass
class Q3Result:
    attempts: list[ThresholdAttempt]
    d_best: float | None
    d_robust: float | None
    selected_ratio: float | None
    final_attempts: list[SeedAttempt] = field(default_factory=list)

    @property
    def final_best(self) -> SeedAttempt | None:
        legal = [
            attempt
            for attempt in self.final_attempts
            if attempt.result.status != "crash" and attempt.result.audit_metrics.get("legal") is True
        ]
        return min(legal, key=lambda attempt: float(attempt.result.formal_metrics["HPWL"])) if legal else None

    def as_dict(self, config: Q3SearchConfig) -> dict:
        return {
            "config": config.as_dict(),
            "d_best": self.d_best,
            "d_robust": self.d_robust,
            "selected_ratio": self.selected_ratio,
            "attempts": [attempt.as_dict(config.robust_min_success_rate) for attempt in self.attempts],
            "final_attempts": [attempt.as_dict() for attempt in self.final_attempts],
            "final_best": self.final_best.as_dict() if self.final_best else None,
        }


def validate_config(config: Q3SearchConfig) -> None:
    if config.candidate not in CANDIDATES:
        raise ValueError(f"unsupported Q3 candidate: {config.candidate}")
    if config.inner_candidate not in INNER_CANDIDATES:
        raise ValueError(f"unsupported inner candidate: {config.inner_candidate}")
    if config.continuous_compression and (
        config.candidate != "Q3-CONT-R" or config.inner_candidate == "Q2-SP"
    ):
        raise ValueError(
            "continuous_compression requires candidate='Q3-CONT-R' and inner_candidate != 'Q2-SP'"
        )
    if not 0.0 <= config.lower_ratio <= config.upper_ratio:
        raise ValueError("require 0 <= lower_ratio <= upper_ratio")
    if config.precision <= 0:
        raise ValueError("precision must be positive")
    if not 0.0 < config.robust_min_success_rate <= 1.0:
        raise ValueError("robust_min_success_rate must be in (0, 1]")
    if config.decision_rule not in {"any", "robust"}:
        raise ValueError("decision_rule must be 'any' or 'robust'")
    if not config.seeds or not config.final_seeds:
        raise ValueError("search and final seeds must be non-empty")
    if min(config.max_evaluations, config.restarts, config.final_max_evaluations, config.final_restarts) <= 0:
        raise ValueError("evaluation budgets and restart counts must be positive")
    if config.workers <= 0:
        raise ValueError("workers must be positive")
    if min(config.time_limit, config.final_time_limit) < 0:
        raise ValueError("time limits must be non-negative")


def outline_side(instance: Instance, dead_space_ratio: float) -> float:
    return square_side(instance, dead_space_ratio)


def ratio_key(value: float) -> float:
    """Avoid duplicate threshold attempts caused by binary floating-point noise."""
    return round(value, 12)


def rounded_midpoint(low: float, high: float, precision: float) -> float:
    midpoint = ratio_key((low + high) / 2.0)
    if math.isclose(midpoint, low) or math.isclose(midpoint, high):
        return high
    return midpoint
