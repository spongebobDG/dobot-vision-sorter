"""Fail-fast Dobot motion wrapper using only the public pydobot interface."""

from __future__ import annotations

from math import ceil
from time import sleep
from typing import Any

from .geometry import Pose, WorkspaceLimits


class RobotMotionError(RuntimeError):
    """Raised when a robot or gripper command fails."""


class DobotController:
    def __init__(
        self,
        device: Any,
        workspace: WorkspaceLimits,
        *,
        safe_z: float,
        move_speed: int,
        descend_speed: int,
        rotation_step_degrees: float = 15.0,
    ) -> None:
        self._device = device
        self.workspace = workspace
        self.safe_z = safe_z
        self.move_speed = move_speed
        self.descend_speed = descend_speed
        self.rotation_step_degrees = rotation_step_degrees
        self.holding_object = False
        workspace.require(Pose(workspace.min_x, 0.0, safe_z, 0.0), label="safe_z")

    @classmethod
    def connect(
        cls,
        port: str,
        workspace: WorkspaceLimits,
        **kwargs: Any,
    ) -> "DobotController":
        try:
            from pydobot import Dobot
        except ImportError as error:
            raise RuntimeError("pydobot is missing; install requirements.txt") from error
        device = Dobot(port=port, verbose=False)
        controller = cls(device, workspace, **kwargs)
        controller._set_speed(controller.move_speed)
        return controller

    def __enter__(self) -> "DobotController":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def _set_speed(self, speed: int) -> None:
        self._device.speed(speed, speed)

    def pose(self) -> Pose:
        raw = self._device.pose()
        return Pose(float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))

    def _move_direct(self, target: Pose, *, speed: int) -> None:
        self.workspace.require(target)
        self._set_speed(speed)
        try:
            self._device.move_to(target.x, target.y, target.z, target.r, wait=True)
        except Exception as error:
            raise RobotMotionError(f"move failed: {target}") from error
        finally:
            self._set_speed(self.move_speed)

    def safe_move(self, target: Pose, *, descend: bool = False) -> None:
        """Raise, translate, then descend after validating the unmodified target."""
        self.workspace.require(target)
        current = self.pose()
        self.workspace.require(current, label="current pose")
        safe_current = Pose(current.x, current.y, self.safe_z, current.r)
        safe_target = Pose(target.x, target.y, self.safe_z, target.r)
        self.workspace.require(safe_current, label="safe current pose")
        self.workspace.require(safe_target, label="safe target pose")

        if current.z < self.safe_z - 0.5:
            self._move_direct(safe_current, speed=self.descend_speed)
        self._move_direct(safe_target, speed=self.move_speed)
        if target.z < self.safe_z - 0.5:
            self._move_direct(
                target,
                speed=self.descend_speed if descend else self.move_speed,
            )

    def rotate_at_safe_height(self, target_r: float) -> None:
        current = self.pose()
        if current.z < self.safe_z - 0.5:
            raise RobotMotionError("rotation is allowed only at the configured safe height")
        final = Pose(current.x, current.y, current.z, target_r)
        self.workspace.require(final, label="rotation target")
        delta = target_r - current.r
        steps = max(1, ceil(abs(delta) / self.rotation_step_degrees))
        for step in range(1, steps + 1):
            intermediate = Pose(
                current.x,
                current.y,
                current.z,
                current.r + delta * step / steps,
            )
            self._move_direct(intermediate, speed=self.descend_speed)
            sleep(0.1)

    def set_gripper(self, closed: bool, *, settle_seconds: float = 0.6) -> None:
        try:
            self._device.grip(closed)
            sleep(settle_seconds)
        except Exception as error:
            raise RobotMotionError(f"gripper command failed: closed={closed}") from error
        self.holding_object = closed

    def close(self) -> None:
        try:
            self._device.close()
        except Exception as error:
            raise RobotMotionError("failed to close Dobot connection") from error
