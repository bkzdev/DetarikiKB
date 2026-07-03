"""
DKB Merger - Merge Engine Skeleton
検証済みのStage A episode_extractionから、Stage B merged knowledge
collectionの最小構造とmerge report骨格を組み立てる。

今回はskeletonのため、単一入力ファイルのみを対象とし、本格的な
candidate merge・canonical ID割り当て・manual override適用・
conflict解決・relationship merge・timeline aggregationは行わない。
entities配下の8配列は空のまま出力し、reportに入力集計だけを記録する。
複数ファイル・ディレクトリ入力は将来の拡張とする。

merge前には必ず検証ゲートを通す (Merged_Knowledge_Design.md §2.2)。
- schemas/extraction.schema.json によるJSON Schema検証
- agents/extractor/validator.py によるsemantic validation
どちらかに失敗した入力はmerge対象にしない。

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

from .models import (
    CANDIDATE_ARRAY_KEYS,
    COLLECTION_DOCUMENT_TYPE,
    COLLECTION_SCHEMA_VERSION,
    MERGED_ENTITY_KEYS,
    MergeReport,
)

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
    """Stage A episode_extraction (単一ファイル) からmerged knowledge
    collectionを生成する。
    """

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
        """単一の入力ファイルを検証し、merged knowledge collectionを組み立てる

        validationに失敗した場合も、reportにinvalidInputs/skippedInputs/
        errorsを記録したcollectionを返す (壊れた入力を黙って取り込まず、
        かつ処理自体はクラッシュさせない)。
        """
        result = self.validate_file(path)
        report = MergeReport(input_files=1)
        valid_documents: list[dict[str, Any]] = []

        if result.is_valid:
            report.valid_inputs = 1
            assert result.document is not None
            valid_documents.append(result.document)
            for issue in result.semantic_warnings:
                report.warnings.append(f"{result.source}: {issue.format()}")
        else:
            report.invalid_inputs = 1
            report.skipped_inputs.append(result.source)
            if result.load_error is not None:
                report.errors.append(
                    f"{result.source}: load failed: {result.load_error}"
                )
            for message in result.schema_errors:
                report.errors.append(f"{result.source}: schema: {message}")
            for issue in result.semantic_errors:
                report.errors.append(f"{result.source}: {issue.format()}")

        return self.build_collection(valid_documents, report)

    def build_collection(
        self,
        documents: list[dict[str, Any]],
        report: MergeReport,
    ) -> dict[str, Any]:
        """検証済みdocument群からcollection構造を組み立てる

        skeletonのため本格mergeはせず、candidate件数の集計と
        sourceDocumentsの記録のみを行う。entities配下は空配列。
        """
        source_documents: list[dict[str, Any]] = []
        for document in documents:
            source_documents.append(
                {
                    "episodeId": document.get("episodeId"),
                    "storyId": document.get("storyId"),
                    "storyCategory": document.get("storyCategory"),
                }
            )
            for key in CANDIDATE_ARRAY_KEYS:
                report.candidate_counts[key] += len(document.get(key, []) or [])

        return {
            "schemaVersion": COLLECTION_SCHEMA_VERSION,
            "documentType": COLLECTION_DOCUMENT_TYPE,
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "sourceDocuments": source_documents,
            "entities": {key: [] for key in MERGED_ENTITY_KEYS},
            "report": report.to_dict(),
        }
