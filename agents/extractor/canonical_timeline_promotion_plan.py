"""Canonical Timeline promotion planの純粋projectionと意味整合性検査。

両APIはschemaおよびreview packet semantic validatorを通過したv0.2 packetを
入力前提とする。I/O、canonical artifactへの反映、review結果の変更は行わない。
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SOURCE_PACKET_MISMATCH = "canonical_timeline_promotion_source_packet_mismatch"
STORY_PAIR_MISMATCH = "canonical_timeline_promotion_story_pair_mismatch"
ELIGIBLE_EDGE_MISSING = "canonical_timeline_promotion_eligible_edge_missing"
ELIGIBLE_EDGE_EXTRA = "canonical_timeline_promotion_eligible_edge_extra"
SOURCE_EDGE_MODIFIED = "canonical_timeline_promotion_source_edge_modified"
PLAN_ENTRY_KEY_DUPLICATE = "canonical_timeline_promotion_plan_entry_key_duplicate"
REVIEW_EDGE_KEY_DUPLICATE = "canonical_timeline_promotion_review_edge_key_duplicate"
EXPIRY_STATUS_MISMATCH = "canonical_timeline_promotion_expiry_status_mismatch"


@dataclass(frozen=True)
class PromotionPlanBuildError(ValueError):
    """内部値を含まない固定codeのbuilder error。"""

    code: str

    def __str__(self) -> str:
        return self.code


def _stable_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_eligible(edge: dict[str, Any]) -> bool:
    return (
        edge["reviewStatus"] == "confirmed"
        and edge["relationState"] in {"before", "after", "same_time"}
        and edge["humanDecision"] is not None
    )


def _plan_id(
    created_at: datetime,
    source_packet: dict[str, Any],
    story_pair: list[dict[str, Any]],
    entries: list[dict[str, Any]],
) -> str:
    compact_timestamp = created_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(
        _stable_value(
            {
                "createdAt": _format_timestamp(created_at),
                "sourcePacket": source_packet,
                "storyPair": story_pair,
                "entries": entries,
            }
        ).encode("utf-8")
    ).hexdigest()[:8]
    return f"ctpp-{compact_timestamp}-{digest}"


def build_canonical_timeline_promotion_plan(
    packet: dict[str, Any],
    *,
    created_at: datetime,
) -> dict[str, Any]:
    """v0.2 packetのconfirmed known relationを非実行planへ完全複写する。

    入力packetはschema-validかつsemantic-validなv0.2であることが前提である。
    `created_at`はtimezone-awareでなければならず、eligible edgeが0件なら固定code
    errorを送出する。packetやそのedgeは変更しない。
    """
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise PromotionPlanBuildError("created-at-timezone-required")
    if packet["schemaVersion"] != "0.2":
        raise PromotionPlanBuildError("source-packet-v02-required")

    created_at_utc = created_at.astimezone(timezone.utc)
    source_packet = {
        key: deepcopy(packet[key])
        for key in (
            "packetId",
            "reviewBatchId",
            "schemaVersion",
            "createdAt",
            "expiresAt",
        )
    }
    source_packet["expiredAtPlanning"] = created_at_utc > _parse_timestamp(
        source_packet["expiresAt"]
    )
    eligible_edges = sorted(
        (edge for edge in packet["edges"] if _is_eligible(edge)),
        key=_stable_value,
    )
    if not eligible_edges:
        raise PromotionPlanBuildError("eligible-confirmed-known-relations-empty")
    if len(eligible_edges) > 9999:
        raise PromotionPlanBuildError(
            "eligible-edge-count-exceeds-plan-entry-key-capacity"
        )

    entries = [
        {
            "planEntryKey": f"plan-entry-{number:04d}",
            "proposedAction": "proposed_canonical_edge",
            "executionStatus": "not_executed",
            "sourceEdge": deepcopy(edge),
        }
        for number, edge in enumerate(eligible_edges, start=1)
    ]
    story_pair = deepcopy(packet["storyPair"])
    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_promotion_plan",
        "planId": _plan_id(created_at_utc, source_packet, story_pair, entries),
        "classification": "local_internal",
        "commitAllowed": False,
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "executionMode": "plan_only",
        "createdAt": _format_timestamp(created_at_utc),
        "sourcePacket": source_packet,
        "storyPair": story_pair,
        "entries": entries,
    }


def _finding(rule: str, **details: Any) -> dict[str, Any]:
    return {"rule": rule, "severity": "error", **details}


def _duplicate_findings(
    values: list[tuple[str, str]], rule: str, field: str
) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for value, entry_key in values:
        grouped[value].append(entry_key)
    return [
        _finding(rule, **{field: value, "count": len(keys)})
        for value, keys in sorted(grouped.items())
        if len(keys) > 1
    ]


def validate_canonical_timeline_promotion_plan_consistency(
    plan: dict[str, Any], packet: dict[str, Any]
) -> list[dict[str, Any]]:
    """schema/semantic-validなplanとv0.2 packetのprojection整合性を検査する。

    入力は変更せず、source packet、story pair、eligible edgeの1:1対応、重複、
    期限状態を固定ruleの決定的findingとして返す。
    """
    findings: list[dict[str, Any]] = []
    source_fields = (
        "packetId",
        "reviewBatchId",
        "schemaVersion",
        "createdAt",
        "expiresAt",
    )
    mismatched_fields = [
        field for field in source_fields if plan["sourcePacket"][field] != packet[field]
    ]
    if mismatched_fields:
        findings.append(
            _finding(SOURCE_PACKET_MISMATCH, fields=sorted(mismatched_fields))
        )
    if _stable_value(plan["storyPair"]) != _stable_value(packet["storyPair"]):
        findings.append(_finding(STORY_PAIR_MISMATCH))

    expected_expired = _parse_timestamp(plan["createdAt"]) > _parse_timestamp(
        packet["expiresAt"]
    )
    if plan["sourcePacket"]["expiredAtPlanning"] != expected_expired:
        findings.append(_finding(EXPIRY_STATUS_MISMATCH))

    entries = sorted(plan["entries"], key=_stable_value)
    findings.extend(
        _duplicate_findings(
            [(entry["planEntryKey"], entry["planEntryKey"]) for entry in entries],
            PLAN_ENTRY_KEY_DUPLICATE,
            "planEntryKey",
        )
    )
    findings.extend(
        _duplicate_findings(
            [
                (entry["sourceEdge"]["reviewEdgeKey"], entry["planEntryKey"])
                for entry in entries
            ],
            REVIEW_EDGE_KEY_DUPLICATE,
            "reviewEdgeKey",
        )
    )

    expected_edges = {
        edge["reviewEdgeKey"]: edge for edge in packet["edges"] if _is_eligible(edge)
    }
    actual_edges: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        actual_edges[entry["sourceEdge"]["reviewEdgeKey"]].append(entry)

    for edge_key in sorted(set(expected_edges) - set(actual_edges)):
        findings.append(_finding(ELIGIBLE_EDGE_MISSING, reviewEdgeKey=edge_key))
    for edge_key in sorted(set(actual_edges) - set(expected_edges)):
        findings.append(_finding(ELIGIBLE_EDGE_EXTRA, reviewEdgeKey=edge_key))
    for edge_key in sorted(set(expected_edges) & set(actual_edges)):
        for entry in actual_edges[edge_key]:
            if _stable_value(entry["sourceEdge"]) != _stable_value(
                expected_edges[edge_key]
            ):
                findings.append(
                    _finding(
                        SOURCE_EDGE_MODIFIED,
                        planEntryKey=entry["planEntryKey"],
                        reviewEdgeKey=edge_key,
                    )
                )

    return sorted(findings, key=_stable_value)
