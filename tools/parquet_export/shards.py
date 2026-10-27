
from pathlib import Path

from .index import Sample

ROW_GROUP_SIZE = 2048

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def plan_shards(samples: list[Sample], target_bytes: int) -> list[list[Sample]]:
    target = max(1, int(target_bytes))
    shards: list[list[Sample]] = []
    current: list[Sample] = []
    current_bytes = 0
    for sample in samples:
        estimated = sample.estimated_bytes
        if current and current_bytes + estimated > target:
            shards.append(current)
            current = []
            current_bytes = 0
        current.append(sample)
        current_bytes += estimated
    if current:
        shards.append(current)
    return shards


def shard_name(index: int, total: int) -> str:
    return f"train-{index:05d}-of-{total:05d}.parquet"


def parquet_schema():
    import pyarrow as pa

    return pa.schema([
        pa.field("image", pa.binary(), nullable=False),
        pa.field("file", pa.string(), nullable=False),
        pa.field("type_id", pa.string(), nullable=False),
        pa.field("plugin", pa.string(), nullable=False),
        pa.field("captcha", pa.string(), nullable=False),
        pa.field("answer", pa.string(), nullable=False),
        pa.field("text", pa.string(), nullable=True),
        pa.field("prompt", pa.string(), nullable=True),
        pa.field("roi", pa.list_(pa.int32()), nullable=True),
        pa.field("width", pa.int32(), nullable=False),
        pa.field("height", pa.int32(), nullable=False),
        pa.field("source", pa.string(), nullable=False),
        pa.field("tree", pa.string(), nullable=False),
    ])


def build_table(samples: list[Sample]):
    import pyarrow as pa

    schema = parquet_schema()
    images = []
    for sample in samples:
        payload = sample.path.read_bytes()
        if not payload.startswith(PNG_MAGIC):
            raise RuntimeError(f"not a PNG: {sample.path}")
        images.append(payload)
    arrays = [
        pa.array(images, type=pa.binary()),
        pa.array([s.file for s in samples], type=pa.string()),
        pa.array([s.type_id for s in samples], type=pa.string()),
        pa.array([s.plugin for s in samples], type=pa.string()),
        pa.array([s.captcha for s in samples], type=pa.string()),
        pa.array([s.answer for s in samples], type=pa.string()),
        pa.array([s.text for s in samples], type=pa.string()),
        pa.array([s.prompt for s in samples], type=pa.string()),
        pa.array([s.roi for s in samples], type=pa.list_(pa.int32())),
        pa.array([s.width for s in samples], type=pa.int32()),
        pa.array([s.height for s in samples], type=pa.int32()),
        pa.array([s.source for s in samples], type=pa.string()),
        pa.array([s.tree for s in samples], type=pa.string()),
    ]
    return pa.Table.from_arrays(arrays, schema=schema)


def write_shard(path: Path, samples: list[Sample]) -> int:
    import pyarrow.parquet as pq

    with pq.ParquetWriter(
        path,
        parquet_schema(),
        compression="snappy",
        use_dictionary=["type_id", "plugin", "captcha", "source", "tree"],
    ) as writer:
        for start in range(0, len(samples), ROW_GROUP_SIZE):
            batch = samples[start:start + ROW_GROUP_SIZE]
            writer.write_table(build_table(batch), row_group_size=ROW_GROUP_SIZE)
    return path.stat().st_size


def shard_rows(shards: list[tuple[Path, int]]) -> list[int]:
    import pyarrow.parquet as pq

    return [pq.ParquetFile(path).metadata.num_rows for path, _ in shards]
