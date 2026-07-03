"""
DKB Merger - Merge Engine Skeleton
検証済みのStage A episode_extraction群から、Stage B merged knowledge
collectionの最小構造とmerge report骨格を組み立てる。

今回はskeletonのため、本格的なcandidate merge・canonical ID割り当て・
manual override適用・conflict解決・relationship merge・timeline
aggregationは行わない。entities配下の8配列は空のまま出力し、reportに
入力集計だけを記録する。

入力は複数ファイル・ディレクトリ・globパターン文字列に対応する
(input_resolver.pyが解決を担う)。merge前には必ず検証ゲートを通す
(Merged_Knowledge_Design.md §2.2)。
- schemas/extraction.schema.json によるJSON Schema検証
- agents/extractor/validator.py によるsemantic validation
どちらかに失敗した入力はmerge対象にしない。1件も解決できなかった
raw引数は"skipped"として区別し、検証には失敗したが読み込めた入力は
"invalid"として区別する。

出力するcollection wrapperはmerge engineのpreview用であり、個別のmerged
entityは将来 schemas/merged_knowledge.schema.json に従う (collection
wrapper自体のschema化は将来検討。TASKS.md参照)。

docs/architecture/06_AI/Merged_Knowledge_Design.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from agents.extractor.validator import SemanticValidationIssue, run_semantic_validation

from .character import build_character_entities
from .event import build_event_entities
from .input_resolver import resolve_input_entries
from .item import build_item_entities
from .location import build_location_entities
from .lore import build_lore_entities
from .models import (
    CANDIDATE_ARRAY_KEYS,
    COLLECTION_DOCUMENT_TYPE,
    COLLECTION_SCHEMA_VERSION,
    INPUT_STATUS_INVALID,
    INPUT_STATUS_SKIPPED,
    INPUT_STATUS_VALID,
    MERGED_ENTITY_KEYS,
    InputResult,
    MergeReport,
)
from .organization import build_organization_entities
from .relationship import build_relationship_entities

_PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_EXTRACTION_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "extraction.schema.json"


@dataclass
class InputValidationResult:
    """1入力ドキュメントの検証結果。"""

    source: str
    document: dict[str, Any] | None = None
    schema_errors: list[str] = field(default_factory=list)
    semantic_errors: list[SemanticValidationIssue] = field(default_factory=list)
    semantic_warnings: list[SemanticValidationIssue] = field(default_factory=list)
    load_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return (
            self.load_error is None
            and not self.schema_errors
            and not self.semantic_errors
        )


class MergeEngine:
    """Stage A episode_extraction群からmerged knowledge collectionを生成する。"""

    def __init__(
        self, extraction_schema_path: Path = DEFAULT_EXTRACTION_SCHEMA_PATH
    ) -> None:
        with open(extraction_schema_path, encoding="utf-8") as f:
            schema = json.load(f)
        self._schema_validator = Draft7Validator(schema)

    def validate_document(
        self, document: dict[str, Any], source: str
    ) -> InputValidationResult:
        """episode_extraction dict をJSON Schema + semantic validationで検証する

        検証ゲート (Merged_Knowledge_Design.md §2.2): schema検証に失敗した
        入力へsemantic validationを重ねてもノイズが増えるだけのため、
        schemaが通ったものだけを対象にする。
        """
        result = InputValidationResult(source=source, document=document)

        schema_errors = sorted(
            self._schema_validator.iter_errors(document), key=lambda e: list(e.path)
        )
        result.schema_errors = [
            f"{'/'.join(str(p) for p in err.path) or '(root)'}: {err.message}"
            for err in schema_errors
        ]

        if not result.schema_errors:
            issues = run_semantic_validation(document)
            result.semantic_errors = [i for i in issues if i.severity == "error"]
            result.semantic_warnings = [i for i in issues if i.severity == "warning"]

        return result

    def validate_file(self, path: Path) -> InputValidationResult:
        """episode_extractionファイルを読み込んで検証する"""
        try:
            with open(path, encoding="utf-8") as f:
                document = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            return InputValidationResult(source=str(path), load_error=str(e))

        return self.validate_document(document, source=str(path))

    def merge_file(self, path: Path) -> dict[str, Any]:
        """単一ファイルパスをmerge対象とする (merge_inputsへの薄いラッパー)。"""
        return self.merge_inputs([str(path)])

    def merge_inputs(
        self, inputs: list[str], recursive: bool = False
    ) -> dict[str, Any]:
        """複数の--input引数 (file/directory/globパターン文字列) を解決・
        検証し、merged knowledge collectionを組み立てる

        解決できなかった (存在しない・0件マッチの) raw引数はinputResultsへ
        status: "skipped" として、解決はできたがvalidationに失敗した
        ファイルはstatus: "invalid" として、それぞれ記録する。
        いずれも黙って無視しない (Merged_Knowledge_Design.md §2.2)。
        """
        entries = resolve_input_entries(inputs, recursive=recursive)

        report = MergeReport(input_files=len(inputs))
        valid_entries: list[tuple[str, dict[str, Any]]] = []

        for entry in entries:
            if entry.path is None:
                report.skipped_inputs.append(entry.raw)
                warning = f"入力を解決できませんでした: {entry.raw}"
                report.warnings.append(warning)
                report.input_results.append(
                    InputResult(
                        path=entry.raw,
                        status=INPUT_STATUS_SKIPPED,
                        warnings=[warning],
                    )
                )
                continue

            report.resolved_input_files += 1
            result = self.validate_file(entry.path)

            if result.is_valid:
                report.valid_inputs += 1
                assert result.document is not None
                valid_entries.append((result.source, result.document))
                warnings = [issue.format() for issue in result.semantic_warnings]
                for warning in warnings:
                    report.warnings.append(f"{result.source}: {warning}")
                report.input_results.append(
                    InputResult(
                        path=result.source,
                        status=INPUT_STATUS_VALID,
                        warnings=warnings,
                    )
                )
            else:
                report.invalid_inputs += 1
                errors: list[str] = []
                if result.load_error is not None:
                    errors.append(f"load failed: {result.load_error}")
                errors.extend(f"schema: {m}" for m in result.schema_errors)
                errors.extend(issue.format() for issue in result.semantic_errors)
                for message in errors:
                    report.errors.append(f"{result.source}: {message}")
                report.input_results.append(
                    InputResult(
                        path=result.source, status=INPUT_STATUS_INVALID, errors=errors
                    )
                )

        return self.build_collection(valid_entries, report)

    def build_collection(
        self,
        valid_entries: list[tuple[str, dict[str, Any]]],
        report: MergeReport,
    ) -> dict[str, Any]:
        """検証済み (path, document) 群からcollection構造を組み立てる

        candidate件数の集計 (全valid input合算) とsourceDocumentsの記録に
        加え、Character/Location/Organization/Item/Lore/Event/Relationship
        のみ最小ルールでmerged entityへ変換する (Merged_Knowledge_Design.md
        §5.1〜§5.6, §6)。Timelineは今回もentities配下を空配列のままにする
        (本格実装は別PR)。
        """
        source_documents: list[dict[str, Any]] = []
        for path, document in valid_entries:
            doc_candidate_counts = {
                key: len(document.get(key, []) or []) for key in CANDIDATE_ARRAY_KEYS
            }
            for key, count in doc_candidate_counts.items():
                report.candidate_counts[key] += count

            extraction_run = document.get("extractionRun") or {}
            source_documents.append(
                {
                    "path": path,
                    "documentId": document.get("episodeId"),
                    "storyId": document.get("storyId"),
                    "storyCategory": document.get("storyCategory"),
                    "episodeId": document.get("episodeId"),
                    "extractionVersion": extraction_run.get("extractionVersion"),
                    "candidateCounts": doc_candidate_counts,
                }
            )

        entities: dict[str, list[dict[str, Any]]] = {
            key: [] for key in MERGED_ENTITY_KEYS
        }
        entities["characters"] = build_character_entities(valid_entries)
        entities["locations"] = build_location_entities(valid_entries)
        entities["organizations"] = build_organization_entities(valid_entries)
        entities["items"] = build_item_entities(valid_entries)
        entities["lore"] = build_lore_entities(valid_entries)
        entities["events"] = build_event_entities(valid_entries)

        known_entities = [
            *entities["characters"],
            *entities["locations"],
            *entities["organizations"],
            *entities["items"],
            *entities["lore"],
            *entities["events"],
        ]
        relationship_entities, relationship_warnings = build_relationship_entities(
            valid_entries, known_entities
        )
        entities["relationships"] = relationship_entities
        report.warnings.extend(relationship_warnings)

        for key, values in entities.items():
            report.merged_entity_counts[key] = len(values)
            for entity in values:
                report.conflicts_count += len(entity.get("conflicts", []))
                if entity.get("status") == "unresolved":
                    report.unresolved_count += 1

        return {
            "schemaVersion": COLLECTION_SCHEMA_VERSION,
            "documentType": COLLECTION_DOCUMENT_TYPE,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceDocuments": source_documents,
            "entities": entities,
            "report": report.to_dict(),
        }
