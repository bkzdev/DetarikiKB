"""
DKB Story Parser - Normalizer
Parser 中間構造を Normalized_Story_JSON.md に準拠した JSON へ整形する。

Phase 7 (Parser_Implementation_Plan.md)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .compatibility import (
    detect_new_speech_commands,
    determine_compatibility_status,
    get_new_speech_hints,
    load_command_config,
)
from .parser import BlockData, EpisodeData, ParseResult, SceneData

# ----------------------------------------------------------------
# Constants
# ----------------------------------------------------------------

SCHEMA_VERSION = "0.2"
DOCUMENT_TYPE = "normalized_story"
PARSER_NAME = "DKB Story Parser"
PARSER_VERSION = "0.2.0"


# ----------------------------------------------------------------
# ID Generator
# ----------------------------------------------------------------


class IdGenerator:
    """
    Identifier_Specification.md に準拠した ID を生成する。

    各カウンターはエピソード単位でリセットする。
    """

    def __init__(self, episode_id: str) -> None:
        self._episode_id = episode_id
        self._scene_count = 0
        self._dlg_count = 0
        self._mono_count = 0
        self._nar_count = 0
        self._choice_count = 0
        self._stage_count = 0
        self._unknown_count = 0

    def next_scene_id(self) -> str:
        self._scene_count += 1
        return f"{self._episode_id}_SC{self._scene_count:03d}"

    def next_block_id(self, block_type: str) -> str:
        if block_type == "dialogue":
            self._dlg_count += 1
            return f"{self._episode_id}_DLG{self._dlg_count:04d}"
        elif block_type == "monologue":
            self._mono_count += 1
            return f"{self._episode_id}_MONO{self._mono_count:04d}"
        elif block_type == "narration":
            self._nar_count += 1
            return f"{self._episode_id}_NAR{self._nar_count:04d}"
        elif block_type == "choice":
            self._choice_count += 1
            return f"{self._episode_id}_CHOICE{self._choice_count:03d}"
        elif block_type == "stage_direction":
            self._stage_count += 1
            return f"{self._episode_id}_STAGE{self._stage_count:04d}"
        else:
            self._unknown_count += 1
            return f"{self._episode_id}_UNKNOWN{self._unknown_count:04d}"

    def next_choice_option_id(self, choice_id: str, option_number: int) -> str:
        return f"{choice_id}_OPT{option_number:02d}"


# ----------------------------------------------------------------
# Normalizer
# ----------------------------------------------------------------


class Normalizer:
    """
    ParseResult → Normalized Story JSON (dict) へ変換する。
    """

    def __init__(
        self,
        story_id: str,
        story_category: str,
        episode_id: str | None = None,
        story_metadata: dict | None = None,
        episode_metadata: dict | None = None,
        source_file: str | None = None,
        source_path: str | None = None,
        preserve_stage_directions: bool = True,
        commands_config_path: str | Path | None = None,
        manifest_source: dict | None = None,
        variant_trace: dict | None = None,
    ) -> None:
        """
        Args:
            story_id: Story ID (例: MAIN_S01_C02)
            story_category: MAIN / EVT / RAID / OTHER / CHAR_MAIN / CHAR_EXTRA /
                CHAR_DATE
            episode_id: Episode ID (例: MAIN_S01_C02_E01)。
                None の場合は story_id + _E01 を自動生成
            story_metadata: Story メタデータ dict
            episode_metadata: Episode メタデータ dict
            source_file: 元ファイル名
            source_path: 元ファイルパス
            preserve_stage_directions: 演出命令を保存したか
            commands_config_path: config/script_commands.yaml のパス。
                指定するとcompatibilityReport.newSpeechCommandsが
                scripts/check_script_compatibility.pyと同じ
                new_speech_detection_hintsを使って実際に判定される
                (feature/compatibility-check-consistency)。Noneの場合は
                従来通りnewSpeechCommandsは空配列になる
                (既存呼び出し元・既存テストとの後方互換のため)。
            manifest_source: story_manifest.yaml照合結果 (manifestPath/
                manifestMatched/matchedBy/sourceFileName/rawPath等) を
                source.manifestへ格納する。Noneの場合は既存通り
                sourceにmanifestキー自体を追加しない
                (feature/normalize-story-manifest-integration、既存呼び出し
                元・既存テストとの後方互換のため)。
            variant_trace: H_scene例外変種の動的判定由来のtrace情報
                (baseEpisodeId/variantPattern/dupIndex/judgment等) を
                source.hsceneVariantTraceへ格納する
                (agents/parser/hscene_variant_judgment.py、
                Character_Story_ID_Manifest_Design.md §6.4)。Noneの場合は
                既存通りsourceにhsceneVariantTraceキー自体を追加しない
                (SourceInfoはadditionalProperties: trueのためschema変更
                不要、既存呼び出し元・既存テストとの後方互換のため)。
        """
        self.story_id = story_id
        self.story_category = story_category
        self.episode_id = episode_id or f"{story_id}_E01"
        self.story_metadata = story_metadata or {}
        self.episode_metadata = episode_metadata or {}
        self.source_file = source_file or story_id
        self.source_path = source_path
        self.preserve_stage_directions = preserve_stage_directions
        self.commands_config_path = commands_config_path
        self.manifest_source = manifest_source
        self.variant_trace = variant_trace

    def normalize(
        self, parse_result: ParseResult, line_count: int | None = None
    ) -> dict[str, Any]:
        """ParseResult を Normalized Story JSON の dict へ変換する"""

        episodes_json = self._normalize_episodes(parse_result.episodes)

        # compatibility report
        compat_report = self._build_compatibility_report(parse_result)

        doc: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "documentType": DOCUMENT_TYPE,
            "storyId": self.story_id,
            "storyCategory": self.story_category,
            "metadata": self._build_story_metadata(),
            "parser": self._build_parser_info(),
            "source": self._build_source_info(line_count),
            "compatibilityReport": compat_report,
            "episodes": episodes_json,
        }
        return doc

    # ----------------------------------------------------------------
    # metadata
    # ----------------------------------------------------------------

    def _build_story_metadata(self) -> dict[str, Any]:
        base: dict[str, Any] = {
            "storyTitle": None,
            "displayTitle": None,
            "season": None,
            "chapter": None,
            "displayOrder": None,
            "releaseOrder": None,
            "canonicalOrder": None,
        }
        base.update(self.story_metadata)
        return base

    def _build_parser_info(self) -> dict[str, Any]:
        return {
            "parserName": PARSER_NAME,
            "parserVersion": PARSER_VERSION,
            "parserMode": "game_script",
            "preserveStageDirections": self.preserve_stage_directions,
            "createdAt": datetime.now(tz=timezone.utc).isoformat(),
        }

    def _build_source_info(self, line_count: int | None) -> dict[str, Any]:
        info: dict[str, Any] = {
            "sourceFile": self.source_file,
            "sourcePath": self.source_path,
            "sourceFormat": "game_script",
            "encoding": "utf-8",
            "lineCount": line_count,
        }
        if self.manifest_source is not None:
            info["manifest"] = self.manifest_source
        if self.variant_trace is not None:
            info["hsceneVariantTrace"] = self.variant_trace
        return info

    def _build_compatibility_report(self, parse_result: ParseResult) -> dict[str, Any]:
        # unresolved character IDs (話者スロットとして実消費されたもののみ。
        # 消費文脈ベースの判定はagents/parser/resolver.py
        # SpeakerResolver.unresolved_character_idsで行う。
        # feature/resolver-consumption-context-report、
        # scripts/check_script_compatibility.pyの#141と対称)
        unresolved_ids: list[dict] = []
        for ep in parse_result.episodes:
            for cid in ep.unresolved_character_ids:
                unresolved_ids.append({"sourceCharacterId": cid})

        # 話者スロットとして一度も消費されなかった未登録の数値代入
        # (costume/mo/fa等の非話者引数専用消費・完全未消費のいずれも含む。
        # 「不明情報を破棄しない」不変則により削除ではなく分類として保持する。
        # parserCompatibility判定には一切影響しない、checker側
        # nonSpeakerNumericAssignmentsと対応する情報フィールド)
        non_speaker_numeric_assignments: list[dict] = []
        for ep in parse_result.episodes:
            for cid in ep.non_speaker_numeric_assignment_ids:
                non_speaker_numeric_assignments.append({"sourceCharacterId": cid})

        # ID形式でない (非リテラル) sourceCharacterId文字列
        # ($split(...)等の未評価の関数呼び出し式・座標様の数値列等)。
        # 未登録キャラクターID候補ではないため、unknownCharacterIds/
        # nonSpeakerNumericAssignmentsとは別の情報フィールドとして保持する
        # (feature/non-literal-character-id-handling、
        # Character_Story_ID_Manifest_Design.md §9.1.2発見③)。
        non_literal_speaker_expressions: list[dict] = []
        for ep in parse_result.episodes:
            for cid, consumed_as_speaker in ep.non_literal_speaker_expressions.items():
                non_literal_speaker_expressions.append(
                    {
                        "sourceCharacterId": cid,
                        "consumedAsSpeaker": consumed_as_speaker,
                    }
                )

        # unknown commands
        unknown_cmds: list[dict] = []
        for cmd, count in parse_result.unknown_commands.items():
            unknown_cmds.append({"command": cmd, "count": count})

        # 新規会話コマンド候補
        # (config/script_commands.yamlのnew_speech_detection_hintsを使い、
        # scripts/check_script_compatibility.pyと同じ判定を行う。
        # commands_config_path未指定時は従来通り空配列のまま
        # = 既存呼び出し元・既存テストとの後方互換)
        new_speech_cmds: list[dict] = []
        if self.commands_config_path is not None:
            config = load_command_config(self.commands_config_path)
            hints = get_new_speech_hints(config)
            new_speech_cmds = detect_new_speech_commands(
                parse_result.unknown_commands, hints
            )

        # 互換性ステータス決定
        # (agents/parser/compatibility.pyのdetermine_compatibility_statusを
        # scripts/check_script_compatibility.pyと共有。StoryParserは
        # branch_issues (孤立#elseif等) やcase_variants使用箇所を追跡
        # していないため、has_critical_branch_issue/
        # has_high_severity_branch_issue/has_case_variantsは常にFalseで
        # 呼び出す — 両経路の既知の非対称性、TASKS.md参照)
        compat = determine_compatibility_status(
            has_new_speech_commands=bool(new_speech_cmds),
            has_unknown_commands=bool(unknown_cmds),
            has_unknown_character_ids=bool(unresolved_ids),
            has_control_chars_removed=parse_result.control_chars_removed > 0,
        )

        return {
            "parserCompatibility": compat,
            "unknownCommands": unknown_cmds,
            "newSpeechCommands": new_speech_cmds,
            "unknownCharacterIds": unresolved_ids,
            "nonSpeakerNumericAssignments": non_speaker_numeric_assignments,
            "nonLiteralSpeakerExpressions": non_literal_speaker_expressions,
            "controlCharsRemoved": parse_result.control_chars_removed,
        }

    # ----------------------------------------------------------------
    # Episodes
    # ----------------------------------------------------------------

    def _normalize_episodes(self, episodes: list[EpisodeData]) -> list[dict]:
        results = []
        for ep_number, episode in enumerate(episodes, start=1):
            ep_id = (
                self.episode_id
                if ep_number == 1
                else f"{self.story_id}_E{ep_number:02d}"
            )
            results.append(self._normalize_episode(episode, ep_id, ep_number))
        return results

    def _normalize_episode(
        self,
        episode: EpisodeData,
        episode_id: str,
        episode_number: int,
    ) -> dict[str, Any]:
        id_gen = IdGenerator(episode_id)

        # speaker assignments
        assignments_json = [rec.to_dict() for rec in episode.speaker_assignments]

        # scenes
        scenes_json = [self._normalize_scene(scene, id_gen) for scene in episode.scenes]

        ep_meta: dict[str, Any] = {
            "episodeTitle": None,
            "episodeSubtitle": None,
            "displayTitle": None,
            "sortKey": episode_id,
        }
        ep_meta.update(self.episode_metadata)

        return {
            "episodeId": episode_id,
            "episodeNumber": episode_number,
            "metadata": ep_meta,
            "speakerAssignments": assignments_json,
            "scenes": scenes_json,
        }

    # ----------------------------------------------------------------
    # Scenes
    # ----------------------------------------------------------------

    def _normalize_scene(self, scene: SceneData, id_gen: IdGenerator) -> dict[str, Any]:
        scene_id = id_gen.next_scene_id()

        blocks_json = [self._normalize_block(block, id_gen) for block in scene.blocks]

        location: dict[str, Any] = {
            "locationId": None,
            "locationName": scene.location_name,
        }

        return {
            "sceneId": scene_id,
            "sceneNumber": scene.scene_number,
            "location": location,
            "blocks": blocks_json,
        }

    # ----------------------------------------------------------------
    # Blocks
    # ----------------------------------------------------------------

    def _normalize_block(self, block: BlockData, id_gen: IdGenerator) -> dict[str, Any]:
        block_id = id_gen.next_block_id(block.block_type)
        source = self._build_block_source(block)

        if block.block_type in {"dialogue", "monologue"}:
            return self._normalize_speech_block(block, block_id, source)
        elif block.block_type == "narration":
            return self._normalize_narration_block(block, block_id, source)
        elif block.block_type == "choice":
            return self._normalize_choice_block(block, block_id, source, id_gen)
        elif block.block_type == "stage_direction":
            return self._normalize_stage_direction_block(block, block_id, source)
        else:
            return self._normalize_unknown_block(block, block_id, source)

    def _normalize_speech_block(
        self,
        block: BlockData,
        block_id: str,
        source: dict,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": block_id,
            "type": block.block_type,
            "source": source,
        }

        if block.speaker is not None:
            result["speaker"] = block.speaker.to_dict()

        if block.has_voice is not None:
            result["voice"] = {"hasVoice": block.has_voice}
        else:
            result["voice"] = {"hasVoice": None}

        if block.text is not None:
            result["text"] = block.text
        if block.raw_text is not None:
            result["rawText"] = block.raw_text

        if block.notes:
            result["notes"] = block.notes

        return result

    def _normalize_narration_block(
        self,
        block: BlockData,
        block_id: str,
        source: dict,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": block_id,
            "type": "narration",
            "source": source,
        }
        if block.text is not None:
            result["text"] = block.text
        if block.raw_text is not None:
            result["rawText"] = block.raw_text
        if block.narration_type is not None:
            result["narrationType"] = block.narration_type
        if block.notes:
            result["notes"] = block.notes
        return result

    def _normalize_choice_block(
        self,
        block: BlockData,
        block_id: str,
        source: dict,
        id_gen: IdGenerator,
    ) -> dict[str, Any]:
        options_json = []
        for i, opt in enumerate(block.options, start=1):
            opt_id = id_gen.next_choice_option_id(block_id, i)
            inner_blocks = [
                self._normalize_block(b, id_gen) for b in opt.get("blocks", [])
            ]
            options_json.append(
                {
                    "optionId": opt_id,
                    "optionText": opt.get("optionText", ""),
                    "blocks": inner_blocks,
                }
            )

        return {
            "id": block_id,
            "type": "choice",
            "choiceText": block.choice_text,
            "options": options_json,
            "source": source,
        }

    def _normalize_stage_direction_block(
        self,
        block: BlockData,
        block_id: str,
        source: dict,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": block_id,
            "type": "stage_direction",
            "source": source,
        }
        if block.direction_type is not None:
            result["directionType"] = block.direction_type
        if block.raw_command is not None:
            result["rawCommand"] = block.raw_command
        if block.normalized_command is not None:
            result["normalizedCommand"] = block.normalized_command
        if block.command_args:
            result["args"] = block.command_args
        if block.raw_text is not None:
            result["raw"] = block.raw_text
        if block.notes:
            result["notes"] = block.notes
        return result

    def _normalize_unknown_block(
        self,
        block: BlockData,
        block_id: str,
        source: dict,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": block_id,
            "type": "unknown",
            "source": source,
        }
        if block.raw_text is not None:
            result["rawText"] = block.raw_text
        if block.text is not None:
            result["text"] = block.text
        result["notes"] = block.notes or ["Parser could not classify this line."]
        return result

    def _build_block_source(self, block: BlockData) -> dict[str, Any]:
        source: dict[str, Any] = {}
        if block.source_file is not None:
            source["sourceFile"] = block.source_file
        if block.line_start is not None:
            source["lineStart"] = block.line_start
        if block.line_end is not None:
            source["lineEnd"] = block.line_end
        if block.raw_line is not None:
            source["raw"] = block.raw_line
        if block.parser_rule is not None:
            source["parserRule"] = block.parser_rule
        if block.confidence is not None:
            source["confidence"] = block.confidence
        return source
