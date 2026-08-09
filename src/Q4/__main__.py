from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from .geometry import EXTERNAL_DATA_MANIFEST_HASH, GEOMETRY_THICKNESSES
from .model import Q4Instance, evaluate_layout, formal_audit_match
from .sa import solve_sa
from .search import solve_exact


def _code_manifest() -> tuple[str, list[dict]]:
    root = Path(__file__).parents[2]
    paths = sorted(list((root / "src" / "Q4").glob("*.py")) + [root / "src" / "_internal" / "audit.py"], key=lambda path: path.relative_to(root).as_posix())
    digest = hashlib.sha256()
    manifest = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        digest.update(relative.encode("utf-8"))
        digest.update(data)
        manifest.append({"path": relative, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return digest.hexdigest(), manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Q4 integer-grid exact/SA runner")
    parser.add_argument("mode", choices=("exact", "sa"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-evaluations", type=int, default=1000)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--restarts", type=int, default=4)
    parser.add_argument("--upper-area", type=int, default=36)
    parser.add_argument("--geometry", choices=tuple(GEOMETRY_THICKNESSES))
    parser.add_argument("--domain-width", type=int)
    parser.add_argument("--domain-height", type=int)
    args = parser.parse_args(argv)
    if args.time_limit < 0:
        parser.error("time_limit must be non-negative")
    geometry = args.geometry or "G0"
    declared_domain = args.domain_width is not None
    if (args.domain_width is None) != (args.domain_height is None):
        parser.error("domain width and height must be provided together")
    domain = None if args.domain_width is None else (args.domain_width, args.domain_height)
    if domain is not None and any(value <= 0 for value in domain):
        parser.error("domain dimensions must be positive")
    if args.mode == "sa" and domain is None:
        domain = (9, 9)
    instance = Q4Instance.default(geometry)
    try:
        if args.mode == "exact":
            result = solve_exact(instance, upper_area=args.upper_area, time_limit=args.time_limit, domain=domain)
        else:
            if args.max_evaluations <= 0:
                parser.error("max_evaluations must be positive")
            if args.restarts <= 0:
                parser.error("restarts must be positive")
            result = solve_sa(instance, seed=args.seed, max_evaluations=args.max_evaluations, time_limit=args.time_limit, restarts=args.restarts, domain=domain, geometry=args.geometry)
    except ValueError as error:
        parser.error(str(error))
    result_data = result.as_dict()
    formal = result_data.get("evaluation", {})
    audit = result_data.get("audit", {})
    domain_formal = result_data.get("domain_evaluation", {})
    domain_audit = result_data.get("domain_audit", {})
    domain_audit_match = result_data.get("domain_audit_match", False)
    if args.mode == "exact":
        config = {"upper_area": args.upper_area, "time_limit": args.time_limit, "grid_step": 1, "rotations": [0, 90, 180, 270], "search_domain": "integer_translation_grid"}
        if args.geometry is not None:
            config.update({"mode": "exact", "geometry": geometry, "b1_beam_thickness": GEOMETRY_THICKNESSES[geometry]})
        if domain is not None:
            config.update({"mode": "exact", "domain": list(domain)})
    else:
        config = result.config
    code_hash, code_manifest = _code_manifest()
    config_hash = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    command = subprocess.list2cmdline([sys.executable, "-B", "-m", "src.Q4", *sys.argv[1:]])
    payload = {
        "problem": "Q4",
        "instance": "integer-domain",
        "geometry": geometry,
        "b1_beam_thickness": GEOMETRY_THICKNESSES[geometry],
        "seed": None if args.mode == "exact" else args.seed,
        "data_hash": EXTERNAL_DATA_MANIFEST_HASH,
        "mode": args.mode,
        "status": result.status,
        "code_hash": code_hash,
        "code_manifest": code_manifest,
        "config": config,
        "config_hash": config_hash,
        "command": command,
        "command_argv": [sys.executable, "-B", "-m", "src.Q4", *sys.argv[1:]],
        "environment": {"python": sys.version, "platform": platform.platform(), "cwd": str(Path.cwd()), "cpu_count": os.cpu_count(),
                        "processes": 1, "threads": 1, "workers": 1,
                        "omp_num_threads": os.environ.get("OMP_NUM_THREADS", ""),
                        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS", ""),
                        "openblas_num_threads": os.environ.get("OPENBLAS_NUM_THREADS", "")},
        "layout": result_data.get("layout", {}),
        "formal": formal,
        "audit": audit,
        "formal_audit_match": result_data.get("formal_audit_match", False),
        "domain_formal": domain_formal,
        "domain_audit": domain_audit,
        "domain_audit_match": domain_audit_match,
        "domain": list(domain) if domain is not None else result_data.get("domain", {}),
        "result": result_data,
    }
    if result.evaluation is not None and result.layout:
        from src._internal.audit import audit_layout

        payload["formal"] = evaluate_layout(instance, result.layout).as_dict()
        payload["audit"] = audit_layout(instance, result.layout)
        payload["formal_audit_match"] = formal_audit_match(instance, result.layout)
        if domain is not None:
            payload["domain_formal"] = evaluate_layout(instance, result.layout, domain).as_dict()
            payload["domain_audit"] = audit_layout(instance, result.layout, (0, 0, *domain))
            payload["domain_audit_match"] = formal_audit_match(instance, result.layout, domain)
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
