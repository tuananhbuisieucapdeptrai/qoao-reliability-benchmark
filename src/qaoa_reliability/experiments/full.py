"""Command-line entry point for the frozen T25 full pilot."""

from __future__ import annotations

import json
from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path

from qaoa_reliability.experiments.smoke import run_full_pilot


def main(argv: Sequence[str] | None = None) -> int:
    parser = ArgumentParser(description="Run the frozen T25 full pilot")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/manifests/pilot-v0.1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/full-pilot-v0.1"),
    )
    args = parser.parse_args(argv)
    execution = run_full_pilot(args.manifest, args.output)
    print(json.dumps(execution, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
