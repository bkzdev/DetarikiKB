"""
tests/docs/test_ai_pr_playbook_docs.py
AI PR Playbook (docs/runbooks/AI_PR_Playbook.md) に関するdocsの
軽量な整合性テスト。

PRワークフロー・PR種別プリセット・匿名化ルール・標準検証コマンド・
commit禁止リスト・恒常Non-goals・最終報告テンプレートが文書化されて
いること、AI_CONTEXT.mdからのリンク、実データヒントが含まれていない
ことを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PLAYBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "AI_PR_Playbook.md"
AI_CONTEXT_PATH = PROJECT_ROOT / "AI_CONTEXT.md"

REQUIRED_SECTIONS = (
    "# 1. 目的",
    "# 2. 使い方",
    "# 3. PRワークフロー",
    "# 4. PR種別プリセットと許容差分",
    "# 5. 匿名化ルール",
    "# 6. 標準検証コマンド",
    "# 7. Commit禁止リスト",
    "# 8. 恒常Non-goals",
    "# 9. 最終報告テンプレート",
    "# 10. 関連ドキュメント",
)

REAL_DATA_HINTS = (
    "CAMI3RD",
    "260425",
    "260707",
    "260624",
    "260504",
    "CAB-csl",
)


def _read_doc() -> str:
    return PLAYBOOK_PATH.read_text(encoding="utf-8")


def test_playbook_exists():
    assert PLAYBOOK_PATH.is_file()


def test_playbook_has_required_sections():
    content = _read_doc()
    missing = [s for s in REQUIRED_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_playbook_states_declares_summary_only_prompts():
    content = _read_doc()
    section = content.split("# 2. 使い方", 1)[1].split("# 3. PRワークフロー", 1)[0]
    assert "PR種別" in section
    assert "Non-goals" in section


def test_playbook_states_workflow_steps():
    content = _read_doc()
    section = content.split("# 3. PRワークフロー", 1)[1].split(
        "# 4. PR種別プリセットと許容差分", 1
    )[0]
    assert "squash" in section.lower()
    assert "git pull origin main" in section
    assert "gh pr create" in section
    assert "CI" in section


def test_playbook_states_pr_type_presets():
    content = _read_doc()
    section = content.split("# 4. PR種別プリセットと許容差分", 1)[1].split(
        "# 5. 匿名化ルール", 1
    )[0]
    for preset in ("docs-only PR", "実装PR", "dry-run PR"):
        assert preset in section
    assert "TASKS.md" in section
    assert "AI_CONTEXT.md" in section


def test_playbook_states_anonymization_rules():
    content = _read_doc()
    section = content.split("# 5. 匿名化ルール", 1)[1].split(
        "# 6. 標準検証コマンド", 1
    )[0]
    assert "sourceKey" in section
    assert "REAL_DATA_HINTS" in section


def test_playbook_states_standard_verification_commands():
    content = _read_doc()
    section = content.split("# 6. 標準検証コマンド", 1)[1].split(
        "# 7. Commit禁止リスト", 1
    )[0]
    for cmd in (
        "uv run pytest",
        "check_invisible_unicode.py",
        "check_dry_run_inputs.py",
        "ruff format",
        "ruff check",
        "mkdocs build --strict",
    ):
        assert cmd in section


def test_playbook_states_commit_forbidden_list():
    content = _read_doc()
    section = content.split("# 7. Commit禁止リスト", 1)[1].split(
        "# 8. 恒常Non-goals", 1
    )[0]
    for item in (
        "実`.dec`",
        "story_manifest.yaml",
        "workspace/dry_runs/",
        "workspace/evidence_index_dry_runs/",
        ".env",
    ):
        assert item in section


def test_playbook_states_standing_non_goals():
    content = _read_doc()
    section = content.split("# 8. 恒常Non-goals", 1)[1].split(
        "# 9. 最終報告テンプレート", 1
    )[0]
    for item in (
        "自動昇格",
        "promote_evidence_index.py --execute",
        "schema",
        "Jinja2",
        "Knowledge Graph生成",
    ):
        assert item in section


def test_playbook_states_final_report_template():
    content = _read_doc()
    section = content.split("# 9. 最終報告テンプレート", 1)[1].split(
        "# 10. 関連ドキュメント", 1
    )[0]
    assert "git diff --stat" in section
    assert "CI" in section
    assert "次に着手する" in section


def test_playbook_does_not_contain_real_data_hints():
    content = _read_doc()
    for forbidden in REAL_DATA_HINTS:
        assert forbidden not in content


def test_ai_context_links_to_playbook():
    content = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    assert "AI_PR_Playbook.md" in content
