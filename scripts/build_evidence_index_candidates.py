#!/usr/bin/env python3
"""
Build Evidence Index Candidates
Normalized Story JSON（必要ならExtraction Resultも補助的に）から、
Public Evidence Index候補YAML（`schemas/evidence_index.schema.json`準拠）を
生成するdry-run用の最小スクリプト。

`docs/architecture/06_AI/Evidence_Index_Design.md` §7.5の採用方針
（source of truthはDedicated Evidence Index file、生成元はNormalized
Story JSON + Extraction Result）を実装したPhase 4
（`evidence-index-generation-dry-run`）。

**重要な制約**（Evidence_Index_Design.md §6、feature/evidence-index-
generation-dry-run）:
- raw dialogue text / raw DEC command / 元セリフ全文 / local pathは
  一切出力しない。Blockの`text`/`rawText`/`raw`/`rawCommand`/`args`等の
  本文系フィールドは読み取らない（存在を検知してカウントするのみ）
- 既存のBlock IDがあるBlockのみ候補化する。IDが無いBlockはskipし、
  reportにカウントする（新しいID生成ルールはこのスクリプトで増やさない）
- speaker情報は`speaker.isResolved`が`true`かつ`speakerId`がある場合のみ
  （displayNameは出力しない、confirmed character dictionary経由で
  解決済みの構造化IDのみを信頼する）
- Scene/Episode/Story単位の粗い粒度のEvidence entryはこのスクリプトでは
  生成しない（Block単位のみ、次PR以降の検討課題）
- 生成物は必ず`--output`配下（呼び出し側がworkspace配下を指定する想定）
  へ書き込む。このスクリプト自体はcommit可否を判断しない
  （`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`参照）
- Internal Review Evidence Packetは生成しない（Public Evidence Index
  候補のみを対象とする）

**entry type filtering**（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`
§4・§7、feature/evidence-index-generation-filtering）:
- `--public-profile default|full|review`でPublic向け/全件/review向けの
  evidenceType集合を切り替える。**デフォルトは`default`**（Public向け、
  `stage_direction`を除外する）。PR #85相当の全type生成が必要な場合は
  `--public-profile full`を指定する
- `--include-types`/`--exclude-types`（comma区切りのevidenceType一覧）で
  profileのtype集合を上書き・追加除外できる。優先順位は
  「profile → `--include-types`（指定時はprofileのinclude集合を丸ごと
  置き換え） → `--exclude-types`（常に最後に適用、includeと衝突時は
  excludeが勝つ）」
- filterで除外されたBlockは**skip（`skippedBlockCount`）ではなく
  filter（`filteredEntryCount`）としてカウントする**（IDが無い/type未対応で
  「そもそも候補化できない」skipと、「候補化はできるがprofileにより
  出力しない」filterは意味が異なるため区別する）
- `referencedBy.candidates`はfilterで出力対象になったentryにのみ付与する
  （filteredで除外されたentryのcandidate referencesはreportにも出力YAMLにも
  含まれない）

Usage:
    # Normalized Story JSON単体、または directory (直下の*.jsonを収集)
    # --public-profileを省略した場合はdefault（Public向け、stage_direction除外）
    uv run python scripts/build_evidence_index_candidates.py \\
        --input workspace/dry_runs/evidence_index_generation/normalized \\
        --output workspace/evidence_index_dry_runs/evidence_index_generation \\
        --clean

    # Extraction Resultを補助的に使う場合 (referencedBy.candidatesの補完)
    uv run python scripts/build_evidence_index_candidates.py \\
        --input workspace/dry_runs/evidence_index_generation/normalized \\
        --extractions workspace/dry_runs/evidence_index_generation/extracted \\
        --output workspace/evidence_index_dry_runs/evidence_index_generation \\
        --clean

    # stage_directionも含めた全type生成 (review/internal用途)
    uv run python scripts/build_evidence_index_candidates.py \\
        --input workspace/dry_runs/evidence_index_generation/normalized \\
        --output workspace/evidence_index_dry_runs/evidence_index_generation_full \\
        --public-profile full \\
        --clean

Exit codes:
    0: 生成成功（0件の場合も含む）
    1: 生成したEvidence Index候補がschema検証/整合性検証に失敗した、
       または入力JSONの読み込みに失敗した (すべての入力が読めなかった場合)
    2: --inputパスが見つからない、または--include-types/--exclude-types に
       未知のevidenceTypeが指定された
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.wiki_generator.evidence_index import (  # noqa: E402
    VALID_EVIDENCE_TYPES,
    EvidenceIndexCollection,
    parse_evidence_index_document,
    validate_evidence_index_collection,
)

DEFAULT_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "evidence_index.schema.json"

# Block type (Normalized_Story_JSON.md §13.2) -> evidenceType
# (Evidence_Index_Design.md §8)。raw command名 (@ChTalk等) はここに含めない。
BLOCK_TYPE_TO_EVIDENCE_TYPE: dict[str, str] = {
    "dialogue": "dialogue",
    "monologue": "monologue",
    "narration": "narration",
    "choice": "choice",
    "stage_direction": "stage_direction",
    "unknown": "unknown",
}

# このスクリプトが実際に生成しうるevidenceType (Scene/Episode/Story/
# speaker_labelは生成しないため含まない)。
GENERATABLE_EVIDENCE_TYPES: frozenset[str] = frozenset(
    BLOCK_TYPE_TO_EVIDENCE_TYPE.values()
)

# public-profile方針 (docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md
# §4・§7)。PR #86で決定したPublic向け初期公開entry typeを"default"の既定値に
# する。"review"は本PRでは"full"と同じ挙動 (将来Internal Review Evidence
# Packetに寄せる可能性があるため名前だけ予約する)。
PUBLIC_PROFILE_DEFAULT = "default"
PUBLIC_PROFILE_FULL = "full"
PUBLIC_PROFILE_REVIEW = "review"

PUBLIC_PROFILES: dict[str, frozenset[str]] = {
    PUBLIC_PROFILE_DEFAULT: frozenset(
        {"dialogue", "monologue", "narration", "choice", "unknown"}
    ),
    PUBLIC_PROFILE_FULL: GENERATABLE_EVIDENCE_TYPES,
    PUBLIC_PROFILE_REVIEW: GENERATABLE_EVIDENCE_TYPES,
}

# Extraction Result側のcandidate配列キー -> CandidateReference.entityType
# (schemas/evidence_index.schema.json definitions/CandidateReference.entityType)
EXTRACTION_ARRAY_TO_ENTITY_TYPE: dict[str, str] = {
    "characters": "character",
    "organizations": "organization",
    "locations": "location",
    "items": "item",
    "lore": "lore",
    "events": "event",
    "relationships": "relationship",
    "timelineCandidates": "timeline",
}

# raw text本文系フィールド。値は一切読み取らないが、存在をreportで
# カウントする (「除外した」ことの証跡)。
RAW_TEXT_FIELD_NAMES: tuple[str, ...] = (
    "text",
    "rawText",
    "raw",
    "rawCommand",
    "args",
    "choiceText",
    "optionText",
)


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def _parse_evidence_type_list(value: str) -> tuple[str, ...]:
    """comma区切りのevidenceType一覧を検証しながらパースする。

    argparseの`type=`に渡すことで、未知のtypeが指定された場合に
    argparse自身がusageを表示してexit code 2で終了する。
    """
    types = tuple(t.strip() for t in value.split(",") if t.strip())
    invalid = sorted({t for t in types if t not in VALID_EVIDENCE_TYPES})
    if invalid:
        raise argparse.ArgumentTypeError(
            f"未知のevidenceType: {', '.join(invalid)} "
            f"(有効な値: {', '.join(sorted(VALID_EVIDENCE_TYPES))})"
        )
    return types


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalized Story JSON (必要ならExtraction Resultも補助的に) から "
            "Public Evidence Index候補YAMLをdry-run生成する"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  uv run python scripts/build_evidence_index_candidates.py \\
      --input workspace/dry_runs/evidence_index_generation/normalized \\
      --output workspace/evidence_index_dry_runs/evidence_index_generation \\
      --clean
""",
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Normalized Story JSONファイル、またはdirectory (直下の*.jsonを収集)",
    )
    parser.add_argument(
        "--extractions",
        default=None,
        help=(
            "episode_extraction JSONファイル、またはdirectory (任意)。"
            "指定した場合のみreferencedBy.candidatesを補完する"
        ),
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=(
            "出力先ディレクトリ。直下に stories/{storyId}.yaml・report.md・"
            "report.jsonを書き出す (workspace配下を指定すること、"
            "commit対象にしない)"
        ),
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--public-profile",
        choices=sorted(PUBLIC_PROFILES),
        default=PUBLIC_PROFILE_DEFAULT,
        help=(
            "生成対象evidenceTypeのprofile (デフォルト: default = Public向け、"
            "stage_directionを除外。full/reviewはstage_directionを含む全type)"
        ),
    )
    parser.add_argument(
        "--include-types",
        type=_parse_evidence_type_list,
        default=None,
        help=(
            "comma区切りのevidenceType一覧。指定した場合、--public-profileの"
            "include集合をこの一覧で置き換える (例: dialogue,narration)"
        ),
    )
    parser.add_argument(
        "--exclude-types",
        type=_parse_evidence_type_list,
        default=None,
        help=(
            "comma区切りのevidenceType一覧。--public-profile/--include-types"
            "で決まった集合から、常に最後にこの一覧を除外する"
            "(includeと衝突した場合はexcludeが勝つ)"
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="出力先ディレクトリを書き込み前に削除する",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _resolve_included_types(args: argparse.Namespace) -> frozenset[str]:
    """--public-profile/--include-types/--exclude-typesから、最終的に
    出力対象とするevidenceType集合を決定する
    (Evidence_Index_Promotion_Policy.md §4・§7の優先順位)。

    1. --public-profileのinclude集合から開始する
    2. --include-typesが指定されていれば、profileのinclude集合を
       丸ごと置き換える (union ではなく置き換え)
    3. --exclude-typesが指定されていれば、常に最後に除外する
       (includeと衝突した場合はexcludeが勝つ)
    """
    included = set(PUBLIC_PROFILES[args.public_profile])
    if args.include_types is not None:
        included = set(args.include_types)
    if args.exclude_types is not None:
        included -= set(args.exclude_types)
    return frozenset(included)


# ----------------------------------------------------------------
# Input collection
# ----------------------------------------------------------------


def _collect_json_paths(input_path: Path) -> list[Path] | None:
    """--input/--extractionsがファイルならそれ単体、directoryなら直下の
    *.jsonを返す (非recursive、既存の`_collect_yaml_paths`と同じ方針)。

    パスが存在しない場合はNoneを返す。
    """
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(input_path.glob("*.json"))
    return None


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"{path}: 読み込み失敗: {e}"


# ----------------------------------------------------------------
# Extraction Result -> referencedBy.candidates 補助index
# ----------------------------------------------------------------


def _build_candidate_reference_index(
    extraction_documents: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    """evidenceId -> [{candidateId, entityType}, ...] の索引を組み立てる。

    Extraction Resultのcandidate配列 (characters/organizations/locations/
    items/lore/events/relationships/timelineCandidates) の`evidenceIds`を
    逆引きする。raw text系フィールドは一切読まない。
    """
    index: dict[str, list[dict[str, str]]] = {}
    for document in extraction_documents:
        for array_key, entity_type in EXTRACTION_ARRAY_TO_ENTITY_TYPE.items():
            for candidate in document.get(array_key, []) or []:
                candidate_id = candidate.get("id")
                if not candidate_id:
                    continue
                for evidence_id in candidate.get("evidenceIds", []) or []:
                    index.setdefault(evidence_id, []).append(
                        {"candidateId": candidate_id, "entityType": entity_type}
                    )
    return index


def _collect_extraction_refs_for_story(
    extraction_documents: list[dict[str, Any]], story_id: str
) -> list[str]:
    """このstoryIdに一致するextraction documentのepisodeIdを重複なく返す
    (generatedFrom.extractionRefs用。local pathは含めない)。"""
    episode_ids = {
        doc.get("episodeId")
        for doc in extraction_documents
        if doc.get("storyId") == story_id and doc.get("episodeId")
    }
    return sorted(episode_ids)


# ----------------------------------------------------------------
# Normalized Story JSON -> Evidence Index entry candidates
# ----------------------------------------------------------------


class GenerationStats:
    def __init__(self) -> None:
        self.skipped_reason_counts: dict[str, int] = {}
        self.entries_by_evidence_type: dict[str, int] = {}
        self.filtered_reason_counts: dict[str, int] = {}
        self.filtered_by_type_counts: dict[str, int] = {}
        self.raw_text_fields_ignored_count = 0
        self.episode_count = 0

    def record_skip(self, reason: str) -> None:
        self.skipped_reason_counts[reason] = (
            self.skipped_reason_counts.get(reason, 0) + 1
        )

    def record_entry(self, evidence_type: str) -> None:
        self.entries_by_evidence_type[evidence_type] = (
            self.entries_by_evidence_type.get(evidence_type, 0) + 1
        )

    def record_filtered(self, evidence_type: str) -> None:
        """Block自体は候補化できたが、--public-profile/--include-types/
        --exclude-typesにより出力対象外となったentryを記録する
        (IDが無い・type未対応で候補化自体できないskipとは区別する、
        Evidence_Index_Promotion_Policy.md §5・§6)。"""
        reason = f"excluded_by_profile:{evidence_type}"
        self.filtered_reason_counts[reason] = (
            self.filtered_reason_counts.get(reason, 0) + 1
        )
        self.filtered_by_type_counts[evidence_type] = (
            self.filtered_by_type_counts.get(evidence_type, 0) + 1
        )

    @property
    def skipped_block_count(self) -> int:
        return sum(self.skipped_reason_counts.values())

    @property
    def generated_entry_count(self) -> int:
        return sum(self.entries_by_evidence_type.values())

    @property
    def filtered_entry_count(self) -> int:
        return sum(self.filtered_by_type_counts.values())


def _build_speaker_and_related_entities(
    block: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """isResolved=trueかつspeakerIdがある場合のみspeaker/relatedEntitiesを
    出力する (displayNameは出力しない、confirmed character dictionary経由の
    構造化IDのみを信頼する方針、Evidence_Index_Design.md §5.1)。"""
    raw_speaker = block.get("speaker")
    if not isinstance(raw_speaker, dict):
        return None, []
    speaker_id = raw_speaker.get("speakerId")
    if not raw_speaker.get("isResolved") or not speaker_id:
        return None, []
    speaker = {
        "speakerId": speaker_id,
        "displayName": None,
        "resolutionStatus": "resolved",
    }
    related_entities = [{"entityType": "character", "id": speaker_id}]
    return speaker, related_entities


def _build_entry(
    *,
    block: dict[str, Any],
    evidence_type: str,
    story_id: str,
    public_story_id: str | None,
    episode_id: str,
    public_episode_id: str | None,
    scene_id: str | None,
    location_id: str | None,
    candidate_index: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    block_id = block["id"]
    speaker, related_entities = _build_speaker_and_related_entities(block)
    if location_id:
        related_entities = [
            *related_entities,
            {"entityType": "location", "id": location_id},
        ]

    referenced_by = None
    candidates = candidate_index.get(block_id)
    if candidates:
        referenced_by = {"summaries": [], "candidates": candidates}

    return {
        "evidenceId": block_id,
        "evidenceType": evidence_type,
        "storyId": story_id,
        "publicStoryId": public_story_id,
        "episodeId": episode_id,
        "publicEpisodeId": public_episode_id,
        "sceneId": scene_id,
        "blockId": block_id,
        "speaker": speaker,
        "relatedEntities": related_entities,
        "referencedBy": referenced_by,
        "visibility": {"public": True, "rawTextIncluded": False},
        "notes": None,
    }


def _iter_blocks_recursive(blocks: list[dict[str, Any]]):
    """choiceブロックのoption内blocksも含め、再帰的にBlockをたどる。"""
    for block in blocks:
        yield block
        if block.get("type") == "choice":
            for option in block.get("options", []) or []:
                yield from _iter_blocks_recursive(option.get("blocks", []) or [])


def _process_block(
    *,
    block: dict[str, Any],
    story_id: str,
    public_story_id: str | None,
    episode_id: str,
    public_episode_id: str | None,
    scene_id: str | None,
    location_id: str | None,
    candidate_index: dict[str, list[dict[str, str]]],
    included_types: frozenset[str],
    stats: GenerationStats,
) -> dict[str, Any] | None:
    if any(field_name in block for field_name in RAW_TEXT_FIELD_NAMES):
        stats.raw_text_fields_ignored_count += 1

    block_id = block.get("id")
    if not block_id:
        stats.record_skip("missing_block_id")
        return None

    block_type = block.get("type")
    evidence_type = BLOCK_TYPE_TO_EVIDENCE_TYPE.get(block_type)
    if evidence_type is None:
        stats.record_skip(f"unmapped_block_type:{block_type}")
        return None

    if evidence_type not in included_types:
        # 候補化はできるが、--public-profile/--include-types/--exclude-types
        # により出力対象外 (skipではなくfilter、candidate referencesも
        # 付与しない、Evidence_Index_Promotion_Policy.md §5・§6)。
        stats.record_filtered(evidence_type)
        return None

    entry = _build_entry(
        block=block,
        evidence_type=evidence_type,
        story_id=story_id,
        public_story_id=public_story_id,
        episode_id=episode_id,
        public_episode_id=public_episode_id,
        scene_id=scene_id,
        location_id=location_id,
        candidate_index=candidate_index,
    )
    stats.record_entry(evidence_type)
    return entry


def _non_blank(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _process_normalized_story_document(
    document: dict[str, Any],
    candidate_index: dict[str, list[dict[str, str]]],
    included_types: frozenset[str],
    stats: GenerationStats,
) -> dict[str, dict[str, Any]]:
    """1つのNormalized Story JSONドキュメントを処理し、
    storyId -> {"refs": [...], "entries": [...]} を返す。"""
    story_id = document.get("storyId")
    if not story_id:
        stats.record_skip("missing_story_id")
        return {}

    public_story_id = _non_blank(document.get("metadata", {}).get("publicStoryId"))
    result: dict[str, dict[str, Any]] = {story_id: {"refs": [], "entries": []}}

    for episode in document.get("episodes", []) or []:
        episode_id = episode.get("episodeId")
        if not episode_id:
            stats.record_skip("missing_episode_id")
            continue
        stats.episode_count += 1
        public_episode_id = _non_blank(
            episode.get("metadata", {}).get("publicEpisodeId")
        )
        result[story_id]["refs"].append({"storyId": story_id, "episodeId": episode_id})

        for scene in episode.get("scenes", []) or []:
            scene_id = scene.get("sceneId")
            location_id = scene.get("location", {}).get("locationId")
            for block in _iter_blocks_recursive(scene.get("blocks", []) or []):
                entry = _process_block(
                    block=block,
                    story_id=story_id,
                    public_story_id=public_story_id,
                    episode_id=episode_id,
                    public_episode_id=public_episode_id,
                    scene_id=scene_id,
                    location_id=location_id,
                    candidate_index=candidate_index,
                    included_types=included_types,
                    stats=stats,
                )
                if entry is not None:
                    result[story_id]["entries"].append(entry)

    return result


# ----------------------------------------------------------------
# Document assembly / validation / output
# ----------------------------------------------------------------


def _merge_story_groups(
    groups: list[dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for story_id, data in group.items():
            bucket = merged.setdefault(story_id, {"refs": [], "entries": []})
            bucket["entries"].extend(data["entries"])
            seen_episode_ids = {r["episodeId"] for r in bucket["refs"]}
            for ref in data["refs"]:
                if ref["episodeId"] not in seen_episode_ids:
                    bucket["refs"].append(ref)
                    seen_episode_ids.add(ref["episodeId"])
    return merged


def _build_document_raw_dict(
    story_id: str,
    data: dict[str, Any],
    extraction_documents: list[dict[str, Any]],
) -> dict[str, Any]:
    extraction_refs = _collect_extraction_refs_for_story(extraction_documents, story_id)
    return {
        "evidenceIndexVersion": 1,
        "generatedFrom": {
            "normalizedStoryRefs": data["refs"],
            "extractionRefs": extraction_refs,
        },
        "entries": data["entries"],
        "notes": (
            "Generated by scripts/build_evidence_index_candidates.py "
            "(dry-run candidate, not human-reviewed)."
        ),
    }


def _validate_raw_document(
    raw_document: dict[str, Any], schema: dict[str, Any]
) -> list[str]:
    """schema検証 + Python側整合性検証 (raw text禁止・enum等) をまとめて行う。"""
    schema_errors = sorted(
        Draft7Validator(schema).iter_errors(raw_document), key=lambda e: list(e.path)
    )
    if schema_errors:
        return [f"{list(e.path)}: {e.message}" for e in schema_errors]

    collection = EvidenceIndexCollection(
        documents=[parse_evidence_index_document(raw_document)]
    )
    return validate_evidence_index_collection(collection)


def _build_story_reports(
    story_documents: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for story_id, data in sorted(story_documents.items()):
        counts: dict[str, int] = {}
        for entry in data["entries"]:
            evidence_type = entry.get("evidenceType")
            if isinstance(evidence_type, str) and evidence_type:
                counts[evidence_type] = counts.get(evidence_type, 0) + 1
        reports.append(
            {
                "storyId": story_id,
                "entryCount": sum(counts.values()),
                "entriesByEvidenceType": dict(sorted(counts.items())),
            }
        )
    return reports


def _build_report_dict(
    *,
    input_file_count: int,
    extraction_file_count: int,
    story_count: int,
    story_documents: dict[str, dict[str, Any]],
    stats: GenerationStats,
    written_files: list[str],
    validation_issues: dict[str, list[str]],
    public_profile: str,
    included_types: frozenset[str],
    excluded_types: frozenset[str],
    candidate_reference_count: int,
) -> dict[str, Any]:
    return {
        "inputFileCount": input_file_count,
        "extractionInputFileCount": extraction_file_count,
        "storyCount": story_count,
        "episodeCount": stats.episode_count,
        "publicProfile": public_profile,
        "includedTypes": sorted(included_types),
        "excludedTypes": sorted(excluded_types),
        "generatedEntryCount": stats.generated_entry_count,
        "generatedEntryCountBeforeFilter": (
            stats.generated_entry_count + stats.filtered_entry_count
        ),
        "generatedEntryCountAfterFilter": stats.generated_entry_count,
        "filteredEntryCount": stats.filtered_entry_count,
        "filteredReasonCounts": stats.filtered_reason_counts,
        "filteredByTypeCounts": stats.filtered_by_type_counts,
        "skippedBlockCount": stats.skipped_block_count,
        "skippedReasonCounts": stats.skipped_reason_counts,
        "entriesByEvidenceType": stats.entries_by_evidence_type,
        "storyReports": _build_story_reports(story_documents),
        "rawTextFieldsIgnoredCount": stats.raw_text_fields_ignored_count,
        "candidateReferencesAttachedCount": candidate_reference_count,
        "outputFiles": written_files,
        "validation": {
            "schemaValid": not validation_issues,
            "issuesByStoryId": validation_issues,
        },
    }


def _append_counted_lines(
    lines: list[str], heading: str, counts: dict[str, int], *, empty_label: str
) -> None:
    lines.append(heading)
    lines.append("")
    if counts:
        for key, count in sorted(counts.items()):
            lines.append(f"- {key}: {count}")
    else:
        lines.append(f"- {empty_label}")
    lines.append("")


def _build_report_markdown_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        "# Evidence Index Generation Dry-Run Report",
        "",
        f"- Input files (normalized): {report['inputFileCount']}",
        f"- Input files (extractions): {report['extractionInputFileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Episode count: {report['episodeCount']}",
        f"- Public profile: {report['publicProfile']}",
        "- Generated entry count (before filter): "
        f"{report['generatedEntryCountBeforeFilter']}",
        "- Generated entry count (after filter): "
        f"{report['generatedEntryCountAfterFilter']}",
        f"- Filtered entry count: {report['filteredEntryCount']}",
        f"- Skipped block count: {report['skippedBlockCount']}",
        f"- Raw text fields ignored (blocks): {report['rawTextFieldsIgnoredCount']}",
        "- Candidate references attached: "
        f"{report['candidateReferencesAttachedCount']}",
        "",
        "## Filter",
        "",
        f"- Included types: {', '.join(report['includedTypes']) or '(none)'}",
        f"- Excluded types: {', '.join(report['excludedTypes']) or '(none)'}",
        "",
    ]
    if report["filteredByTypeCounts"]:
        for evidence_type, count in sorted(report["filteredByTypeCounts"].items()):
            lines.append(f"- filtered {evidence_type}: {count}")
    else:
        lines.append("- (no entries filtered)")
    lines.append("")
    _append_counted_lines(
        lines,
        "## Skipped reason counts",
        report["skippedReasonCounts"],
        empty_label="(none)",
    )
    _append_counted_lines(
        lines,
        "## Entries by evidenceType (after filter)",
        report["entriesByEvidenceType"],
        empty_label="(none)",
    )
    lines.append("## Output files")
    lines.append("")
    if report["outputFiles"]:
        lines.extend(f"- {path}" for path in report["outputFiles"])
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Validation")
    lines.append("")
    validation_issues = report["validation"]["issuesByStoryId"]
    if validation_issues:
        lines.append("schemaValid: false")
        for story_id, issues in validation_issues.items():
            lines.append(f"- {story_id}:")
            lines.extend(f"  - {issue}" for issue in issues)
    else:
        lines.append("schemaValid: true")
    lines.append("")
    return lines


def _write_report(
    output_dir: Path,
    *,
    input_file_count: int,
    extraction_file_count: int,
    story_documents: dict[str, dict[str, Any]],
    stats: GenerationStats,
    written_files: list[str],
    validation_issues: dict[str, list[str]],
    public_profile: str,
    included_types: frozenset[str],
    excluded_types: frozenset[str],
) -> None:
    candidate_reference_count = sum(
        1
        for data in story_documents.values()
        for entry in data["entries"]
        if entry.get("referencedBy")
    )
    report = _build_report_dict(
        input_file_count=input_file_count,
        extraction_file_count=extraction_file_count,
        story_count=len(story_documents),
        stats=stats,
        story_documents=story_documents,
        written_files=written_files,
        validation_issues=validation_issues,
        public_profile=public_profile,
        included_types=included_types,
        excluded_types=excluded_types,
        candidate_reference_count=candidate_reference_count,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(
        "\n".join(_build_report_markdown_lines(report)), encoding="utf-8"
    )


def _load_json_documents(
    paths: list[Path],
) -> tuple[list[dict[str, Any]], list[str]]:
    documents: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in paths:
        document, error = _load_json(path)
        if error:
            errors.append(error)
        else:
            documents.append(document)
    return documents, errors


def _load_inputs(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int | None]:
    """--input/--extractionsを読み込む。

    戻り値: (normalized_documents, extraction_documents,
    extraction_file_count, エラー時のexit code)。exit code以外がNoneでない
    場合、documentsは空リストとして扱ってよい。
    """
    input_path = Path(args.input)
    normalized_paths = _collect_json_paths(input_path)
    if normalized_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return [], [], 0, 2

    normalized_documents, load_errors = _load_json_documents(normalized_paths)

    extraction_documents: list[dict[str, Any]] = []
    extraction_file_count = 0
    if args.extractions:
        extraction_input_path = Path(args.extractions)
        extraction_paths = _collect_json_paths(extraction_input_path)
        if extraction_paths is None:
            print(
                f"[エラー] --extractionsパスが見つかりません: {extraction_input_path}",
                file=sys.stderr,
            )
            return [], [], 0, 2
        extraction_file_count = len(extraction_paths)
        extraction_documents, extraction_load_errors = _load_json_documents(
            extraction_paths
        )
        load_errors.extend(extraction_load_errors)

    if load_errors and not normalized_documents:
        print(
            "[エラー] Normalized Story JSONの読み込みにすべて失敗しました:",
            file=sys.stderr,
        )
        for error in load_errors:
            print(f"  - {error}", file=sys.stderr)
        return [], [], 0, 1
    if load_errors and not args.quiet:
        for error in load_errors:
            print(f"[警告] {error}", file=sys.stderr)

    return normalized_documents, extraction_documents, extraction_file_count, None


def _write_story_documents(
    story_documents: dict[str, dict[str, Any]],
    extraction_documents: list[dict[str, Any]],
    schema: dict[str, Any],
    output_dir: Path,
) -> tuple[list[str], dict[str, list[str]]]:
    stories_dir = output_dir / "stories"
    written_files: list[str] = []
    validation_issues: dict[str, list[str]] = {}
    for story_id, data in sorted(story_documents.items()):
        raw_document = _build_document_raw_dict(story_id, data, extraction_documents)
        issues = _validate_raw_document(raw_document, schema)
        if issues:
            validation_issues[story_id] = issues
            continue
        stories_dir.mkdir(parents=True, exist_ok=True)
        out_path = stories_dir / f"{story_id}.yaml"
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw_document, f, allow_unicode=True, sort_keys=False)
        written_files.append(str(out_path.relative_to(output_dir)))
    return written_files, validation_issues


def main() -> int:
    args = parse_args()

    schema_path = Path(args.schema)
    if not schema_path.exists():
        print(
            f"[エラー] schemaファイルが見つかりません: {schema_path}", file=sys.stderr
        )
        return 2
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)

    normalized_documents, extraction_documents, extraction_file_count, exit_code = (
        _load_inputs(args)
    )
    if exit_code is not None:
        return exit_code

    included_types = _resolve_included_types(args)
    excluded_types = frozenset(VALID_EVIDENCE_TYPES) - included_types

    candidate_index = _build_candidate_reference_index(extraction_documents)

    stats = GenerationStats()
    story_groups = [
        _process_normalized_story_document(
            document, candidate_index, included_types, stats
        )
        for document in normalized_documents
    ]
    story_documents = _merge_story_groups(story_groups)

    output_dir = Path(args.output)
    if args.clean and output_dir.exists():
        shutil.rmtree(output_dir)

    written_files, validation_issues = _write_story_documents(
        story_documents, extraction_documents, schema, output_dir
    )

    _write_report(
        output_dir,
        input_file_count=len(normalized_documents),
        extraction_file_count=extraction_file_count,
        story_documents=story_documents,
        stats=stats,
        written_files=written_files,
        validation_issues=validation_issues,
        public_profile=args.public_profile,
        included_types=included_types,
        excluded_types=excluded_types,
    )

    if not args.quiet:
        print(
            f"[build] evidence_index候補: {len(story_documents)} story、"
            f"{stats.generated_entry_count} entries生成 "
            f"({stats.skipped_block_count} block skip, "
            f"{stats.filtered_entry_count} entry filtered "
            f"[profile={args.public_profile}])"
        )
        print(f"[build] 出力先: {output_dir}")
        if validation_issues:
            print(
                f"[エラー] {len(validation_issues)} storyの検証に失敗したため"
                "書き出しをskipしました（report参照）",
                file=sys.stderr,
            )

    return 1 if validation_issues else 0


if __name__ == "__main__":
    sys.exit(main())
