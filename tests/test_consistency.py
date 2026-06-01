"""
Consistency test suite — runs the four canonical benchmark scenarios
against both Baseline and Neuro-Symbolic modes and prints a comparison table.

Usage:
    python -m tests.test_consistency          # quick (scale=10)
    python -m tests.test_consistency --scale 50
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.benchmark import ALL_SCENARIOS, _pad, BenchmarkRunner
from src.evaluator import Evaluator


def run_comparison(scenario_name: str, scale: int = 10) -> None:
    prompts = _pad(ALL_SCENARIOS[scenario_name], scale)
    evaluator = Evaluator()
    comparison = evaluator.compare_baselines(prompts, scenario_name=scenario_name)

    print(f"\n{'='*55}")
    print(f"  Scenario: {scenario_name}  (scale={scale})")
    print(f"{'='*55}")
    header = f"  {'Metric':<8}  {'Baseline':>10}  {'Neuro-Sym':>10}  {'Δ':>8}"
    print(header)
    print("  " + "-" * 51)
    for key in ("CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF"):
        b = comparison["baseline"].get(key, 0)
        n = comparison["neurosymbolic"].get(key, 0)
        delta = n - b if isinstance(n, (int, float)) else "—"
        delta_str = f"{delta:+.2f}" if isinstance(delta, float) else str(delta)
        print(f"  {key:<8}  {b:>10}  {n:>10}  {delta_str:>8}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Neuro-Symbolic RAG consistency tests")
    parser.add_argument(
        "--scenario",
        choices=list(ALL_SCENARIOS) + ["all"],
        default="death_barrier",
        help="Which scenario to run (default: death_barrier)",
    )
    parser.add_argument("--scale", type=int, default=10, help="Number of story steps")
    parser.add_argument(
        "--benchmark", action="store_true",
        help="Run the full benchmark suite across all scenarios and scales",
    )
    args = parser.parse_args()

    if args.benchmark:
        runner = BenchmarkRunner()
        runner.run_all()
        return

    if args.scenario == "all":
        for name in ALL_SCENARIOS:
            run_comparison(name, args.scale)
    else:
        run_comparison(args.scenario, args.scale)


if __name__ == "__main__":
    main()
