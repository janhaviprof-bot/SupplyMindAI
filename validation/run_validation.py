"""
run_validation.py

Two-phase wrapper to make the validation experiment user-friendly.

Phase 1 runs:
  - 01_generate_reports.py for shipment and optimization
  - 02_ai_quality_control.py for shipment and optimization

Phase 2 runs:
  - 03_statistical_comparison.py for both experiments

This reduces the workflow to exactly two commands:
  py validation/run_validation.py --phase 1
  py validation/run_validation.py --phase 2
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


THIS = Path(__file__).resolve()
PROJECT_ROOT = THIS.parent.parent


def _run(cmd: list[str]) -> None:
    print(f"\nRunning: {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=str(PROJECT_ROOT))


def phase1(n: int | None, workers: int, temperature: float, force: bool,
           reviewer_model: str, reviewer_temperature: float,
           reviewer_max_tokens: int, reliability_n: int,
           reliability_repeats: int) -> None:
    common_gen = [sys.executable, "validation/01_generate_reports.py"]
    common_qc = [sys.executable, "validation/02_ai_quality_control.py"]
    gen_flags = []
    qc_flags = []
    if n is not None:
        gen_flags += ["--n", str(n)]
        qc_flags += ["--n", str(n)]
    if force:
        gen_flags.append("--force")
        qc_flags.append("--force")
    if workers:
        gen_flags += ["--workers", str(workers)]
        qc_flags += ["--workers", str(workers)]
    if temperature is not None:
        gen_flags += ["--temperature", str(temperature)]
    qc_flags += ["--reviewer-model", reviewer_model]
    qc_flags += ["--temperature", str(reviewer_temperature)]
    qc_flags += ["--max-tokens", str(reviewer_max_tokens)]
    qc_flags += ["--reliability-n", str(reliability_n)]
    qc_flags += ["--reliability-repeats", str(reliability_repeats)]

    # Shipment
    _run(common_gen + ["--experiment", "shipment"] + gen_flags)
    _run(common_qc + ["--experiment", "shipment"] + qc_flags)

    # Optimization
    _run(common_gen + ["--experiment", "optimization"] + gen_flags)
    _run(common_qc + ["--experiment", "optimization"] + qc_flags)


def phase2() -> None:
    _run([sys.executable, "validation/03_statistical_comparison.py", "--experiment", "both"])


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    p.add_argument("--phase", type=int, choices=(1, 2), required=True,
                   help="Phase 1 = generate + review, Phase 2 = stats")
    p.add_argument("--n", type=int, default=None,
                   help="Smoke test: score only first N samples per prompt")
    p.add_argument("--workers", type=int, default=8,
                   help="Concurrent OpenAI requests")
    p.add_argument("--temperature", type=float, default=0.3,
                   help="Generator temperature (default 0.3)")
    p.add_argument("--force", action="store_true",
                   help="Ignore caches and re-run")
    p.add_argument("--reviewer-model", default="gpt-4.1-nano",
                   help="Reviewer model (default gpt-4.1-nano)")
    p.add_argument("--reviewer-temperature", type=float, default=0.1,
                   help="Reviewer temperature (default 0.1)")
    p.add_argument("--reviewer-max-tokens", type=int, default=300,
                   help="Reviewer max output tokens (default 300)")
    p.add_argument("--reliability-n", type=int, default=5,
                   help="Reliability subset size (default 5)")
    p.add_argument("--reliability-repeats", type=int, default=2,
                   help="Repeated reviewer scoring per reliability sample (default 2)")
    args = p.parse_args()

    if args.phase == 1:
        phase1(
            n=args.n,
            workers=args.workers,
            temperature=args.temperature,
            force=args.force,
            reviewer_model=args.reviewer_model,
            reviewer_temperature=args.reviewer_temperature,
            reviewer_max_tokens=args.reviewer_max_tokens,
            reliability_n=args.reliability_n,
            reliability_repeats=args.reliability_repeats,
        )
    else:
        phase2()


if __name__ == "__main__":
    main()

