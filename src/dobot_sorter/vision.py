"""YOLO segmentation adapter. Heavy dependencies are imported only at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .geometry import Point2D, normalize_gripper_angle


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    pixel_center: Point2D
    angle_degrees: float
    bounding_box: tuple[int, int, int, int]
    polygon: tuple[tuple[int, int], ...]


class YOLOSegmenter:
    """Small adapter that keeps Ultralytics details out of the robot controller."""

    def __init__(
        self,
        weights: str,
        *,
        confidence: float = 0.5,
        device: str | int | None = None,
        near_square_ratio: float = 1.08,
    ) -> None:
        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO
        except ImportError as error:
            raise RuntimeError(
                "vision dependencies are missing; install requirements.txt"
            ) from error
        self._cv2 = cv2
        self._np = np
        self._model = YOLO(weights)
        self._confidence = confidence
        self._device = device
        self._near_square_ratio = near_square_ratio

    def _angle_from_polygon(self, polygon: Any) -> float:
        points = self._np.asarray(polygon, dtype=self._np.float32)
        if len(points) < 3:
            return 0.0
        rectangle = self._cv2.minAreaRect(points)
        width, height = rectangle[1]
        if min(width, height) <= 0:
            return 0.0
        # A square has no stable long edge. Treat its rotation as symmetric.
        if max(width, height) / min(width, height) < self._near_square_ratio:
            return 0.0
        angle = float(rectangle[2])
        if width < height:
            angle += 90.0
        return normalize_gripper_angle(angle)

    def detect(self, frame: Any) -> list[Detection]:
        arguments: dict[str, Any] = {
            "source": frame,
            "conf": self._confidence,
            "verbose": False,
        }
        if self._device is not None:
            arguments["device"] = self._device
        result = self._model.predict(**arguments)[0]
        if result.masks is None or result.boxes is None:
            return []

        detections: list[Detection] = []
        for polygon, box in zip(result.masks.xy, result.boxes):
            class_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            center = Point2D((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            points = tuple((int(x), int(y)) for x, y in polygon)
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name="normal" if class_id == 0 else "defect",
                    confidence=confidence,
                    pixel_center=center,
                    angle_degrees=self._angle_from_polygon(polygon),
                    bounding_box=(x1, y1, x2, y2),
                    polygon=points,
                )
            )
        return detections

    def draw(self, frame: Any, detections: list[Detection], status: str = "") -> Any:
        display = frame.copy()
        colors = {"normal": (0, 190, 0), "defect": (0, 0, 230)}
        for detection in detections:
            color = colors[detection.class_name]
            polygon = self._np.asarray(detection.polygon, dtype=self._np.int32).reshape((-1, 1, 2))
            self._cv2.polylines(display, [polygon], True, color, 2)
            x1, y1, _, _ = detection.bounding_box
            label = (
                f"{detection.class_name} {detection.confidence:.2f} "
                f"R={detection.angle_degrees:.0f}"
            )
            self._cv2.putText(
                display,
                label,
                (x1, max(18, y1 - 6)),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )
        if status:
            self._cv2.rectangle(display, (0, 0), (display.shape[1], 34), (20, 20, 20), -1)
            self._cv2.putText(
                display,
                status,
                (10, 23),
                self._cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (240, 240, 240),
                1,
            )
        return display
