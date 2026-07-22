from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from dobot_sorter.calibration import CalibrationValidationError, RobotCalibration
from dobot_sorter.geometry import Point2D


class CalibrationTests(unittest.TestCase):
    def _write(self, root: Path, passed: bool) -> Path:
        path = root / "calibration.json"
        path.write_text(
            json.dumps(
                {
                    "homography": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
                    "camera": {"center_robot_mm": [0, 0], "height_mm": 100},
                    "object_height_mm": 10,
                    "validation": {
                        "mean_mm": 1,
                        "p95_mm": 2,
                        "max_mm": 3,
                        "passed": passed,
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_unvalidated_calibration_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(CalibrationValidationError):
                RobotCalibration.from_file(self._write(Path(directory), False))

    def test_validated_calibration_converts_height(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calibration = RobotCalibration.from_file(self._write(Path(directory), True))
            result = calibration.pixel_to_robot(Point2D(50, 20))
            self.assertEqual(result, Point2D(45, 18))


if __name__ == "__main__":
    unittest.main()
