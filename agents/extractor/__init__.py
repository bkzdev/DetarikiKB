"""
DKB Extractor Package

Usage:
    from agents.extractor import Extractor

Normalized Story JSONからExtraction Phase Stage A (episode_extraction) の
最小構造を生成する。Character/Location/Organization/Item/Lore/Event/
Relationship/Timeline の8種のCandidateを、構造的な手がかりのみからrule-baseで
抽出する (本文の自然文推定は行わない)。LLM呼び出し・OpenAI/Anthropic/Ollama
連携・prompt作成はまだ実装しない。

docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
"""

from .extractor import Extractor
from .models import (
    DOCUMENT_TYPE,
    EXTRACTOR_VERSION,
    SCHEMA_VERSION,
    EvidenceRef,
    ExtractionRunInfo,
)
from .validator import (
    SemanticValidationIssue,
    has_errors,
    run_semantic_validation,
)

__all__ = [
    "Extractor",
    "EvidenceRef",
    "ExtractionRunInfo",
    "SCHEMA_VERSION",
    "DOCUMENT_TYPE",
    "EXTRACTOR_VERSION",
    "SemanticValidationIssue",
    "run_semantic_validation",
    "has_errors",
]
