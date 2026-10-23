"""Append-only JSONL persistence for optimization trajectories."""

from __future__ import annotations

import json
from pathlib import Path

from qaoa_reliability.optimization.schema import TrajectoryRecord


def save_trajectory_record(record: TrajectoryRecord, path: str | Path) -> None:
    """Append and flush one complete trajectory record."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        record.to_dict(),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    with destination.open("a", encoding="utf-8") as stream:
        stream.write(encoded + "\n")
        stream.flush()


def load_trajectory_jsonl(path: str | Path) -> tuple[TrajectoryRecord, ...]:
    """Load and validate every non-empty JSONL record."""

    records: list[TrajectoryRecord] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                record = TrajectoryRecord.from_dict(payload)
            except (json.JSONDecodeError, ValueError) as error:
                raise ValueError(
                    f"invalid trajectory JSONL record on line {line_number}"
                ) from error
            records.append(record)
    return tuple(records)
