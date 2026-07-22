"""Validated camera-to-robot calibration loading and coordinate conversion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .geometry import Point2D, correct_for_object_height, project_homography


class CalibrationValidationError(ValueError):
    """Raised when a calibration has no independent passing validation result."""


@dataclass(frozen=True)
class RobotCalibration:
    homography: tuple[tuple[float, float, float], ...]
    camera_center_robot: Point2D
    camera_height_mm: float
    object_height_mm: float
    validation_mean_mm: float
    validation_p95_mm: float
    validation_max_mm: float
    validated: bool

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        require_validated: bool = True,
    ) -> "RobotCalibration":
        payload: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
        validation = payload.get("validation", {})

        def validation_metric(name: str) -> float:
            raw_value = validation.get(name)
            return float("inf") if raw_value is None else float(raw_value)

        calibration = cls(
            homography=tuple(tuple(float(value) for value in row) for row in payload["homography"]),
            camera_center_robot=Point2D(
                *map(float, payload["camera"]["center_robot_mm"])
            ),
            camera_height_mm=float(payload["camera"]["height_mm"]),
            object_height_mm=float(payload["object_height_mm"]),
            validation_mean_mm=validation_metric("mean_mm"),
            validation_p95_mm=validation_metric("p95_mm"),
            validation_max_mm=validation_metric("max_mm"),
            validated=bool(validation.get("passed", False)),
        )
        if require_validated and not calibration.validated:
            raise CalibrationValidationError(
                "calibration is not independently validated; run scripts/fit_calibration.py"
            )
        return calibration

    def pixel_to_robot(self, pixel: Point2D, *, object_height_mm: float | None = None) -> Point2D:
        apparent = project_homography(self.homography, pixel)
        return correct_for_object_height(
            apparent,
            self.camera_center_robot,
            self.camera_height_mm,
            self.object_height_mm if object_height_mm is None else object_height_mm,
        )
