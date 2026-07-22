#!/usr/bin/env python3
"""Leakage-guarded YOLOv8 segmentation training and held-out test evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dobot_sorter.dataset import audit_dataset  # noqa: E402


def _metric(container: Any, name: str) -> float | None:
    value = getattr(container, name, None)
    return None if value is None else float(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data/dataset.yaml"))
    parser.add_argument("--model", default="yolov8n-seg.pt")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="auto")
    parser.add_argument("--project", type=Path, default=Path("runs/segment"))
    parser.add_argument("--name", default="dobot_blocks")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    try:
        import yaml
        from ultralytics import YOLO
    except ImportError as error:
        raise SystemExit("Install requirements.txt before training") from error

    data_yaml = args.data.resolve()
    definition = yaml.safe_load(data_yaml.read_text(encoding="utf-8"))
    dataset_root = Path(definition["path"])
    if not dataset_root.is_absolute():
        dataset_root = (REPOSITORY_ROOT / dataset_root).resolve()

    report = audit_dataset(dataset_root)
    report.require_clean()
    missing_splits = {"train", "val", "test"} - set(report.splits)
    if missing_splits:
        raise SystemExit(f"Independent train/val/test splits are required: missing {missing_splits}")

    # Ultralytics path resolution differs across environments. Record and use an
    # absolute runtime YAML while keeping the committed example portable.
    resolved_definition = dict(definition)
    resolved_definition["path"] = dataset_root.as_posix()
    args.project.mkdir(parents=True, exist_ok=True)
    resolved_yaml = args.project / f"{args.name}.dataset.resolved.yaml"
    resolved_yaml.write_text(
        yaml.safe_dump(resolved_definition, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    model = YOLO(args.model)
    train_arguments: dict[str, Any] = {
        "data": str(resolved_yaml),
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "batch": args.batch,
        "project": str(args.project),
        "name": args.name,
        "seed": args.seed,
        "deterministic": True,
        "patience": 20,
        "save": True,
        "plots": True,
        "degrees": 45.0,
        "fliplr": 0.5,
        "flipud": 0.3,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "scale": 0.5,
        "mosaic": 1.0,
    }
    if args.device != "auto":
        train_arguments["device"] = args.device
    model.train(**train_arguments)

    best_path = Path(model.trainer.best)
    best_model = YOLO(str(best_path))
    test_metrics = best_model.val(data=str(resolved_yaml), split="test")
    summary = {
        "model": str(best_path),
        "seed": args.seed,
        "test": {
            "mask_map50": _metric(test_metrics.seg, "map50"),
            "mask_map50_95": _metric(test_metrics.seg, "map"),
            "box_map50": _metric(test_metrics.box, "map50"),
            "box_map50_95": _metric(test_metrics.box, "map"),
        },
    }
    summary_path = best_path.parents[1] / "test_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
