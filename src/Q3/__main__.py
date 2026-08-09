"""Command-line entry point for Q3 dead-space threshold searches."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import time

from .._internal.parser import parse_instance_files
from .common import CANDIDATES, INNER_CANDIDATES, Q3SearchConfig, outline_side
from .search import solve_q3


def _parse_seeds(value: str) -> tuple[int, ...]:
    seeds: list[int] = []
    for token in value.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start, end = token.split("-", 1)
            seeds.extend(range(int(start), int(end) + 1))
        else:
            seeds.append(int(token))
    if not seeds:
        raise argparse.ArgumentTypeError("at least one seed is required")
    return tuple(seeds)


def _on_off(value: str) -> bool:
    lowered = value.lower()
    if lowered in {"on", "true", "1", "yes"}:
        return True
    if lowered in {"off", "false", "0", "no"}:
        return False
    raise argparse.ArgumentTypeError("expected on or off")


def _load_instance(raw_dir: Path, instance_name: str):
    paths = tuple(raw_dir / f"{instance_name}{suffix}" for suffix in (".blocks", ".nets", ".pl"))
    if not all(path.is_file() for path in paths):
        raise FileNotFoundError(", ".join(str(path) for path in paths if not path.is_file()))
    instance = parse_instance_files(*paths)
    references = {pin for net in instance.nets for pin in net.pins}
    known = set(instance.blocks) | set(instance.terminals)
    if references - known or sum(len(net.pins) for net in instance.nets) != instance.declared_pins:
        raise ValueError("Q3 input audit failed")
    return instance


def _code_hash() -> str:
    root = Path(__file__).parents[1]
    files = [
        Path(__file__),
        Path(__file__).with_name("common.py"),
        Path(__file__).with_name("search.py"),
        root / "Q2" / "common.py",
        root / "Q2" / "p0.py",
        root / "Q2" / "p1_p2.py",
        root / "_internal" / "parser.py",
        root / "_internal" / "evaluator.py",
        root / "_internal" / "audit.py",
        root / "Q1" / "p0.py",
        root / "Q1" / "p1_p2.py",
    ]
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.as_posix().encode("utf-8"))
        digest.update(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
    return digest.hexdigest()


def _data_hash(raw_dir: Path, instance_name: str) -> str:
    root = Path.cwd().resolve()
    rows = []
    for suffix in (".blocks", ".nets", ".pl"):
        path = raw_dir / f"{instance_name}{suffix}"
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        try:
            relative = path.resolve().relative_to(root).as_posix()
        except ValueError:
            relative = path.as_posix()
        rows.append({"bytes": len(data), "path": relative, "sha256": hashlib.sha256(data).hexdigest()})
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _config_hash(config: Q3SearchConfig) -> str:
    return hashlib.sha256(json.dumps(config.as_dict(), sort_keys=True).encode("utf-8")).hexdigest()


def _layout_dict(result) -> dict:
    if result.best is None:
        return {}
    return {
        name: {"x": x, "y": y, "rotation": rotation}
        for name, (x, y, rotation) in sorted(result.best.layout.items())
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class _ProgressWriter:
    """Append-only seed progress stream for an external local viewer."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = None
        self.error: str | None = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("w", encoding="utf-8", newline="\n")

    def __call__(self, event: dict) -> None:
        if self._stream is None or self.error is not None:
            return
        record = {"timestamp": time.time(), **event}
        try:
            self._stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            self._stream.flush()
        except (OSError, TypeError, ValueError) as exc:
            self.error = f"{type(exc).__name__}: {exc}"

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None


def _attempt_rows(result, config: Q3SearchConfig, layout_path: str = "") -> list[dict]:
    rows: list[dict] = []
    for attempt in result.attempts:
        for seed_attempt in attempt.seed_attempts:
            rows.append({
                "phase": "threshold",
                "dead_space_ratio": attempt.dead_space_ratio,
                "outline_side": attempt.outline_side,
                "cold_success_rate": attempt.success_rate,
                "robust": attempt.success_rate >= config.robust_min_success_rate,
                "layout_path": "",
                **seed_attempt.as_dict(),
            })
    for seed_attempt in result.final_attempts:
        final_best = result.final_best
        rows.append({
            "phase": "final",
            "dead_space_ratio": result.selected_ratio,
            "outline_side": None,
            "cold_success_rate": None,
            "robust": None,
            "layout_path": layout_path if seed_attempt is final_best else "",
            **seed_attempt.as_dict(),
        })
    return rows


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _config_from_args(args: argparse.Namespace) -> Q3SearchConfig:
    return Q3SearchConfig(
        candidate=args.candidate,
        inner_candidate=args.inner_candidate,
        lower_ratio=args.lower_ratio,
        upper_ratio=args.upper_ratio,
        precision=args.precision,
        robust_min_success_rate=args.robust_min_success_rate,
        decision_rule=args.decision_rule,
        seeds=args.seeds,
        max_evaluations=args.max_evaluations,
        time_limit=args.time_limit,
        restarts=args.restarts,
        workers=args.workers,
        adaptive_constraints=args.adaptive_constraints,
        hypergraph_init=args.hypergraph_init,
        continuous_compression=(
            args.continuous_compression
            if args.continuous_compression is not None
            else args.candidate == "Q3-CONT-R"
        ),
        final_seeds=args.final_seeds,
        final_max_evaluations=args.final_max_evaluations,
        final_time_limit=args.final_time_limit,
        final_restarts=args.final_restarts,
    )


def main(argv: list[str] | None = None) -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Q3 minimum-dead-space search")
    parser.add_argument("--instance", default="n100")
    parser.add_argument("--candidate", choices=CANDIDATES, default="Q3-BIN")
    parser.add_argument("--inner-candidate", choices=INNER_CANDIDATES, default="Q2-HG")
    parser.add_argument("--lower-ratio", type=float, default=0.0)
    parser.add_argument("--upper-ratio", type=float, default=0.15)
    parser.add_argument("--precision", type=float, default=0.005)
    parser.add_argument("--robust-min-success-rate", type=float, default=0.8)
    parser.add_argument("--decision-rule", choices=("any", "robust"), default="robust")
    parser.add_argument("--seeds", type=_parse_seeds, default=tuple(range(1101, 1111)))
    parser.add_argument("--max-evaluations", type=int, default=30_000)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--restarts", type=int, default=4)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--adaptive-constraints", type=_on_off, default=None)
    parser.add_argument("--hypergraph-init", type=_on_off, default=None)
    parser.add_argument("--continuous-compression", type=_on_off, default=None)
    parser.add_argument("--final-seeds", type=_parse_seeds, default=tuple(range(1101, 1111)))
    parser.add_argument("--final-max-evaluations", type=int, default=30_000)
    parser.add_argument("--final-time-limit", type=float, default=60.0)
    parser.add_argument("--final-restarts", type=int, default=4)
    parser.add_argument("--raw", default="data/raw/附件")
    parser.add_argument("--runtime-root", default="outputs/q3/_runtime/v2")
    parser.add_argument("--table-root", default="outputs/q3/tables")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stop-submissions-after", type=float, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--hard-stop-after", type=float, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if (args.stop_submissions_after is None) != (args.hard_stop_after is None):
        parser.error("stop-submissions-after and hard-stop-after must be provided together")
    if args.stop_submissions_after is not None and not (
        0 < args.stop_submissions_after < args.hard_stop_after
    ):
        parser.error("require 0 < stop-submissions-after < hard-stop-after")
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    actual_command = subprocess.list2cmdline(
        [sys.executable, "-B", "-m", "src.Q3", *actual_argv]
    )
    environment = {
        "python": sys.version,
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "cpu_count": os.cpu_count(),
    }

    config = _config_from_args(args)
    instance = _load_instance(Path(args.raw), args.instance)
    code_hash = _code_hash()
    config_hash = _config_hash(config)
    data_hash = _data_hash(Path(args.raw), args.instance)
    run_id = args.run_id or f"v2_{args.candidate.lower()}_{args.instance}_{config_hash}"
    runtime_dir = Path(args.runtime_root) / args.instance / run_id
    progress_path = runtime_dir / "_live_progress.jsonl"
    progress = _ProgressWriter(progress_path)
    progress.open()
    progress({
        "event": "run_start",
        "candidate": config.candidate,
        "phase": "run",
        "run_id": run_id,
        "instance": args.instance,
        "workers": config.workers,
        "cold_seeds": list(config.seeds),
        "final_seeds": list(config.final_seeds),
    })
    try:
        result = solve_q3(
            instance,
            config,
            progress_callback=progress,
            submission_deadline=(
                started + args.stop_submissions_after
                if args.stop_submissions_after is not None
                else None
            ),
            hard_deadline=(
                started + args.hard_stop_after
                if args.hard_stop_after is not None
                else None
            ),
        )
    except BaseException as exc:
        progress({
            "event": "run_error",
            "candidate": config.candidate,
            "phase": "run",
            "run_id": run_id,
            "error": f"{type(exc).__name__}: {exc}",
        })
        progress.close()
        raise
    final_best = result.final_best
    status = (
        "partial_time_limit"
        if not result.execution_complete and result.stop_reason in {
            "submission_deadline_reached",
            "hard_deadline_reached",
        }
        else "partial_stopped"
        if not result.execution_complete
        else final_best.result.status
        if final_best is not None
        else "no_feasible"
    )
    progress({
        "event": "run_complete" if result.execution_complete else "run_stopped",
        "candidate": config.candidate,
        "phase": "run",
        "run_id": run_id,
        "status": status,
        "selected_ratio": result.selected_ratio,
        "stop_reason": result.stop_reason,
        "progress_error": progress.error,
    })
    progress.close()
    layout_path = ""
    if final_best is not None:
        final_layout_path = runtime_dir / "layout.json"
        layout_path = final_layout_path.as_posix()
        final_record = {
            "instance": args.instance,
            "problem": "Q3",
            "run_id": run_id,
            "candidate": config.candidate,
            "inner_candidate": config.inner_candidate,
            "selected_ratio": result.selected_ratio,
            "outline_side": outline_side(instance, result.selected_ratio),
            "seed": final_best.seed,
            "mode": final_best.mode,
            "status": final_best.result.status,
            "legal": final_best.result.audit_metrics.get("legal"),
            "runtime": final_best.result.runtime,
            "evaluations": final_best.result.evaluations,
            "proposals": final_best.result.proposals,
            "accepted": final_best.result.accepted,
            "restarts_completed": final_best.result.restarts_completed,
            "formal_audit_match": final_best.result.formal_metrics == final_best.result.audit_metrics,
            "config_hash": config_hash,
            "code_hash": code_hash,
            "data_hash": data_hash,
            "layout_path": layout_path,
            "error": final_best.result.error or "",
        }
        _write_json(
            final_layout_path,
            {
                "record": final_record,
                "config": config.as_dict(),
                "layout": _layout_dict(final_best.result),
                "formal_metrics": final_best.result.formal_metrics,
                "audit_metrics": final_best.result.audit_metrics,
                "runtime_metadata": {
                    "command": actual_command,
                    "environment": environment,
                    "progress_path": progress_path.as_posix(),
                    "progress_error": progress.error,
                },
            },
        )

    result_payload = result.as_dict(config)
    if result_payload["final_best"] is not None:
        result_payload["final_best"]["layout_path"] = layout_path
    runtime_seconds = time.perf_counter() - started
    payload = {
        "instance": args.instance,
        "problem": "Q3",
        "run_id": run_id,
        "code_hash": code_hash,
        "config_hash": config_hash,
        "data_hash": data_hash,
        "status": status,
        "layout_path": layout_path,
        "command": actual_command,
        "environment": environment,
        "progress_path": progress_path.as_posix(),
        "progress_error": progress.error,
        "runtime_seconds": runtime_seconds,
        **result_payload,
    }
    _write_json(runtime_dir / "result.json", payload)
    _write_csv(Path(args.table_root) / f"{run_id}_attempts.csv", _attempt_rows(result, config, layout_path))
    _write_json(Path(args.table_root) / f"{run_id}_config_snapshot.json", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if not result.execution_complete:
        return 2
    return 0 if result.final_best is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
