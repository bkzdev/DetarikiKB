"""
tests/summarizer/test_domain_context.py
agents/summarizer/domain_context.py (`knowledge/dictionaries/
summary_domain_context.yaml`相当のYAMLファイル読み込み) のテスト。

合成fixtureのみを一時ファイルとして生成して使う。実データ・実データ由来の
ドメイン知識文言は一切含まない (`docs/runbooks/AI_PR_Playbook.md` §5)。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from agents.summarizer.domain_context import (
    DEFAULT_DOMAIN_CONTEXT_PATH,
    load_domain_context,
)


def _write_yaml(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True)
    return path


def test_default_domain_context_path_points_under_knowledge_dictionaries():
    assert DEFAULT_DOMAIN_CONTEXT_PATH.parts[-3:] == (
        "knowledge",
        "dictionaries",
        "summary_domain_context.yaml",
    )


def test_load_domain_context_missing_file_returns_empty_list(tmp_path):
    assert load_domain_context(tmp_path / "does_not_exist.yaml") == []


def test_load_domain_context_empty_file_returns_empty_list(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_domain_context(path) == []


def test_load_domain_context_no_entries_key_returns_empty_list(tmp_path):
    path = _write_yaml(tmp_path / "no_entries.yaml", {"schemaVersion": "0.1"})
    assert load_domain_context(path) == []


def test_load_domain_context_empty_entries_list_returns_empty_list(tmp_path):
    path = _write_yaml(tmp_path / "empty_entries.yaml", {"entries": []})
    assert load_domain_context(path) == []


def test_load_domain_context_returns_texts_in_order(tmp_path):
    path = _write_yaml(
        tmp_path / "context.yaml",
        {
            "entries": [
                {"id": "fact-a", "text": "合成事実A"},
                {"id": "fact-b", "text": "合成事実B"},
            ]
        },
    )
    assert load_domain_context(path) == ["合成事実A", "合成事実B"]


def test_load_domain_context_normalizes_folded_newlines_to_single_space(tmp_path):
    # YAML `>-` 折り返しをsafe_loadした結果は改行を含むことがあるため、
    # 単一の半角スペースへ正規化されることを確認する。
    path = _write_yaml(
        tmp_path / "folded.yaml",
        {"entries": [{"id": "fact-a", "text": "合成事実A\n続きの行B"}]},
    )
    assert load_domain_context(path) == ["合成事実A 続きの行B"]


def test_load_domain_context_skips_blank_or_whitespace_only_text(tmp_path):
    path = _write_yaml(
        tmp_path / "blank.yaml",
        {
            "entries": [
                {"id": "fact-a", "text": "合成事実A"},
                {"id": "fact-blank", "text": "   "},
                {"id": "fact-missing-text"},
            ]
        },
    )
    assert load_domain_context(path) == ["合成事実A"]


def test_load_domain_context_skips_non_dict_entries(tmp_path):
    path = _write_yaml(
        tmp_path / "mixed.yaml",
        {"entries": ["not-a-dict", {"id": "fact-a", "text": "合成事実A"}]},
    )
    assert load_domain_context(path) == ["合成事実A"]


def test_load_domain_context_default_path_is_valid_when_committed_file_exists():
    # 実プロジェクトのknowledge/dictionaries/summary_domain_context.yaml
    # (commit対象) を読み込めること自体を確認する (実データ由来の文言の内容
    # までは検証しない、ファイル形式の健全性のみ)。
    result = load_domain_context()
    assert isinstance(result, list)
    assert all(isinstance(item, str) for item in result)


if __name__ == "__main__":
    import pytest

    pytest.main([__file__])
