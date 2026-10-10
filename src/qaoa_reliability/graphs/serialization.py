"""Validated JSON serialization for canonical graph records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from qaoa_reliability.graphs.schema import (
    SCHEMA_VERSION,
    GraphIntegrityError,
    GraphRecord,
    GraphSerializationError,
    GraphValidationError,
    JSONValue,
    compute_graph_id,
)

_RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "graph_id",
        "family",
        "n_nodes",
        "edges",
        "generation_seed",
        "generation_parameters",
    }
)


def graph_record_to_dict(record: GraphRecord) -> dict[str, JSONValue]:
    """Convert a validated graph record into a JSON-compatible dictionary.

    The graph ID is recomputed before conversion so an inconsistent record can
    never be written silently.
    """

    expected_id = compute_graph_id(record.n_nodes, record.edges)
    if record.graph_id != expected_id:
        raise GraphIntegrityError(
            f"graph_id does not match topology: expected {expected_id!r}"
        )

    # A JSON round trip makes a deep copy of nested provenance values, ensuring
    # callers cannot mutate the record by changing the returned dictionary.
    parameters = json.loads(json.dumps(record.generation_parameters, allow_nan=False))

    return {
        "schema_version": record.schema_version,
        "graph_id": record.graph_id,
        "family": record.family,
        "n_nodes": record.n_nodes,
        "edges": [[u, v] for u, v in record.edges],
        "generation_seed": record.generation_seed,
        "generation_parameters": parameters,
    }


def graph_record_from_dict(data: Mapping[str, object]) -> GraphRecord:
    """Validate a dictionary and reconstruct its canonical graph record."""
    if not isinstance(data, Mapping):
        raise GraphSerializationError("graph record must be a JSON object")
    non_string_fields = [key for key in data if not isinstance(key, str)]
    if non_string_fields:
        raise GraphSerializationError("graph record field names must be strings")

    supplied_fields = set(data)
    missing_fields = sorted(_RECORD_FIELDS - supplied_fields)
    unknown_fields = sorted(supplied_fields - _RECORD_FIELDS)
    if missing_fields:
        raise GraphSerializationError(
            f"graph record is missing required fields: {', '.join(missing_fields)}"
        )
    if unknown_fields:
        raise GraphSerializationError(
            f"graph record contains unknown fields: {', '.join(unknown_fields)}"
        )

    schema_version = data["schema_version"]
    if schema_version != SCHEMA_VERSION:
        raise GraphSerializationError(
            f"unsupported schema_version {schema_version!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )

    raw_edges = data["edges"]
    if not isinstance(raw_edges, list):
        raise GraphSerializationError("edges must be a JSON array")

    raw_parameters = data["generation_parameters"]
    if not isinstance(raw_parameters, Mapping):
        raise GraphSerializationError("generation_parameters must be a JSON object")

    try:
        edges = tuple(tuple(edge) for edge in raw_edges)
    except TypeError as error:
        raise GraphSerializationError(
            "each edge must be a JSON array containing two endpoints"
        ) from error

    try:
        return GraphRecord(
            schema_version=schema_version,
            graph_id=data["graph_id"],
            family=data["family"],
            n_nodes=data["n_nodes"],
            edges=edges,
            generation_seed=data["generation_seed"],
            generation_parameters=dict(raw_parameters),
        )
    except GraphIntegrityError:
        raise
    except (GraphValidationError, TypeError) as error:
        raise GraphSerializationError(f"invalid graph record: {error}") from error


def save_graph_record(record: GraphRecord, path: str | Path) -> None:
    """Write one graph record as deterministic, human-readable UTF-8 JSON."""
    destination = Path(path)
    payload = graph_record_to_dict(record)
    try:
        text = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        destination.write_text(f"{text}\n", encoding="utf-8")
    except (OSError, TypeError, ValueError) as error:
        raise GraphSerializationError(
            f"could not save graph record to {destination}: {error}"
        ) from error


def load_graph_record(path: str | Path) -> GraphRecord:
    """Load one UTF-8 JSON graph record and verify its structural identity."""

    source = Path(path)
    try:
        text = source.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise GraphSerializationError(
            f"could not read graph record from {source}: {error}"
        ) from error

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise GraphSerializationError(
            f"invalid JSON in graph record {source}: {error.msg}"
        ) from error

    if not isinstance(data, dict):
        raise GraphSerializationError("graph record must be a JSON object")
    return graph_record_from_dict(data)
