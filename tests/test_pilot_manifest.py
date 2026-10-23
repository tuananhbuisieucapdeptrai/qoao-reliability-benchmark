"""Validation and reproducibility tests for the frozen T21 pilot manifest."""

from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pytest

from qaoa_reliability.experiments import load_pilot_manifest
from qaoa_reliability.graphs.generators import generate_graph
from qaoa_reliability.graphs.schema import to_networkx

MANIFEST_PATH = Path("experiments/manifests/pilot-v0.1.json")
EXPECTED_MANIFEST_ID = (
    "sha256:84a992b08c73e3988cf4773c2b919e930e5ac2e6bd361970bad411f6698d80f3"
)


def test_frozen_pilot_matrix_and_workload() -> None:
    manifest = load_pilot_manifest(MANIFEST_PATH)

    assert manifest.manifest_id == EXPECTED_MANIFEST_ID
    assert {batch.family for batch in manifest.graph_batches} == {
        "erdos_renyi",
        "random_regular",
        "watts_strogatz",
        "stochastic_block_model",
    }
    assert {batch.n_nodes for batch in manifest.graph_batches} == {8, 10}
    assert all(len(batch.seeds) == 5 for batch in manifest.graph_batches)
    assert manifest.graph_count == 40
    assert manifest.optimizer_seeds == tuple(range(10))
    assert manifest.depths == (1,)
    assert manifest.budgets == (25, 50, 100)
    assert manifest.run_count == 400
    assert manifest.maximum_objective_evaluations == 40_000
    assert manifest.evaluator == "numpy_statevector@1.0"
    assert manifest.target_ratio == 0.95


def test_every_listed_graph_is_reproducible_connected_and_unique() -> None:
    manifest = load_pilot_manifest(MANIFEST_PATH)
    first = [generate_graph(spec) for spec in manifest.graph_specs]
    second = [generate_graph(spec) for spec in manifest.graph_specs]

    assert first == second
    assert len({record.graph_id for record in first}) == 40
    assert all(nx.is_connected(to_networkx(record)) for record in first)


def test_content_tampering_is_detected(tmp_path) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["budgets"] = [25, 50, 99]
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="manifest_id"):
        load_pilot_manifest(path)


def test_missing_required_field_is_rejected(tmp_path) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    del payload["optimizer_seeds"]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid pilot manifest"):
        load_pilot_manifest(path)
