"""Summarize persisted Module 15 calibration and offline ablation evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from incidentlens.evaluation import HumanReview, calibrate_judge


def main() -> None:
    artifact_dir = PROJECT_ROOT / "artifacts" / "evaluation"
    reviews_payload = json.loads(
        (artifact_dir / "human_reviews.json").read_text(encoding="utf-8")
    )
    reviews = [HumanReview.model_validate(item) for item in reviews_payload["reviews"]]
    calibration = calibrate_judge(reviews)
    print(json.dumps({"judge_calibration": calibration.model_dump(mode="json")}, indent=2))


if __name__ == "__main__":
    main()
