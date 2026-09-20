"""Run the frozen deterministic held-out evaluation once."""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from incidentlens.evaluation import (
    EvaluationDataset,
    EvaluationRunStore,
    deterministic_variant_runner,
    run_held_out_evaluation,
)


def main() -> None:
    dataset = EvaluationDataset.load("fixtures/evaluation/scenarios.json")
    store = EvaluationRunStore("artifacts/evaluation")
    run_set = run_held_out_evaluation(
        dataset=dataset,
        runners={"deterministic": deterministic_variant_runner},
        store=store,
        run_set_id="held-out-final",
    )
    print(json.dumps(run_set.model_dump(mode="json"), indent=2, sort_keys=True))
    print("Persisted: artifacts/evaluation/held-out-final.json")


if __name__ == "__main__":
    main()
