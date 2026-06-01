"""
Automated Benchmark Suite — four canonical consistency scenarios.

Scenario 1 — Death Barrier       : character dies, must not act afterward
Scenario 2 — Item Transfer       : item passes between two characters
Scenario 3 — Travel Event        : character moves between locations
Scenario 4 — Relationship Change : rivals become allies

Each scenario can be run at three scales: 10 / 50 / 100 prompt-steps.
(Longer stories pad with neutral continuation prompts to simulate a real session.)
A full benchmark run generates per-scenario and aggregate CSV / JSON / chart reports.
"""

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List

from src.evaluator import Evaluator

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports") / "benchmark"

# ──────────────────────────────────────────────────────────────────────────────
# Canonical scenario definitions
# ──────────────────────────────────────────────────────────────────────────────

_NEUTRAL_PADS = [
    "The wind howls through the empty corridor. Nothing stirs.",
    "Hours pass in uneasy silence.",
    "A distant sound echoes but fades before anyone can identify it.",
    "The torchlight flickers, casting long shadows across the stone floor.",
    "Time moves on, and the world holds its breath.",
]


def _pad(base: List[str], target: int) -> List[str]:
    """Extend a prompt list to exactly `target` items using neutral pads."""
    result = list(base)
    i = 0
    while len(result) < target:
        result.append(_NEUTRAL_PADS[i % len(_NEUTRAL_PADS)])
        i += 1
    return result[:target]


SCENARIO_1_DEATH_BARRIER: List[str] = [
    "Arthur the knight enters a dark dungeon alone.",
    "Arthur finds a golden sword lying on an altar.",
    "Arthur picks up the golden sword.",
    "A trap triggers: a poisoned arrow strikes Arthur in the heart. He collapses and dies instantly.",
    # The following prompts should be flagged as contradictions:
    "Arthur stands up and walks toward the exit carrying the golden sword.",
    "Arthur attacks the dungeon guardian with the golden sword.",
    "Arthur speaks to the dungeon guardian, taunting it.",
    "Arthur picks up a healing potion from the corner.",
]

SCENARIO_2_ITEM_TRANSFER: List[str] = [
    "Elena the mage enters the marketplace.",
    "Elena purchases a magic amulet from the merchant.",
    "Elena wears the magic amulet around her neck.",
    "Elena meets her companion Roderick at the city gates.",
    "Elena gives the magic amulet to Roderick as a gift.",
    "Roderick places the magic amulet in his belt pouch.",
    # Contradiction: Elena uses an item she no longer owns
    "Elena uses the magic amulet to cast a shielding spell.",
    # Correct continuation: Roderick uses the amulet
    "Roderick activates the magic amulet to ward off the approaching bandits.",
]

SCENARIO_3_TRAVEL_EVENT: List[str] = [
    "Sir Marcus is stationed at Castle Ironhold in the northern mountains.",
    "A royal messenger arrives at Castle Ironhold with urgent orders.",
    "Sir Marcus reads the orders and prepares for a long journey south.",
    "After three days of riding, Sir Marcus arrives at the Port of Valdris.",
    "Sir Marcus meets the harbour master at the Port of Valdris.",
    # Contradiction: acting at old location without travel
    "Sir Marcus trains in the castle courtyard of Castle Ironhold.",
    # Correct: acting at new location
    "Sir Marcus negotiates passage aboard a merchant vessel at the Port of Valdris.",
    "The ship departs at dawn, carrying Sir Marcus toward the Isle of Mourne.",
]

SCENARIO_4_RELATIONSHIP_CHANGE: List[str] = [
    "Lady Seraphine and Lord Dravec have been bitter rivals for a decade.",
    "Lord Dravec launches a surprise attack on Lady Seraphine's estate.",
    "Lady Seraphine repels the attack and captures two of Dravec's soldiers.",
    "The king summons both nobles to court and demands peace.",
    # Relationship change event — must be acknowledged before being used
    "Under the king's mediation, Seraphine and Dravec sign a formal alliance treaty.",
    "Lady Seraphine and Lord Dravec now fight side by side against the northern invasion.",
    # The verifier should accept alliance-based cooperation from this point
    "Lord Dravec sends reinforcements to aid Lady Seraphine's eastern flank.",
    "Their joint forces defeat the northern army at the Battle of Thornfield.",
]

ALL_SCENARIOS: Dict[str, List[str]] = {
    "death_barrier": SCENARIO_1_DEATH_BARRIER,
    "item_transfer": SCENARIO_2_ITEM_TRANSFER,
    "travel_event": SCENARIO_3_TRAVEL_EVENT,
    "relationship_change": SCENARIO_4_RELATIONSHIP_CHANGE,
}

SCALES: List[int] = [10, 50, 100]


# ──────────────────────────────────────────────────────────────────────────────
# Benchmark runner
# ──────────────────────────────────────────────────────────────────────────────

class BenchmarkRunner:
    """Runs all four scenarios at configurable scales and aggregates reports."""

    def __init__(self, scales: List[int] = None, reports_dir: Path = None) -> None:
        self.scales = scales or SCALES
        self.reports_dir = reports_dir or REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.evaluator = Evaluator(reports_dir=self.reports_dir)

    def run_all(self) -> Dict[str, Any]:
        """Run every scenario at every scale for both modes."""
        aggregate: Dict[str, Any] = {}
        t_start = time.time()

        for scenario_name, base_prompts in ALL_SCENARIOS.items():
            aggregate[scenario_name] = {}
            for scale in self.scales:
                prompts = _pad(base_prompts, scale)
                tag = f"{scenario_name}_n{scale}"
                print(f"\n{'='*60}")
                print(f"  Scenario: {scenario_name}  |  Scale: {scale} prompts")
                print(f"{'='*60}")

                comparison = self.evaluator.compare_baselines(prompts, scenario_name=tag)
                aggregate[scenario_name][f"n{scale}"] = comparison

        elapsed = time.time() - t_start
        summary = self._build_summary(aggregate, elapsed)
        self._save_aggregate(summary)
        self._print_summary(summary)
        return summary

    def run_scenario(
        self, name: str, scale: int = 10, use_neurosymbolic: bool = True
    ) -> Dict[str, Any]:
        """Run a single named scenario at the given scale."""
        if name not in ALL_SCENARIOS:
            raise ValueError(f"Unknown scenario '{name}'. Choose from {list(ALL_SCENARIOS)}")
        prompts = _pad(ALL_SCENARIOS[name], scale)
        tag = f"{name}_n{scale}"
        return self.evaluator.run_evaluation(
            prompts, use_neurosymbolic=use_neurosymbolic, scenario_name=tag
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self, aggregate: Dict[str, Any], elapsed: float
    ) -> Dict[str, Any]:
        metric_keys = ("CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF")
        summary: Dict[str, Any] = {
            "total_runtime_seconds": round(elapsed, 1),
            "scales_tested": self.scales,
            "scenarios": list(ALL_SCENARIOS),
            "results": aggregate,
            "aggregate_averages": {},
        }

        # Average each metric across all scenarios and scales
        for mode_key in ("baseline", "neurosymbolic"):
            totals: Dict[str, List[float]] = {m: [] for m in metric_keys}
            for scn_data in aggregate.values():
                for scale_data in scn_data.values():
                    mode_data = scale_data.get(mode_key, {})
                    for m in metric_keys:
                        val = mode_data.get(m)
                        if val is not None:
                            totals[m].append(float(val))
            summary["aggregate_averages"][mode_key] = {
                m: round(sum(v) / len(v), 2) if v else None
                for m, v in totals.items()
            }

        return summary

    def _save_aggregate(self, summary: Dict[str, Any]) -> None:
        path = self.reports_dir / "benchmark_aggregate.json"
        # step_records are too large to include in the aggregate
        path.write_text(
            json.dumps(
                {k: v for k, v in summary.items() if k != "results"},
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"\n[Benchmark] Aggregate summary → {path}")

    def _print_summary(self, summary: Dict[str, Any]) -> None:
        print("\n" + "=" * 60)
        print("  BENCHMARK COMPLETE")
        print("=" * 60)
        print(f"  Runtime: {summary['total_runtime_seconds']}s")
        for mode in ("baseline", "neurosymbolic"):
            avgs = summary["aggregate_averages"].get(mode, {})
            print(f"\n  {mode.upper()} averages across all scenarios & scales:")
            for m, v in avgs.items():
                print(f"    {m}: {v}")


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry-point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Neuro-Symbolic RAG Benchmark Suite")
    parser.add_argument("--scenario", choices=list(ALL_SCENARIOS) + ["all"], default="all")
    parser.add_argument("--scale", type=int, default=10)
    parser.add_argument("--mode", choices=["ns", "baseline", "both"], default="both")
    args = parser.parse_args()

    runner = BenchmarkRunner(scales=[args.scale])

    if args.scenario == "all":
        runner.run_all()
    else:
        if args.mode == "both":
            runner.evaluator.compare_baselines(
                _pad(ALL_SCENARIOS[args.scenario], args.scale),
                scenario_name=args.scenario,
            )
        else:
            runner.run_scenario(
                args.scenario,
                scale=args.scale,
                use_neurosymbolic=(args.mode == "ns"),
            )
