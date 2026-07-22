"""Dataset integrity audit for YOLO segmentation projects."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


class DatasetLeakageError(RuntimeError):
    """Raised when byte-identical images exist across dataset splits."""


@dataclass
class SplitStats:
    images: int = 0
    labels: int = 0
    objects: int = 0
    classes: Counter[int] = field(default_factory=Counter)
    missing_labels: list[str] = field(default_factory=list)
    malformed_labels: list[str] = field(default_factory=list)


@dataclass
class AuditReport:
    root: Path
    splits: dict[str, SplitStats]
    duplicate_hashes: dict[str, list[str]]

    @property
    def clean(self) -> bool:
        return not self.duplicate_hashes and all(
            not stats.missing_labels and not stats.malformed_labels
            for stats in self.splits.values()
        )

    def require_clean(self) -> None:
        if self.duplicate_hashes:
            examples = next(iter(self.duplicate_hashes.values()))
            raise DatasetLeakageError(
                "cross-split duplicate images detected: " + ", ".join(examples)
            )
        problems = [
            f"{name}: missing={len(stats.missing_labels)}, malformed={len(stats.malformed_labels)}"
            for name, stats in self.splits.items()
            if stats.missing_labels or stats.malformed_labels
        ]
        if problems:
            raise ValueError("dataset label audit failed: " + "; ".join(problems))


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_label(path: Path, stats: SplitStats) -> None:
    stats.labels += 1
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        reference = f"{path}:{line_number}"
        try:
            class_id = int(tokens[0])
            coordinates = [float(token) for token in tokens[1:]]
        except ValueError:
            stats.malformed_labels.append(reference)
            continue
        if len(coordinates) < 6 or len(coordinates) % 2 != 0:
            stats.malformed_labels.append(reference)
            continue
        if any(not 0.0 <= coordinate <= 1.0 for coordinate in coordinates):
            stats.malformed_labels.append(reference)
            continue
        stats.objects += 1
        stats.classes[class_id] += 1


def audit_dataset(
    root: str | Path,
    splits: tuple[str, ...] = ("train", "val", "valid", "test"),
) -> AuditReport:
    root_path = Path(root).resolve()
    stats_by_split: dict[str, SplitStats] = {}
    hashes: dict[str, list[str]] = defaultdict(list)

    for split in splits:
        images_dir = root_path / split / "images"
        labels_dir = root_path / split / "labels"
        if not images_dir.exists():
            continue
        stats = SplitStats()
        stats_by_split[split] = stats
        images = sorted(
            path for path in images_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        stats.images = len(images)
        for image in images:
            hashes[_file_hash(image)].append(f"{split}/{image.name}")
            label = labels_dir / f"{image.stem}.txt"
            if not label.exists():
                stats.missing_labels.append(str(label))
            else:
                _validate_label(label, stats)

    duplicate_hashes = {
        digest: paths
        for digest, paths in hashes.items()
        if len({path.split("/", 1)[0] for path in paths}) > 1
    }
    return AuditReport(root=root_path, splits=stats_by_split, duplicate_hashes=duplicate_hashes)
