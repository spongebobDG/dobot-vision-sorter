"""Pure geometry and workspace primitives with no hardware dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Sequence


class UnsafeCoordinateError(ValueError):
    """Raised when a raw robot target is outside the configured workspace."""


class GridFullError(IndexError):
    """Raised before picking when the destination grid has no free cell."""


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def distance_to(self, other: "Point2D") -> float:
        return hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True)
class Pose:
    x: float
    y: float
    z: float
    r: float = 0.0


@dataclass(frozen=True)
class WorkspaceLimits:
    min_x: float
    max_x: float
    min_y: float
    max_y: float
    min_z: float
    max_z: float
    max_reach: float
    min_r: float = -135.0
    max_r: float = 135.0

    def contains(self, pose: Pose) -> bool:
        return (
            self.min_x <= pose.x <= self.max_x
            and self.min_y <= pose.y <= self.max_y
            and self.min_z <= pose.z <= self.max_z
            and hypot(pose.x, pose.y) <= self.max_reach
            and self.min_r <= pose.r <= self.max_r
        )

    def require(self, pose: Pose, *, label: str = "target") -> None:
        """Reject unsafe raw coordinates; never clamp them to a boundary."""
        if not self.contains(pose):
            raise UnsafeCoordinateError(f"{label} is outside workspace: {pose}")


@dataclass(frozen=True)
class GridSpec:
    origin: Pose
    rows: int
    columns: int
    row_step_x: float
    row_step_y: float = 0.0
    column_step_x: float = 0.0
    column_step_y: float = 0.0
    target_r: float = 0.0

    @property
    def capacity(self) -> int:
        return self.rows * self.columns

    def target(self, index: int) -> Pose:
        if index < 0 or index >= self.capacity:
            raise GridFullError(f"grid capacity exceeded: {index + 1}/{self.capacity}")
        row, column = divmod(index, self.columns)
        return Pose(
            x=self.origin.x + row * self.row_step_x + column * self.column_step_x,
            y=self.origin.y + row * self.row_step_y + column * self.column_step_y,
            z=self.origin.z,
            r=self.target_r,
        )


def project_homography(matrix: Sequence[Sequence[float]], pixel: Point2D) -> Point2D:
    """Project a pixel onto the calibration plane with a 3x3 homography."""
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError("homography must be a 3x3 matrix")
    x, y = pixel.x, pixel.y
    denominator = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
    if abs(denominator) < 1e-12:
        raise ZeroDivisionError("homography projected to a point at infinity")
    return Point2D(
        (matrix[0][0] * x + matrix[0][1] * y + matrix[0][2]) / denominator,
        (matrix[1][0] * x + matrix[1][1] * y + matrix[1][2]) / denominator,
    )


def correct_for_object_height(
    apparent: Point2D,
    camera_center_robot: Point2D,
    camera_height_mm: float,
    object_height_mm: float,
) -> Point2D:
    """Correct parallax when the detected point is above the calibrated table plane."""
    if camera_height_mm <= 0:
        raise ValueError("camera height must be positive")
    if not 0 <= object_height_mm < camera_height_mm:
        raise ValueError("object height must be within [0, camera height)")
    ratio = (camera_height_mm - object_height_mm) / camera_height_mm
    return Point2D(
        camera_center_robot.x + (apparent.x - camera_center_robot.x) * ratio,
        camera_center_robot.y + (apparent.y - camera_center_robot.y) * ratio,
    )


def normalize_gripper_angle(angle_degrees: float) -> float:
    """Normalize a rectangular mask angle to the gripper's [-45, 45] symmetry range."""
    angle = angle_degrees
    while angle > 45.0:
        angle -= 90.0
    while angle < -45.0:
        angle += 90.0
    return angle
