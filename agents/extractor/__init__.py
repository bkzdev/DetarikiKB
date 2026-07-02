"""
DKB Extractor Package

Usage:
    from agents.extractor import Extractor

Normalized Story JSONからExtraction Phase Stage A (episode_extraction) の
最小構造を生成する。LLM呼び出し・OpenAI/Anthropic/Ollama連携・prompt作成は
まだ実装しない (候補配列は空のまま出力する)。

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

__all__ = [
    "Extractor",
    "EvidenceRef",
    "ExtractionRunInfo",
    "SCHEMA_VERSION",
    "DOCUMENT_TYPE",
    "EXTRACTOR_VERSION",
]
