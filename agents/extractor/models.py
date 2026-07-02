"""
DKB Extractor - Models
Extraction Phase Stage A (episode_extraction) の出力に使う定数・データ構造。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCHEMA_VERSION = "0.1"
DOCUMENT_TYPE = "episode_extraction"
EXTRACTOR_VERSION = "0.1.0"

# Extraction_Pipeline.md §5.4: 抽出対象として直接読むBlock種別
# (stage_directionは補助的手がかりに留め、unknownは対象外)
EVIDENCE_BLOCK_TYPES = frozenset({"dialogue", "monologue", "narration", "choice"})

# BlockのsourceにconfidenceがないときのEvidenceRef既定値
DEFAULT_EVIDENCE_CONFIDENCE = 1.0


@dataclass
class ExtractionRunInfo:
    """extractionRun (Extraction_Result_Schema.md §3.2)。

    LLM呼び出しはまだ実装していないため、model_provider/model_name/
    prompt_version/extracted_at は常にNoneのまま出力する。
    """

    parser_compatibility_at_extraction: str
    extraction_version: str = EXTRACTOR_VERSION
    extraction_method: str = "llm"
    model_provider: str | None = None
    model_name: str | None = None
    prompt_version: str | None = None
    extracted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "extractionVersion": self.extraction_version,
            "extractionMethod": self.extraction_method,
            "modelProvider": self.model_provider,
            "modelName": self.model_name,
            "promptVersion": self.prompt_version,
            "extractedAt": self.extracted_at,
            "parserCompatibilityAtExtraction": self.parser_compatibility_at_extraction,
        }


@dataclass
class EvidenceRef:
    """EvidenceRef (Extraction_Result_Schema.md §5.1)。evidenceIndexの1エントリ。"""

    source_id: str
    story_id: str
    episode_id: str
    scene_id: str | None
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "sourceId": self.source_id,
            "storyId": self.story_id,
            "episodeId": self.episode_id,
            "sceneId": self.scene_id,
            "confidence": self.confidence,
        }
