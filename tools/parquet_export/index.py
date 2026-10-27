"""The index over the dataset: every label row and every PNG it points at."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Trees of the local dataset, in the order samples are written.
TREES = ("out", "out_ru")

#: Rough per-row overhead (label strings, page indexes) used only for planning.
ROW_OVERHEAD_BYTES = 384


@dataclass
class Sample:
    tree: str
    type_id: str
    path: Path
    file: str
    plugin: str
    captcha: str
    answer: str
    text: str | None
    prompt: str | None
    roi: list[int] | None
    width: int
    height: int
    source: str
    png_bytes: int

    @property
    def estimated_bytes(self) -> int:
        return self.png_bytes + ROW_OVERHEAD_BYTES


@dataclass
class TypeInfo:
    tree: str
    type_id: str
    plugin: str
    captcha: str
    labels_path: Path
    samples: int = 0
    png_bytes: int = 0
    roi_rows: int = 0
    text_ne_answer: int = 0


@dataclass
class DatasetIndex:
    samples: list[Sample] = field(default_factory=list)
    types: dict[str, TypeInfo] = field(default_factory=dict)
    missing_png: list[str] = field(default_factory=list)
    samples_per_tree: dict[str, int] = field(default_factory=dict)
    bytes_per_tree: dict[str, int] = field(default_factory=dict)
    types_per_tree: dict[str, int] = field(default_factory=dict)

    @property
    def total_png_bytes(self) -> int:
        return sum(s.png_bytes for s in self.samples)

    @property
    def estimated_parquet_bytes(self) -> int:
        return sum(s.estimated_bytes for s in self.samples)


def find_label_files(data_dir: Path) -> list[tuple[str, Path]]:
    """All ``labels.jsonl`` under the known trees, in deterministic order.

    ``real_shots`` directories are reference screenshots and are never part of the
    published dataset; they are skipped explicitly.
    """
    found: list[tuple[str, Path]] = []
    for tree in TREES:
        base = data_dir / tree
        if not base.is_dir():
            warn(f"tree not found: {base}")
            continue
        for labels in sorted(base.rglob("labels.jsonl")):
            if "real_shots" in labels.parts:
                continue
            found.append((tree, labels))
    return found


def build_index(data_dir: Path) -> DatasetIndex:
    """Read every ``labels.jsonl`` and stat every referenced PNG.

    Read-only: this function never creates or writes a file.
    """
    index = DatasetIndex()
    for tree, labels_path in find_label_files(data_dir):
        type_id = labels_path.parent.relative_to(data_dir).as_posix()
        if not type_id.startswith(tree + "/"):
            type_id = f"{tree}/{type_id}"
        info = TypeInfo(tree=tree, type_id=type_id, plugin="", captcha="",
                        labels_path=labels_path)
        with open(labels_path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                row = json.loads(line)
                png_path = labels_path.parent / row["file"]
                try:
                    png_bytes = png_path.stat().st_size
                except OSError:
                    index.missing_png.append(f"{type_id}/{row['file']}")
                    png_bytes = 0
                roi = row.get("roi")
                if roi is None:
                    roi_value = None
                else:
                    roi_value = [int(v) for v in roi]
                sample = Sample(
                    tree=tree,
                    type_id=type_id,
                    path=png_path,
                    file=str(row["file"]),
                    plugin=str(row["plugin"]),
                    captcha=str(row["captcha"]),
                    answer="" if row.get("answer") is None else str(row["answer"]),
                    text=None if row.get("text") is None else str(row["text"]),
                    prompt=None if row.get("prompt") is None else str(row["prompt"]),
                    roi=roi_value,
                    width=int(row["width"]),
                    height=int(row["height"]),
                    source="" if row.get("source") is None else str(row["source"]),
                    png_bytes=png_bytes,
                )
                if not info.plugin:
                    info.plugin = sample.plugin
                    info.captcha = sample.captcha
                info.samples += 1
                info.png_bytes += png_bytes
                if roi_value is not None:
                    info.roi_rows += 1
                if sample.text is not None and sample.answer is not None \
                        and sample.text != sample.answer:
                    info.text_ne_answer += 1
                index.samples.append(sample)
        if info.samples == 0:
            warn(f"empty labels file, skipped: {type_id}")
            continue
        index.types[type_id] = info
        index.samples_per_tree[tree] = index.samples_per_tree.get(tree, 0) + info.samples
        index.bytes_per_tree[tree] = index.bytes_per_tree.get(tree, 0) + info.png_bytes
        index.types_per_tree[tree] = index.types_per_tree.get(tree, 0) + 1
    return index


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)
