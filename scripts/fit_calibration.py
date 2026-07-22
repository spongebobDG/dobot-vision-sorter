#!/usr/bin/env python3
"""Fit a homography and evaluate it only on held-out robot coordinates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dobot_sorter.geometry import Point2D, project_homography  # noqa: E402


def _pairs(points: list[dict]) -> tuple[list[list[float]], list[list[float]]]:
    pixels = [list(map(float, point["pixel"])) for point in points]
    robots = [list(map(float, point["robot"])) for point in points]
    return pixels, robots


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="JSON with calibration_points and validation_points")
    parser.add_argument("--output", type=Path, default=Path("calibration/calibration.json"))
    parser.add_argument("--max-mean-error-mm", type=float, default=3.0)
    parser.add_argument("--max-max-error-mm", type=float, default=7.0)
    args = parser.parse_args()

    try:
        import cv2
        import numpy as np
    except ImportError as error:
        raise SystemExit("Install requirements.txt before fitting calibration") from error

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    calibration_points = payload.get("calibration_points", [])
    validation_points = payload.get("validation_points", [])
    if len(calibration_points) < 6:
        raise SystemExit("At least 6 calibration points are required (12+ recommended)")
    if len(validation_points) < 4:
        raise SystemExit("At least 4 held-out validation points are required (8+ recommended)")

    calibration_keys = {
        (tuple(point["pixel"]), tuple(point["robot"])) for point in calibration_points
    }
    validation_keys = {
        (tuple(point["pixel"]), tuple(point["robot"])) for point in validation_points
    }
    if calibration_keys & validation_keys:
        raise SystemExit("Calibration and validation points must be disjoint")

    source, destination = _pairs(calibration_points)
    homography, inlier_mask = cv2.findHomography(
        np.asarray(source, dtype=np.float32),
        np.asarray(destination, dtype=np.float32),
        cv2.RANSAC,
        3.0,
    )
    if homography is None:
        raise SystemExit("Homography fitting failed")

    errors: list[float] = []
    for point in validation_points:
        predicted = project_homography(homography.tolist(), Point2D(*map(float, point["pixel"])))
        expected = Point2D(*map(float, point["robot"]))
        errors.append(predicted.distance_to(expected))

    mean_error = float(np.mean(errors))
    p95_error = float(np.percentile(errors, 95))
    max_error = float(np.max(errors))
    passed = mean_error <= args.max_mean_error_mm and max_error <= args.max_max_error_mm
    result = {
        "schema_version": 1,
        "homography": homography.tolist(),
        "camera": payload["camera"],
        "object_height_mm": float(payload["object_height_mm"]),
        "calibration": {
            "points": len(calibration_points),
            "inliers": int(inlier_mask.sum()) if inlier_mask is not None else len(calibration_points),
        },
        "validation": {
            "points": len(validation_points),
            "mean_mm": mean_error,
            "p95_mm": p95_error,
            "max_mm": max_error,
            "passed": passed,
            "thresholds_mm": {
                "mean": args.max_mean_error_mm,
                "max": args.max_max_error_mm,
            },
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        f"held-out error: mean={mean_error:.3f}mm p95={p95_error:.3f}mm "
        f"max={max_error:.3f}mm passed={passed}"
    )
    print(f"saved: {args.output}")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
