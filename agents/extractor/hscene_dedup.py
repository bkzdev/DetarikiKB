"""
DKB Extractor - H_scene Variant Dedup
Character_Story_ID_Manifest_Design.md §6.3・§9 PR E: CHAR_HS本体episodeと
例外変種episode間 (および例外変種同士) の重複ブロックを、抽出段階で
voice/textアセットpath同一性により除外マークする。

対象は `source.hsceneVariantTrace` (agents/parser/hscene_variant_judgment.py・
agents/parser/normalizer.py) を持つ変種episodeと、そのbaseEpisodeIdが指す
本体episode。トレースの無い通常episode・CHAR_HS以外のカテゴリの抽出挙動は
完全無回帰 (グループを構成しないepisodeは従来通りExtractor.extract_episode
がそのまま処理する)。

**不破棄不変則を維持する**: Normalized Story JSONからは何もブロックを削除
しない。ここで行うのは、Extractorへ渡すepisode dictの「コピー」から重複と
判定したブロックを取り除くことだけであり (元のepisode dict自体は変更しない)、
除外した事実はepisode_extraction出力の`hsceneDedup`フィールドへ記録する
(除外件数・除外Block ID・重複の起点となったepisodeIdの一覧)。

本体documentが入力に含まれない場合 (変種のみが与えられた場合) は、dedupを
実施せず黙って本体扱いもしない。`hsceneDedup.baseEpisodeAvailable: false`
としてその旨を記録する。

内容同一性の判定子は、agents/parser/hscene_variant_judgment.pyの
extract_identifier_set系 (発話系コマンドが参照するvoice/textアセットpath＋
正規化済み日本語TEXT行の集合) と同じ意味論を、ファイル全体ではなくBlock1件分
のsource.raw/rawText/choiceTextから再構築したテキストに適用することで
再利用する。

docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md §6.3・§9
docs/architecture/01_Project/03_Scope.md §5.5.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.parser.hscene_variant_judgment import extract_identifier_set_from_tokens
from agents.parser.tokenizer import Tokenizer

from .extractor import Extractor
from .models import EVIDENCE_BLOCK_TYPES

HSCENE_DEDUP_ROLE_BODY = "body"
HSCENE_DEDUP_ROLE_VARIANT = "variant"


# ----------------------------------------------------------------
# Block走査 (agents/extractor/base.py の evidence_from_block と同じ
# 再帰パターン: dialogue/monologue/narration/choiceを対象とし、
# choiceのoption内blocksも再帰的に辿る)
# ----------------------------------------------------------------


def _iter_evidence_blocks(blocks: list[dict[str, Any]]):
    for block in blocks:
        if block.get("type") in EVIDENCE_BLOCK_TYPES:
            yield block
        for option in block.get("options") or []:
            yield from _iter_evidence_blocks(option.get("blocks") or [])


def _episode_evidence_blocks(episode: dict[str, Any]):
    for scene in episode.get("scenes") or []:
        yield from _iter_evidence_blocks(scene.get("blocks") or [])


# ----------------------------------------------------------------
# Block単位の識別子集合
# ----------------------------------------------------------------


def block_identifier_set(
    block: dict[str, Any], tokenizer: Tokenizer | None = None
) -> frozenset[str]:
    """Block1件分のvoice/textアセット識別子集合を抽出する。

    agents/parser/hscene_variant_judgment.extract_identifier_set系と同じ
    意味論 (発話系コマンドのアセットpath＋正規化済み日本語TEXT行) を、
    Blockのsource.raw (発話コマンド行、dialogue/monologue) /rawText
    (本文行、dialogue/monologue/narration) /choiceText (choice) から
    再構築したテキストに対して適用する。stage_direction/unknown等
    EVIDENCE_BLOCK_TYPES以外のBlockは呼び出し側で対象外とする想定。
    """
    pieces: list[str] = []
    source = block.get("source") or {}
    raw = source.get("raw")
    if raw:
        pieces.append(raw)
    raw_text = block.get("rawText")
    if raw_text:
        pieces.append(raw_text)
    choice_text = block.get("choiceText")
    if choice_text:
        pieces.append(choice_text)

    if not pieces:
        return frozenset()

    tok = tokenizer or Tokenizer()
    tokens = tok.tokenize_text("\n".join(pieces))
    return extract_identifier_set_from_tokens(tokens)


# ----------------------------------------------------------------
# Episodeコピーからの重複Block除外 (Normalized Story JSON自体は変更しない)
# ----------------------------------------------------------------


def _filter_blocks(
    blocks: list[dict[str, Any]], duplicate_ids: frozenset[str]
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for block in blocks:
        if block.get("id") in duplicate_ids:
            continue
        options = block.get("options")
        if options:
            new_block = dict(block)
            new_block["options"] = [
                {
                    **option,
                    "blocks": _filter_blocks(option.get("blocks") or [], duplicate_ids),
                }
                for option in options
            ]
            filtered.append(new_block)
        else:
            filtered.append(block)
    return filtered


def _filter_episode_for_extraction(
    episode: dict[str, Any], duplicate_ids: frozenset[str]
) -> dict[str, Any]:
    """抽出用のepisodeコピーを作る。duplicate_idsが空なら元のepisodeをそのまま返す
    (無回帰ケースで無駄なコピーをしない)。
    """
    if not duplicate_ids:
        return episode
    new_episode = dict(episode)
    new_episode["scenes"] = [
        {
            **scene,
            "blocks": _filter_blocks(scene.get("blocks") or [], duplicate_ids),
        }
        for scene in episode.get("scenes") or []
    ]
    return new_episode


# ----------------------------------------------------------------
# グループ化 (baseEpisodeId単位)
# ----------------------------------------------------------------


@dataclass
class _GroupMember:
    story_json: dict[str, Any]
    episode: dict[str, Any]
    episode_id: str


@dataclass
class HsceneDedupGroup:
    base_episode_id: str
    body: _GroupMember | None
    variants: list[_GroupMember] = field(default_factory=list)


def _group_documents(
    story_jsons: list[dict[str, Any]],
) -> dict[str, HsceneDedupGroup]:
    """入力document群を、H_sceneN本体+例外変種のgroupへ分類する。

    グループの単位はhsceneVariantTrace.baseEpisodeId。本体documentが入力に
    含まれない場合、group.bodyはNoneのままになる (dedup非実施の判定材料)。
    """
    all_members: dict[str, _GroupMember] = {}
    trace_by_episode: dict[str, dict[str, Any]] = {}

    for story_json in story_jsons:
        trace = (story_json.get("source") or {}).get("hsceneVariantTrace")
        for episode in story_json.get("episodes") or []:
            episode_id = episode.get("episodeId")
            if not episode_id:
                continue
            all_members[episode_id] = _GroupMember(
                story_json=story_json, episode=episode, episode_id=episode_id
            )
            if trace is not None and trace.get("baseEpisodeId"):
                trace_by_episode[episode_id] = trace

    groups: dict[str, HsceneDedupGroup] = {}
    for episode_id in trace_by_episode:
        base_episode_id = trace_by_episode[episode_id]["baseEpisodeId"]
        group = groups.setdefault(
            base_episode_id,
            HsceneDedupGroup(base_episode_id=base_episode_id, body=None),
        )
        group.variants.append(all_members[episode_id])

    for group in groups.values():
        group.body = all_members.get(group.base_episode_id)
        group.variants.sort(key=lambda m: m.episode_id)

    return groups


# ----------------------------------------------------------------
# グループ単位のdedup計算
# ----------------------------------------------------------------


@dataclass
class _EpisodeDedupOutcome:
    duplicate_block_ids: frozenset[str] = frozenset()
    deduped_against_episode_ids: tuple[str, ...] = ()


def _compute_group_dedup(
    group: HsceneDedupGroup, tokenizer: Tokenizer | None = None
) -> dict[str, _EpisodeDedupOutcome]:
    """group内の各episodeについて、重複除外マークするBlock IDの集合を計算する。

    本体が入力に含まれない場合はdedupを実施せず、全variantを空のoutcome
    (重複0件) で返す (§5.5.1: 黙って本体扱いしない)。

    変種は決定的な順序 (episodeIdの辞書順、_group_documentsで既にsort済み)
    で処理し、本体→変種1→変種2…の順にidentifierの"既出"集合を蓄積する。
    これにより変種同士の重複も初出のみが残る (二重計上しない)。
    """
    tok = tokenizer or Tokenizer()
    outcomes: dict[str, _EpisodeDedupOutcome] = {}

    if group.body is None:
        for member in group.variants:
            outcomes[member.episode_id] = _EpisodeDedupOutcome()
        return outcomes

    seen: set[str] = set()
    seen_owner: dict[str, str] = {}
    for block in _episode_evidence_blocks(group.body.episode):
        for identifier in block_identifier_set(block, tok):
            seen.add(identifier)
            seen_owner.setdefault(identifier, group.body.episode_id)
    outcomes[group.body.episode_id] = _EpisodeDedupOutcome()

    for member in group.variants:
        duplicate_block_ids: set[str] = set()
        owners_used: set[str] = set()
        for block in _episode_evidence_blocks(member.episode):
            ids = block_identifier_set(block, tok)
            # 空集合 (アセットpath/本文のいずれも持たないBlock) は
            # 比較材料が無いため常に維持する (subsetの自明な成立で誤って
            # 除外マークしないようにする)。
            if ids and ids <= seen:
                block_id = block.get("id")
                if block_id:
                    duplicate_block_ids.add(block_id)
                owners_used.update(seen_owner[i] for i in ids)
            else:
                for identifier in ids:
                    seen.add(identifier)
                    seen_owner.setdefault(identifier, member.episode_id)
        outcomes[member.episode_id] = _EpisodeDedupOutcome(
            duplicate_block_ids=frozenset(duplicate_block_ids),
            deduped_against_episode_ids=tuple(sorted(owners_used)),
        )

    return outcomes


# ----------------------------------------------------------------
# 抽出オーケストレーション
# ----------------------------------------------------------------


def extract_stories_with_hscene_dedup(
    story_jsons: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """複数のNormalized Story JSON documentを受け取り、CHAR_HS本体/例外変種
    グループ間の重複ブロックを抽出段階で除外マークした上でepisode_extraction
    のリストを返す (documentの入力順・episode順を保つ)。

    hsceneVariantTraceを持たない、かつどのgroupのbaseEpisodeIdにも該当しない
    episode (通常episode・CHAR_HS以外のカテゴリを含む) は、従来通り
    Extractor.extract_episode をそのまま呼び出す (hsceneDedupフィールド自体
    を付与しない、完全無回帰)。
    """
    groups = _group_documents(story_jsons)

    dedup_by_episode: dict[str, _EpisodeDedupOutcome] = {}
    for group in groups.values():
        dedup_by_episode.update(_compute_group_dedup(group))

    extractor = Extractor()
    extractions: list[dict[str, Any]] = []

    for story_json in story_jsons:
        story_id = story_json["storyId"]
        story_category = story_json["storyCategory"]
        parser_compatibility = story_json.get("compatibilityReport", {}).get(
            "parserCompatibility", "compatible"
        )
        story_title = story_json.get("metadata", {}).get("storyTitle")
        public_story_id = story_json.get("metadata", {}).get("publicStoryId")
        trace = (story_json.get("source") or {}).get("hsceneVariantTrace")

        for episode in story_json.get("episodes") or []:
            episode_id = episode.get("episodeId")
            hscene_dedup_info: dict[str, Any] | None = None
            episode_for_extraction = episode

            if episode_id in dedup_by_episode:
                outcome = dedup_by_episode[episode_id]
                if trace is not None:
                    # role=variant: このdocument自身がhsceneVariantTraceを持つ
                    base_episode_id = trace["baseEpisodeId"]
                    group = groups[base_episode_id]
                    base_available = group.body is not None
                    episode_for_extraction = _filter_episode_for_extraction(
                        episode, outcome.duplicate_block_ids
                    )
                    hscene_dedup_info = {
                        "role": HSCENE_DEDUP_ROLE_VARIANT,
                        "groupBaseEpisodeId": base_episode_id,
                        "baseEpisodeAvailable": base_available,
                        "excludedBlockCount": len(outcome.duplicate_block_ids),
                        "excludedBlockIds": sorted(outcome.duplicate_block_ids),
                        "dedupedAgainstEpisodeIds": list(
                            outcome.deduped_against_episode_ids
                        ),
                    }
                else:
                    # role=body: episode_idがどこかのgroupのbaseEpisodeId
                    group = groups[episode_id]
                    hscene_dedup_info = {
                        "role": HSCENE_DEDUP_ROLE_BODY,
                        "groupBaseEpisodeId": episode_id,
                        "variantEpisodeIds": [m.episode_id for m in group.variants],
                    }

            extraction = extractor.extract_episode(
                episode_for_extraction,
                story_id=story_id,
                story_category=story_category,
                parser_compatibility=parser_compatibility,
                story_title=story_title,
                public_story_id=public_story_id,
            )
            if hscene_dedup_info is not None:
                extraction["hsceneDedup"] = hscene_dedup_info
            extractions.append(extraction)

    return extractions
