from __future__ import annotations

import unittest

from dobot_sorter.geometry import (
    GridFullError,
    GridSpec,
    Point2D,
    Pose,
    UnsafeCoordinateError,
    WorkspaceLimits,
    correct_for_object_height,
    normalize_gripper_angle,
    project_homography,
)


class GeometryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = WorkspaceLimits(80, 335, -300, 300, -30, 200, 335, -90, 90)

    def test_identity_homography(self) -> None:
        point = project_homography(
            ((1, 0, 0), (0, 1, 0), (0, 0, 1)),
            Point2D(120, 240),
        )
        self.assertEqual(point, Point2D(120, 240))

    def test_workspace_rejects_instead_of_clamping(self) -> None:
        with self.assertRaises(UnsafeCoordinateError):
            self.workspace.require(Pose(500, 0, 100, 0))

    def test_height_correction_moves_toward_camera_center(self) -> None:
        corrected = correct_for_object_height(
            Point2D(300, 100), Point2D(200, 0), camera_height_mm=400, object_height_mm=20
        )
        self.assertAlmostEqual(corrected.x, 295.0)
        self.assertAlmostEqual(corrected.y, 95.0)

    def test_grid_capacity_is_enforced(self) -> None:
        grid = GridSpec(Pose(270, 150, -15), rows=2, columns=1, row_step_x=-30)
        self.assertEqual(grid.target(1), Pose(240, 150, -15, 0))
        with self.assertRaises(GridFullError):
            grid.target(2)

    def test_angle_normalization(self) -> None:
        self.assertEqual(normalize_gripper_angle(80), -10)
        self.assertEqual(normalize_gripper_angle(-80), 10)


if __name__ == "__main__":
    unittest.main()
