"""Hardware-independent selection and state primitives for the sorting loop."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from .geometry import Point2D, Pose, WorkspaceLimits
from .vision import Detection


class SortState(Enum):
    IDLE = auto()
    DETECTING = auto()
    PICKING = auto()
    PLACING = auto()
    RETURNING = auto()
    ERROR = auto()
    EXIT = auto()


@dataclass(frozen=True)
class LocatedDetection:
    detection: Detection
    robot_point: Point2D


def choose_pick_target(
    candidates: list[LocatedDetection],
    *,
    workspace: WorkspaceLimits,
    pick_z: float,
    pick_zone: tuple[float, float, float, float],
) -> LocatedDetection | None:
    min_x, max_x, min_y, max_y = pick_zone
    safe = [
        candidate
        for candidate in candidates
        if min_x <= candidate.robot_point.x <= max_x
        and min_y <= candidate.robot_point.y <= max_y
        and workspace.contains(
            Pose(
                candidate.robot_point.x,
                candidate.robot_point.y,
                pick_z,
                candidate.detection.angle_degrees,
            )
        )
    ]
    return max(safe, key=lambda item: item.detection.confidence, default=None)


def choose_feedback_target(
    candidates: list[LocatedDetection],
    *,
    class_name: str,
    target: Point2D,
    search_radius_mm: float,
) -> LocatedDetection | None:
    matching = [
        candidate
        for candidate in candidates
        if candidate.detection.class_name == class_name
        and candidate.robot_point.distance_to(target) <= search_radius_mm
    ]
    return min(
        matching,
        key=lambda item: item.robot_point.distance_to(target),
        default=None,
    )
