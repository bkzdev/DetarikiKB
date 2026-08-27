"""Canonical Timeline promotionのread-only preflight。

schema-validかつpromotion planのcross-document semantic validation済みの入力を
前提に、既存canonical Timelineへplanを仮想追加した場合だけを検査する。
I/O、schema検証、artifact更新、adoptionの実行は行わない。
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from agents.extractor.canonical_timeline_consistency import (
    SAME_TIME_CONTRADICTION,
    validate_canonical_timeline_consistency,
)

BASELINE_INVALID = "canonical_timeline_promotion_preflight_baseline_invalid"


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _node_key(node: dict[str, Any]) -> tuple[str, str]:
    return (node["storyId"], node["episodeId"])


def _project_edge(entry: dict[str, Any]) -> dict[str, Any]:
    """plan固有fieldを落としたcanonical Timeline edgeのdeep-copy projection。"""
    source_edge = entry["sourceEdge"]
    return {
        "from": deepcopy(source_edge["from"]),
        "to": deepcopy(source_edge["to"]),
        "relationState": deepcopy(source_edge["relationState"]),
        "stateReason": deepcopy(source_edge["stateReason"]),
        "adoptionStatus": "canonical",
        "reviewStatus": deepcopy(source_edge["reviewStatus"]),
        "candidateProvenance": deepcopy(source_edge["candidateProvenance"]),
        "humanDecision": deepcopy(source_edge["humanDecision"]),
    }


def _build_preflight_document(
    plan: dict[str, Any], canonical_timeline: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """入力を変更せず仮canonical documentとedge record→plan key対応を作る。"""
    nodes = deepcopy(canonical_timeline["nodes"])
    existing_node_keys = {_node_key(node) for node in nodes}
    projected: list[tuple[str, dict[str, Any]]] = [
        (entry["planEntryKey"], _project_edge(entry)) for entry in plan["entries"]
    ]
    projected.sort(key=lambda item: (item[0], _stable_value(item[1])))

    missing_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    edge_keys: dict[str, list[str]] = {}
    for plan_entry_key, edge in projected:
        edge_keys.setdefault(_stable_value(edge), []).append(plan_entry_key)
        for endpoint in (edge["from"], edge["to"]):
            key = _node_key(endpoint)
            if key not in existing_node_keys:
                missing_nodes.setdefault(key, deepcopy(endpoint))

    nodes.extend(missing_nodes[key] for key in sorted(missing_nodes))
    return (
        {
            "schemaVersion": "0.1",
            "documentType": "canonical_timeline",
            "scopeStoryCategory": "EVT",
            "visibility": "internal_only",
            "nodes": nodes,
            "edges": [
                *deepcopy(canonical_timeline["edges"]),
                *(edge for _key, edge in projected),
            ],
        },
        {record: sorted(keys) for record, keys in edge_keys.items()},
    )


def _finding_records(finding: dict[str, Any]) -> set[str]:
    """既存validatorのsafeなedge参照からrecordだけを取り出す。"""
    records: set[str] = set()
    edge = finding.get("edge")
    if edge is not None:
        records.add(edge["record"])
    for item in finding.get("edges", []):
        records.add(item["record"])
    return records


def _finding_plan_entry_keys(
    finding: dict[str, Any], entry_keys_by_record: dict[str, list[str]]
) -> set[str]:
    """findingへ因果的に関係するplan entry keyを内部的に解決する。"""
    entry_keys = {
        entry_key
        for record in _finding_records(finding)
        for entry_key in entry_keys_by_record.get(record, [])
    }
    if finding["rule"] != SAME_TIME_CONTRADICTION:
        return entry_keys

    same_time_class = {
        (node["storyId"], node["episodeId"]) for node in finding["sameTimeClass"]
    }
    for record, record_entry_keys in entry_keys_by_record.items():
        edge = json.loads(record)
        if (
            edge["relationState"] == "same_time"
            and _node_key(edge["from"]) in same_time_class
            and _node_key(edge["to"]) in same_time_class
        ):
            entry_keys.update(record_entry_keys)
    return entry_keys


def preflight_canonical_timeline_promotion(
    plan: dict[str, Any], canonical_timeline: dict[str, Any]
) -> dict[str, Any]:
    """planの仮想追加によるsemantic findingだけをsafe aggregateで返す。

    baseline artifactにfindingがあれば、内部node/edge/provenanceを露出せず固定ruleと
    件数だけを返してfail-closedにする。clean時も同じsafe aggregate形式を返す。
    """
    baseline_findings = validate_canonical_timeline_consistency(canonical_timeline)
    if baseline_findings:
        return {
            "status": "blocked",
            "findings": [{"rule": BASELINE_INVALID, "count": len(baseline_findings)}],
        }

    document, entry_keys_by_record = _build_preflight_document(plan, canonical_timeline)
    aggregates: dict[tuple[str, str], int] = {}
    for finding in validate_canonical_timeline_consistency(document):
        for entry_key in sorted(
            _finding_plan_entry_keys(finding, entry_keys_by_record)
        ):
            aggregate_key = (entry_key, finding["rule"])
            aggregates[aggregate_key] = aggregates.get(aggregate_key, 0) + 1

    return {
        "status": "clean" if not aggregates else "blocked",
        "findings": [
            {"planEntryKey": entry_key, "rule": rule, "count": count}
            for (entry_key, rule), count in sorted(aggregates.items())
        ],
    }
