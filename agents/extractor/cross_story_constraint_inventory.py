"""EVT内のcross-story relative_order候補を判定せず集計する。"""

from __future__ import annotations

import json
from typing import Any

_SCOPE_STORY_CATEGORY = "EVT"
_SUPPORTED_RELATIONS = {"before", "after", "same_time"}


def _sort_key(value: Any) -> str:
    """任意のJSON値を決定的な比較キーへ変換する。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _document_ref(source_path: str, document: dict[str, Any]) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "storyId": document.get("storyId"),
        "episodeId": document.get("episodeId"),
        "storyCategory": document.get("storyCategory"),
        "extractionRun": dict(document.get("extractionRun") or {}),
    }


def _observation(
    source_path: str,
    document: dict[str, Any],
    candidate: dict[str, Any],
    target_document_refs: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "sourcePath": source_path,
        "sourceStoryId": document.get("storyId"),
        "sourceEpisodeId": document.get("episodeId"),
        "relativeTo": candidate.get("relativeTo"),
        "relation": candidate.get("relation"),
        "candidateId": candidate.get("id"),
        "evidenceIds": list(candidate.get("evidenceIds", []) or []),
        "sourceType": candidate.get("sourceType"),
        "confidence": candidate.get("confidence"),
        "extractionRun": dict(candidate.get("extractionRun") or {}),
        "targetDocumentRefs": target_document_refs,
    }


def _classification_record(reason: str, candidate: dict[str, Any]) -> dict[str, Any]:
    return {"reason": reason, "candidate": candidate}


def _classify_observation(
    observation: dict[str, Any],
    target_refs: list[dict[str, Any]],
) -> tuple[str, tuple[str, str] | None]:
    relative_to = observation["relativeTo"]
    relation = observation["relation"]
    if not isinstance(relative_to, str) or not relative_to:
        return "missing_relative_to", None
    if relation is None:
        return "missing_relation", None
    if relation not in _SUPPORTED_RELATIONS:
        return "unsupported_relation", None
    if not target_refs:
        return "target_not_loaded", None

    in_scope_target_refs = [
        reference
        for reference in target_refs
        if reference["storyCategory"] == _SCOPE_STORY_CATEGORY
    ]
    if not in_scope_target_refs:
        return "target_out_of_scope", None

    target_story_ids = sorted(
        {reference["storyId"] for reference in target_refs}, key=_sort_key
    )
    if len(target_story_ids) != 1:
        return "ambiguous_target_story", None
    if target_story_ids[0] == observation["sourceStoryId"]:
        return "same_story", None
    return "cross_story", tuple(
        sorted((observation["sourceStoryId"], target_story_ids[0]), key=_sort_key)
    )


def _store_classified_observation(
    observation: dict[str, Any],
    target_refs: list[dict[str, Any]],
    story_pair_candidates: dict[tuple[str, str], list[dict[str, Any]]],
    invalid_relative_candidates: list[dict[str, Any]],
    unresolved_targets: list[dict[str, Any]],
    ambiguous_target_stories: list[dict[str, Any]],
) -> int:
    classification, pair = _classify_observation(observation, target_refs)
    if classification == "same_story":
        return 1
    if classification == "cross_story":
        assert pair is not None
        story_pair_candidates.setdefault(pair, []).append(observation)
    elif classification in {"target_not_loaded", "target_out_of_scope"}:
        unresolved_targets.append(_classification_record(classification, observation))
    elif classification == "ambiguous_target_story":
        ambiguous_target_stories.append(
            _classification_record(classification, observation)
        )
    else:
        invalid_relative_candidates.append(
            _classification_record(classification, observation)
        )
    return 0


def build_cross_story_constraint_inventory(
    documents: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    """検証済み抽出結果からEVTのcross-story候補review queueを構築する。

    数値順序やcandidateの方向は正規化・判定せず、各観測をそのまま保持する。
    """
    sorted_documents = sorted(
        documents,
        key=lambda item: (item[0], _sort_key(item[1])),
    )
    document_refs_by_episode: dict[str, list[dict[str, Any]]] = {}
    in_scope_documents: list[tuple[str, dict[str, Any]]] = []
    out_of_scope_document_refs: list[dict[str, Any]] = []

    for source_path, document in sorted_documents:
        reference = _document_ref(source_path, document)
        episode_id = document.get("episodeId")
        if isinstance(episode_id, str):
            document_refs_by_episode.setdefault(episode_id, []).append(reference)
        if document.get("storyCategory") == _SCOPE_STORY_CATEGORY:
            in_scope_documents.append((source_path, document))
        else:
            out_of_scope_document_refs.append(reference)

    for references in document_refs_by_episode.values():
        references.sort(key=_sort_key)

    story_pair_candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    invalid_relative_candidates: list[dict[str, Any]] = []
    unresolved_targets: list[dict[str, Any]] = []
    ambiguous_target_stories: list[dict[str, Any]] = []
    relative_order_candidate_count = 0
    same_story_candidate_count = 0

    for source_path, document in in_scope_documents:
        candidates = sorted(
            (
                candidate
                for candidate in document.get("timelineCandidates", []) or []
                if candidate.get("kind") == "relative_order"
            ),
            key=_sort_key,
        )
        for candidate in candidates:
            relative_order_candidate_count += 1
            relative_to = candidate.get("relativeTo")
            target_refs = (
                list(document_refs_by_episode.get(relative_to, []))
                if isinstance(relative_to, str)
                else []
            )
            observation = _observation(source_path, document, candidate, target_refs)
            same_story_candidate_count += _store_classified_observation(
                observation,
                target_refs,
                story_pair_candidates,
                invalid_relative_candidates,
                unresolved_targets,
                ambiguous_target_stories,
            )

    story_pairs: list[dict[str, Any]] = []
    for story_ids, candidates in sorted(story_pair_candidates.items(), key=_sort_key):
        ordered_candidates = sorted(candidates, key=_sort_key)
        relation_counts = {
            relation: sum(
                candidate["relation"] == relation for candidate in ordered_candidates
            )
            for relation in sorted(_SUPPORTED_RELATIONS)
        }
        story_pairs.append(
            {
                "storyIds": list(story_ids),
                "candidateObservationCount": len(ordered_candidates),
                "relationCounts": relation_counts,
                "candidates": ordered_candidates,
            }
        )

    invalid_relative_candidates.sort(key=_sort_key)
    unresolved_targets.sort(key=_sort_key)
    ambiguous_target_stories.sort(key=_sort_key)
    out_of_scope_document_refs.sort(key=_sort_key)

    cross_story_candidate_observation_count = sum(
        pair["candidateObservationCount"] for pair in story_pairs
    )
    return {
        "scopeStoryCategory": _SCOPE_STORY_CATEGORY,
        "inScopeDocumentCount": len(in_scope_documents),
        "outOfScopeDocumentRefs": out_of_scope_document_refs,
        "relativeOrderCandidateCount": relative_order_candidate_count,
        "crossStoryCandidateObservationCount": cross_story_candidate_observation_count,
        "distinctStoryPairCount": len(story_pairs),
        "sameStoryCandidateCount": same_story_candidate_count,
        "unresolvedTargetCount": len(unresolved_targets),
        "ambiguousTargetStoryCount": len(ambiguous_target_stories),
        "invalidRelativeCandidateCount": len(invalid_relative_candidates),
        "storyPairs": story_pairs,
        "invalidRelativeCandidates": invalid_relative_candidates,
        "unresolvedTargets": unresolved_targets,
        "ambiguousTargetStories": ambiguous_target_stories,
    }
