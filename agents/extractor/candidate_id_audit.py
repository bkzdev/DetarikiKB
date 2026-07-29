"""Stage A Candidate ID の運用契約を匿名集計で監査する。

監査結果は件数だけを返し、episode ID、candidate ID、evidence ID、
ファイル名、パス、本文、名称を含めない。
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

CANDIDATE_ARRAY_SPECS = {
    "characters": ("character_candidate", "CHAR"),
    "organizations": ("organization_candidate", "ORG"),
    "locations": ("location_candidate", "LOC"),
    "items": ("item_candidate", "ITEM"),
    "lore": ("lore_candidate", "LORE"),
    "events": ("event_candidate", "EVENT"),
    "relationships": ("relationship_candidate", "REL"),
    "timelineCandidates": ("timeline_candidate", "TL"),
    "specialSpeakerLabelCandidates": (
        "special_speaker_label_candidate",
        "SSL",
    ),
}

_TYPE_PREFIXES = tuple(spec[1] for spec in CANDIDATE_ARRAY_SPECS.values())
_EXTRACTION_METHODS = frozenset({"rule_based", "llm", "manual", "hybrid"})
_TYPE_PREFIX_PATTERN = "|".join(
    sorted((re.escape(prefix) for prefix in _TYPE_PREFIXES), key=len, reverse=True)
)


@dataclass(frozen=True)
class EpisodeBlockOrder:
    """normalized episode内のBlock順とchoice内判定。"""

    ranks: dict[str, int]
    allowed_source_ids: frozenset[str]
    block_ids: frozenset[str]
    nested_ids: frozenset[str]
    duplicate_source_id_count: int = 0


def parse_candidate_id(
    candidate_id: Any, episode_id: Any
) -> tuple[str, int, bool] | None:
    """暫定IDを解析し、(type prefix, number, canonical number表記)を返す。"""
    if not isinstance(candidate_id, str) or not isinstance(episode_id, str):
        return None
    match = re.fullmatch(
        rf"{re.escape(episode_id)}_CAND_({_TYPE_PREFIX_PATTERN})(\d+)",
        candidate_id,
    )
    if match is None:
        return None
    number_text = match.group(2)
    try:
        number = int(number_text)
    except ValueError:
        return None
    return match.group(1), number, number_text == str(number).zfill(3)


def _collect_block_order(
    blocks: Any,
    *,
    nested: bool,
    ranks: dict[str, int],
    block_ids: set[str],
    nested_ids: set[str],
) -> int:
    duplicate_count = 0
    if not isinstance(blocks, list):
        return duplicate_count
    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_id = block.get("id")
        if isinstance(block_id, str) and block_id:
            block_ids.add(block_id)
            duplicate_count += _add_ordered_source_id(
                block_id,
                nested=nested,
                ranks=ranks,
                nested_ids=nested_ids,
            )
        for option in block.get("options", []) or []:
            if isinstance(option, dict):
                duplicate_count += _collect_block_order(
                    option.get("blocks", []),
                    nested=True,
                    ranks=ranks,
                    block_ids=block_ids,
                    nested_ids=nested_ids,
                )
    return duplicate_count


def _add_ordered_source_id(
    source_id: str,
    *,
    nested: bool,
    ranks: dict[str, int],
    nested_ids: set[str],
) -> int:
    if source_id in ranks:
        return 1
    ranks[source_id] = len(ranks)
    if nested:
        nested_ids.add(source_id)
    return 0


def build_normalized_episode_orders(  # noqa: C901
    normalized_documents: list[dict[str, Any]],
) -> tuple[dict[str, EpisodeBlockOrder], dict[str, int]]:
    """normalized documentsからepisodeごとのdepth-first preorderを構築する。"""
    orders: dict[str, EpisodeBlockOrder] = {}
    errors: Counter[str] = Counter()

    for document in normalized_documents:
        if not isinstance(document, dict):
            errors["normalizedDocumentInvalid"] += 1
            continue
        episodes = document.get("episodes", []) or []
        if not isinstance(episodes, list):
            errors["normalizedEpisodesInvalid"] += 1
            continue
        story_id = document.get("storyId")
        for episode in episodes:
            if not isinstance(episode, dict):
                errors["normalizedEpisodeInvalid"] += 1
                continue
            episode_id = episode.get("episodeId")
            if not isinstance(episode_id, str) or not episode_id:
                errors["normalizedEpisodeIdInvalid"] += 1
                continue
            if episode_id in orders:
                errors["normalizedEpisodeIdDuplicate"] += 1
                continue

            ranks: dict[str, int] = {}
            allowed_source_ids = {episode_id}
            if isinstance(story_id, str) and story_id:
                allowed_source_ids.add(story_id)
            block_ids: set[str] = set()
            nested_ids: set[str] = set()
            duplicate_count = 0
            scenes = episode.get("scenes", []) or []
            if not isinstance(scenes, list):
                errors["normalizedScenesInvalid"] += 1
                scenes = []
            for scene in scenes:
                if isinstance(scene, dict):
                    scene_id = scene.get("sceneId")
                    if isinstance(scene_id, str) and scene_id:
                        allowed_source_ids.add(scene_id)
                        duplicate_count += _add_ordered_source_id(
                            scene_id,
                            nested=False,
                            ranks=ranks,
                            nested_ids=nested_ids,
                        )
                    duplicate_count += _collect_block_order(
                        scene.get("blocks", []),
                        nested=False,
                        ranks=ranks,
                        block_ids=block_ids,
                        nested_ids=nested_ids,
                    )
            allowed_source_ids.update(block_ids)

            if duplicate_count:
                errors["normalizedSourceIdDuplicate"] += duplicate_count
            orders[episode_id] = EpisodeBlockOrder(
                ranks=ranks,
                allowed_source_ids=frozenset(allowed_source_ids),
                block_ids=frozenset(block_ids),
                nested_ids=frozenset(nested_ids),
                duplicate_source_id_count=duplicate_count,
            )

    return orders, dict(errors)


def _stable_projection(document: dict[str, Any]) -> str:
    """実行時metadataを除いた決定性比較用projectionを返す。"""

    def strip(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip(child)
                for key, child in value.items()
                if key != "extractionRun"
            }
        if isinstance(value, list):
            return [strip(child) for child in value]
        return value

    return json.dumps(
        strip(document),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _documents_by_episode(
    documents: list[dict[str, Any]], errors: Counter[str], error_key: str
) -> dict[str, dict[str, Any]]:
    by_episode: dict[str, dict[str, Any]] = {}
    for document in documents:
        if not isinstance(document, dict):
            errors["extractionDocumentInvalid"] += 1
            continue
        episode_id = document.get("episodeId")
        if not isinstance(episode_id, str) or not episode_id:
            errors["extractionEpisodeIdInvalid"] += 1
            continue
        if episode_id in by_episode:
            errors[error_key] += 1
            continue
        by_episode[episode_id] = document
    return by_episode


def audit_candidate_ids(  # noqa: C901
    extraction_documents: list[dict[str, Any]],
    normalized_documents: list[dict[str, Any]],
    comparison_documents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Candidate ID契約を検証し、匿名aggregate reportを返す。"""
    errors: Counter[str] = Counter()
    observations: Counter[str] = Counter()
    candidate_counts = dict.fromkeys(_TYPE_PREFIXES, 0)
    max_per_document = dict.fromkeys(_TYPE_PREFIXES, 0)
    method_counts: Counter[str] = Counter()

    episode_orders, normalized_errors = build_normalized_episode_orders(
        normalized_documents
    )
    errors.update(normalized_errors)
    documents_by_episode = _documents_by_episode(
        extraction_documents, errors, "extractionEpisodeIdDuplicate"
    )

    documents_with_candidates = 0
    global_candidate_ids: set[str] = set()
    nested_evidence_refs = 0
    candidates_with_nested_evidence = 0
    candidates_with_top_and_nested_evidence = 0
    same_type_multi_candidate_evidence_groups = 0
    max_same_type_evidence_fanout = 0

    for episode_id, document in documents_by_episode.items():
        extraction_run = document.get("extractionRun") or {}
        if not isinstance(extraction_run, dict):
            errors["extractionRunInvalid"] += 1
            extraction_run = {}
        method = extraction_run.get("extractionMethod", "unknown")
        if not isinstance(method, str) or method not in _EXTRACTION_METHODS:
            errors["extractionMethodInvalid"] += 1
            method = "unknown"
        method_counts[method] += 1
        order = episode_orders.get(episode_id)
        if order is None:
            errors["normalizedEpisodeMissing"] += 1

        document_candidate_count = 0
        for array_key, (
            expected_type,
            expected_prefix,
        ) in CANDIDATE_ARRAY_SPECS.items():
            candidates = document.get(array_key, []) or []
            if not isinstance(candidates, list):
                errors["candidateArrayInvalid"] += 1
                continue

            candidate_counts[expected_prefix] += len(candidates)
            max_per_document[expected_prefix] = max(
                max_per_document[expected_prefix], len(candidates)
            )
            document_candidate_count += len(candidates)
            observed_numbers: list[int] = []
            first_block_ranks: list[int] = []
            evidence_fanout: Counter[str] = Counter()

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    errors["candidateInvalid"] += 1
                    continue
                if candidate.get("type") != expected_type:
                    errors["candidateArrayTypeMismatch"] += 1

                candidate_id = candidate.get("id")
                parsed = parse_candidate_id(candidate_id, episode_id)
                if parsed is None:
                    errors["candidateIdPattern"] += 1
                else:
                    prefix, number, canonical_number = parsed
                    if prefix != expected_prefix:
                        errors["candidateIdTypeMismatch"] += 1
                    if not canonical_number:
                        errors["candidateIdNumberFormat"] += 1
                    if number < 1:
                        errors["candidateIdNumberNonPositive"] += 1
                    observed_numbers.append(number)
                    if number >= 1000:
                        observations["fourPlusDigitCandidateIds"] += 1

                if isinstance(candidate_id, str):
                    if candidate_id in global_candidate_ids:
                        errors["candidateIdDuplicate"] += 1
                    global_candidate_ids.add(candidate_id)

                evidence_ids = candidate.get("evidenceIds", []) or []
                if not isinstance(evidence_ids, list):
                    errors["candidateEvidenceInvalid"] += 1
                    continue
                string_evidence_ids = [
                    value for value in evidence_ids if isinstance(value, str)
                ]
                if len(string_evidence_ids) != len(evidence_ids):
                    errors["candidateEvidenceInvalid"] += 1
                if len(string_evidence_ids) != len(set(string_evidence_ids)):
                    errors["candidateEvidenceDuplicate"] += 1
                if order is not None:
                    unmatched_evidence_count = sum(
                        evidence_id not in order.allowed_source_ids
                        for evidence_id in string_evidence_ids
                    )
                    if unmatched_evidence_count:
                        errors["candidateEvidenceNotInNormalized"] += (
                            unmatched_evidence_count
                        )
                    for evidence_id in set(string_evidence_ids):
                        if evidence_id in order.block_ids:
                            evidence_fanout[evidence_id] += 1
                    block_ranks = [
                        order.ranks[evidence_id]
                        for evidence_id in string_evidence_ids
                        if evidence_id in order.ranks
                    ]
                    if method == "rule_based" and block_ranks != sorted(block_ranks):
                        errors["ruleBasedEvidencePreorder"] += 1
                    if block_ranks:
                        first_block_ranks.append(block_ranks[0])

                    nested_count = sum(
                        evidence_id in order.nested_ids
                        for evidence_id in string_evidence_ids
                    )
                    top_count = sum(
                        evidence_id in order.ranks
                        and evidence_id not in order.nested_ids
                        for evidence_id in string_evidence_ids
                    )
                    nested_evidence_refs += nested_count
                    if nested_count:
                        candidates_with_nested_evidence += 1
                    if nested_count and top_count:
                        candidates_with_top_and_nested_evidence += 1

            if method == "rule_based":
                if observed_numbers != list(range(1, len(candidates) + 1)):
                    errors["ruleBasedCandidateSequence"] += 1
                if first_block_ranks != sorted(first_block_ranks):
                    errors["ruleBasedCandidatePreorder"] += 1
            else:
                observations["nonRuleBasedSequenceChecksSkipped"] += 1

            multi_candidate_groups = sum(
                fanout > 1 for fanout in evidence_fanout.values()
            )
            same_type_multi_candidate_evidence_groups += multi_candidate_groups
            max_same_type_evidence_fanout = max(
                max_same_type_evidence_fanout,
                max(evidence_fanout.values(), default=0),
            )

        if document_candidate_count:
            documents_with_candidates += 1

    comparison = {
        "enabled": comparison_documents is not None,
        "missingFromComparisonDocuments": 0,
        "extraInComparisonDocuments": 0,
        "stableProjectionMismatchDocuments": 0,
    }
    if comparison_documents is not None:
        comparison_by_episode = _documents_by_episode(
            comparison_documents, errors, "comparisonEpisodeIdDuplicate"
        )
        primary_ids = set(documents_by_episode)
        comparison_ids = set(comparison_by_episode)
        comparison["missingFromComparisonDocuments"] = len(primary_ids - comparison_ids)
        comparison["extraInComparisonDocuments"] = len(comparison_ids - primary_ids)
        comparison["stableProjectionMismatchDocuments"] = sum(
            _stable_projection(documents_by_episode[episode_id])
            != _stable_projection(comparison_by_episode[episode_id])
            for episode_id in primary_ids & comparison_ids
        )
        for key in (
            "missingFromComparisonDocuments",
            "extraInComparisonDocuments",
            "stableProjectionMismatchDocuments",
        ):
            if comparison[key]:
                errors[key] += comparison[key]

    report = {
        "reportVersion": "1.0",
        "status": "pass" if not errors else "fail",
        "documentCount": len(documents_by_episode),
        "documentsWithCandidates": documents_with_candidates,
        "zeroCandidateDocuments": len(documents_by_episode) - documents_with_candidates,
        "candidateCount": sum(candidate_counts.values()),
        "candidateCountsByType": candidate_counts,
        "maxCandidatesPerDocumentByType": max_per_document,
        "extractionMethodCounts": dict(sorted(method_counts.items())),
        "errorCount": sum(errors.values()),
        "errorCountsByRule": dict(sorted(errors.items())),
        "observationCounts": dict(sorted(observations.items())),
        "normalizedCoverage": {
            "episodeCount": len(episode_orders),
            "blockCount": sum(
                len(order.block_ids) for order in episode_orders.values()
            ),
            "nestedBlockCount": sum(
                len(order.nested_ids) for order in episode_orders.values()
            ),
        },
        "evidenceObservations": {
            "nestedEvidenceReferenceCount": nested_evidence_refs,
            "candidatesWithNestedEvidence": candidates_with_nested_evidence,
            "candidatesWithTopAndNestedEvidence": (
                candidates_with_top_and_nested_evidence
            ),
            "sameTypeMultiCandidateEvidenceGroupCount": (
                same_type_multi_candidate_evidence_groups
            ),
            "maxSameTypeEvidenceFanout": max_same_type_evidence_fanout,
        },
        "comparison": comparison,
    }
    return report
