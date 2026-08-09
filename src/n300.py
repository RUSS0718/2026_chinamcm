"""Independent n300 holdout planning, execution, and locked summaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

from .Q1.__main__ import _code_hash as q1_code_hash, _config_hash as q1_config_hash
from .Q1.p1_p2 import Q1SearchConfig
from .Q2.__main__ import _code_hash as q2_code_hash, _config_hash as q2_config_hash
from .Q2.common import Q2SearchConfig
from .v3 import (
    CommandPlan,
    FreezeError,
    FreezeSpec,
    ROOT,
    _code_paths,
    _pad_registered_summaries,
    _q1_protocol_deviations,
    _validate_completed,
    build_plan,
    check_registered,
    execute_plan,
    file_manifest,
    manifest_hash,
    paired_differences,
    runtime_environment,
    summarize_q1,
    summarize_q2,
    write_once,
)


HOLDOUT_SEEDS = tuple(range(3301, 3331))
Q1_CANDIDATES = ("Q1-G", "Q1-SP", "Q1-BT")
Q2_CANDIDATES = ("P0", "P1")
N300_OUTPUT_ROOTS = {
    "q1": "outputs/q1/_runtime/v3_n300_holdout",
    "q2": "outputs/q2/_runtime/v3_n300_holdout",
}
N300_MANIFEST_PATH = ROOT / "outputs" / "v3_n300_frozen_manifest_v3.json"
_STOP_CONDITIONS = ("max_evaluations", "wall_clock", "uncaught_exception", "preserve_failure_status")


def _q1_configs() -> dict[str, Q1SearchConfig]:
    common = {"max_evaluations": 100_000, "time_limit": 600.0, "restarts": 4}
    return {
        "Q1-G": Q1SearchConfig(candidate="Q1-G", **common),
        "Q1-SP": Q1SearchConfig(candidate="Q1-SP", **common),
        "Q1-BT": Q1SearchConfig(candidate="Q1-BT", **common),
    }


def _q2_configs() -> dict[str, Q2SearchConfig]:
    common = {"max_evaluations": 30_000, "time_limit": 600.0, "restarts": 4, "initialization_mode": "shelf"}
    return {
        "P0": Q2SearchConfig(candidate="Q2-SP", adaptive_constraints=False, hypergraph_init=False, sa_schedule="classic", **common),
        "P1": Q2SearchConfig(candidate="Q2-BT", adaptive_constraints=True, hypergraph_init=False, sa_schedule="fast", **common),
    }


def build_specs(root: Path = ROOT, output_root: str = "outputs") -> dict[str, FreezeSpec]:
    data_root = root / "data" / "raw" / "附件"
    blocks = data_root / "n300.blocks"
    q2_data = file_manifest([blocks, data_root / "n300.nets", data_root / "n300.pl"], root)
    q1_configs = _q1_configs()
    q2_configs = _q2_configs()
    return {
        "q1": FreezeSpec(
            "q1", "n300", Q1_CANDIDATES,
            {name: q1_code_hash() for name in q1_configs},
            {name: q1_config_hash(config) for name, config in q1_configs.items()},
            file_manifest([blocks], root)[0]["sha256"], HOLDOUT_SEEDS,
            {"max_evaluations": 100_000, "time_limit": 600.0, "restarts": 4},
            1, 1, 8, "random.Random (CPython MT19937)", _STOP_CONDITIONS,
            N300_OUTPUT_ROOTS["q1"],
        ),
        "q2": FreezeSpec(
            "q2", "n300", Q2_CANDIDATES,
            {name: q2_code_hash() for name in q2_configs},
            {name: q2_config_hash(config) for name, config in q2_configs.items()},
            manifest_hash(q2_data), HOLDOUT_SEEDS,
            {"max_evaluations": 30_000, "time_limit": 600.0, "restarts": 4},
            8, 1, 8, "random.Random (CPython MT19937)", _STOP_CONDITIONS,
            N300_OUTPUT_ROOTS["q2"], q2_v3_baseline="B",
        ),
    }


def _selection_metadata(problem: str) -> dict[str, Any]:
    return {
        "selection_locked": True,
        "preselected": "Q1-BT" if problem == "q1" else "P1",
        "baselines": ["Q1-G", "Q1-SP"] if problem == "q1" else ["P0"],
        "ablations": [],
        "reselection_allowed": False,
    }


def _code_files(problem: str, root: Path = ROOT) -> list[dict[str, Any]]:
    paths = [root / "src" / "n300.py", *_code_paths(problem, root)]
    unique = {path.resolve(): path for path in paths}
    return file_manifest(unique.values(), root)


def _data_files(problem: str, root: Path = ROOT) -> list[dict[str, Any]]:
    data_root = root / "data" / "raw" / "附件"
    paths = (data_root / "n300.blocks",) if problem == "q1" else tuple(data_root / f"n300{suffix}" for suffix in (".blocks", ".nets", ".pl"))
    return file_manifest(paths, root)


def registered_payload(spec: FreezeSpec, root: Path = ROOT, *, python: str = sys.executable) -> dict[str, Any]:
    configs = _q1_configs() if spec.problem == "q1" else _q2_configs()
    plans = build_plan(spec, python=python)
    commands = []
    seen: set[str] = set()
    for plan in plans:
        config_id = str(plan.fingerprint["config_id"])
        if config_id in seen:
            continue
        seen.add(config_id)
        command = list(plan.command)
        command[command.index("--seed") + 1] = "<registered-seed>"
        commands.append({"config_id": config_id, "command": command, "seed_set": list(HOLDOUT_SEEDS), "final_seed_set": []})
    payload = {
        "spec": spec.as_dict(),
        "code_files": _code_files(spec.problem, root),
        "data_files": _data_files(spec.problem, root),
        "configs": {name: config.as_dict() for name, config in configs.items()},
        "environment": runtime_environment(spec, python=python),
        "commands": commands,
        **_selection_metadata(spec.problem),
    }
    payload["code_manifest_hash"] = manifest_hash(payload["code_files"])
    payload["data_manifest_hash"] = manifest_hash(payload["data_files"])
    return payload


def _joint_manifest(root: Path = ROOT, *, python: str = sys.executable) -> dict[str, Any]:
    specs = build_specs(root)
    return {
        "protocol": "v3_n300_holdout_v3",
        "instance": "n300",
        "selection_locked": True,
        "reselection_allowed": False,
        "q1": registered_payload(specs["q1"], root, python=python),
        "q2": registered_payload(specs["q2"], root, python=python),
    }


def _manifest_path(path: Path | None) -> Path:
    selected = (path or N300_MANIFEST_PATH).resolve()
    if selected != N300_MANIFEST_PATH.resolve():
        raise FreezeError(f"n300 requires its dedicated manifest: {N300_MANIFEST_PATH}")
    return selected


def _load_manifest(path: Path | None = None) -> dict[str, Any]:
    selected = _manifest_path(path)
    if not selected.is_file():
        raise FreezeError(f"missing n300 manifest: {selected}")
    payload = json.loads(selected.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise FreezeError("n300 manifest must be a JSON object")
    return payload


def _check_manifest(spec: FreezeSpec, manifest: Mapping[str, Any], root: Path = ROOT) -> None:
    if manifest.get("selection_locked") is not True or manifest.get("reselection_allowed") is not False:
        raise FreezeError("n300 manifest must lock selection")
    if manifest.get("preselected") != _selection_metadata(spec.problem)["preselected"]:
        raise FreezeError("n300 manifest preselected candidate mismatch")
    check_registered(registered_payload(spec, root), manifest)


def _summary_directory(problem: str, input_root: Path, spec: FreezeSpec) -> dict[str, Any]:
    root = input_root.resolve()
    if not root.is_dir():
        raise FreezeError(f"summary attempt root does not exist: {root}")
    expected = build_plan(spec)
    expected_markers = {plan.marker.resolve(): plan for plan in expected}
    discovered = {path.resolve() for path in root.rglob("events.jsonl")}
    unexpected = discovered - set(expected_markers)
    if unexpected:
        raise FreezeError(f"summary found unregistered marker(s): {sorted(map(str, unexpected))}")
    rows: list[dict[str, Any]] = []
    missing = 0
    for marker, plan in expected_markers.items():
        if not marker.is_file():
            if marker.parent.is_dir() and any(marker.parent.iterdir()):
                raise FreezeError(f"summary found partial output: {marker.parent}")
            missing += 1
            continue
        rows.append(_validate_completed(plan))
    if problem == "q1":
        summary = _pad_registered_summaries(summarize_q1(rows, spec.seeds), spec.config_hashes, len(spec.seeds), "Q1", "area", secondary="aspect_ratio")
        pairwise = {
            "Q1-BT_vs_Q1-G": paired_differences(rows, "area", "Q1-G", "Q1-BT"),
            "Q1-BT_vs_Q1-SP": paired_differences(rows, "area", "Q1-SP", "Q1-BT"),
        }
        payload = {"problem": "q1", "instance": "n300", "summary": summary, "pairwise": pairwise,
                   "protocol_deviations": _q1_protocol_deviations(summary)}
    else:
        summary = _pad_registered_summaries(summarize_q2(rows, spec.seeds), spec.config_hashes, len(spec.seeds), "Q2", "HPWL", checkpoints=True)
        payload = {"problem": "q2", "instance": "n300", "summary": summary,
                   "pairwise": {
                       "P1_vs_P0": paired_differences(rows, "HPWL", "P0", "P1"),
                   }}
    payload.update({"attempt_root": root.as_posix(), "registered_runs": len(expected), "discovered_runs": len(rows), "missing_runs": missing,
                    "mechanical_decision": {"decision": "selection_locked", "selected": None}, **_selection_metadata(problem)})
    return payload


def summarize_directory(problem: str, input_root: Path, *, output: Path | None = None) -> dict[str, Any]:
    specs = build_specs()
    if problem not in specs:
        raise FreezeError(f"unsupported problem: {problem}")
    payload = _summary_directory(problem, input_root, specs[problem])
    if output:
        write_once(output, payload)
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independent n300 holdout runner")
    parser.add_argument("command", choices=("plan", "freeze", "run", "summary"))
    parser.add_argument("--problem", choices=("q1", "q2"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        target = _manifest_path(args.output)
        write_once(target, _joint_manifest())
        return 0
    if args.problem is None:
        parser.error(f"{args.command} requires --problem")
    spec = build_specs()[args.problem]
    if args.command == "summary":
        if args.input is None:
            parser.error("summary requires --input")
        if args.input.resolve() != Path(spec.output_root).resolve():
            raise FreezeError(f"summary input must be {spec.output_root}")
        summarize_directory(args.problem, args.input, output=args.output)
        return 0
    plans = build_plan(spec)
    if args.command == "plan":
        payload = {"spec": spec.as_dict(), "commands": [{"command": list(plan.command), "marker": plan.marker.as_posix(), "fingerprint": plan.fingerprint} for plan in plans], **_selection_metadata(args.problem)}
    else:
        if not args.execute:
            parser.error("run requires --execute")
        manifest = _load_manifest(args.manifest)
        entry = manifest.get(args.problem)
        if not isinstance(entry, Mapping):
            raise FreezeError(f"n300 manifest has no {args.problem} registration")
        _check_manifest(spec, entry)
        payload = {"spec": spec.as_dict(), "results": execute_plan(plans, execute=True), **_selection_metadata(args.problem)}
    if args.output:
        write_once(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
