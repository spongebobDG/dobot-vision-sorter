from __future__ import annotations

import unittest

from dobot_sorter.geometry import Point2D, WorkspaceLimits
from dobot_sorter.orchestrator import LocatedDetection, choose_feedback_target, choose_pick_target
from dobot_sorter.vision import Detection


def detection(name: str, confidence: float) -> Detection:
    return Detection(0 if name == "normal" else 1, name, confidence, Point2D(1, 1), 0, (0, 0, 2, 2), ())


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = WorkspaceLimits(80, 335, -300, 300, -30, 200, 335, -90, 90)

    def test_pick_selection_excludes_placement_zone(self) -> None:
        candidates = [
            LocatedDetection(detection("normal", 0.99), Point2D(270, 150)),
            LocatedDetection(detection("defect", 0.80), Point2D(250, 0)),
        ]
        chosen = choose_pick_target(
            candidates,
            workspace=self.workspace,
            pick_z=-13,
            pick_zone=(120, 325, -110, 110),
        )
        self.assertEqual(chosen, candidates[1])

    def test_feedback_uses_nearest_same_class(self) -> None:
        candidates = [
            LocatedDetection(detection("defect", 0.99), Point2D(271, 150)),
            LocatedDetection(detection("normal", 0.70), Point2D(272, 151)),
            LocatedDetection(detection("normal", 0.60), Point2D(280, 150)),
        ]
        chosen = choose_feedback_target(
            candidates,
            class_name="normal",
            target=Point2D(270, 150),
            search_radius_mm=20,
        )
        self.assertEqual(chosen, candidates[1])


if __name__ == "__main__":
    unittest.main()
