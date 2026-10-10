"""Tests for validated graph-record serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from qaoa_reliability.graphs.schema import (
    GraphIntegrityError,
    GraphRecord,
    GraphSerializationError,
)
from qaoa_reliability.graphs.serialization import (
    graph_record_from_dict,
    graph_record_to_dict,
    load_graph_record,
    save_graph_record,
)


@pytest.fixture
def record() -> GraphRecord:
    return GraphRecord.from_topology(
        family="fixture",
        n_nodes=4,
        edges=[(2, 1), (1, 0)],
        generation_seed=42,
        generation_parameters={
            "purpose": "round-trip test",
            "nested": {"probabilities": [0.25, 0.75]},
        },
    )


def test_dictionary_round_trip(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)

    assert graph_record_from_dict(payload) == record
    assert payload["edges"] == [[0, 1], [1, 2]]


def test_dictionary_output_is_a_deep_copy(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    parameters = payload["generation_parameters"]
    assert isinstance(parameters, dict)
    nested = parameters["nested"]
    assert isinstance(nested, dict)
    probabilities = nested["probabilities"]
    assert isinstance(probabilities, list)

    probabilities.append(1.0)

    assert record.generation_parameters["nested"] == {"probabilities": [0.25, 0.75]}


def test_json_file_round_trip(tmp_path: Path, record: GraphRecord) -> None:
    path = tmp_path / "graph.json"

    save_graph_record(record, path)
    loaded = load_graph_record(path)

    assert loaded == record


def test_saved_json_is_stable_readable_and_newline_terminated(
    tmp_path: Path, record: GraphRecord
) -> None:
    path = tmp_path / "graph.json"
    save_graph_record(record, path)

    saved = path.read_text(encoding="utf-8")

    assert saved.endswith("\n")
    assert json.loads(saved)["edges"] == [[0, 1], [1, 2]]
    assert saved.index('"edges"') < saved.index('"family"')


def test_provenance_changes_do_not_change_graph_id(record: GraphRecord) -> None:
    changed = GraphRecord.from_topology(
        family="another_source",
        n_nodes=record.n_nodes,
        edges=record.edges,
        generation_seed=999,
        generation_parameters={"note": "different provenance"},
    )

    assert changed.graph_id == record.graph_id


def test_changed_topology_with_stale_id_is_rejected(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    payload["edges"] = [[0, 1], [1, 3]]

    with pytest.raises(GraphIntegrityError, match="does not match"):
        graph_record_from_dict(payload)


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ("family", "missing required fields: family"),
        ("graph_id", "missing required fields: graph_id"),
        ("generation_parameters", "missing required fields: generation_parameters"),
    ],
)
def test_missing_required_fields_are_rejected(
    record: GraphRecord, field: str, message: str
) -> None:
    payload = graph_record_to_dict(record)
    del payload[field]

    with pytest.raises(GraphSerializationError, match=message):
        graph_record_from_dict(payload)


def test_unknown_fields_are_rejected(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    payload["graph_name"] = "unexpected"

    with pytest.raises(GraphSerializationError, match="unknown fields: graph_name"):
        graph_record_from_dict(payload)


def test_non_string_field_name_is_rejected(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    payload[1] = "invalid"  # type: ignore[index]

    with pytest.raises(GraphSerializationError, match="field names must be strings"):
        graph_record_from_dict(payload)


def test_unsupported_schema_version_is_rejected(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    payload["schema_version"] = "99.0"

    with pytest.raises(GraphSerializationError, match="unsupported schema_version"):
        graph_record_from_dict(payload)


def test_malformed_edge_is_rejected(record: GraphRecord) -> None:
    payload = graph_record_to_dict(record)
    payload["edges"] = [[0, 1, 2]]

    with pytest.raises(GraphSerializationError, match="exactly two endpoints"):
        graph_record_from_dict(payload)


def test_malformed_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text('{"not": valid JSON}', encoding="utf-8")

    with pytest.raises(GraphSerializationError, match="invalid JSON"):
        load_graph_record(path)


def test_non_object_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(GraphSerializationError, match="must be a JSON object"):
        load_graph_record(path)


def test_missing_file_has_a_domain_specific_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.json"

    with pytest.raises(GraphSerializationError, match="could not read"):
        load_graph_record(path)
