#!/usr/bin/env python3
"""Audit labels and exact cross-split duplicates before training."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "src"))

from dobot_sorter.dataset import DatasetLeakageError, audit_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset_root", type=Path)
    args = parser.parse_args()

    report = audit_dataset(args.dataset_root)
    print(f"Dataset: {report.root}")
    for split, stats in report.splits.items():
        classes = ", ".join(f"class {key}={value}" for key, value in sorted(stats.classes.items()))
        print(
            f"  {split:5} images={stats.images} objects={stats.objects} "
            f"missing={len(stats.missing_labels)} malformed={len(stats.malformed_labels)} "
            f"{classes}"
        )
    print(f"  cross-split duplicate hashes={len(report.duplicate_hashes)}")
    try:
        report.require_clean()
    except (DatasetLeakageError, ValueError) as error:
        print(f"Audit failed: {error}", file=sys.stderr)
        return 2
    print("Audit passed: splits are byte-disjoint and labels are valid polygons.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
