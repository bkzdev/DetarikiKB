#!/usr/bin/env python3
"""
Project Evidence Index Public IDs
Public Evidence Index候補に`publicEvidenceId`を生成・付与するprojection
scriptである（`feature/evidence-index-public-id-projection`、
`feature/evidence-index-public-id-public-safe-projection`、
`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §6/§12
Phase 2/Phase 2.5）。

`--projection-mode`で2つのmodeを切り替える:

- `compatible`（既定）: 既存の内部ID`evidenceId`/`storyId`/`episodeId`/
  `sceneId`/`blockId`は一切削除しない。`publicEvidenceId`を追加するだけの
  Compatible projection（案A）。migration/debugging/mapping確認用であり、
  **Public promotion対象ではない**
- `public-safe`: 内部IDを`publicEvidenceId`/`publicStoryId`/
  `publicEpisodeId`へ置換・除去するPublic-safe projection（案B）。出力
  ファイル名も`publicStoryId`ベースにする。promotion-candidateの判定は
  行うが、本scriptは`promote_evidence_index.py --execute`を呼び出さない
  （実promotionは別途行う）

**重要な安全方針**（両modeで共通）:
- `--output`/`--mapping-output`/`--report`はいずれも`knowledge/evidence/`
  配下を指定できない（安全確認で拒否、exit code 2）。すべてworkspace
  配下の一時出力を想定する
- `promote_evidence_index.py`の実行、`knowledge/evidence/stories/`への
  実copyは本scriptの責務外であり、一切行わない
- `--input`ファイル自体は読み込みのみで変更しない（書き込み先は常に
  `--output`）
- `--mapping-output`は内部ID⇔公開IDのmappingを常に含む
  （public-safe modeでも同様）。Internal Review Evidence Packet候補データ
  であり、**commit禁止**

publicEvidenceId形式（`Evidence_Index_Public_ID_Policy.md` §6.4）:
    {publicEpisodeId}_{PREFIX}{sequence:04d}

採番方針（同 §6.6）:
- `--policy`で許可されたevidenceTypeのentryのみ、
  (publicEpisodeId, evidenceType) 単位で1始まりの連番を振る
  （`stage_direction`等policy対象外のtypeは採番対象に含めない）
- 連番は入力entriesの出現順（複数ファイルの場合はfile収集順→file内の
  entries順）に従う。そのため、同じ入力・同じprofileであれば再現可能だが、
  entryの並び順が変わればpublicEvidenceIdも変わりうる
- 既にpublicEvidenceIdを持つentryは、再生成した値と比較する。一致すれば
  そのまま採用、不一致ならblocking error（`--overwrite-public-ids`相当の
  上書きオプションは本PRでは実装しない）

public-safe modeの方針（`Evidence_Index_Public_ID_Policy.md` §6.7.1）:
- `evidenceId`/`storyId`/`episodeId`は、それぞれ`publicEvidenceId`/
  `publicStoryId`/`publicEpisodeId`の値へ置換する（schema互換のため
  required fieldとしては維持しつつ、値を公開向けIDにする）
- `sceneId`/`blockId`/`referencedBy`/document-level`generatedFrom`は出力
  しない（内部IDやextraction/summary内部参照を含みうるため）
- `speaker`は`resolutionStatus: resolved`のentryのみ保持する
- `publicEvidenceId`を持たないentry（`--policy`対象外のevidenceType、
  既定では`stage_direction`等）はpublic-safe出力から除外する（schema上
  `evidenceId`はrequiredかつpattern一致必須のため、値を持たないentryを
  出力に含められない）
- 出力ファイル名は`{publicStoryId}.yaml`。1 fileにつき1 publicStoryIdを
  前提とし、document内で複数のpublicStoryIdが混在する場合や、複数の入力
  ファイルが同じpublicStoryIdへ解決される場合はblocking errorにする
- 出力文字列に対して内部ID (`storyId`/`episodeId`/`evidenceId`/`sceneId`/
  `blockId`の値のうち、対応する公開IDと異なり一定長以上のもの) が残って
  いないかをscanし、検出したらblocking errorにする
- `publicEpisodeId`欠落は（compatible modeと同様）blocking error。
  自動補完は行わない（次PR候補
  `evidence-index-public-id-public-episode-id-assignment`）

Non-goals（本scriptで行わないこと。詳細は
`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §13参照）:
- `knowledge/evidence/stories/`への実copy・commit
- `promote_evidence_index.py --execute`の実行
- rendererのEvidence page見出し・anchor・Summary evidenceRefsリンクの
  publicEvidenceId中心への切り替え
- `publicEpisodeId`の自動補完・推測

Usage:
    uv run python scripts/project_evidence_index_public_ids.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --output workspace/evidence_index_dry_runs/public_id_projection \\
        --mapping-output workspace/evidence_index_dry_runs/public_id_map.csv \\
        --report workspace/evidence_index_dry_runs/public_id_report.md \\
        --projection-mode compatible \\
        --clean

    uv run python scripts/project_evidence_index_public_ids.py \\
        --input workspace/evidence_index_dry_runs/<run>/default/stories \\
        --output workspace/evidence_index_dry_runs/public_safe/stories \\
        --mapping-output workspace/evidence_index_dry_runs/public_safe/mapping.csv \\
        --report workspace/evidence_index_dry_runs/public_safe/report.md \\
        --projection-mode public-safe \\
        --clean

Exit codes:
    0: projection成功（blocking issueなし）
    1: projection validation失敗（publicStoryId/publicEpisodeId欠落、
       既存publicEvidenceIdとの不一致、duplicate publicEvidenceId、
       projected出力のschema検証失敗、--strict指定時のpolicy対象外type、
       public-safe mode時の複数publicStoryId混在・出力ファイル名衝突・
       内部ID exposure検出等）
    2: --input/--schemaパスが見つからない、または--output/--mapping-output/
       --reportがknowledge/evidence/配下を指しているなどのconfig error
"""

from __future__ import annotations

import argparse
import csv
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
_SCRIPTS_DIR = Path(__file__).parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from check_evidence_index_promotion import (  # noqa: E402
    DEFAULT_SCHEMA_PATH,
    POLICIES,
    POLICY_PUBLIC_DEFAULT,
    _collect_yaml_paths,
    _load_yaml_documents,
)

# `Evidence_Index_Public_ID_Policy.md` §6.5 evidenceType prefix mapping。
EVIDENCE_TYPE_PREFIXES: dict[str, str] = {
    "dialogue": "DLG",
    "monologue": "MONO",
    "narration": "NAR",
    "choice": "CHO",
    "unknown": "UNK",
    "stage_direction": "STG",
    "speaker_label": "SPK",
    "scene": "SCN",
    "episode": "EP",
    "story": "STORY",
}

# knowledge/evidence配下は本scriptの出力先として一切許可しない
# (§安全方針。stories/以外のサブpathも念のため含めて拒否する)。
_KNOWLEDGE_EVIDENCE_DIR = (_PROJECT_ROOT / "knowledge" / "evidence").resolve()

PROJECTION_MODE_COMPATIBLE = "compatible"
PROJECTION_MODE_PUBLIC_SAFE = "public-safe"
PROJECTION_MODES = (PROJECTION_MODE_COMPATIBLE, PROJECTION_MODE_PUBLIC_SAFE)

# public-safe modeのsourceKey由来ID exposure scanで対象にする内部IDの
# 最小長。実データの内部ID（story/episode/evidence等）はいずれも十分長い
# ため、短い汎用トークンの誤検出を避けるための閾値
# (`Evidence_Index_Public_ID_Policy.md` §6.7.1)。
MIN_FORBIDDEN_INTERNAL_ID_LENGTH = 4

# public-safe modeでspeakerを保持してよい resolutionStatus
# (§6.7.1、未解決/placeholder speakerは公開しない)。
_PUBLIC_SAFE_SPEAKER_RESOLUTION_STATUS = "resolved"

MAPPING_FIELDNAMES = [
    "storyId",
    "publicStoryId",
    "episodeId",
    "publicEpisodeId",
    "evidenceId",
    "publicEvidenceId",
    "evidenceType",
    "sceneId",
    "blockId",
]


# ----------------------------------------------------------------
# Argument parser
# ----------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Public Evidence Index候補にpublicEvidenceIdを生成・付与する "
            "projection script。--projection-mode compatible (既定、内部ID "
            "は削除しない) と public-safe (内部IDを公開IDへ置換・除去する) "
            "を切り替えられる。出力はworkspace配下のみを想定し、"
            "knowledge/evidence/配下への書き込みは拒否する"
        ),
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Evidence Index YAMLファイル、またはdirectory (直下の*.yaml/*.ymlを収集)",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help=(
            "projection結果を書き出すdirectory (workspace配下のみ。"
            "knowledge/evidence/配下は指定不可)"
        ),
    )
    parser.add_argument(
        "--mapping-output",
        required=True,
        help=(
            "内部ID<->公開IDのmapping CSVを書き出すファイルパス "
            "(workspace配下のみ。内部IDを含むためcommit禁止)"
        ),
    )
    parser.add_argument(
        "--report",
        required=True,
        help="projection結果をMarkdownで書き出すファイルパス (workspace配下のみ)",
    )
    parser.add_argument(
        "--schema",
        default=str(DEFAULT_SCHEMA_PATH),
        help=f"evidence_index.schema.jsonのパス (デフォルト: {DEFAULT_SCHEMA_PATH})",
    )
    parser.add_argument(
        "--policy",
        choices=sorted(POLICIES),
        default=POLICY_PUBLIC_DEFAULT,
        help=(
            "publicEvidenceId採番対象のevidenceType policy "
            "(デフォルト: public-default。dialogue/monologue/narration/"
            "choice/unknownのみ採番、stage_direction等は採番対象外のまま"
            "entryとしては出力に残る)"
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "policy対象外のevidenceType (stage_direction等) を持つentryが"
            "入力に含まれている場合、blocking errorにする "
            "(既定では警告なしでpublicEvidenceIdを付与せず素通しする)"
        ),
    )
    parser.add_argument(
        "--projection-mode",
        choices=PROJECTION_MODES,
        default=PROJECTION_MODE_COMPATIBLE,
        help=(
            "projection mode (デフォルト: compatible。compatibleは既存の"
            "内部IDを維持したままpublicEvidenceIdを追加するのみで"
            "promotion対象ではない。public-safeは内部IDを公開IDへ置換・"
            "除去し、出力ファイル名もpublicStoryIdベースにする)"
        ),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="--output出力先ディレクトリを書き込み前に削除する",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="進捗メッセージを抑制する",
    )
    return parser.parse_args()


def _is_under_knowledge_evidence(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    try:
        resolved.relative_to(_KNOWLEDGE_EVIDENCE_DIR)
        return True
    except ValueError:
        return False


# ----------------------------------------------------------------
# publicEvidenceId generation
# ----------------------------------------------------------------


def _build_public_evidence_id(
    public_episode_id: str, evidence_type: str, sequence: int
) -> str:
    prefix = EVIDENCE_TYPE_PREFIXES.get(evidence_type, "UNK")
    return f"{public_episode_id}_{prefix}{sequence:04d}"


def _check_missing_public_story_id(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    """document (file) 単位でpublicStoryIdを持つentryが1件も無い場合を検出する。"""
    missing: list[str] = []
    issues: list[str] = []
    for path, raw in raw_documents:
        entries = raw.get("entries", []) or []
        has_public_story_id = any(entry.get("publicStoryId") for entry in entries)
        if not has_public_story_id:
            missing.append(str(path))
            issues.append(
                f"{path}: publicStoryIdを持つentryがありません (document全体で欠落)"
            )
    return missing, issues


def _flatten_entries(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> list[tuple[Path, dict[str, Any]]]:
    flat: list[tuple[Path, dict[str, Any]]] = []
    for path, raw in raw_documents:
        for entry in raw.get("entries", []) or []:
            flat.append((path, entry))
    return flat


def _check_missing_public_episode_id(
    flat_entries: list[tuple[Path, dict[str, Any]]],
) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    issues: list[str] = []
    for path, entry in flat_entries:
        if not entry.get("publicEpisodeId"):
            label = f"{path}: evidenceId={entry.get('evidenceId')!r}"
            missing.append(label)
            issues.append(f"{label}: publicEpisodeIdが欠落しています")
    return missing, issues


def _assign_public_evidence_ids(
    flat_entries: list[tuple[Path, dict[str, Any]]],
    *,
    policy_types: frozenset[str],
    strict: bool,
) -> dict[str, Any]:
    """policy許可typeのentryにpublicEvidenceIdを採番・検証する。

    publicEpisodeIdが欠落しているentryは (別途blocking issueとして記録
    済みのため) 採番対象から除外する。
    """
    strict_issues: list[str] = []
    conflict_issues: list[str] = []
    counters: dict[tuple[str, str], int] = {}
    generated_count = 0
    existing_matched_count = 0
    out_of_policy_count = 0

    for path, entry in flat_entries:
        evidence_type = entry.get("evidenceType")
        public_episode_id = entry.get("publicEpisodeId")

        if evidence_type not in policy_types:
            out_of_policy_count += 1
            if strict:
                strict_issues.append(
                    f"{path}: evidenceId={entry.get('evidenceId')!r}: evidenceType "
                    f"'{evidence_type}' はpolicy '{'/'.join(sorted(policy_types))}' "
                    "の対象外です (--strict)"
                )
            continue

        if not public_episode_id:
            continue

        key = (public_episode_id, evidence_type)
        counters[key] = counters.get(key, 0) + 1
        expected = _build_public_evidence_id(
            public_episode_id, evidence_type, counters[key]
        )

        existing = entry.get("publicEvidenceId")
        if existing:
            if existing == expected:
                existing_matched_count += 1
            else:
                conflict_issues.append(
                    f"{path}: evidenceId={entry.get('evidenceId')!r}: "
                    f"既存publicEvidenceId '{existing}' が生成結果 "
                    f"'{expected}' と一致しません"
                )
        else:
            entry["publicEvidenceId"] = expected
            generated_count += 1

    return {
        "issues": conflict_issues + strict_issues,
        "conflictCount": len(conflict_issues),
        "generatedCount": generated_count,
        "existingMatchedCount": existing_matched_count,
        "outOfPolicyCount": out_of_policy_count,
    }


def _check_duplicate_public_evidence_ids(
    flat_entries: list[tuple[Path, dict[str, Any]]],
) -> tuple[int, list[str]]:
    seen: dict[str, int] = {}
    for _, entry in flat_entries:
        public_evidence_id = entry.get("publicEvidenceId")
        if public_evidence_id:
            seen[public_evidence_id] = seen.get(public_evidence_id, 0) + 1
    duplicates = sorted(pid for pid, count in seen.items() if count > 1)
    issues = [f"publicEvidenceId '{pid}' が重複しています" for pid in duplicates]
    return len(duplicates), issues


def _validate_projected_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]], schema: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    for path, raw in raw_documents:
        errors = sorted(
            Draft7Validator(schema).iter_errors(raw), key=lambda e: list(e.path)
        )
        issues.extend(
            f"{path} (projected): {list(e.path)}: {e.message}" for e in errors
        )
    return issues


def _project_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    schema: dict[str, Any],
    *,
    policy_types: frozenset[str],
    strict: bool,
) -> dict[str, Any]:
    missing_public_story_id, story_id_issues = _check_missing_public_story_id(
        raw_documents
    )

    flat_entries = _flatten_entries(raw_documents)
    missing_public_episode_id, episode_id_issues = _check_missing_public_episode_id(
        flat_entries
    )

    entries_by_type: dict[str, int] = {}
    story_ids: set[str] = set()
    for _, entry in flat_entries:
        evidence_type = entry.get("evidenceType")
        entries_by_type[evidence_type] = entries_by_type.get(evidence_type, 0) + 1
        if entry.get("storyId"):
            story_ids.add(entry["storyId"])

    assignment = _assign_public_evidence_ids(
        flat_entries, policy_types=policy_types, strict=strict
    )

    duplicate_count, duplicate_issues = _check_duplicate_public_evidence_ids(
        flat_entries
    )

    schema_issues = _validate_projected_documents(raw_documents, schema)

    all_issues = (
        story_id_issues
        + episode_id_issues
        + assignment["issues"]
        + duplicate_issues
        + schema_issues
    )

    generated_count = assignment["generatedCount"]
    existing_matched_count = assignment["existingMatchedCount"]

    return {
        "fileCount": len(raw_documents),
        "storyCount": len(story_ids),
        "entryCount": len(flat_entries),
        "entriesByType": entries_by_type,
        "projectedEntryCount": generated_count + existing_matched_count,
        "generatedCount": generated_count,
        "existingMatchedCount": existing_matched_count,
        "missingPublicStoryIdCount": len(missing_public_story_id),
        "missingPublicStoryId": missing_public_story_id,
        "missingPublicEpisodeIdCount": len(missing_public_episode_id),
        "missingPublicEpisodeId": missing_public_episode_id,
        "conflictCount": assignment["conflictCount"],
        "outOfPolicyCount": assignment["outOfPolicyCount"],
        "duplicateCount": duplicate_count,
        "schemaIssueCount": len(schema_issues),
        "issues": all_issues,
        "passed": not all_issues,
    }


# ----------------------------------------------------------------
# Output writing (--output / --mapping-output)
# ----------------------------------------------------------------


def _write_projected_documents(
    output_dir: Path, raw_documents: list[tuple[Path, dict[str, Any]]], *, clean: bool
) -> list[str]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for path, raw in raw_documents:
        target = output_dir / path.name
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
        written.append(str(target))
    return written


def _write_mapping_csv(
    mapping_output_path: Path, raw_documents: list[tuple[Path, dict[str, Any]]]
) -> None:
    mapping_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(mapping_output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MAPPING_FIELDNAMES)
        writer.writeheader()
        for _, raw in raw_documents:
            for entry in raw.get("entries", []) or []:
                writer.writerow(
                    {key: entry.get(key, "") or "" for key in MAPPING_FIELDNAMES}
                )


# ----------------------------------------------------------------
# Public-safe projection (案B): field rewrite / filename policy /
# internal ID exposure scan
# ----------------------------------------------------------------


def _check_public_story_id_consistency(
    raw_documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[dict[Path, str | None], list[str]]:
    """public-safe modeの出力ファイル名決定のため、document (file) ごとに
    単一のpublicStoryIdへ解決できるかを確認する (1 file 1 publicStoryId方針)。

    戻り値: (path -> 解決したpublicStoryId (欠落/複数混在時はNone), issues)。
    """
    resolved: dict[Path, str | None] = {}
    issues: list[str] = []
    for path, raw in raw_documents:
        entries = raw.get("entries", []) or []
        distinct = {
            entry.get("publicStoryId")
            for entry in entries
            if entry.get("publicStoryId")
        }
        if len(distinct) > 1:
            issues.append(
                f"{path}: 複数のpublicStoryId {sorted(distinct)!r} が混在して"
                "います (public-safe projectionは1 file 1 publicStoryId方針の"
                "ため、blocking errorとして扱います)"
            )
            resolved[path] = None
        elif len(distinct) == 1:
            resolved[path] = next(iter(distinct))
        else:
            resolved[path] = None
    return resolved, issues


def _check_duplicate_target_filenames(
    resolved_public_story_ids: dict[Path, str | None],
) -> list[str]:
    """複数の入力ファイルが同じpublicStoryId (= 同じ出力ファイル名) へ解決
    される場合、出力の衝突としてblocking errorにする。"""
    by_public_story_id: dict[str, list[Path]] = {}
    for path, public_story_id in resolved_public_story_ids.items():
        if public_story_id:
            by_public_story_id.setdefault(public_story_id, []).append(path)
    issues: list[str] = []
    for public_story_id, paths in sorted(by_public_story_id.items()):
        if len(paths) > 1:
            source_list = sorted(str(p) for p in paths)
            issues.append(
                f"publicStoryId '{public_story_id}' が複数の入力ファイル "
                f"{source_list!r} に混在しています "
                "(public-safe projectionの出力ファイル名が衝突します)"
            )
    return issues


def _to_public_safe_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """内部entryをpublic-safe entryへ変換する。

    publicEvidenceId/publicStoryId/publicEpisodeIdのいずれかを持たない
    entry (policy対象外のevidenceType、または欠落によりすでに別途
    blocking issueとして記録済みのentry) はNoneを返し、呼び出し側で除外する。
    """
    public_evidence_id = entry.get("publicEvidenceId")
    public_story_id = entry.get("publicStoryId")
    public_episode_id = entry.get("publicEpisodeId")
    if not public_evidence_id or not public_story_id or not public_episode_id:
        return None

    new_entry: dict[str, Any] = {
        "evidenceId": public_evidence_id,
        "evidenceType": entry.get("evidenceType"),
        "storyId": public_story_id,
        "episodeId": public_episode_id,
        "publicEvidenceId": public_evidence_id,
        "publicStoryId": public_story_id,
        "publicEpisodeId": public_episode_id,
        "visibility": {"public": True, "rawTextIncluded": False},
    }

    speaker = entry.get("speaker")
    if (
        isinstance(speaker, dict)
        and speaker.get("resolutionStatus") == _PUBLIC_SAFE_SPEAKER_RESOLUTION_STATUS
    ):
        new_entry["speaker"] = speaker

    related_entities = entry.get("relatedEntities")
    if related_entities:
        new_entry["relatedEntities"] = related_entities

    notes = entry.get("notes")
    if notes:
        new_entry["notes"] = notes

    return new_entry


def _build_public_safe_documents(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    resolved_public_story_ids: dict[Path, str | None],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[Path]], dict[str, int]]:
    """public-safe出力directory向けに `{publicStoryId}.yaml` -> projected raw
    dict のmappingを組み立てる。

    戻り値: (target filename -> projected raw dict, target filename -> 由来
    source paths一覧, counters (rewrittenIdFieldsCount/
    removedInternalFieldsCount/excludedEntryCount))。
    """
    target_documents: dict[str, dict[str, Any]] = {}
    target_sources: dict[str, list[Path]] = {}
    rewritten_id_fields_count = 0
    removed_internal_fields_count = 0
    excluded_entry_count = 0

    for path, raw in raw_documents:
        public_story_id = resolved_public_story_ids.get(path)
        if not public_story_id:
            continue
        target_filename = f"{public_story_id}.yaml"
        target_sources.setdefault(target_filename, []).append(path)
        target_doc = target_documents.setdefault(
            target_filename,
            {
                "evidenceIndexVersion": raw.get("evidenceIndexVersion", 1),
                "generatedFrom": None,
                "entries": [],
                "notes": raw.get("notes"),
            },
        )

        if raw.get("generatedFrom"):
            removed_internal_fields_count += 1

        for entry in raw.get("entries", []) or []:
            if (
                entry.get("sceneId")
                or entry.get("blockId")
                or entry.get("referencedBy")
            ):
                removed_internal_fields_count += 1
            new_entry = _to_public_safe_entry(entry)
            if new_entry is None:
                excluded_entry_count += 1
                continue
            rewritten_id_fields_count += 3
            target_doc["entries"].append(new_entry)

    counters = {
        "rewrittenIdFieldsCount": rewritten_id_fields_count,
        "removedInternalFieldsCount": removed_internal_fields_count,
        "excludedEntryCount": excluded_entry_count,
    }
    return target_documents, target_sources, counters


def _collect_forbidden_internal_ids(
    flat_entries: list[tuple[Path, dict[str, Any]]],
) -> frozenset[str]:
    """public-safe modeのsourceKey由来ID exposure scan用に、除去すべき
    内部ID値を収集する。

    storyId/episodeId/evidenceId/sceneId/blockIdの値を集め、
    publicStoryId/publicEpisodeId/publicEvidenceIdと一致する値は除外する
    (偶然一致した値は安全)。さらに`MIN_FORBIDDEN_INTERNAL_ID_LENGTH`未満の
    短い値は誤検出防止のため対象から除く。
    """
    internal_ids: set[str] = set()
    public_ids: set[str] = set()
    for _, entry in flat_entries:
        for key in ("storyId", "episodeId", "evidenceId", "sceneId", "blockId"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                internal_ids.add(value)
        for key in ("publicStoryId", "publicEpisodeId", "publicEvidenceId"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                public_ids.add(value)
    return frozenset(
        value
        for value in internal_ids
        if value not in public_ids and len(value) >= MIN_FORBIDDEN_INTERNAL_ID_LENGTH
    )


def _scan_text_for_forbidden_internal_ids(
    text: str, forbidden_ids: frozenset[str]
) -> dict[str, int]:
    """textから内部ID文字列の出現回数を数える。戻り値: {internal_id: 出現回数}
    (出現しなかったIDはキーに含めない)。"""
    counts: dict[str, int] = {}
    for internal_id in forbidden_ids:
        occurrences = text.count(internal_id)
        if occurrences:
            counts[internal_id] = occurrences
    return counts


def _validate_documents_against_schema(
    documents: dict[str, dict[str, Any]], schema: dict[str, Any]
) -> list[str]:
    issues: list[str] = []
    for filename, raw in sorted(documents.items()):
        errors = sorted(
            Draft7Validator(schema).iter_errors(raw), key=lambda e: list(e.path)
        )
        issues.extend(
            f"{filename} (public-safe projected): {list(e.path)}: {e.message}"
            for e in errors
        )
    return issues


def _write_public_safe_documents(
    output_dir: Path, documents: dict[str, dict[str, Any]], *, clean: bool
) -> list[str]:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for filename, raw in sorted(documents.items()):
        target = output_dir / filename
        with open(target, "w", encoding="utf-8") as f:
            yaml.safe_dump(raw, f, allow_unicode=True, sort_keys=False)
        written.append(str(target))
    return written


def _scan_public_safe_documents_for_exposure(
    target_documents: dict[str, dict[str, Any]], forbidden_ids: frozenset[str]
) -> tuple[dict[str, int], list[str]]:
    """target_documents (書き出し前のprojected raw dict) を直列化し、
    内部ID exposureを検出する。戻り値: (internal_id -> 出現回数の合計, issues)。"""
    exposure_counts: dict[str, int] = {}
    issues: list[str] = []
    for filename, raw in target_documents.items():
        text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
        for internal_id, count in _scan_text_for_forbidden_internal_ids(
            text, forbidden_ids
        ).items():
            exposure_counts[internal_id] = exposure_counts.get(internal_id, 0) + count
            issues.append(
                f"{filename}: 内部ID '{internal_id}' がpublic-safe出力に "
                f"{count}回残っています (internal ID exposure)"
            )
    return exposure_counts, issues


def _run_public_safe_projection(
    raw_documents: list[tuple[Path, dict[str, Any]]],
    schema: dict[str, Any],
    result: dict[str, Any],
    *,
    output_dir: Path,
    clean: bool,
) -> list[str]:
    """public-safe projectionの追加チェック・field rewrite・書き出しを行い、
    `result`を書き換える (in-place)。戻り値: 書き出したファイルパス一覧。"""
    resolved_public_story_ids, consistency_issues = _check_public_story_id_consistency(
        raw_documents
    )
    duplicate_filename_issues = _check_duplicate_target_filenames(
        resolved_public_story_ids
    )
    target_documents, _target_sources, counters = _build_public_safe_documents(
        raw_documents, resolved_public_story_ids
    )
    public_safe_schema_issues = _validate_documents_against_schema(
        target_documents, schema
    )

    forbidden_ids = _collect_forbidden_internal_ids(_flatten_entries(raw_documents))
    exposure_counts, exposure_issues = _scan_public_safe_documents_for_exposure(
        target_documents, forbidden_ids
    )

    result["issues"].extend(
        consistency_issues
        + duplicate_filename_issues
        + public_safe_schema_issues
        + exposure_issues
    )
    result["passed"] = not result["issues"]
    result.update(counters)
    result["internalIdExposureCount"] = sum(exposure_counts.values())
    result["internalIdExposureDetails"] = [
        f"'{internal_id}': {count}回"
        for internal_id, count in sorted(exposure_counts.items())
    ]
    result["promotionReadiness"] = (
        "promotion-candidate" if result["passed"] else "not-promotion-ready"
    )

    return _write_public_safe_documents(output_dir, target_documents, clean=clean)


# ----------------------------------------------------------------
# Report building
# ----------------------------------------------------------------


def _report_summary_lines(report: dict[str, Any]) -> list[str]:
    return [
        "# Evidence Index Public ID Projection Report",
        "",
        f"- Input: {report['input']}",
        f"- Output: {report['output']}",
        f"- Mapping output: {report['mappingOutput']}",
        f"- Projection mode: {report['projectionMode']}",
        f"- Policy: {report['policy']}",
        f"- File count: {report['fileCount']}",
        f"- Story count: {report['storyCount']}",
        f"- Entry count: {report['entryCount']}",
        "",
    ]


def _report_entries_by_type_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Entries by evidenceType", ""]
    if report["entriesByType"]:
        for evidence_type, count in sorted(report["entriesByType"].items()):
            lines.append(f"- {evidence_type}: {count}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _report_projection_result_lines(report: dict[str, Any]) -> list[str]:
    return [
        "## Projection Result",
        "",
        f"- Projected entry count: {report['projectedEntryCount']}",
        "- Existing publicEvidenceId count (matched): "
        f"{report['existingMatchedCount']}",
        f"- Generated publicEvidenceId count: {report['generatedCount']}",
        f"- Missing publicStoryId count: {report['missingPublicStoryIdCount']}",
        f"- Missing publicEpisodeId count: {report['missingPublicEpisodeIdCount']}",
        f"- Conflicts count: {report['conflictCount']}",
        f"- Duplicate publicEvidenceId count: {report['duplicateCount']}",
        f"- Out-of-policy entry count: {report['outOfPolicyCount']}",
        "",
    ]


def _report_issues_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Issues", ""]
    if report["issues"]:
        for issue in report["issues"]:
            lines.append(f"- {issue}")
    else:
        lines.append("- (none)")
    lines.append("")
    return lines


def _report_public_safe_lines(report: dict[str, Any]) -> list[str]:
    lines = ["## Public-safe Projection", ""]
    lines.append("- Output filename policy: publicStoryId-based ({publicStoryId}.yaml)")
    lines.append(f"- Rewritten ID fields count: {report['rewrittenIdFieldsCount']}")
    lines.append(
        f"- Removed internal fields count: {report['removedInternalFieldsCount']}"
    )
    lines.append(
        "- Excluded entry count (no publicEvidenceId, e.g. out-of-policy type): "
        f"{report['excludedEntryCount']}"
    )
    lines.append(
        f"- Internal ID exposure scan: {report['internalIdExposureCount']} "
        "occurrence(s) across "
        f"{len(report['internalIdExposureDetails'])} distinct internal ID(s)"
    )
    if report["internalIdExposureDetails"]:
        for detail in report["internalIdExposureDetails"]:
            lines.append(f"  - {detail}")
    lines.append(f"- Promotion readiness: {report['promotionReadiness']}")
    lines.append("")
    return lines


def _build_report_lines(report: dict[str, Any]) -> list[str]:
    is_public_safe = report["projectionMode"] == PROJECTION_MODE_PUBLIC_SAFE

    lines: list[str] = []
    lines.extend(_report_summary_lines(report))
    lines.extend(_report_entries_by_type_lines(report))
    lines.extend(_report_projection_result_lines(report))
    if is_public_safe:
        lines.extend(_report_public_safe_lines(report))
    lines.extend(_report_issues_lines(report))
    lines.append("## Final Decision")
    lines.append("")
    lines.append(f"- {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")
    lines.append("## Note")
    lines.append("")
    if is_public_safe:
        lines.append(
            "- This is a public-safe projection (Option B, "
            "Evidence_Index_Public_ID_Policy.md §6.7.1). Internal IDs "
            "(evidenceId/storyId/episodeId/sceneId/blockId) are rewritten to "
            "public IDs or removed; the output filename is publicStoryId-based."
        )
        lines.append(
            f"- Promotion readiness: {report['promotionReadiness']}. Even when "
            "this projection passes validation and the internal ID exposure "
            "scan, it must not be used with promote_evidence_index.py "
            "--execute yet (renderer switch and Summary evidenceRefs "
            "migration have not happened)."
        )
    else:
        lines.append(
            "- This is a compatible projection only (Option A, "
            "Evidence_Index_Public_ID_Policy.md §6.2). Internal IDs "
            "(evidenceId/storyId/episodeId/sceneId/blockId) remain unchanged "
            "in the output."
        )
        lines.append(
            "- The output is NOT promotion-ready: it must not be used with "
            "promote_evidence_index.py --execute, and must not be committed to "
            "knowledge/evidence/stories/."
        )
    lines.append(
        "- The mapping output contains internal IDs alongside public IDs and "
        "must never be committed (Internal Review Evidence Packet candidate, "
        "not yet implemented)."
    )
    lines.append("")
    return lines


def _print_summary(report: dict[str, Any], *, quiet: bool) -> None:
    if quiet:
        return
    print(
        f"[projection] mode={report['projectionMode']} "
        f"{report['fileCount']} ファイル、{report['entryCount']} entries "
        f"(policy={report['policy']})"
    )
    print(
        f"[projection] projected={report['projectedEntryCount']} "
        f"(generated={report['generatedCount']}, "
        f"existing_matched={report['existingMatchedCount']})"
    )
    if report["projectionMode"] == PROJECTION_MODE_PUBLIC_SAFE:
        print(
            f"[projection] public-safe: excluded={report['excludedEntryCount']} "
            f"internal_id_exposure={report['internalIdExposureCount']} "
            f"promotion_readiness={report['promotionReadiness']}"
        )
    if report["issues"]:
        print(f"[エラー] {len(report['issues'])}件のissueがあります:", file=sys.stderr)
        for issue in report["issues"]:
            print(f"  - {issue}", file=sys.stderr)
    print(f"[projection] 結果: {'PASS' if report['passed'] else 'FAIL'}")


# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------


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

    input_path = Path(args.input)
    yaml_paths = _collect_yaml_paths(input_path)
    if yaml_paths is None:
        print(f"[エラー] --inputパスが見つかりません: {input_path}", file=sys.stderr)
        return 2

    output_dir = Path(args.output)
    mapping_output_path = Path(args.mapping_output)
    report_path = Path(args.report)
    for label, path in (
        ("--output", output_dir),
        ("--mapping-output", mapping_output_path),
        ("--report", report_path),
    ):
        if _is_under_knowledge_evidence(path):
            print(
                f"[エラー] {label}にknowledge/evidence配下のpathは"
                f"指定できません: {path}",
                file=sys.stderr,
            )
            return 2

    raw_documents, schema_errors = _load_yaml_documents(yaml_paths, schema)
    if schema_errors:
        print("[エラー] 入力のschema検証に失敗しました:", file=sys.stderr)
        for issue in schema_errors:
            print(f"  - {issue}", file=sys.stderr)
        return 2

    policy_types = POLICIES[args.policy]
    result = _project_documents(
        raw_documents, schema, policy_types=policy_types, strict=args.strict
    )

    if args.projection_mode == PROJECTION_MODE_PUBLIC_SAFE:
        written_paths = _run_public_safe_projection(
            raw_documents,
            schema,
            result,
            output_dir=output_dir,
            clean=args.clean,
        )
    else:
        result["promotionReadiness"] = "not-promotion-ready"
        written_paths = _write_projected_documents(
            output_dir, raw_documents, clean=args.clean
        )

    _write_mapping_csv(mapping_output_path, raw_documents)

    report = {
        "input": str(input_path),
        "output": str(output_dir),
        "mappingOutput": str(mapping_output_path),
        "projectionMode": args.projection_mode,
        "policy": args.policy,
        **result,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(_build_report_lines(report)), encoding="utf-8")

    if not args.quiet:
        for path in written_paths:
            print(f"[projection] wrote {path}")

    _print_summary(report, quiet=args.quiet)

    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
