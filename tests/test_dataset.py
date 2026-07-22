from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from dobot_sorter.dataset import DatasetLeakageError, audit_dataset


VALID_POLYGON = "0 0.1 0.1 0.2 0.1 0.2 0.2 0.1 0.2\n"


class DatasetAuditTests(unittest.TestCase):
    def _split(self, root: Path, split: str, name: str, image_bytes: bytes) -> None:
        images = root / split / "images"
        labels = root / split / "labels"
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        (images / f"{name}.jpg").write_bytes(image_bytes)
        (labels / f"{name}.txt").write_text(VALID_POLYGON, encoding="utf-8")

    def test_clean_disjoint_splits_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._split(root, "train", "a", b"train")
            self._split(root, "val", "b", b"val")
            self._split(root, "test", "c", b"test")
            report = audit_dataset(root)
            self.assertTrue(report.clean)
            report.require_clean()

    def test_cross_split_duplicate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._split(root, "train", "a", b"same")
            self._split(root, "val", "b", b"same")
            report = audit_dataset(root)
            self.assertFalse(report.clean)
            with self.assertRaises(DatasetLeakageError):
                report.require_clean()

    def test_malformed_segmentation_label_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._split(root, "train", "a", b"train")
            (root / "train" / "labels" / "a.txt").write_text(
                "0 1.5 0.1 0.2 0.2 0.3 0.3\n", encoding="utf-8"
            )
            report = audit_dataset(root)
            self.assertFalse(report.clean)
            with self.assertRaises(ValueError):
                report.require_clean()


if __name__ == "__main__":
    unittest.main()
