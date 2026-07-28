#!/usr/bin/env python3
"""Measure renderer-neutral graph preparation at the 1k/10k boundaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.graph_explorer import (  # noqa: E402
    build_visual_spec,
    graph_performance_policy,
)


def synthetic_evidence(node_count: int) -> dict:
    nodes = [
        {
            "id": f"node-{index}",
            "label": "ProcessRun",
            "properties": {
                "run_id": f"RUN-{index:05d}",
                "sequence": index,
            },
        }
        for index in range(node_count)
    ]
    relationships = [
        {
            "id": f"relationship-{index}",
            "source": f"node-{index}",
            "target": f"node-{index + 1}",
            "type": "NEXT",
            "properties": {},
        }
        for index in range(max(node_count - 1, 0))
    ]
    return {
        "root_id": "node-0" if nodes else None,
        "nodes": nodes,
        "relationships": relationships,
    }


def measure(node_count: int, repeats: int) -> dict:
    evidence = synthetic_evidence(node_count)
    policy = graph_performance_policy(node_count)
    timings = []
    visual = None
    for _ in range(repeats):
        started = perf_counter()
        visual = build_visual_spec(
            evidence,
            identity_by_label={"ProcessRun": "run_id"},
            root_id=evidence["root_id"],
            label_mode=policy.label_mode,
        )
        timings.append((perf_counter() - started) * 1_000)
    assert visual is not None
    encoded_bytes = len(
        json.dumps(visual, ensure_ascii=False).encode("utf-8")
    )
    return {
        "node_count": node_count,
        "relationship_count": len(evidence["relationships"]),
        "renderer_policy": policy.renderer,
        "label_mode": policy.label_mode,
        "sampling_required": policy.sampling_required,
        "recommended_limit": policy.recommended_limit,
        "preparation_ms_median": round(statistics.median(timings), 3),
        "preparation_ms_max": round(max(timings), 3),
        "serialized_payload_bytes": encoded_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--sizes", nargs="+", type=int, default=[1_000, 10_000]
    )
    args = parser.parse_args()
    payload = {
        "scope": (
            "Python preprocessing only; browser FPS and interaction latency "
            "must be measured separately on the deployment device."
        ),
        "results": [
            measure(size, max(1, args.repeats)) for size in args.sizes
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

