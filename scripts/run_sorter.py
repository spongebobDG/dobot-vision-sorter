#!/usr/bin/env python3
"""Run one-object-per-scan vision-guided sorting with fail-fast motion checks."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dobot_sorter.calibration import RobotCalibration  # noqa: E402
from dobot_sorter.geometry import (  # noqa: E402
    GridFullError,
    GridSpec,
    Point2D,
    Pose,
    WorkspaceLimits,
    normalize_gripper_angle,
)
from dobot_sorter.orchestrator import (  # noqa: E402
    LocatedDetection,
    SortState,
    choose_feedback_target,
    choose_pick_target,
)
from dobot_sorter.robot import DobotController  # noqa: E402
from dobot_sorter.vision import Detection, YOLOSegmenter  # noqa: E402


def _repository_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _pose(values: list[float]) -> Pose:
    return Pose(*map(float, values))


def _grid(payload: dict[str, Any]) -> GridSpec:
    row_step = payload["row_step"]
    column_step = payload["column_step"]
    origin = _pose(payload["origin"])
    return GridSpec(
        origin=origin,
        rows=int(payload["rows"]),
        columns=int(payload["columns"]),
        row_step_x=float(row_step[0]),
        row_step_y=float(row_step[1]),
        column_step_x=float(column_step[0]),
        column_step_y=float(column_step[1]),
        target_r=origin.r,
    )


def _stable_frame(cap: Any, drain_frames: int = 4) -> Any:
    for _ in range(drain_frames):
        cap.read()
    ok, frame = cap.read()
    if not ok:
        raise RuntimeError("camera frame capture failed")
    return frame


def _locate(
    detections: list[Detection],
    calibration: RobotCalibration,
) -> list[LocatedDetection]:
    return [
        LocatedDetection(
            detection=detection,
            robot_point=calibration.pixel_to_robot(detection.pixel_center),
        )
        for detection in detections
    ]


def _placement_with_feedback(
    *,
    robot: DobotController,
    cap: Any,
    segmenter: YOLOSegmenter,
    calibration: RobotCalibration,
    candidate: LocatedDetection,
    target: Pose,
    release_z: float,
    feedback: dict[str, Any],
) -> None:
    """Visually align a held block near table height, then release it."""
    nominal = Point2D(target.x, target.y)
    proposed = Pose(target.x, target.y, release_z, target.r)
    converged = False

    for _ in range(int(feedback["max_attempts"])):
        robot.safe_move(proposed, descend=True)
        frame = _stable_frame(cap, 3)
        located = _locate(segmenter.detect(frame), calibration)
        observed = choose_feedback_target(
            located,
            class_name=candidate.detection.class_name,
            target=nominal,
            search_radius_mm=float(feedback["search_radius_mm"]),
        )
        if observed is None:
            raise RuntimeError("held block was not detected inside the placement ROI")

        error_x = target.x - observed.robot_point.x
        error_y = target.y - observed.robot_point.y
        position_error = Point2D(error_x, error_y).distance_to(Point2D(0.0, 0.0))
        angle_error = normalize_gripper_angle(
            target.r - observed.detection.angle_degrees
        )
        if (
            position_error <= float(feedback["position_tolerance_mm"])
            and abs(angle_error) <= float(feedback["angle_tolerance_degrees"])
        ):
            converged = True
            break

        robot.safe_move(Pose(proposed.x, proposed.y, robot.safe_z, proposed.r))
        adjusted_r = normalize_gripper_angle(proposed.r + angle_error)
        if abs(adjusted_r - proposed.r) > 0.5:
            robot.rotate_at_safe_height(adjusted_r)
        gain = float(feedback["gain"])
        proposed = Pose(
            proposed.x + error_x * gain,
            proposed.y + error_y * gain,
            release_z,
            adjusted_r,
        )
        robot.workspace.require(proposed, label="feedback-adjusted placement")

    if not converged:
        raise RuntimeError("placement feedback did not converge; object remains gripped")
    robot.set_gripper(False)
    robot.safe_move(Pose(proposed.x, proposed.y, robot.safe_z, proposed.r))
    robot.rotate_at_safe_height(0.0)


def _pick(
    *,
    robot: DobotController,
    candidate: LocatedDetection,
    pick_z: float,
) -> None:
    source = candidate.robot_point
    angle = candidate.detection.angle_degrees
    robot.safe_move(Pose(source.x, source.y, robot.safe_z, 0.0))
    robot.rotate_at_safe_height(angle)
    robot.safe_move(Pose(source.x, source.y, pick_z, angle), descend=True)
    robot.set_gripper(True)
    robot.safe_move(Pose(source.x, source.y, robot.safe_z, angle))
    robot.rotate_at_safe_height(0.0)


def _place(
    *,
    robot: DobotController,
    cap: Any,
    segmenter: YOLOSegmenter,
    calibration: RobotCalibration,
    candidate: LocatedDetection,
    target: Pose,
    release_clearance_z: float,
    feedback: dict[str, Any],
) -> None:
    release_z = target.z + release_clearance_z
    if bool(feedback["enabled"]):
        _placement_with_feedback(
            robot=robot,
            cap=cap,
            segmenter=segmenter,
            calibration=calibration,
            candidate=candidate,
            target=target,
            release_z=release_z,
            feedback=feedback,
        )
    else:
        robot.safe_move(Pose(target.x, target.y, release_z, target.r), descend=True)
        robot.set_gripper(False)
        robot.safe_move(Pose(target.x, target.y, robot.safe_z, target.r))
        robot.rotate_at_safe_height(0.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    args = parser.parse_args()

    try:
        import cv2
        import yaml
    except ImportError as error:
        raise SystemExit("Install requirements.txt before running hardware") from error

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    workspace_data = config["workspace"]
    workspace = WorkspaceLimits(
        **{
            key: float(workspace_data[key])
            for key in (
                "min_x", "max_x", "min_y", "max_y", "min_z", "max_z",
                "max_reach", "min_r", "max_r",
            )
        }
    )
    pick_zone = tuple(map(float, workspace_data["pick_zone"]))
    robot_config = config["robot"]
    home_pose = _pose(robot_config["home_pose"])
    grids = {
        "normal": _grid(config["placement"]["normal"]),
        "defect": _grid(config["placement"]["defect"]),
    }
    counts = {"normal": 0, "defect": 0}

    model_path = _repository_path(config["model"]["weights"])
    calibration_path = _repository_path(config["calibration"]["file"])
    if not model_path.exists():
        raise SystemExit(f"model weights not found: {model_path}")
    calibration = RobotCalibration.from_file(calibration_path)
    device = config["model"].get("device")
    device = None if device == "auto" else device
    segmenter = YOLOSegmenter(
        str(model_path),
        confidence=float(config["model"]["confidence"]),
        device=device,
        near_square_ratio=float(config["objects"]["near_square_ratio"]),
    )

    camera = config["camera"]
    cap = cv2.VideoCapture(int(camera["index"]))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(camera["width"]))
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(camera["height"]))
    for _ in range(int(camera["warmup_frames"])):
        cap.read()
    if not cap.isOpened():
        raise SystemExit(f"camera {camera['index']} could not be opened")

    robot: DobotController | None = None
    state = SortState.IDLE
    auto_mode = False
    empty_scans = 0
    latest_detections: list[Detection] = []
    try:
        robot = DobotController.connect(
            str(robot_config["port"]),
            workspace,
            safe_z=float(robot_config["safe_z"]),
            move_speed=int(robot_config["move_speed"]),
            descend_speed=int(robot_config["descend_speed"]),
            rotation_step_degrees=float(robot_config["rotation_step_degrees"]),
        )
        robot.set_gripper(False)
        robot.safe_move(home_pose)

        while state is not SortState.EXIT:
            ok, live_frame = cap.read()
            if not ok:
                raise RuntimeError("camera stream lost")
            status = (
                f"{state.name} | normal={counts['normal']} defect={counts['defect']} | "
                "SPACE=start/pause Q=quit"
            )
            cv2.imshow("Dobot Vision Sorter", segmenter.draw(live_frame, latest_detections, status))
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                state = SortState.EXIT
                continue
            if key == ord(" "):
                auto_mode = not auto_mode
                state = SortState.DETECTING if auto_mode else SortState.IDLE
            if not auto_mode:
                continue

            state = SortState.DETECTING
            frame = _stable_frame(cap)
            latest_detections = segmenter.detect(frame)
            located = _locate(latest_detections, calibration)
            candidate = choose_pick_target(
                located,
                workspace=workspace,
                pick_z=float(robot_config["pick_z"]),
                pick_zone=pick_zone,
            )
            if candidate is None:
                empty_scans += 1
                if empty_scans >= 3:
                    auto_mode = False
                    state = SortState.IDLE
                time.sleep(0.3)
                continue
            empty_scans = 0

            class_name = candidate.detection.class_name
            try:
                target = grids[class_name].target(counts[class_name])
            except GridFullError as error:
                print(error)
                auto_mode = False
                state = SortState.IDLE
                continue

            state = SortState.PICKING
            _pick(
                robot=robot,
                candidate=candidate,
                pick_z=float(robot_config["pick_z"]),
            )
            state = SortState.PLACING
            _place(
                robot=robot,
                cap=cap,
                segmenter=segmenter,
                calibration=calibration,
                candidate=candidate,
                target=target,
                release_clearance_z=float(robot_config["release_clearance_z"]),
                feedback=config["placement"]["feedback"],
            )
            counts[class_name] += 1
            state = SortState.RETURNING
            robot.safe_move(home_pose)
            latest_detections = []
            time.sleep(0.5)

    except KeyboardInterrupt:
        state = SortState.EXIT
    except Exception as error:
        state = SortState.ERROR
        print(f"ERROR: {error}", file=sys.stderr)
        if robot is not None and robot.holding_object:
            print(
                "The gripper may still hold an object. Motion is stopped for manual recovery.",
                file=sys.stderr,
            )
        return 1
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if robot is not None:
            if not robot.holding_object:
                try:
                    robot.safe_move(home_pose)
                    robot.set_gripper(False)
                except Exception as cleanup_error:
                    print(f"cleanup warning: {cleanup_error}", file=sys.stderr)
            robot.close()

    print(f"completed: normal={counts['normal']} defect={counts['defect']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
