"""Core modules for the Dobot vision sorting portfolio project."""

from .calibration import CalibrationValidationError, RobotCalibration
from .dataset import DatasetLeakageError, audit_dataset
from .geometry import GridFullError, GridSpec, Point2D, Pose, WorkspaceLimits

__all__ = [
    "CalibrationValidationError",
    "DatasetLeakageError",
    "GridFullError",
    "GridSpec",
    "Point2D",
    "Pose",
    "RobotCalibration",
    "WorkspaceLimits",
    "audit_dataset",
]
