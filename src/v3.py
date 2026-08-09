"""Fail-closed V3 planning, execution isolation, and result summaries.

The existing Q1--Q4 CLIs remain the only search implementations.  This module
only freezes their invocation contract and makes an execution plan; callers
must pass ``execute=True`` explicitly before any subprocess is started.
"""

from __future__ import annotations

import argparse
import ast
import csv
from dataclasses import dataclass, replace
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import statistics
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Iterable, Mapping, Sequence

from .Q1.__main__ import _code_hash as q1_code_hash, _config_hash as q1_config_hash
from .Q1.p1_p2 import Q1SearchConfig
from .Q2.__main__ import (
    _code_hash as q2_code_hash,
    _config_hash as q2_config_hash,
)
from .Q2.common import Q2SearchConfig
from .Q3.__main__ import _code_hash as q3_code_hash, _config_hash as q3_config_hash
from .Q3.common import Q3SearchConfig


ROOT = Path(__file__).resolve().parents[1]
COLD_SEEDS = tuple(range(2201, 2221))
FINAL_SEEDS = tuple(range(2301, 2321))
Q1_CANDIDATES = ("Q1-G", "Q1-SP", "Q1-BT", "Q1-BT-D")
Q1_ABLATION_CANDIDATES = ("Q1-BT-directed-only", "Q1-BT-dedup-only", "Q1-BT-both")
Q2_CANDIDATES = ("P0", "P1", "P2")
Q3_CANDIDATES = ("Q3-BIN", "Q3-LIN", "Q3-CONT-R")
HASH_RE = __import__("re").compile(r"^[0-9a-f]{64}$")
ATTEMPT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
RESERVED_ATTEMPTS = {".", "..", "base", "final", "root", "runtime", "tables", "outputs", "con", "prn", "nul", "aux"}
FROZEN_MANIFEST_PATH = ROOT / "outputs" / "v3_frozen_manifest.json"


class FreezeError(ValueError):
    """Raised when a proposed run differs from the registered protocol."""


@dataclass(frozen=True)
class FreezeSpec:
    problem: str
    instance: str
    candidates: tuple[str, ...]
    code_hashes: Mapping[str, str]
    config_hashes: Mapping[str, str]
    data_hash: str
    seeds: tuple[int, ...]
    budgets: Mapping[str, Any]
    processes: int
    threads: int
    workers: int
    rng: str
    stop_conditions: tuple[str, ...]
    output_root: str
    final_seeds: tuple[int, ...] = ()
    q2_v3_baseline: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "problem": self.problem,
            "instance": self.instance,
            "candidates": list(self.candidates),
            "code_hashes": dict(self.code_hashes),
            "config_hashes": dict(self.config_hashes),
            "data_hash": self.data_hash,
            "seeds": list(self.seeds),
            "final_seeds": list(self.final_seeds),
            "budgets": dict(self.budgets),
            "processes": self.processes,
            "threads": self.threads,
            "workers": self.workers,
            "rng": self.rng,
            "stop_conditions": list(self.stop_conditions),
            "output_root": self.output_root,
            "q2_v3_baseline": self.q2_v3_baseline,
        }


@dataclass(frozen=True)
class CommandPlan:
    command: tuple[str, ...]
    marker: Path
    fingerprint: Mapping[str, Any] | None = None
    env: Mapping[str, str] | None = None
    auxiliary_markers: tuple[Path, ...] = ()


def _normal_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def file_manifest(paths: Iterable[Path], root: Path = ROOT) -> list[dict[str, Any]]:
    rows = []
    for path in paths:
        data = _normal_bytes(path)
        rows.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return rows


def manifest_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _config_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _q1_configs() -> dict[str, Q1SearchConfig]:
    common = {"max_evaluations": 100_000, "time_limit": 180.0, "restarts": 4}
    return {
        "Q1-G": Q1SearchConfig(candidate="Q1-G", **common),
        "Q1-SP": Q1SearchConfig(candidate="Q1-SP", **common),
        "Q1-BT": Q1SearchConfig(candidate="Q1-BT", **common),
        "Q1-BT-D": Q1SearchConfig(candidate="Q1-BT-D", directed_moves=True, state_dedup=True, **common),
        "Q1-BT-directed-only": Q1SearchConfig(candidate="Q1-BT", directed_moves=True, state_dedup=False, **common),
        "Q1-BT-dedup-only": Q1SearchConfig(candidate="Q1-BT", directed_moves=False, state_dedup=True, **common),
        "Q1-BT-both": Q1SearchConfig(candidate="Q1-BT", directed_moves=True, state_dedup=True, **common),
    }


def _q2_configs() -> dict[str, Q2SearchConfig]:
    common = {"max_evaluations": 30_000, "time_limit": 180.0, "restarts": 4, "initialization_mode": "shelf"}
    return {
        "P0": Q2SearchConfig(candidate="Q2-SP", adaptive_constraints=False, hypergraph_init=False, sa_schedule="classic", **common),
        "P1": Q2SearchConfig(candidate="Q2-BT", adaptive_constraints=True, hypergraph_init=False, sa_schedule="fast", **common),
        "P2": Q2SearchConfig(candidate="Q2-HG", adaptive_constraints=True, hypergraph_init=True, sa_schedule="fast", **common),
    }


def _q3_configs() -> dict[str, Q3SearchConfig]:
    common = {
        "inner_candidate": "Q2-HG",
        "lower_ratio": 0.0,
        "upper_ratio": 0.15,
        "precision": 0.005,
        "robust_min_success_rate": 0.8,
        "decision_rule": "robust",
        "seeds": COLD_SEEDS,
        "max_evaluations": 30_000,
        "time_limit": 60.0,
        "restarts": 4,
        "workers": 5,
        "adaptive_constraints": True,
        "hypergraph_init": True,
        "final_seeds": FINAL_SEEDS,
        "final_max_evaluations": 30_000,
        "final_time_limit": 60.0,
        "final_restarts": 4,
    }
    return {
        "Q3-BIN": Q3SearchConfig(candidate="Q3-BIN", continuous_compression=False, **common),
        "Q3-LIN": Q3SearchConfig(candidate="Q3-LIN", continuous_compression=False, **common),
        "Q3-CONT-R": Q3SearchConfig(candidate="Q3-CONT-R", continuous_compression=True, **common),
    }


def build_specs(root: Path = ROOT, output_root: str = "outputs") -> dict[str, FreezeSpec]:
    """Build current-checkout specs; all hashes are calculated from bytes now."""
    data_root = root / "data" / "raw" / "附件"
    blocks = data_root / "n200.blocks"
    q2_data = file_manifest([blocks, data_root / "n200.nets", data_root / "n200.pl"], root)
    q1_data = file_manifest([blocks], root)
    q1_configs = _q1_configs()
    q2_configs = _q2_configs()
    q3_configs = _q3_configs()
    common_stop = ("max_evaluations", "wall_clock", "uncaught_exception", "preserve_failure_status")
    return {
        "q1": FreezeSpec(
            "q1", "n200", Q1_CANDIDATES,
            {name: q1_code_hash() for name in q1_configs},
            {name: q1_config_hash(config) for name, config in q1_configs.items()},
            q1_data[0]["sha256"], COLD_SEEDS, {"max_evaluations": 100_000, "time_limit": 180.0, "restarts": 4},
            1, 1, 8, "random.Random (CPython MT19937)", common_stop, str(Path(output_root) / "q1" / "_runtime" / "v3_n200"),
        ),
        "q2": FreezeSpec(
            "q2", "n200", Q2_CANDIDATES,
            {name: q2_code_hash() for name in q2_configs},
            {name: q2_config_hash(config) for name, config in q2_configs.items()},
            manifest_hash(q2_data), COLD_SEEDS, {"max_evaluations": 30_000, "time_limit": 180.0, "restarts": 4},
            1, 1, 1, "random.Random (CPython MT19937)", common_stop, str(Path(output_root) / "q2" / "_runtime" / "v3_n200"), q2_v3_baseline="B",
        ),
        "q3": FreezeSpec(
            "q3", "n200", Q3_CANDIDATES,
            {name: q3_code_hash() for name in q3_configs},
            {name: q3_config_hash(config) for name, config in q3_configs.items()},
            manifest_hash(q2_data), COLD_SEEDS, {"max_evaluations": 30_000, "time_limit": 60.0, "restarts": 4},
            1, 1, 5, "random.Random (CPython MT19937)", common_stop, str(Path(output_root) / "q3" / "_runtime" / "v3_n200"), FINAL_SEEDS,
        ),
    }


def _code_paths(problem: str, root: Path = ROOT) -> tuple[Path, ...]:
    internal = tuple(root / "src" / "_internal" / name for name in ("parser.py", "evaluator.py", "audit.py", "geometry.py"))
    q1 = (root / "src" / "Q1" / "__init__.py", root / "src" / "Q1" / "__main__.py", root / "src" / "Q1" / "p0.py", root / "src" / "Q1" / "p1_p2.py")
    q2 = (root / "src" / "Q2" / name for name in ("__init__.py", "__main__.py", "common.py", "p0.py", "p1_p2.py", "summarize.py"))
    q3 = (root / "src" / "Q3" / name for name in ("__init__.py", "__main__.py", "common.py", "search.py"))
    v3 = (root / "src" / "v3.py",)
    if problem == "q1":
        return v3 + q1 + internal
    if problem == "q2":
        return v3 + tuple(q2) + (root / "src" / "Q1" / "p0.py", root / "src" / "Q1" / "p1_p2.py") + internal
    if problem == "q3":
        return v3 + tuple(q3) + tuple(q2) + q1[2:] + internal
    if problem == "q4":
        q4 = tuple(root / "src" / "Q4" / name for name in ("__init__.py", "__main__.py", "geometry.py", "model.py", "sa.py", "search.py"))
        return v3 + q4 + (root / "src" / "_internal" / "audit.py",)
    raise FreezeError(f"unsupported problem: {problem}")


def _data_paths(problem: str, root: Path = ROOT) -> tuple[Path, ...]:
    data_root = root / "data" / "raw" / "附件"
    if problem == "q1":
        return (data_root / "n200.blocks",)
    if problem in {"q2", "q3"}:
        return tuple(data_root / f"n200{suffix}" for suffix in (".blocks", ".nets", ".pl"))
    return ()


def runtime_environment(spec: FreezeSpec, *, python: str = sys.executable) -> dict[str, Any]:
    return {
        "python_executable": str(Path(python).resolve()),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "os": platform.system(),
        "platform": platform.platform(),
        "logical_cpu_count": os.cpu_count(),
        "processes": spec.processes,
        "threads": spec.threads,
        "workers": spec.workers,
        "omp_num_threads": "1",
        "mkl_num_threads": "1",
        "openblas_num_threads": "1",
        "rng": spec.rng,
    }


def registered_payload(spec: FreezeSpec, root: Path = ROOT, *, python: str = sys.executable) -> dict[str, Any]:
    code_files = file_manifest(_code_paths(spec.problem, root), root)
    data_files = file_manifest(_data_paths(spec.problem, root), root)
    configs = {}
    if spec.problem == "q1":
        configs = {name: config.as_dict() for name, config in _q1_configs().items()}
    elif spec.problem == "q2":
        configs = {name: config.as_dict() for name, config in _q2_configs().items()}
    elif spec.problem == "q3":
        configs = {name: config.as_dict() for name, config in _q3_configs().items()}
    plans = build_plan(spec, python=python)
    commands = []
    seen_command_keys: set[str] = set()
    for plan in plans:
        key = str((plan.fingerprint or {}).get("config_id"))
        if key in seen_command_keys:
            continue
        seen_command_keys.add(key)
        command = list(plan.command)
        if "--seed" in command:
            command[command.index("--seed") + 1] = "<registered-seed>"
        commands.append({"config_id": key, "command": command,
                         "seed_set": list(spec.seeds), "final_seed_set": list(spec.final_seeds),
                         "auxiliary_suffixes": [path.name for path in plan.auxiliary_markers]})
    return {
        "spec": spec.as_dict(),
        "code_files": code_files,
        "code_manifest_hash": manifest_hash(code_files),
        "data_files": data_files,
        "data_manifest_hash": manifest_hash(data_files) if data_files else None,
        "configs": configs,
        "environment": runtime_environment(spec, python=python),
        "commands": commands,
    }


def load_frozen_manifest(path: Path = FROZEN_MANIFEST_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FreezeError(f"missing immutable V3 manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def q4_extension_checklist(root: Path = ROOT) -> dict[str, Any]:
    """Return the independently frozen integer-domain Q4 extension matrix."""
    code_files = file_manifest(_code_paths("q4", root), root)
    code_hash = manifest_hash(code_files)
    configurations = {}
    for geometry, thickness in (("G-", 1), ("G0", 2), ("G+", 3)):
        for domain in ((9, 9), (12, 12)):
            for mode in ("exact", "sa"):
                key = f"{geometry}_{domain[0]}x{domain[1]}_{mode}"
                config = {
                    "geometry": geometry, "b1_beam_thickness": thickness,
                    "domain": list(domain), "mode": mode, "rotations": [0, 90, 180, 270], "grid_step": 1,
                }
                if mode == "exact":
                    config.update({"upper_area": 36, "time_limit": 300.0})
                else:
                    config.update({"max_evaluations": [10000, 30000, 60000], "time_limits": [60.0, 120.0], "seeds": list(COLD_SEEDS), "restarts": 4})
                configurations[key] = {"config": config, "config_hash": _config_digest(config)}
    return {
        "problem": "q4",
        "selection_scope": "geometry_budget_domain_sensitivity_only",
        "geometry_confirmed": True,
        "integer_domain_confirmed": True,
        "continuous_domain_confirmed": False,
        "code_hash": code_hash,
        "code_files": code_files,
        "configurations": configurations,
        "config_hash": manifest_hash([{"path": key, **value} for key, value in configurations.items()]),
        "data_hash": None,
        "environment": {
            "python_executable": str(Path(sys.executable).resolve()),
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "os": platform.system(),
            "platform": platform.platform(),
            "logical_cpu_count": os.cpu_count(),
            "workers": 1,
            "threads": 1,
            "omp_num_threads": "1",
            "mkl_num_threads": "1",
            "openblas_num_threads": "1",
        },
        "status": "frozen_integer_domain_pending_main_run_review",
    }


def check_q4_extension(manifest: Mapping[str, Any]) -> None:
    if manifest.get("problem") != "q4" or manifest.get("selection_scope") != "geometry_budget_domain_sensitivity_only":
        raise FreezeError("Q4 extension is independent of n200 selection")
    if not manifest.get("geometry_confirmed") or not manifest.get("integer_domain_confirmed") or manifest.get("continuous_domain_confirmed"):
        raise FreezeError("Q4 requires confirmed integer domain and must not claim continuous domain")
    for key in ("code_hash", "config_hash"):
        _require_hash(f"q4.{key}", manifest.get(key))
    if manifest.get("n200_selection") or manifest.get("n300_selection"):
        raise FreezeError("Q4 extension cannot be labelled n200/n300 selection")


def check_q4_registered(root: Path = ROOT) -> dict[str, Any]:
    actual = q4_extension_checklist(root)
    frozen = load_frozen_manifest().get("q4")
    if not isinstance(frozen, Mapping) or actual != frozen:
        raise FreezeError("Q4 checklist differs from immutable registration")
    check_q4_extension(actual)
    return actual


def _require_hash(name: str, value: Any) -> None:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise FreezeError(f"{name} must be a complete lowercase 64-hex SHA-256")


def check_freeze(actual: Mapping[str, Any], expected: FreezeSpec, *, dry_run: bool = False) -> None:
    """Fail closed on every registered field before a formal command starts."""
    problem = actual.get("problem")
    if problem != expected.problem:
        raise FreezeError(f"problem mismatch: {problem!r} != {expected.problem!r}")
    instance = actual.get("instance")
    if instance == "n300":
        raise FreezeError("n300 is not a V3 tuning/selection target")
    if instance != expected.instance and not dry_run:
        raise FreezeError(f"formal instance must be {expected.instance}")
    if tuple(actual.get("candidates", ())) != expected.candidates:
        raise FreezeError("candidate registration/order mismatch")
    if tuple(actual.get("seeds", ())) != expected.seeds:
        raise FreezeError("cold seed set mismatch")
    if tuple(actual.get("final_seeds", ())) != expected.final_seeds:
        raise FreezeError("final seed set mismatch")
    if actual.get("budgets") != dict(expected.budgets):
        raise FreezeError("budget mismatch")
    for key in ("processes", "threads", "workers", "rng", "stop_conditions", "output_root"):
        expected_value = getattr(expected, key)
        actual_value = actual.get(key)
        if key == "stop_conditions":
            actual_value = tuple(actual_value or ())
        if actual_value != expected_value:
            raise FreezeError(f"{key} mismatch")
    if expected.problem == "q2" and actual.get("q2_v3_baseline") != "B":
        raise FreezeError("Q2 V3 baseline must be confirmed as B")
    _require_hash("data_hash", actual.get("data_hash"))
    if actual.get("data_hash") != expected.data_hash:
        raise FreezeError("data_hash mismatch")
    for field in ("code_hashes", "config_hashes"):
        actual_hashes = actual.get(field)
        expected_hashes = getattr(expected, field)
        if not isinstance(actual_hashes, Mapping) or set(actual_hashes) != set(expected_hashes):
            raise FreezeError(f"{field} registration mismatch")
        for key, value in actual_hashes.items():
            _require_hash(f"{field}.{key}", value)
            if value != expected_hashes[key]:
                raise FreezeError(f"{field}.{key} mismatch")
    if not expected.output_root or str(expected.output_root).replace("\\", "/").endswith("/final"):
        raise FreezeError("formal output must not target a final directory")


def check_registered(actual: Mapping[str, Any], frozen: Mapping[str, Any]) -> None:
    """Compare a fresh checkout payload with an immutable registered JSON."""
    expected = frozen.get("spec")
    if not isinstance(expected, Mapping):
        raise FreezeError("frozen manifest has no spec")
    if actual.get("spec") != dict(expected):
        raise FreezeError("runtime spec differs from immutable registration")
    for field in ("code_files", "data_files", "configs", "environment", "commands"):
        if actual.get(field) != frozen.get(field):
            raise FreezeError(f"runtime {field} differs from immutable registration")
    for field in ("code_manifest_hash", "data_manifest_hash"):
        value = actual.get(field)
        if value is not None:
            _require_hash(field, value)
        if value != frozen.get(field):
            raise FreezeError(f"runtime {field} differs from immutable registration")
    for item in actual.get("code_files", ()):
        _require_hash(f"code_files[{item.get('path')}].sha256", item.get("sha256"))
    for item in actual.get("data_files", ()):
        _require_hash(f"data_files[{item.get('path')}].sha256", item.get("sha256"))


def write_once(path: Path, value: Mapping[str, Any]) -> None:
    """Write a manifest once; an identical rerun is idempotent."""
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise FreezeError(f"refusing to overwrite existing record: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="") as stream:
            stream.write(payload)
    except FileExistsError as exc:
        raise FreezeError(f"concurrent manifest creation: {path}") from exc


def _range_arg(values: Sequence[int]) -> str:
    return f"{values[0]}-{values[-1]}" if values == tuple(range(values[0], values[-1] + 1)) else ",".join(map(str, values))


def validate_attempt_slug(attempt: str | None) -> None:
    if attempt is None:
        return
    if not isinstance(attempt, str) or not ATTEMPT_RE.fullmatch(attempt) or attempt in RESERVED_ATTEMPTS or ".." in attempt:
        raise FreezeError("attempt must be a non-reserved short slug without path traversal")


def build_plan(
    spec: FreezeSpec, *, python: str = sys.executable, raw: str = "data/raw/附件", attempt: str | None = None,
) -> tuple[CommandPlan, ...]:
    """Build isolated CLI calls without running them."""
    validate_attempt_slug(attempt)
    base_root = Path(spec.output_root).resolve()
    root = (base_root / attempt).resolve() if attempt else base_root
    if root != base_root and base_root not in root.parents:
        raise FreezeError("attempt output escapes frozen output_root")
    thread_env = {"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1"}
    plans: list[CommandPlan] = []
    if spec.problem == "q1":
        for config_id in spec.config_hashes:
            candidate = config_id if config_id in Q1_CANDIDATES else "Q1-BT"
            flags = []
            if config_id.endswith("directed-only") or config_id.endswith("-both") or config_id == "Q1-BT-D":
                flags += ["--directed-moves", "on"]
            if config_id.endswith("dedup-only") or config_id.endswith("-both") or config_id == "Q1-BT-D":
                flags += ["--state-dedup", "on"]
            for seed in spec.seeds:
                command = (python, "-B", "-m", "src.Q1", "run", "--instance", spec.instance,
                           "--candidate", candidate, "--seed", str(seed), "--max-evaluations", str(spec.budgets["max_evaluations"]),
                           "--time-limit", str(spec.budgets["time_limit"]), "--restarts", str(spec.budgets["restarts"]),
                           "--raw", raw, "--output-root", str(root), "--config-id", config_id, *flags)
                plans.append(CommandPlan(
                    command,
                    root / spec.instance / config_id / f"seed_{seed}" / "events.jsonl",
                    {"problem": "q1", "instance": spec.instance, "config_id": config_id, "seed": seed,
                     "code_hash": spec.code_hashes[config_id], "config_hash": spec.config_hashes[config_id], "data_hash": spec.data_hash,
                     "attempt": attempt or "base", "command": list(command), "environment": runtime_environment(spec, python=python)},
                    thread_env,
                ))
    elif spec.problem == "q2":
        settings = {"P0": ("Q2-SP", "off", "off"), "P1": ("Q2-BT", "on", "off"), "P2": ("Q2-HG", "on", "on")}
        for config_id in spec.candidates:
            candidate, adaptive, hypergraph = settings[config_id]
            for seed in spec.seeds:
                command = (python, "-B", "-m", "src.Q2", "run", "--instance", spec.instance,
                           "--candidate", candidate, "--seed", str(seed), "--max-evaluations", str(spec.budgets["max_evaluations"]),
                           "--time-limit", str(spec.budgets["time_limit"]), "--restarts", str(spec.budgets["restarts"]),
                           "--adaptive-constraints", adaptive, "--hypergraph-init", hypergraph, "--initialization-mode", "shelf",
                           "--raw", raw, "--output-root", str(root), "--config-id", config_id)
                plans.append(CommandPlan(
                    command,
                    root / spec.instance / config_id / f"seed_{seed}" / "events.jsonl",
                    {"problem": "q2", "instance": spec.instance, "config_id": config_id, "seed": seed,
                     "code_hash": spec.code_hashes[config_id], "config_hash": spec.config_hashes[config_id], "data_hash": spec.data_hash,
                     "q2_v3_baseline": spec.q2_v3_baseline, "attempt": attempt or "base", "command": list(command), "environment": runtime_environment(spec, python=python)},
                    thread_env,
                ))
    elif spec.problem == "q3":
        for candidate in spec.candidates:
            run_id = f"v3_n200_{candidate.lower()}"
            command = (python, "-B", "-m", "src.Q3", "--instance", spec.instance, "--candidate", candidate,
                       "--inner-candidate", "Q2-HG", "--lower-ratio", "0", "--upper-ratio", "0.15", "--precision", "0.005",
                       "--robust-min-success-rate", "0.8", "--decision-rule", "robust", "--seeds", _range_arg(spec.seeds),
                       "--max-evaluations", str(spec.budgets["max_evaluations"]), "--time-limit", str(spec.budgets["time_limit"]),
                       "--restarts", str(spec.budgets["restarts"]), "--workers", str(spec.workers), "--adaptive-constraints", "on",
                       "--hypergraph-init", "on", "--continuous-compression", "on" if candidate == "Q3-CONT-R" else "off",
                       "--final-seeds", _range_arg(spec.final_seeds), "--final-max-evaluations", str(spec.budgets["max_evaluations"]),
                       "--final-time-limit", str(spec.budgets["time_limit"]), "--final-restarts", str(spec.budgets["restarts"]),
                       "--raw", raw, "--runtime-root", str(root / "runtime"), "--table-root", str(root / "tables"), "--run-id", run_id)
            plans.append(CommandPlan(
                command,
                root / "runtime" / spec.instance / run_id / "result.json",
                {"problem": "q3", "instance": spec.instance, "config_id": candidate,
                 "cold_seeds": list(spec.seeds), "final_seeds": list(spec.final_seeds),
                 "code_hash": spec.code_hashes[candidate], "config_hash": spec.config_hashes[candidate], "data_hash": spec.data_hash,
                 "attempt": attempt or "base", "command": list(command), "environment": runtime_environment(spec, python=python)},
                thread_env,
                (root / "tables" / f"{run_id}_attempts.csv", root / "tables" / f"{run_id}_config_snapshot.json"),
            ))
    else:
        raise FreezeError(f"unsupported problem: {spec.problem}")
    return tuple(plans)


def _json_lines(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FreezeError(f"invalid JSON marker row: {path}") from exc
            if not isinstance(value, dict):
                raise FreezeError(f"marker row is not an object: {path}")
            rows.append(value)
    if not rows:
        raise FreezeError(f"empty marker: {path}")
    return rows


def _q3_expected_attempt_keys(payload: Mapping[str, Any]) -> set[tuple[str, Any, Any]]:
    keys: set[tuple[str, Any, Any]] = set()
    for threshold in payload.get("attempts", ()):
        ratio = threshold.get("dead_space_ratio")
        for item in threshold.get("seed_attempts", ()):
            keys.add(("threshold", ratio, item.get("seed")))
    for item in payload.get("final_attempts", ()):
        keys.add(("final", payload.get("selected_ratio"), item.get("seed")))
    return keys


def _validate_q3_auxiliary(payload: Mapping[str, Any], plan: CommandPlan) -> None:
    if len(plan.auxiliary_markers) != 2:
        raise FreezeError(f"Q3 requires attempts and config snapshot markers: {plan.marker}")
    attempts_path, snapshot_path = plan.auxiliary_markers
    try:
        with attempts_path.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except (OSError, csv.Error) as exc:
        raise FreezeError(f"invalid Q3 attempts table: {attempts_path}") from exc
    if not rows or "phase" not in rows[0] or "seed" not in rows[0]:
        raise FreezeError(f"incomplete Q3 attempts table: {attempts_path}")
    actual_keys = set()
    for row in rows:
        try:
            seed = int(row["seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise FreezeError(f"invalid Q3 attempts seed: {attempts_path}") from exc
        phase = row.get("phase")
        ratio = row.get("dead_space_ratio")
        if phase in {"threshold", "final"}:
            try:
                ratio = round(float(ratio), 12)
            except (TypeError, ValueError) as exc:
                raise FreezeError(f"invalid Q3 threshold ratio: {attempts_path}") from exc
        actual_keys.add((phase, ratio, seed))
    expected_keys = _q3_expected_attempt_keys(payload)
    normalized_expected = {(phase, round(float(ratio), 12) if ratio is not None else ratio, seed) for phase, ratio, seed in expected_keys}
    if actual_keys != normalized_expected:
        raise FreezeError(f"Q3 attempts table does not match result attempts: {attempts_path}")
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError(f"invalid Q3 config snapshot: {snapshot_path}") from exc
    if not isinstance(snapshot, dict):
        raise FreezeError(f"Q3 config snapshot is not an object: {snapshot_path}")
    for key in ("problem", "instance", "run_id", "code_hash", "config_hash", "data_hash", "status", "config", "attempts", "final_attempts"):
        if snapshot.get(key) != payload.get(key):
            raise FreezeError(f"Q3 config snapshot {key} mismatch: {snapshot_path}")


def _validate_completed(plan: CommandPlan) -> dict[str, Any]:
    """Validate a completed marker and every Q3 auxiliary table before skip."""
    if plan.fingerprint is None:
        raise FreezeError(f"missing freeze fingerprint: {plan.marker}")
    sidecar = plan.marker.parent / "v3_freeze.json"
    try:
        if json.loads(sidecar.read_text(encoding="utf-8")) != dict(plan.fingerprint):
            raise FreezeError(f"freeze sidecar mismatch: {sidecar}")
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError(f"invalid freeze sidecar: {sidecar}") from exc
    if plan.marker.suffix == ".jsonl":
        rows = _json_lines(plan.marker)
        if len(rows) != 1:
            raise FreezeError(f"duplicate or repeated marker rows: {plan.marker}")
        record = rows[-1]
        required = ("problem", "instance", "config_id", "seed", "code_hash", "config_hash", "data_hash", "status", "formal_audit_match")
        if any(key not in record for key in required):
            raise FreezeError(f"incomplete run marker: {plan.marker}")
        for key in ("instance", "config_id", "seed", "code_hash", "config_hash", "data_hash"):
            if record.get(key) != plan.fingerprint.get(key):
                raise FreezeError(f"run marker {key} mismatch: {plan.marker}")
        if str(record.get("problem", "")).lower() != str(plan.fingerprint.get("problem", "")).lower():
            raise FreezeError(f"run marker problem mismatch: {plan.marker}")
        if not isinstance(record.get("formal_audit_match"), bool):
            raise FreezeError(f"run marker audit flag is not boolean: {plan.marker}")
        return record
    try:
        payload = json.loads(plan.marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeError(f"invalid Q3 result marker: {plan.marker}") from exc
    if not isinstance(payload, dict) or payload.get("problem") != "Q3":
        raise FreezeError(f"incomplete Q3 result marker: {plan.marker}")
    for key in ("instance", "code_hash", "config_hash", "data_hash", "config", "attempts", "final_attempts", "status"):
        if key not in payload:
            raise FreezeError(f"Q3 result missing {key}: {plan.marker}")
    for key in ("instance", "code_hash", "config_hash", "data_hash"):
        if payload.get(key) != plan.fingerprint.get(key):
            raise FreezeError(f"Q3 result {key} mismatch: {plan.marker}")
    config = payload["config"]
    if config.get("candidate") != plan.fingerprint["config_id"]:
        raise FreezeError(f"Q3 candidate mismatch: {plan.marker}")
    if tuple(config.get("seeds", ())) != tuple(plan.fingerprint["cold_seeds"]):
        raise FreezeError(f"Q3 cold seed set mismatch: {plan.marker}")
    if tuple(config.get("final_seeds", ())) != tuple(plan.fingerprint["final_seeds"]):
        raise FreezeError(f"Q3 final seed set mismatch: {plan.marker}")
    cold_by_ratio: dict[Any, list[int]] = {}
    for threshold in payload["attempts"]:
        ratio = threshold.get("dead_space_ratio")
        if ratio in cold_by_ratio:
            raise FreezeError(f"Q3 duplicate threshold: {ratio}")
        attempts = threshold.get("seed_attempts", ())
        cold = [item.get("seed") for item in attempts if item.get("mode") == "cold"]
        if len(cold) != len(plan.fingerprint["cold_seeds"]) or tuple(cold) != tuple(plan.fingerprint["cold_seeds"]):
            raise FreezeError(f"Q3 threshold cold seed set mismatch at {ratio}: {plan.marker}")
        cold_by_ratio[ratio] = cold
    if config.get("candidate") == "Q3-LIN":
        expected_ratios = {round(index * 0.005, 12) for index in range(31)}
        actual_ratios = {round(float(value), 12) for value in cold_by_ratio}
        if actual_ratios != expected_ratios:
            raise FreezeError(f"Q3-LIN requires complete 0.005 grid: {plan.marker}")
    final = [item.get("seed") for item in payload["final_attempts"] if item.get("mode") == "final_cold"]
    if tuple(final) != tuple(plan.fingerprint["final_seeds"]):
        raise FreezeError(f"Q3 final seed set mismatch: {plan.marker}")
    _validate_q3_auxiliary(payload, plan)
    return payload


def _preflight_plan(plan: CommandPlan) -> bool:
    """Validate one output slot without creating files or starting a child."""
    parent = plan.marker.parent
    if plan.marker.exists():
        _validate_completed(plan)
        return True
    if parent.exists() and not parent.is_dir():
        raise FreezeError(f"output parent is not a directory: {parent}")
    if parent.is_dir() and any(parent.iterdir()):
        raise FreezeError(f"partial output exists; refusing overwrite: {parent}")
    for auxiliary in plan.auxiliary_markers:
        sibling_conflicts = tuple(auxiliary.parent.glob(f"{auxiliary.stem}*")) if auxiliary.parent.is_dir() else ()
        if auxiliary.exists() or sibling_conflicts:
            raise FreezeError(f"partial auxiliary output exists; refusing overwrite: {auxiliary}")
    return False


def _execute_one(index: int, plan: CommandPlan, cwd: Path) -> dict[str, Any]:
    """Execute one already-preflighted plan and retain every failure state."""
    parent = plan.marker.parent
    status: dict[str, Any] = {"index": index, "command": list(plan.command), "marker": plan.marker.as_posix()}
    try:
        parent.mkdir(parents=True, exist_ok=True)
        if plan.fingerprint is not None:
            write_once(parent / "v3_freeze.json", plan.fingerprint)
        child_env = os.environ.copy()
        if plan.env:
            child_env.update(plan.env)
        completed = subprocess.run(plan.command, cwd=cwd, env=child_env, capture_output=True, text=True, check=False)
        status.update({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr})
    except Exception as exc:  # retain spawn/IO failures; retry is an explicit new attempt
        status.update({"returncode": None, "stdout": "", "stderr": "", "exception": f"{type(exc).__name__}: {exc}"})
        write_once(parent / "_orchestrator_status.json", status)
        return {"status": "failed_exception", **status}
    if plan.marker.exists():
        try:
            _validate_completed(plan)
            run_status = "completed" if status["returncode"] == 0 else "completed_failure"
        except Exception as exc:  # preserve invalid marker for audit instead of aborting siblings
            status["validation_error"] = f"{type(exc).__name__}: {exc}"
            run_status = "failed_invalid_marker"
    else:
        run_status = "failed_missing_marker"
    write_once(parent / "_orchestrator_status.json", status)
    return {"status": run_status, **status}


def _execute_parallel(todo: Sequence[tuple[int, CommandPlan]], workers: int, cwd: Path) -> list[dict[str, Any]]:
    """Keep at most ``workers`` futures in flight and stop submitting after interruption."""
    executor = ThreadPoolExecutor(max_workers=min(workers, len(todo)))
    futures: dict[Any, int] = {}
    pending = iter(todo)
    results: dict[int, dict[str, Any]] = {}

    def submit_one() -> None:
        try:
            index, plan = next(pending)
        except StopIteration:
            return
        futures[executor.submit(_execute_one, index, plan, cwd)] = index

    try:
        for _ in range(min(workers, len(todo))):
            submit_one()
        while futures:
            done, _ = wait(tuple(futures), return_when=FIRST_COMPLETED)
            for future in sorted(done, key=lambda item: futures[item]):
                index = futures.pop(future)
                results[index] = future.result()
                submit_one()
    except BaseException:
        for future in futures:
            future.cancel()
        executor.shutdown(wait=False, cancel_futures=True)
        raise
    executor.shutdown(wait=True)
    return [results[index] for index, _ in todo]


def execute_plan(plans: Sequence[CommandPlan], *, execute: bool = False, cwd: Path = ROOT) -> list[dict[str, Any]]:
    """Run isolated commands only with explicit consent; never overwrite records."""
    registered = tuple(plans)
    seen_markers: set[Path] = set()
    skipped: dict[int, dict[str, Any]] = {}
    todo: list[tuple[int, CommandPlan]] = []
    # Full preflight happens before any formal child starts, including Q1's 140 slots.
    for index, plan in enumerate(registered):
        marker = plan.marker.resolve()
        if marker in seen_markers:
            raise FreezeError(f"duplicate registered marker path: {plan.marker}")
        seen_markers.add(marker)
        if _preflight_plan(plan):
            skipped[index] = {"index": index, "status": "skipped_existing", "marker": plan.marker.as_posix()}
        else:
            todo.append((index, plan))
    if not execute:
        return [skipped.get(index, {"index": index, "status": "planned", "command": list(plan.command),
                                     "marker": plan.marker.as_posix()}) for index, plan in enumerate(registered)]
    workers = 1
    if todo and registered[0].fingerprint:
        environment = registered[0].fingerprint.get("environment", {})
        if registered[0].fingerprint.get("problem") == "q1":
            workers = max(1, int(environment.get("workers", 1)))
    results: list[dict[str, Any]] = list(skipped.values())
    if workers > 1 and len(todo) > 1:
        results.extend(_execute_parallel(todo, workers, cwd))
    else:
        results.extend(_execute_one(index, plan, cwd) for index, plan in todo)
    return sorted(results, key=lambda item: item["index"])


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def _spread(values: Sequence[float]) -> tuple[float | None, float | None, float | None]:
    if not values:
        return None, None, None
    if len(values) == 1:
        return values[0], values[0], 0.0
    quartiles = statistics.quantiles(values, n=4, method="inclusive")
    return statistics.median(values), _percentile(values, 0.9), quartiles[2] - quartiles[0]


def _status_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {f"status_{status}": sum(row.get("status") == status for row in rows) for status in ("success", "timeout", "no_feasible", "crash")}


def summarize_q1(rows: Sequence[Mapping[str, Any]], registered_seeds: Sequence[int] | None = None) -> list[dict[str, Any]]:
    summaries = _summarize_metric(rows, "area", "aspect_ratio", "Q1", registered_seeds)
    for summary in summaries:
        group = [row for row in rows if str(row.get("config_id")) == summary["config_id"]]
        legal_rows = [row for row in group if _bool(row.get("legal")) and _bool(row.get("formal_audit_match"))]
        area_values = [float(row["area"]) for row in legal_rows if row.get("area") not in (None, "")]
        aspect_values = [float(row["aspect_ratio"]) for row in legal_rows if row.get("aspect_ratio") not in (None, "")]
        summary["min_area"] = min(area_values) if area_values else None
        summary["max_area"] = max(area_values) if area_values else None
        summary["min_aspect_ratio"] = min(aspect_values) if aspect_values else None
        summary["max_aspect_ratio"] = max(aspect_values) if aspect_values else None
        values = [float(row["first_feasible_evaluation"]) for row in group if row.get("first_feasible_evaluation") not in (None, "")]
        summary["median_first_feasible_evaluation"] = statistics.median(values) if values else None
        summary["first_feasible_status"] = "complete" if values else "not_recorded_protocol_deviation"
    return summaries


def _q1_protocol_deviations(summaries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"config_id": summary.get("config_id"), "field": "first_feasible_evaluation",
             "status": "not_recorded_protocol_deviation", "runs": summary.get("runs", 0)}
            for summary in summaries if summary.get("first_feasible_status") == "not_recorded_protocol_deviation"]


def summarize_q2(rows: Sequence[Mapping[str, Any]], registered_seeds: Sequence[int] | None = None) -> list[dict[str, Any]]:
    summaries = _summarize_metric(rows, "HPWL", None, "Q2", registered_seeds)
    for summary in summaries:
        group = [row for row in rows if row.get("config_id") == summary["config_id"]]
        first_feasible = [float(row["first_feasible_evaluation"]) for row in group if row.get("first_feasible_evaluation") not in (None, "")]
        summary["median_first_feasible_evaluation"] = statistics.median(first_feasible) if first_feasible else None
        checkpoints = {str(point): [] for point in (25, 50, 75, 100)}
        for row in group:
            values = row.get("checkpoints") or row.get("checkpoint_best_hpwl") or {}
            for point in checkpoints:
                value = values.get(point, values.get(f"{point}%")) if isinstance(values, Mapping) else None
                if value not in (None, ""):
                    checkpoints[point].append(float(value))
        summary["checkpoint_median_best_so_far_HPWL"] = {point: statistics.median(values) if values else None for point, values in checkpoints.items()}
        summary["checkpoint_status"] = "complete" if all(checkpoints.values()) else "missing"
    return summaries


def summarize_q3(
    rows: Sequence[Mapping[str, Any]],
    registered_cold_seeds: Sequence[int] | None = None,
    registered_final_seeds: Sequence[int] | None = None,
) -> dict[str, Any]:
    cold = [row for row in rows if row.get("phase") == "threshold" and row.get("mode") == "cold"]
    warm = [row for row in rows if row.get("phase") == "threshold" and row.get("mode") == "warm"]
    final = [row for row in rows if row.get("phase") == "final" and row.get("mode") == "final_cold"]
    def legal_rate(group: Sequence[Mapping[str, Any]], denominator: int | None = None) -> float:
        return sum(_bool(row.get("legal")) and _bool(row.get("formal_audit_match")) for row in group) / (denominator or len(group)) if (group or denominator) else 0.0
    threshold_summary = []
    cold_with_ratio = [row for row in cold if row.get("dead_space_ratio") not in (None, "")]
    for ratio in sorted({row.get("dead_space_ratio") for row in cold_with_ratio}, key=lambda value: float(value)):
        group = [row for row in cold_with_ratio if row.get("dead_space_ratio") == ratio]
        threshold_summary.append({
            "dead_space_ratio": ratio,
            "cold_runs": len(group),
            "cold_legal_rate": legal_rate(group, len(registered_cold_seeds) if registered_cold_seeds is not None else None),
            "missing_cold_runs": max(0, len(registered_cold_seeds or ()) - len(group)),
            "robust": legal_rate(group, len(registered_cold_seeds) if registered_cold_seeds is not None else None) >= 0.8,
            "has_cold_legal": any(_bool(item.get("legal")) and _bool(item.get("formal_audit_match")) for item in group),
        })
    final_hpwl = [float(row["HPWL"]) for row in final if _bool(row.get("legal")) and _bool(row.get("formal_audit_match")) and row.get("HPWL") not in (None, "")]
    final_median, final_p90, final_iqr = _spread(final_hpwl)
    d_best_values = [float(item["dead_space_ratio"]) for item in threshold_summary if item["has_cold_legal"]]
    d_robust_values = [float(item["dead_space_ratio"]) for item in threshold_summary if item["robust"]]
    status_counts = _status_counts(rows)
    threshold_count = len(threshold_summary)
    cold_denominator = threshold_count * len(registered_cold_seeds) if registered_cold_seeds is not None else len(cold)
    cold_missing = max(0, cold_denominator - len(cold)) if registered_cold_seeds is not None else 0
    return {
        "threshold_cold_runs": len(cold),
        "threshold_count": threshold_count,
        "threshold_cold_registered_runs": cold_denominator,
        "threshold_cold_legal_rate": legal_rate(cold, cold_denominator),
        "threshold_cold_missing_runs": cold_missing,
        "threshold_warm_runs": len(warm),
        "final_runs": len(final),
        "final_legal_rate": legal_rate(final, len(registered_final_seeds) if registered_final_seeds is not None else None),
        "final_missing_runs": max(0, len(registered_final_seeds or ()) - len({row.get('seed') for row in final})) if registered_final_seeds is not None else 0,
        "final_median_HPWL": final_median,
        "final_p90_HPWL": final_p90,
        "final_iqr_HPWL": final_iqr,
        "d_best": min(d_best_values) if d_best_values else None,
        "d_robust": min(d_robust_values) if d_robust_values else None,
        "thresholds": threshold_summary,
        "warm_excluded_from_cold": True,
        "final_excluded_from_cold": True,
        "threshold_cold_status_counts": _status_counts(cold),
        "threshold_warm_status_counts": _status_counts(warm),
        "final_status_counts": _status_counts(final),
        "status_counts": status_counts,
    }


def q3_mechanical_decision(route_summaries: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Choose among complete routes by robust threshold, then final metrics."""
    route_rank = {"Q3-BIN": 0, "Q3-LIN": 1, "Q3-CONT-R": 2}
    routes = {name: dict(summary) for name, summary in route_summaries.items()}
    missing = [name for name in route_rank if name not in routes or routes[name].get("d_robust") is None]
    rankings = []
    for name in route_rank:
        item = routes.get(name, {})
        rankings.append({"route": name, "d_robust": item.get("d_robust"), "final_legal_rate": item.get("final_legal_rate"),
                         "final_median_HPWL": item.get("final_median_HPWL"), "final_iqr_HPWL": item.get("final_iqr_HPWL"),
                         "route_rank": route_rank[name]})
    if missing:
        return {"decision": "blocked_missing_route", "missing_routes": missing, "rankings": rankings, "selected": None}
    min_robust = min(float(item["d_robust"]) for item in rankings)
    robust_ties = [item for item in rankings if float(item["d_robust"]) - min_robust <= 0.005 + 1e-12]
    max_legal = max(float(item["final_legal_rate"]) for item in robust_ties if item["final_legal_rate"] is not None)
    legal_ok = [item for item in robust_ties if item["final_legal_rate"] is not None and float(item["final_legal_rate"]) >= max_legal - 0.05]
    finite_hpwl = [float(item["final_median_HPWL"]) for item in legal_ok if item["final_median_HPWL"] is not None]
    min_hpwl = min(finite_hpwl) if finite_hpwl else float("inf")
    hpwl_ok = [item for item in legal_ok if item["final_median_HPWL"] is not None and float(item["final_median_HPWL"]) <= min_hpwl * 1.01]
    selected = sorted(hpwl_ok or legal_ok or robust_ties, key=lambda item: (
        float(item["final_median_HPWL"]) if item["final_median_HPWL"] is not None else float("inf"),
        float(item["final_iqr_HPWL"]) if item["final_iqr_HPWL"] is not None else float("inf"), item["route_rank"],
    ))[0]
    for rank, item in enumerate(sorted(rankings, key=lambda row: (float(row["d_robust"]), row["route_rank"])), 1):
        item["robust_rank"] = rank
    return {"decision": "selected", "selected": selected["route"], "d_robust_priority": True,
            "robust_tie_routes": [item["route"] for item in robust_ties], "rankings": rankings,
            "final_legal_rate_noninferior": [item["route"] for item in legal_ok],
            "final_HPWL_noninferior": [item["route"] for item in hpwl_ok]}


def paired_differences(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    baseline: str,
    candidate: str,
) -> list[dict[str, Any]]:
    """Return same-seed differences; missing/failed values remain explicit."""
    left = {row.get("seed"): row for row in rows if row.get("config_id") == baseline}
    right = {row.get("seed"): row for row in rows if row.get("config_id") == candidate}
    output = []
    for seed in sorted(set(left) & set(right), key=lambda value: (value is None, value)):
        a, b = left[seed], right[seed]
        base_value, candidate_value = a.get(metric), b.get(metric)
        difference = None
        if base_value not in (None, "") and candidate_value not in (None, ""):
            difference = float(candidate_value) - float(base_value)
        output.append({"seed": seed, "baseline": baseline, "candidate": candidate,
                       "baseline_value": base_value, "candidate_value": candidate_value,
                       "difference_candidate_minus_baseline": difference})
    return output


def q1_mechanical_decision(summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {row.get("config_id"): row for row in summaries}
    missing_main = [config_id for config_id in Q1_CANDIDATES if config_id not in by_id]
    main_rows = [by_id[config_id] for config_id in Q1_CANDIDATES if config_id in by_id]
    hard_gate = not missing_main and all(
        row.get("legal_rate", 0.0) >= 0.90 and row.get("audit_match_runs") == 20 and row.get("missing_runs") == 0
        for row in main_rows
    )
    rankings = sorted(
        ({"config_id": row["config_id"], "median_area": row.get("median_area"),
          "median_aspect_ratio": row.get("median_aspect_ratio"),
          "legal_rate": row.get("legal_rate", 0.0), "eligible": hard_gate}
         for row in main_rows),
        key=lambda row: (row["median_area"] is None, row["median_area"] if row["median_area"] is not None else float("inf"),
                         row["median_aspect_ratio"] if row["median_aspect_ratio"] is not None else float("inf"), row["config_id"]),
    )
    for rank, row in enumerate(rankings, 1):
        row["rank"] = rank
    ablation_rows = [by_id[config_id] for config_id in Q1_ABLATION_CANDIDATES if config_id in by_id]
    ablation_completeness = {
        row["config_id"]: {"registered_runs": row.get("registered_runs", 0), "runs": row.get("runs", 0),
                            "missing_runs": row.get("missing_runs", 0), "audit_match_runs": row.get("audit_match_runs", 0),
                            "complete": row.get("missing_runs", 0) == 0 and row.get("audit_match_runs") == 20}
        for row in ablation_rows
    }
    ablation_comparisons = {
        row["config_id"]: {"baseline": "Q1-BT", "median_area": row.get("median_area"),
                           "median_aspect_ratio": row.get("median_aspect_ratio"),
                           "legal_rate": row.get("legal_rate", 0.0)}
        for row in ablation_rows
    }
    if missing_main:
        return {"decision": "blocked_missing_main_candidate", "hard_gate": False, "missing_main_candidates": missing_main,
                "rankings": rankings, "selected": None, "ablation_completeness": ablation_completeness,
                "ablation_comparisons": ablation_comparisons,
                "p2_ablation": "blocked_missing_main_candidate", "p2_legal_noninferior": None,
                "p2_area_noninferior": None, "p2_stability_gain": None}
    p1, p2 = by_id.get("Q1-BT"), by_id.get("Q1-BT-D")
    if not p1 or not p2 or p1.get("median_area") is None or p2.get("median_area") is None:
        return {"decision": "blocked_missing_ablation_baseline", "hard_gate": hard_gate, "rankings": rankings, "selected": None,
                "ablation_completeness": ablation_completeness, "ablation_comparisons": ablation_comparisons,
                "p2_ablation": "blocked_missing_ablation_baseline",
                "p2_legal_noninferior": None, "p2_area_noninferior": None, "p2_stability_gain": None}
    legal = p2["legal_rate"] >= p1["legal_rate"] - 0.05
    area = p2["median_area"] <= 1.01 * p1["median_area"]
    stability = ((p1.get("iqr_area") is not None and p2.get("iqr_area") is not None and p2["iqr_area"] <= 0.95 * p1["iqr_area"]) or
                 (p1.get("p90_area") is not None and p2.get("p90_area") is not None and p2["p90_area"] <= 0.99 * p1["p90_area"]))
    p2_ablation = "supports_p2" if hard_gate and legal and area and stability else "report_only"
    return {"decision": "selected" if hard_gate else "blocked_hard_gate", "hard_gate": hard_gate,
            "selected": rankings[0]["config_id"] if hard_gate and rankings else None, "rankings": rankings,
            "ablation_completeness": ablation_completeness, "ablation_comparisons": ablation_comparisons,
            "p2_ablation": p2_ablation,
            "p2_legal_noninferior": legal, "p2_area_noninferior": area, "p2_stability_gain": stability}


def q2_mechanical_decision(summaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_id = {row.get("config_id"): row for row in summaries}
    required = tuple(by_id)
    hard_gate = all(
        by_id.get(config_id, {}).get("legal_rate", 0.0) >= 0.90
        and by_id.get(config_id, {}).get("audit_match_runs") == 20
        and by_id.get(config_id, {}).get("missing_runs") == 0
        for config_id in required
    ) and bool(required)
    rankings = sorted(
        ({"config_id": config_id, "median_HPWL": by_id[config_id].get("median_HPWL"),
          "legal_rate": by_id[config_id].get("legal_rate", 0.0), "eligible": hard_gate}
         for config_id in required),
        key=lambda row: (row["median_HPWL"] is None, row["median_HPWL"] if row["median_HPWL"] is not None else float("inf"), row["config_id"]),
    )
    for rank, row in enumerate(rankings, 1):
        row["rank"] = rank
    p1, p2 = by_id.get("P1"), by_id.get("P2")
    if not p1 or not p2 or p1.get("median_HPWL") is None or p2.get("median_HPWL") is None:
        return {"decision": "blocked_missing_summary", "hard_gate": hard_gate, "rankings": rankings, "selected": None, "p2_same_budget": "blocked_missing_summary"}
    legal = p2["legal_rate"] >= p1["legal_rate"] - 0.05
    hpwl = p2["median_HPWL"] <= 1.01 * p1["median_HPWL"]
    better = p2["median_HPWL"] <= 0.99 * p1["median_HPWL"]
    checkpoints = p1.get("checkpoint_median_best_so_far_HPWL", {})
    candidate_checkpoints = p2.get("checkpoint_median_best_so_far_HPWL", {})
    checkpoint_better = sum(
        candidate_checkpoints.get(point) is not None and checkpoints.get(point) is not None and candidate_checkpoints[point] <= 0.99 * checkpoints[point]
        for point in ("25", "50", "75", "100")
    ) >= 3
    first_feasible = (p1.get("median_first_feasible_evaluation") is not None and p2.get("median_first_feasible_evaluation") is not None and
                      p2["median_first_feasible_evaluation"] <= p1["median_first_feasible_evaluation"])
    support = hard_gate and legal and hpwl and (better or first_feasible or checkpoint_better)
    return {"decision": "selected" if hard_gate else "blocked_hard_gate", "hard_gate": hard_gate,
            "selected": rankings[0]["config_id"] if hard_gate else None, "rankings": rankings,
            "p2_same_budget": "supports_p2" if support else "report_only", "legal": legal, "hpwl": hpwl,
            "better_hpwl": better, "first_feasible": first_feasible, "checkpoint_better": checkpoint_better}


def _summarize_metric(
    rows: Sequence[Mapping[str, Any]], metric: str, secondary: str | None, problem: str,
    registered_seeds: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    output = []
    for config_id in sorted({str(row.get("config_id")) for row in rows}):
        group = [row for row in rows if str(row.get("config_id")) == config_id]
        legal = [row for row in group if _bool(row.get("legal")) and _bool(row.get("formal_audit_match")) and row.get(metric) not in (None, "")]
        values = [float(row[metric]) for row in legal]
        median, p90, iqr = _spread(values)
        denominator = len(registered_seeds) if registered_seeds is not None else len(group)
        row = {"problem": problem, "config_id": config_id, "runs": len(group), "registered_runs": denominator,
               "missing_runs": max(0, denominator - len({item.get('seed') for item in group})) if registered_seeds is not None else 0,
               "legal_runs": len(legal), "legal_rate": len(legal) / denominator if denominator else 0.0,
               "audit_match_runs": sum(_bool(item.get("formal_audit_match")) for item in group),
               f"median_{metric}": median, f"p90_{metric}": p90, f"iqr_{metric}": iqr, **_status_counts(group)}
        if secondary:
            secondary_values = [float(item[secondary]) for item in legal if item.get(secondary) not in (None, "")]
            secondary_median, secondary_p90, secondary_iqr = _spread(secondary_values)
            row[f"median_{secondary}"] = secondary_median
            row[f"p90_{secondary}"] = secondary_p90
            row[f"iqr_{secondary}"] = secondary_iqr
        output.append(row)
    return output


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return [dict(row) for row in payload]
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return [dict(row) for row in payload["rows"]]
        if isinstance(payload, dict) and payload.get("problem") == "Q3":
            rows = []
            for threshold in payload.get("attempts", ()):
                for attempt in threshold.get("seed_attempts", ()):
                    rows.append({"phase": "threshold", "dead_space_ratio": threshold.get("dead_space_ratio"),
                                 "instance": payload.get("instance"), "config_id": payload.get("config", {}).get("candidate"),
                                 "code_hash": payload.get("code_hash"),
                                 "config_hash": payload.get("config_hash"), "data_hash": payload.get("data_hash"), **attempt})
            for attempt in payload.get("final_attempts", ()):
                rows.append({"phase": "final", "instance": payload.get("instance"),
                             "config_id": payload.get("config", {}).get("candidate"),
                             "code_hash": payload.get("code_hash"), "config_hash": payload.get("config_hash"),
                             "data_hash": payload.get("data_hash"), **attempt})
            return rows
        raise FreezeError(f"unsupported JSON summary input: {path}")
    with path.open(encoding="utf-8", newline="") as stream:
        rows = [dict(row) for row in csv.DictReader(stream)]
    for row in rows:
        for key in ("legal", "formal_audit_match"):
            if key in row:
                row[key] = _bool(row[key])
        for key in ("checkpoint_best_hpwl", "checkpoints"):
            if isinstance(row.get(key), str) and row[key].strip():
                try:
                    row[key] = ast.literal_eval(row[key])
                except (SyntaxError, ValueError):
                    row[key] = {}
    return rows


def summarize_file(problem: str, input_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    rows = _read_rows(input_path)
    specs = build_specs()
    spec = specs[problem]
    _validate_summary_rows(problem, rows, spec)
    if problem == "q1":
        value: Any = summarize_q1(rows, spec.seeds)
        value = _pad_registered_summaries(value, spec.config_hashes, len(spec.seeds), "Q1", "area", secondary="aspect_ratio", checkpoints=False)
        protocol_deviations = _q1_protocol_deviations(value)
        pairwise = {"Q1-BT_vs_Q1-BT-D": paired_differences(rows, "area", "Q1-BT", "Q1-BT-D"),
                    "Q1-BT_vs_directed_only": paired_differences(rows, "area", "Q1-BT", "Q1-BT-directed-only")}
        decision = q1_mechanical_decision(value)
    elif problem == "q2":
        value = summarize_q2(rows, spec.seeds)
        value = _pad_registered_summaries(value, spec.config_hashes, len(spec.seeds), "Q2", "HPWL", checkpoints=True)
        pairwise = {"P1_vs_P2": paired_differences(rows, "HPWL", "P1", "P2")}
        decision = q2_mechanical_decision(value)
    elif problem == "q3":
        route_ids = {str(row.get("config_id")) for row in rows}
        if len(route_ids) > 1:
            raise FreezeError("Q3 summary input mixes routes/attempts")
        value = summarize_q3(rows, spec.seeds, spec.final_seeds)
        pairwise = {}
        candidate = str(rows[0].get("config_id")) if rows else ""
        decision = q3_mechanical_decision({candidate: value})
    else:
        raise FreezeError(f"unsupported summary problem: {problem}")
    payload = {"problem": problem, "registered_seeds": list(spec.seeds), "summary": value, "pairwise": pairwise, "mechanical_decision": decision}
    if problem == "q1":
        payload["protocol_deviations"] = protocol_deviations
    if output_path:
        write_once(output_path, payload)
    return payload


def _plans_for_summary_root(problem: str, root: Path) -> tuple[FreezeSpec, tuple[CommandPlan, ...]]:
    spec = replace(build_specs()[problem], output_root=str(root))
    return spec, build_plan(spec)


def summarize_directory(problem: str, input_root: Path, output_path: Path | None = None) -> dict[str, Any]:
    """Discover and verify one explicit attempt root without mixing attempts."""
    root = input_root.resolve()
    if not root.is_dir():
        raise FreezeError(f"summary attempt root does not exist: {root}")
    spec, plans = _plans_for_summary_root(problem, root)
    expected_markers = {plan.marker.resolve(): plan for plan in plans}
    if problem in {"q1", "q2"}:
        discovered = {path.resolve() for path in root.rglob("events.jsonl")}
        unexpected = discovered - set(expected_markers)
        if unexpected:
            raise FreezeError(f"summary found unregistered marker(s): {sorted(map(str, unexpected))}")
        rows: list[dict[str, Any]] = []
        missing = 0
        for marker, plan in expected_markers.items():
            if not marker.is_file():
                missing += 1
                continue
            rows.append(_validate_completed(plan))
        _validate_summary_rows(problem, rows, spec)
        if problem == "q1":
            summary = _pad_registered_summaries(summarize_q1(rows, spec.seeds), spec.config_hashes, len(spec.seeds), "Q1", "area", secondary="aspect_ratio")
            protocol_deviations = _q1_protocol_deviations(summary)
            decision = q1_mechanical_decision(summary)
            pairwise = {"Q1-BT_vs_Q1-BT-D": paired_differences(rows, "area", "Q1-BT", "Q1-BT-D"),
                        "Q1-BT_vs_directed_only": paired_differences(rows, "area", "Q1-BT", "Q1-BT-directed-only")}
        else:
            summary = _pad_registered_summaries(summarize_q2(rows, spec.seeds), spec.config_hashes, len(spec.seeds), "Q2", "HPWL", checkpoints=True)
            decision = q2_mechanical_decision(summary)
            pairwise = {"P1_vs_P2": paired_differences(rows, "HPWL", "P1", "P2")}
        payload = {"problem": problem, "attempt_root": root.as_posix(), "registered_runs": len(plans),
                   "discovered_runs": len(rows), "missing_runs": missing, "summary": summary,
                   "pairwise": pairwise, "mechanical_decision": decision}
        if problem == "q1":
            payload["protocol_deviations"] = protocol_deviations
    else:
        discovered = {path.resolve() for path in root.rglob("result.json")}
        unexpected = discovered - set(expected_markers)
        if unexpected:
            raise FreezeError(f"summary found unregistered Q3 result(s): {sorted(map(str, unexpected))}")
        expected_attempts = {plan.auxiliary_markers[0].resolve() for plan in plans}
        expected_snapshots = {plan.auxiliary_markers[1].resolve() for plan in plans}
        found_attempts = {path.resolve() for path in root.rglob("*_attempts.csv")}
        found_snapshots = {path.resolve() for path in root.rglob("*_config_snapshot.json")}
        if found_attempts - expected_attempts or found_snapshots - expected_snapshots:
            raise FreezeError("summary found unregistered Q3 table artifact")
        route_summaries: dict[str, Any] = {}
        missing_routes = []
        for marker, plan in expected_markers.items():
            if not marker.is_file():
                missing_routes.append(plan.fingerprint["config_id"])
                continue
            payload = _validate_completed(plan)
            rows = _read_rows(marker)
            _validate_summary_rows(problem, rows, spec)
            route_summaries[plan.fingerprint["config_id"]] = summarize_q3(rows, spec.seeds, spec.final_seeds)
        if missing_routes:
            raise FreezeError(f"summary missing Q3 routes: {missing_routes}")
        payload = {"problem": problem, "attempt_root": root.as_posix(), "registered_routes": list(Q3_CANDIDATES),
                   "summary_by_route": route_summaries, "mechanical_decision": q3_mechanical_decision(route_summaries)}
    if output_path:
        write_once(output_path, payload)
    return payload


def _validate_summary_rows(problem: str, rows: Sequence[Mapping[str, Any]], spec: FreezeSpec) -> None:
    """Reject summaries assembled from markers outside this registered run."""
    expected_code = set(spec.code_hashes.values())
    seen: set[tuple[Any, ...]] = set()
    for row in rows:
        if row.get("instance") not in (None, spec.instance):
            raise FreezeError(f"summary instance mismatch: {row.get('instance')!r}")
        if row.get("code_hash") not in expected_code:
            raise FreezeError("summary code_hash missing or mismatched")
        config_id = row.get("config_id")
        if problem == "q3":
            expected_config = spec.config_hashes.get(str(config_id))
            if expected_config is None or row.get("config_hash") != expected_config:
                raise FreezeError("summary Q3 config_hash missing or mismatched")
        elif config_id not in spec.config_hashes or row.get("config_hash") != spec.config_hashes[config_id]:
            raise FreezeError("summary config_hash missing or mismatched")
        if row.get("data_hash") != spec.data_hash:
            raise FreezeError("summary data_hash missing or mismatched")
        if problem == "q3":
            key = (config_id, row.get("phase"), row.get("dead_space_ratio"), row.get("seed"))
        else:
            key = (config_id, row.get("seed"))
        if key in seen:
            raise FreezeError("summary contains duplicate seed rows")
        seen.add(key)


def _pad_registered_summaries(
    summaries: Sequence[Mapping[str, Any]], registered_configs: Mapping[str, str],
    seed_count: int, problem: str, metric: str, *, secondary: str | None = None,
    checkpoints: bool = False,
) -> list[dict[str, Any]]:
    """Keep registered-but-missing configurations in the summary denominator."""
    output = [dict(item) for item in summaries]
    present = {str(item.get("config_id")) for item in output}
    for config_id in registered_configs:
        if config_id in present:
            continue
        item: dict[str, Any] = {
            "problem": problem, "config_id": config_id, "runs": 0,
            "registered_runs": seed_count, "missing_runs": seed_count,
            "legal_runs": 0, "legal_rate": 0.0, "audit_match_runs": 0,
            f"median_{metric}": None, f"p90_{metric}": None, f"iqr_{metric}": None,
            f"min_{metric}": None, f"max_{metric}": None,
            "status_success": 0, "status_timeout": 0, "status_no_feasible": 0, "status_crash": 0,
        }
        if secondary:
            item.update({f"median_{secondary}": None, f"p90_{secondary}": None, f"iqr_{secondary}": None,
                         f"min_{secondary}": None, f"max_{secondary}": None})
        if problem == "Q1":
            item.update({"median_first_feasible_evaluation": None, "first_feasible_status": "not_recorded_protocol_deviation"})
        if checkpoints:
            item.update({"median_first_feasible_evaluation": None,
                         "checkpoint_median_best_so_far_HPWL": {str(point): None for point in (25, 50, 75, 100)},
                         "checkpoint_status": "missing"})
        output.append(item)
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V3 fail-closed plan/dry-run helper")
    parser.add_argument("command", choices=("dry-run", "plan", "run", "summary", "q4-check"))
    parser.add_argument("--problem", choices=("q1", "q2", "q3"), default="q2")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--attempt", help="safe retry suffix; never reuses a prior output path")
    parser.add_argument("--execute", action="store_true", help="required for run; starts registered CLI subprocesses")
    args = parser.parse_args(argv)
    if args.command == "q4-check":
        payload = check_q4_registered()
        if args.output:
            write_once(args.output, payload)
        else:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "summary":
        if args.input is None:
            parser.error("summary requires --input")
        summary_root = args.input
        if args.attempt:
            validate_attempt_slug(args.attempt)
            if not summary_root.is_dir():
                parser.error("--attempt with summary requires a directory input root")
            summary_root = summary_root / args.attempt
        payload = summarize_directory(args.problem, summary_root, args.output) if summary_root.is_dir() else summarize_file(args.problem, summary_root, args.output)
        if args.output is None:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    specs = build_specs()
    spec = specs[args.problem]
    actual = registered_payload(spec)
    frozen = load_frozen_manifest()
    check_registered(actual, frozen[args.problem])
    plans = build_plan(spec, attempt=args.attempt)
    if args.command == "run" and not args.execute:
        parser.error("run requires --execute; use dry-run for a non-executing plan")
    if args.command == "run":
        result = execute_plan(plans, execute=True)
        payload = {"spec": spec.as_dict(), "results": result}
    else:
        payload = {"spec": spec.as_dict(), "commands": [{"command": list(item.command), "marker": item.marker.as_posix(), "fingerprint": item.fingerprint} for item in plans]}
    if args.output:
        write_once(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
