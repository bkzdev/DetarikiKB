"""
tests/docs/test_project_context_compaction.py
AI_CONTEXT.md / TASKS.md の圧縮・project_history分離構成の軽量な整合性テスト。

実装・schema・workflowの挙動は一切変更していない (docs-only PR) ため、
ここでは構造・重要方針の残存確認のみを行う。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
AI_CONTEXT_PATH = PROJECT_ROOT / "AI_CONTEXT.md"
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
PROJECT_HISTORY_PATH = (
    PROJECT_ROOT / "docs" / "project_history" / "Completed_PRs_2026-07.md"
)


def test_ai_context_exists():
    assert AI_CONTEXT_PATH.is_file()


def test_tasks_exists():
    assert TASKS_PATH.is_file()


def test_project_history_exists():
    assert PROJECT_HISTORY_PATH.is_file()


def test_ai_context_is_compact():
    lines = AI_CONTEXT_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 250, (
        f"AI_CONTEXT.md が {len(lines)} 行あります。詳細は "
        "docs/project_history/ や docs/architecture/ へ移してください。"
    )


def test_tasks_is_reasonably_sized():
    lines = TASKS_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 400, (
        f"TASKS.md が {len(lines)} 行あります。完了済み履歴は "
        "docs/project_history/ へ移してください。"
    )


def test_ai_context_retains_source_of_truth_policy():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    assert "Source of Truth" in content


def test_ai_context_retains_no_real_data_commit_policy():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    assert "実データ" in content
    assert "commit" in content


def test_ai_context_retains_key_policies():
    """canonical ID / character dictionary / character profile /
    story manifest / title-subtitle / raw script方針が要約として
    残っていることを確認する (詳細docsへのリンクのみに削られていないか)。"""
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    for keyword in (
        "canonicalId",
        "characters.yaml",
        "character_profiles.yaml",
        "story_manifest.yaml",
        "title/subtitle",
        "Raw Script",
    ):
        assert keyword in content, f"AI_CONTEXT.md に '{keyword}' が見つかりません"


def test_ai_context_links_to_project_history_and_tasks():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    assert "docs/project_history/Completed_PRs_2026-07.md" in content
    assert "TASKS.md" in content


def test_tasks_has_expected_sections():
    content = TASKS_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Current Focus",
        "## Next",
        "## Backlog",
        "## Known Issues",
        "## Recently Completed",
        "## Archive",
    ):
        assert heading in content, f"TASKS.md に '{heading}' セクションがありません"


def test_tasks_links_to_project_history():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "docs/project_history/Completed_PRs_2026-07.md" in content


def test_tasks_retains_rules_section():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "## Rules" in content
    assert "実スクリプト全文" in content
    assert "APIキーをcommitしない" in content


def test_project_history_covers_recent_prs():
    content = PROJECT_HISTORY_PATH.read_text(encoding="utf-8")
    for pr_marker in ("PR #56", "PR #57", "PR #58", "PR #59", "PR #60"):
        assert pr_marker in content, f"{pr_marker} の記載が見つかりません"


def test_project_history_has_category_sections():
    content = PROJECT_HISTORY_PATH.read_text(encoding="utf-8")
    for heading in (
        "## Parser / Normalization",
        "## Extraction / Merge",
        "## Character Dictionary / Profiles",
        "## Wiki / MkDocs",
        "## Quality / CI / Refactor",
    ):
        assert heading in content, f"project_historyに '{heading}' がありません"
