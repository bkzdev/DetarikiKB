"""
DKB Parser - Story Manifest Candidate Builder
ローカルのraw DECファイル配置（`EVENT`・`CHARACTER`・`CHARACTER_DATE`カテゴリ）
から、`story_manifest.yaml`候補（`schemas/story_manifest.schema.json`準拠）を
機械的に生成する。

docs/architecture/05_Parser/Story_Manifest_Design.md、
docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md 参照。

**重要**: このモジュールはDEC本文を一切読まない（ファイル名・ディレクトリ名の
文字列処理のみ）。title/subtitle/displayTitleは常にnull、metadataStatusは
常にpendingとして組み立てる。MAIN/RAIDカテゴリのraw配置規約は未確認のため、
このモジュールはEVENT・CHARACTER・CHARACTER_DATEカテゴリのみに対応する
（Story_Manifest_Design.md §6・§18 OD-002）。
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

from agents.parser.character_dictionary import (
    STATUS_CONFIRMED,
    CharacterDictionaryEntry,
    resolve_character_by_source_id,
)

SCHEMA_VERSION = "0.1.0"
DOCUMENT_TYPE = "story_manifest"
METADATA_STATUS_PENDING = "pending"

# EVENT/csl_script_event_{sourceKey}_export ディレクトリ名パターン
_EXPORT_DIRECTORY_PATTERN = re.compile(
    r"^csl_script_event_(?P<source_key>.+)_export$", re.IGNORECASE
)

# CAB-csl_script_event_{sourceKey}-episode{N}.dec ファイル名パターン
_EPISODE_FILE_PATTERN = re.compile(
    r"^CAB-csl_script_event_(?P<source_key>.+)-episode(?P<episode_number>\d+)\.dec$",
    re.IGNORECASE,
)

# ----------------------------------------------------------------
# CHARACTER / CHARACTER_DATE (Character_Story_ID_Manifest_Design.md §4・§8)
# ----------------------------------------------------------------

# CHARACTER/csl_script_charastory_character{N}_export ディレクトリ名パターン
_CHARACTER_EXPORT_DIR_PATTERN = re.compile(
    r"^csl_script_charastory_character(?P<n>\d+)_export$", re.IGNORECASE
)
# CHARACTER_DATE/csl_script_surprise_character{N}_export ディレクトリ名パターン
_CHARACTER_DATE_EXPORT_DIR_PATTERN = re.compile(
    r"^csl_script_surprise_character(?P<n>\d+)_export$", re.IGNORECASE
)

# CAB-csl_script_charastory_character{N}-{suffix}.dec ファイル名パターン
_CHARACTER_FILE_PATTERN = re.compile(
    r"^CAB-csl_script_charastory_character(?P<n>\d+)-(?P<suffix>.+)\.dec$",
    re.IGNORECASE,
)
# CAB-csl_script_surprise_character{N}-Surprise_{M}.dec ファイル名パターン
_CHARACTER_DATE_FILE_PATTERN = re.compile(
    r"^CAB-csl_script_surprise_character(?P<n>\d+)-(?P<suffix>.+)\.dec$",
    re.IGNORECASE,
)

# story本体を構成する種別のsuffixパターン（Character_Story_ID_Manifest_Design.md §4.2）
_EPISODE_MAIN_PATTERN = re.compile(r"^episode(?P<n>\d+)$", re.IGNORECASE)
_EPISODE_EXTRA_PATTERN = re.compile(r"^episode_EX(?P<n>\d+)$", re.IGNORECASE)
_HSCENE_BODY_PATTERN = re.compile(r"^H_scene(?P<n>\d+)$", re.IGNORECASE)
_HSCENE_S_PATTERN = re.compile(r"^H_scene_s$", re.IGNORECASE)
_SURPRISE_PATTERN = re.compile(r"^Surprise_(?P<m>\d+)$", re.IGNORECASE)

# H_sceneN変種（fileRole: variant、Character_Story_ID_Manifest_Design.md §3.3・§8.1）。
# 部分集合判定はパース時の動的判定のため、manifest生成時点では一律variantとする。
_VARIANT_SUFFIX_PATTERNS = [
    re.compile(r"^H_scene\d+_n$", re.IGNORECASE),
    re.compile(r"^H_scene\d+_spine$", re.IGNORECASE),
    re.compile(r"^H_scene\d+_VR$", re.IGNORECASE),
    re.compile(r"^H_scene\d+ #\d+$", re.IGNORECASE),
    re.compile(r"^H_scene\d+_n #\d+$", re.IGNORECASE),
    re.compile(r"^H_scene\d+_spine #\d+$", re.IGNORECASE),
]

# 純コマンド/演出系ファイル（fileRole: direction）
# Character_Story_ID_Manifest_Design.md §3.3・§8.1
_DIRECTION_SUFFIX_PATTERNS = [
    re.compile(r"^camera\d+$", re.IGNORECASE),
    re.compile(r"^camera\d+ #\d+$", re.IGNORECASE),
    re.compile(r"^camera$", re.IGNORECASE),
    re.compile(r"^camera #\d+$", re.IGNORECASE),
    re.compile(r"^finish #\d+$", re.IGNORECASE),
    re.compile(r"^finish$", re.IGNORECASE),
    re.compile(r"^episode_bgm\d+$", re.IGNORECASE),
    re.compile(r"^sv_\d+$", re.IGNORECASE),
    re.compile(r"^docking\d+$", re.IGNORECASE),
    re.compile(r"^cameradocking\d+$", re.IGNORECASE),
    re.compile(r"^episode_osawari\d+_start$", re.IGNORECASE),
    re.compile(r"^episode_osawari\d+_end$", re.IGNORECASE),
    re.compile(r"^camerabreast\d+$", re.IGNORECASE),
    re.compile(r"^breast\d+$", re.IGNORECASE),
    re.compile(r"^cameracrotch\d+$", re.IGNORECASE),
    re.compile(r"^crotch\d+$", re.IGNORECASE),
    re.compile(r"^episode_ASMR\d+$", re.IGNORECASE),
    re.compile(r"^VR_\d+$", re.IGNORECASE),
    re.compile(r"^talk$", re.IGNORECASE),
    re.compile(r"^start$", re.IGNORECASE),
    re.compile(r"^position$", re.IGNORECASE),
]

# storyId/episodeIdがschemaのpattern (^[A-Z][A-Z0-9_]*$) を満たすかの確認用
# (characterIdはCHARACTER_ID_PATTERNでハイフンを許容するが、storyId側は許容しない)。
_STORY_ID_SAFE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def normalize_path_separators(path: str) -> str:
    """Windowsのバックスラッシュ区切りをスラッシュ区切りへ正規化する
    (Story_Manifest_Design.md §5)。"""
    return path.replace("\\", "/")


def _relative_posix_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    return normalize_path_separators(str(PurePosixPath(*relative.parts)))


def parse_export_directory_name(name: str) -> str | None:
    """ディレクトリ名から sourceKey を抽出する。一致しなければNone。"""
    match = _EXPORT_DIRECTORY_PATTERN.match(name)
    if match is None:
        return None
    return match.group("source_key")


def parse_episode_filename(name: str, expected_source_key: str) -> int | None:
    """ファイル名から episodeNumber を抽出する。

    ディレクトリ名から抽出したsourceKeyと一致しない場合はNoneを返す
    (認識できないファイルとして候補生成対象外にする、Story_Manifest_Design.md §16)。
    """
    match = _EPISODE_FILE_PATTERN.match(name)
    if match is None:
        return None
    if match.group("source_key").lower() != expected_source_key.lower():
        return None
    return int(match.group("episode_number"))


def build_story_manifest_candidate(
    export_dir: Path, raw_root: Path
) -> dict[str, Any] | None:
    """1つの`_export`ディレクトリからstory manifest候補エントリを組み立てる。

    対象となる`.dec`ファイルが1件も見つからない場合はNoneを返す。
    """
    source_key = parse_export_directory_name(export_dir.name)
    if source_key is None:
        return None

    story_id = f"EVT_{source_key.upper()}"
    episodes: list[dict[str, Any]] = []
    for entry in export_dir.iterdir():
        if not entry.is_file():
            continue
        episode_number = parse_episode_filename(entry.name, source_key)
        if episode_number is None:
            continue
        episodes.append(
            {
                "episodeId": f"{story_id}_E{episode_number:02d}",
                "episodeNumber": episode_number,
                "subtitle": None,
                "displayTitle": None,
                "rawPath": _relative_posix_path(entry, raw_root),
                "sourceFileName": entry.name,
                "metadataStatus": METADATA_STATUS_PENDING,
                "notes": None,
            }
        )

    if not episodes:
        return None

    episodes.sort(key=lambda episode: episode["episodeNumber"])

    return {
        "storyId": story_id,
        "category": "event",
        "sourceKey": source_key,
        "title": None,
        "displayTitle": None,
        "metadataStatus": METADATA_STATUS_PENDING,
        "rawDirectory": _relative_posix_path(export_dir, raw_root),
        "notes": None,
        "episodes": episodes,
    }


def find_event_category_directory(raw_root: Path) -> Path | None:
    """raw_root直下のEVENTディレクトリを探す (大文字小文字を区別しない)。"""
    for entry in raw_root.iterdir():
        if entry.is_dir() and entry.name.lower() == "event":
            return entry
    return None


def build_story_manifest_candidates(raw_root: Path) -> list[dict[str, Any]]:
    """raw_root配下のEVENTカテゴリから、story manifest候補一覧を組み立てる。

    storyId順にソートして返す (他カテゴリはStory_Manifest_Design.md §6の通り
    このモジュールでは未対応)。
    """
    event_dir = find_event_category_directory(raw_root)
    if event_dir is None:
        return []

    candidates: list[dict[str, Any]] = []
    for entry in event_dir.iterdir():
        if not entry.is_dir():
            continue
        candidate = build_story_manifest_candidate(entry, raw_root)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda story: story["storyId"])
    return candidates


def build_candidate_document(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": SCHEMA_VERSION,
        "documentType": DOCUMENT_TYPE,
        "stories": candidates,
    }


# ----------------------------------------------------------------
# CHARACTER / CHARACTER_DATE candidate builder
# (Character_Story_ID_Manifest_Design.md §4・§8・§9 PR C)
# ----------------------------------------------------------------


def find_character_category_directory(raw_root: Path) -> Path | None:
    """raw_root直下のCHARACTERディレクトリを探す (大文字小文字を区別しない)。"""
    for entry in raw_root.iterdir():
        if entry.is_dir() and entry.name.lower() == "character":
            return entry
    return None


def find_character_date_category_directory(raw_root: Path) -> Path | None:
    """raw_root直下のCHARACTER_DATEディレクトリを探す (大文字小文字を区別しない)。"""
    for entry in raw_root.iterdir():
        if entry.is_dir() and entry.name.lower() == "character_date":
            return entry
    return None


def _collect_export_dirs_by_source_id(
    category_dir: Path, dir_pattern: re.Pattern[str]
) -> dict[str, Path]:
    """カテゴリdir直下のexportディレクトリを、ディレクトリ名から抽出した
    sourceCharacterId (`{N}`) をキーにして集める。"""
    result: dict[str, Path] = {}
    for entry in sorted(category_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_dir():
            continue
        match = dir_pattern.match(entry.name)
        if match is None:
            continue
        result[match.group("n")] = entry
    return result


def classify_auxiliary_suffix(suffix: str) -> str:
    """ファイル名suffixからauxiliaryFilesの`fileRole`を分類する。

    variant/directionいずれのパターンにも一致しない場合はすべて`other`に
    分類する (H_sceneN_img等の特殊ファイル・未知の新種別を含め、認識できない
    ファイルを黙って落とさず必ずotherとして残す方針、Character_Story_ID_
    Manifest_Design.md §8.1)。
    """
    for pattern in _VARIANT_SUFFIX_PATTERNS:
        if pattern.match(suffix):
            return "variant"
    for pattern in _DIRECTION_SUFFIX_PATTERNS:
        if pattern.match(suffix):
            return "direction"
    return "other"


def _new_character_story(
    story_id: str, character_id: str, source_key: str, raw_directory: str
) -> dict[str, Any]:
    return {
        "storyId": story_id,
        "characterId": character_id,
        "category": "character",
        "sourceKey": source_key,
        "title": None,
        "displayTitle": None,
        "metadataStatus": METADATA_STATUS_PENDING,
        "rawDirectory": raw_directory,
        "notes": None,
        "auxiliaryFiles": [],
        "episodes": [],
    }


def _make_episode_entry(
    episode_id: str, episode_number: int, entry: Path, raw_root: Path
) -> dict[str, Any]:
    return {
        "episodeId": episode_id,
        "episodeNumber": episode_number,
        "subtitle": None,
        "displayTitle": None,
        "rawPath": _relative_posix_path(entry, raw_root),
        "sourceFileName": entry.name,
        "metadataStatus": METADATA_STATUS_PENDING,
        "notes": None,
    }


def _make_auxiliary_file_entry(
    entry: Path, raw_root: Path, file_role: str
) -> dict[str, Any]:
    return {
        "rawPath": _relative_posix_path(entry, raw_root),
        "sourceFileName": entry.name,
        "fileRole": file_role,
        "notes": None,
    }


def _attach_auxiliary_file(
    entry: Path,
    raw_root: Path,
    suffix: str,
    source_id: str,
    hs_story_id: str,
    fallback_story_id: str | None,
    candidates_by_story_id: dict[str, dict[str, Any]],
    report: list[dict[str, Any]],
) -> None:
    """variant/direction/otherに分類したファイルを、対応するstoryの
    `auxiliaryFiles`へ添付する。紐づけ先が存在しない場合はpending報告へ
    残す（黙って除外しない、Character_Story_ID_Manifest_Design.md §8.1）。
    """
    role = classify_auxiliary_suffix(suffix)
    if role == "variant":
        target_story = candidates_by_story_id.get(hs_story_id)
    else:
        target_story = candidates_by_story_id.get(hs_story_id)
        if target_story is None and fallback_story_id is not None:
            target_story = candidates_by_story_id.get(fallback_story_id)

    if target_story is None:
        report.append(
            {
                "issueType": "unattached_auxiliary_file",
                "sourceCharacterId": source_id,
                "path": _relative_posix_path(entry, raw_root),
                "fileRole": role,
                "detail": (
                    "紐づけ先のstory (CHAR_HS"
                    + ("/CHAR_MAIN" if fallback_story_id is not None else "")
                    + ") が存在しません"
                ),
            }
        )
        return

    target_story["auxiliaryFiles"].append(
        _make_auxiliary_file_entry(entry, raw_root, role)
    )


def _classify_character_body_suffix(suffix: str) -> tuple[str, int | None] | None:
    """`character`カテゴリのsuffixが、story本体を構成する種別
    (episodeN/episode_EXN/H_sceneN/H_scene_s) に一致すれば`(kind, n)`を
    返す。一致しなければNone (variant/direction/other側の処理へ回す)。"""
    main_match = _EPISODE_MAIN_PATTERN.match(suffix)
    if main_match is not None:
        return "main", int(main_match.group("n"))
    extra_match = _EPISODE_EXTRA_PATTERN.match(suffix)
    if extra_match is not None:
        return "extra", int(extra_match.group("n"))
    hs_match = _HSCENE_BODY_PATTERN.match(suffix)
    if hs_match is not None:
        return "hs", int(hs_match.group("n"))
    if _HSCENE_S_PATTERN.match(suffix) is not None:
        return "hs_s", None
    return None


def _classify_character_date_body_suffix(suffix: str) -> tuple[str, int | None] | None:
    """`character_date`カテゴリのsuffixが`Surprise_{M}`に一致すれば
    `("date", M)`を返す。一致しなければNone。"""
    match = _SURPRISE_PATTERN.match(suffix)
    if match is None:
        return None
    return "date", int(match.group("m"))


def _split_character_export_entries(
    export_dir: Path,
    raw_root: Path,
    source_id: str,
    file_pattern: re.Pattern[str],
    body_classifier: Any,
    report: list[dict[str, Any]],
) -> tuple[list[tuple[Path, str, int | None]], list[tuple[Path, str]]]:
    """exportディレクトリ配下のファイルを、body種別 (`(entry, kind, n)`) 一覧
    とその他 (variant/direction/other候補、`(entry, suffix)`) 一覧へ分類する。

    `{N}`（ディレクトリ名由来のsourceCharacterId）とファイル名の`{N}`が
    一致しないファイルは、認識できないファイルとしてreportへ記録し、
    どちらの一覧にも含めない (Character_Story_ID_Manifest_Design.md §4.5)。
    """
    body_entries: list[tuple[Path, str, int | None]] = []
    other_entries: list[tuple[Path, str]] = []

    for entry in sorted(export_dir.iterdir(), key=lambda p: p.name):
        if not entry.is_file():
            continue
        match = file_pattern.match(entry.name)
        if match is None:
            continue

        file_source_id = match.group("n")
        suffix = match.group("suffix")
        if file_source_id != source_id:
            report.append(
                {
                    "issueType": "id_mismatch",
                    "sourceCharacterId": source_id,
                    "path": _relative_posix_path(entry, raw_root),
                    "detail": (
                        f"ディレクトリのcharacterId ({source_id}) とファイル名の"
                        f"characterId ({file_source_id}) が一致しません"
                    ),
                }
            )
            continue

        classified = body_classifier(suffix)
        if classified is not None:
            kind, n = classified
            body_entries.append((entry, kind, n))
        else:
            other_entries.append((entry, suffix))

    return body_entries, other_entries


def _add_body_episode(
    kind: str,
    n: int | None,
    entry: Path,
    raw_root: Path,
    story_id: str,
    character_id: str,
    source_id: str,
    raw_directory: str,
    candidates_by_story_id: dict[str, dict[str, Any]],
) -> None:
    """body種別1件をepisodeとして対応するstoryへ追加する (storyが無ければ
    新規作成する)。`H_scene_s`のみepisodeId末尾が`_ES01`固定になる
    (Character_Story_ID_Manifest_Design.md §4.2)。"""
    story = candidates_by_story_id.setdefault(
        story_id,
        _new_character_story(story_id, character_id, source_id, raw_directory),
    )
    if kind == "hs_s":
        episode = _make_episode_entry(f"{story_id}_ES01", 1, entry, raw_root)
    else:
        episode = _make_episode_entry(f"{story_id}_E{n:02d}", n, entry, raw_root)
    story["episodes"].append(episode)


def _process_character_export_dir(
    export_dir: Path,
    raw_root: Path,
    source_id: str,
    character_id: str,
    romaji: str,
    candidates_by_story_id: dict[str, dict[str, Any]],
    report: list[dict[str, Any]],
) -> None:
    """`character`カテゴリの1つのexportディレクトリ (charastory) から、
    CHAR_MAIN/CHAR_EXTRA/CHAR_HS storyのepisode/auxiliaryFilesを組み立てる。

    body種別 (episodeN/episode_EXN/H_sceneN/H_scene_s) を先に処理して該当
    storyを確定させ、その後にvariant/direction/other種別を処理する2パス
    方式にすることで、ファイルシステムのイテレーション順序に依存せず
    auxiliaryFilesの紐づけ先 (CHAR_HS/CHAR_MAIN) を決定できるようにする。
    """
    raw_directory = _relative_posix_path(export_dir, raw_root)
    main_story_id = f"CHAR_MAIN_{romaji}"
    hs_story_id = f"CHAR_HS_{romaji}"
    story_id_by_kind = {
        "main": main_story_id,
        "extra": f"CHAR_EXTRA_{romaji}",
        "hs": hs_story_id,
        "hs_s": hs_story_id,
    }

    body_entries, other_entries = _split_character_export_entries(
        export_dir,
        raw_root,
        source_id,
        _CHARACTER_FILE_PATTERN,
        _classify_character_body_suffix,
        report,
    )

    for entry, kind, n in body_entries:
        _add_body_episode(
            kind,
            n,
            entry,
            raw_root,
            story_id_by_kind[kind],
            character_id,
            source_id,
            raw_directory,
            candidates_by_story_id,
        )

    for entry, suffix in other_entries:
        _attach_auxiliary_file(
            entry,
            raw_root,
            suffix,
            source_id,
            hs_story_id,
            main_story_id,
            candidates_by_story_id,
            report,
        )


def _process_character_date_export_dir(
    export_dir: Path,
    raw_root: Path,
    source_id: str,
    character_id: str,
    romaji: str,
    candidates_by_story_id: dict[str, dict[str, Any]],
    report: list[dict[str, Any]],
) -> None:
    """`character_date`カテゴリの1つのexportディレクトリ (surprise) から、
    CHAR_DATE storyのepisode/auxiliaryFilesを組み立てる (2パス方式、
    _process_character_export_dirと同じ理由)。
    """
    raw_directory = _relative_posix_path(export_dir, raw_root)
    date_story_id = f"CHAR_DATE_{romaji}"

    body_entries, other_entries = _split_character_export_entries(
        export_dir,
        raw_root,
        source_id,
        _CHARACTER_DATE_FILE_PATTERN,
        _classify_character_date_body_suffix,
        report,
    )

    for entry, kind, n in body_entries:
        _add_body_episode(
            kind,
            n,
            entry,
            raw_root,
            date_story_id,
            character_id,
            source_id,
            raw_directory,
            candidates_by_story_id,
        )

    for entry, suffix in other_entries:
        _attach_auxiliary_file(
            entry,
            raw_root,
            suffix,
            source_id,
            date_story_id,
            None,
            candidates_by_story_id,
            report,
        )


def build_character_story_manifest_candidates(
    raw_root: Path,
    dictionary_entries: list[CharacterDictionaryEntry],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """raw_root配下のCHARACTER・CHARACTER_DATEカテゴリから、story manifest
    候補一覧を組み立てる (Character_Story_ID_Manifest_Design.md §4・§8)。

    戻り値は`(candidates, report)`のtuple。`report`は、未confirmedキャラクター・
    `{N}`不一致ファイル・紐づけ先の無いauxiliaryFilesを人間確認用に列挙した
    もので、`story_manifest.yaml`のschemaには含まれない (黙って除外しない
    方針を満たすための、CLI表示専用の付随情報)。
    """
    candidates_by_story_id: dict[str, dict[str, Any]] = {}
    report: list[dict[str, Any]] = []

    character_dir = find_character_category_directory(raw_root)
    character_date_dir = find_character_date_category_directory(raw_root)

    character_export_dirs = (
        _collect_export_dirs_by_source_id(character_dir, _CHARACTER_EXPORT_DIR_PATTERN)
        if character_dir is not None
        else {}
    )
    character_date_export_dirs = (
        _collect_export_dirs_by_source_id(
            character_date_dir, _CHARACTER_DATE_EXPORT_DIR_PATTERN
        )
        if character_date_dir is not None
        else {}
    )

    all_source_ids = sorted(
        set(character_export_dirs) | set(character_date_export_dirs), key=int
    )

    for source_id in all_source_ids:
        entry = resolve_character_by_source_id(dictionary_entries, source_id)
        if entry is None or entry.status != STATUS_CONFIRMED or not entry.character_id:
            report.append(
                {
                    "issueType": "unconfirmed_character",
                    "sourceCharacterId": source_id,
                    "detail": (
                        "characters.yamlでstatus: confirmedとして登録されていない"
                        "ため、candidate生成対象外です"
                    ),
                }
            )
            continue

        character_id = entry.character_id
        romaji = character_id[len("CHAR_") :]
        if not _STORY_ID_SAFE_PATTERN.match(f"CHAR_MAIN_{romaji}"):
            report.append(
                {
                    "issueType": "invalid_story_id",
                    "sourceCharacterId": source_id,
                    "detail": (
                        f"characterId '{character_id}' から組み立てたstoryIdが"
                        "story_manifest schemaのstoryIdパターンを満たさない"
                        "ため、candidate生成対象外です"
                    ),
                }
            )
            continue

        if source_id in character_export_dirs:
            _process_character_export_dir(
                character_export_dirs[source_id],
                raw_root,
                source_id,
                character_id,
                romaji,
                candidates_by_story_id,
                report,
            )
        if source_id in character_date_export_dirs:
            _process_character_date_export_dir(
                character_date_export_dirs[source_id],
                raw_root,
                source_id,
                character_id,
                romaji,
                candidates_by_story_id,
                report,
            )

    candidates = list(candidates_by_story_id.values())
    for story in candidates:
        story["episodes"].sort(
            key=lambda episode: (episode["episodeNumber"], episode["episodeId"])
        )
    candidates.sort(key=lambda story: story["storyId"])
    return candidates, report
