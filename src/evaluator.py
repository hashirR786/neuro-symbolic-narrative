"""
Evaluation Framework — research-grade metrics for the Neuro-Symbolic RAG system.

Metrics
───────
  CS   — Consistency Score          (0–100)  fraction of steps that pass verification
  KGCS — KG Consistency Score       (0–100)  fraction of KG edges without conflicts
  TCS  — Temporal Consistency Score (0–100)  fraction of steps with no temporal violations
  CCS  — Character Consistency Score(0–100)  character state / relationship checks
  ICS  — Inventory Consistency Score(0–100)  ownership and location checks
  HR   — Hallucination Rate         (0–1)    facts referencing unrecognised entities
  RF   — Rewrite Frequency          (float)  avg corrections per step

Output
──────
  * In-memory results dict
  * CSV report
  * JSON report
  * Matplotlib charts (saved to disk)
"""

import csv
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.schema import Fact
from src.story_engine import StoryEngine
from src.verifier import ConsistencyVerifier, _ACTION_RELATIONS, _POSSESSION_RELATIONS

logger = logging.getLogger(__name__)

REPORTS_DIR = Path("reports")


class EvaluationMetrics:
    """Accumulates per-step metric observations and computes aggregate scores."""

    def __init__(self) -> None:
        self.steps: int = 0
        # CS
        self.consistent_steps: int = 0
        # TCS — steps with no temporal violations
        self.temporal_ok_steps: int = 0
        # CCS — steps with no character-state violations
        self.character_ok_steps: int = 0
        # ICS — steps with no inventory violations
        self.inventory_ok_steps: int = 0
        # HR — per-step hallucination counts
        self.hallucination_counts: List[float] = []
        # RF — corrections per step
        self.corrections: List[int] = []
        # Per-step detail for CSV export
        self.step_records: List[Dict[str, Any]] = []

    def record_step(
        self,
        step: int,
        facts: List[Fact],
        violations,
        corrections: int,
        known_entities: set,
    ) -> None:
        self.steps += 1
        errors = [v for v in violations if v.severity == "error"]
        temporal_errors = [v for v in errors if v.rule in {
            "temporal_dead_actor", "location_mismatch"
        }]
        char_errors = [v for v in errors if v.rule in {
            "dead_actor", "illegal_resurrection", "relationship_contradiction"
        }]
        inv_errors = [v for v in errors if v.rule in {
            "duplicate_ownership", "item_transfer_without_exchange", "use_without_possession"
        }]

        is_consistent = len(errors) == 0
        if is_consistent:
            self.consistent_steps += 1
        if not temporal_errors:
            self.temporal_ok_steps += 1
        if not char_errors:
            self.character_ok_steps += 1
        if not inv_errors:
            self.inventory_ok_steps += 1

        # Hallucination: fraction of facts whose subject/object is not in known entities
        if facts:
            hallu = sum(
                1 for f in facts
                if f.subject.lower() not in known_entities
                or f.object.lower() not in known_entities
            ) / len(facts)
        else:
            hallu = 0.0
        self.hallucination_counts.append(hallu)
        self.corrections.append(corrections)

        self.step_records.append({
            "step": step,
            "is_consistent": is_consistent,
            "temporal_ok": not temporal_errors,
            "character_ok": not char_errors,
            "inventory_ok": not inv_errors,
            "hallucination_rate": round(hallu, 4),
            "corrections": corrections,
            "violations": [v.rule for v in violations],
        })

    def compute(self) -> Dict[str, Any]:
        n = self.steps or 1
        hallu = self.hallucination_counts
        corrs = self.corrections
        return {
            "CS":   round(100 * self.consistent_steps / n, 2),
            "TCS":  round(100 * self.temporal_ok_steps / n, 2),
            "CCS":  round(100 * self.character_ok_steps / n, 2),
            "ICS":  round(100 * self.inventory_ok_steps / n, 2),
            "HR":   round(sum(hallu) / len(hallu), 4) if hallu else 0.0,
            "RF":   round(sum(corrs) / len(corrs), 4) if corrs else 0.0,
            "total_steps": self.steps,
            "consistent_steps": self.consistent_steps,
        }


class Evaluator:
    """Runs evaluation scenarios and computes the full metric suite."""

    def __init__(self, reports_dir: Optional[Path] = None) -> None:
        self.reports_dir = reports_dir or REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def run_evaluation(
        self,
        prompts: List[str],
        use_neurosymbolic: bool = True,
        scenario_name: str = "eval",
    ) -> Dict[str, Any]:
        """
        Run a story sequence and return the full metric dict.
        Also exports CSV, JSON, and chart files under reports_dir.
        """
        engine = StoryEngine(use_neurosymbolic=use_neurosymbolic)
        metrics = EvaluationMetrics()
        mode = "neuro_symbolic" if use_neurosymbolic else "baseline"
        known_entities: set = set()

        print(f"\n[Evaluator] Starting '{scenario_name}' | mode={mode} | steps={len(prompts)}")

        for idx, prompt in enumerate(prompts):
            step = idx + 1
            print(f"  Step {step}/{len(prompts)}: {prompt[:60]}…")
            t0 = time.time()

            result = engine.generate_step(prompt)

            facts = [Fact(**f) for f in result.get("facts", [])]
            corrections = result.get("corrections_made", 0)

            # Update known entity set from accumulated KG
            known_entities = {str(n).lower() for n in engine.kg.graph.nodes()}

            # Get violations as ViolationReport objects from the engine's last state
            violations = engine.last_violations

            # For baseline mode, run an offline verification pass so we get metrics
            if not use_neurosymbolic:
                offline_verifier = ConsistencyVerifier(engine.kg, engine.world_state)
                violations = offline_verifier.get_violations(facts)
                engine.kg.add_facts(facts)
                engine.world_state.update_from_facts(facts)

            metrics.record_step(step, facts, violations, corrections, known_entities)
            logger.debug("Step %d completed in %.2fs", step, time.time() - t0)

        # Compute KGCS from the final KG state
        kgcs = self._compute_kgcs(engine)

        result_dict = metrics.compute()
        result_dict["KGCS"] = kgcs
        result_dict["mode"] = mode
        result_dict["scenario"] = scenario_name
        result_dict["step_records"] = metrics.step_records

        self._export_csv(metrics.step_records, scenario_name, mode)
        self._export_json(result_dict, scenario_name, mode)
        self._export_chart(metrics, result_dict, scenario_name, mode)

        print(f"\n[Evaluator] Results for '{scenario_name}' ({mode}):")
        for key in ("CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF"):
            print(f"  {key}: {result_dict[key]}")

        return result_dict

    def compare_baselines(
        self, prompts: List[str], scenario_name: str = "comparison"
    ) -> Dict[str, Any]:
        """Run both modes and return a side-by-side comparison dict."""
        print("=== BASELINE (LLM Only) ===")
        baseline = self.run_evaluation(prompts, use_neurosymbolic=False,
                                       scenario_name=f"{scenario_name}_baseline")
        print("\n=== NEURO-SYMBOLIC RAG ===")
        ns = self.run_evaluation(prompts, use_neurosymbolic=True,
                                 scenario_name=f"{scenario_name}_ns")

        comparison = {
            "scenario": scenario_name,
            "baseline": {k: baseline[k] for k in ("CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF")},
            "neurosymbolic": {k: ns[k] for k in ("CS", "KGCS", "TCS", "CCS", "ICS", "HR", "RF")},
        }
        path = self.reports_dir / f"{scenario_name}_comparison.json"
        path.write_text(json.dumps(comparison, indent=2), encoding="utf-8")
        print(f"\n[Evaluator] Comparison saved → {path}")
        return comparison

    # ------------------------------------------------------------------
    # KGCS computation
    # ------------------------------------------------------------------

    def _compute_kgcs(self, engine: StoryEngine) -> float:
        """
        KG Consistency Score: fraction of KG nodes whose latest scalar-relation
        values are non-contradictory.

        Contradiction: a node has two different latest objects for the same
        scalar relation (e.g. isAlive=true AND isAlive=false at the same step).
        """
        kg = engine.kg
        if kg.graph.number_of_nodes() == 0:
            return 100.0

        scalar_rels = {"isalive", "locatedin", "locatedat", "health", "faction"}
        total_checks = 0
        conflict_checks = 0

        for node in kg.graph.nodes():
            state: Dict[str, Dict[str, int]] = {}
            for _, v, data in kg.graph.out_edges(node, data=True):
                rel = data.get("relation", "").lower()
                if rel in scalar_rels:
                    step = data.get("step_id", 0)
                    if rel not in state or step > state[rel]["step"]:
                        state[rel] = {"value": str(v).lower(), "step": step}

            # Check for any contradictions within the same step
            seen: Dict[str, Dict] = {}
            for _, v, data in kg.graph.out_edges(node, data=True):
                rel = data.get("relation", "").lower()
                step = data.get("step_id", 0)
                val = str(v).lower()
                if rel in scalar_rels:
                    key = (rel, step)
                    total_checks += 1
                    if key in seen and seen[key] != val:
                        conflict_checks += 1
                    else:
                        seen[key] = val

        if total_checks == 0:
            return 100.0
        return round(100 * (1 - conflict_checks / total_checks), 2)

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def _export_csv(
        self,
        records: List[Dict[str, Any]],
        scenario: str,
        mode: str,
    ) -> None:
        path = self.reports_dir / f"{scenario}_{mode}_steps.csv"
        if not records:
            return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[k for k in records[0] if k != "violations"],
            )
            writer.writeheader()
            for row in records:
                writer.writerow({k: v for k, v in row.items() if k != "violations"})
        print(f"  CSV → {path}")

    def _export_json(
        self, data: Dict[str, Any], scenario: str, mode: str
    ) -> None:
        path = self.reports_dir / f"{scenario}_{mode}_summary.json"
        exportable = {k: v for k, v in data.items() if k != "step_records"}
        path.write_text(json.dumps(exportable, indent=2), encoding="utf-8")
        print(f"  JSON → {path}")

    def _export_chart(
        self,
        metrics: EvaluationMetrics,
        summary: Dict[str, Any],
        scenario: str,
        mode: str,
    ) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available — skipping chart export.")
            return

        fig, axes = plt.subplots(1, 3, figsize=(16, 5))
        fig.suptitle(f"Evaluation: {scenario} [{mode}]", fontsize=14)

        # 1. Metric bar chart
        ax = axes[0]
        bar_metrics = ["CS", "KGCS", "TCS", "CCS", "ICS"]
        vals = [summary.get(m, 0) for m in bar_metrics]
        bars = ax.bar(bar_metrics, vals, color=["#4CAF50", "#2196F3", "#FF9800", "#9C27B0", "#F44336"])
        ax.set_ylim(0, 105)
        ax.set_ylabel("Score (0–100)")
        ax.set_title("Consistency Metrics")
        for bar, val in zip(bars, vals):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                    f"{val:.1f}", ha="center", va="bottom", fontsize=9)

        # 2. Hallucination rate over steps
        ax2 = axes[1]
        ax2.plot(range(1, len(metrics.hallucination_counts) + 1),
                 metrics.hallucination_counts, color="#F44336", linewidth=1.5)
        ax2.fill_between(range(1, len(metrics.hallucination_counts) + 1),
                         metrics.hallucination_counts, alpha=0.2, color="#F44336")
        ax2.set_xlabel("Step")
        ax2.set_ylabel("Hallucination Rate")
        ax2.set_title("Hallucination Rate per Step")
        ax2.set_ylim(0, 1)

        # 3. Corrections per step
        ax3 = axes[2]
        ax3.bar(range(1, len(metrics.corrections) + 1),
                metrics.corrections, color="#FF9800")
        ax3.set_xlabel("Step")
        ax3.set_ylabel("Corrections")
        ax3.set_title(f"Rewrite Frequency (avg={summary.get('RF', 0):.2f})")

        plt.tight_layout()
        path = self.reports_dir / f"{scenario}_{mode}_chart.png"
        plt.savefig(path, dpi=120)
        plt.close(fig)
        print(f"  Chart → {path}")
