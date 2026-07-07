"""
tests/scripts/test_evidence_index_generation_dry_run_docs.py
Evidence Index Generation Dry-Run手順
(docs/runbooks/Evidence_Index_Generation_Dry_Run.md) と .gitignore の
軽量な整合性テスト。

Evidence Index候補生成dry-run出力をcommitしないルールが.gitignoreへ
機械的に反映されていること、手順書に必須セクション・raw text非表示方針・
workspace出力方針・commit禁止方針が明記されていること、TASKS.mdに次PR
候補が記録されていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Evidence_Index_Generation_Dry_Run.md"
)
EVIDENCE_INDEX_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Evidence_Index_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"

REQUIRED_RUNBOOK_SECTIONS = (
    "Purpose",
    "前提",
    "スコープ",
    "raw text非表示の実装方針",
    "evidenceId方針",
    "実行手順",
    "Evidence Indexへの昇格",
    "source text exposure check",
    "commit前チェックリスト",
)


def _read_runbook() -> str:
    return RUNBOOK_PATH.read_text(encoding="utf-8")


def test_gitignore_contains_evidence_index_dry_run_pattern():
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    assert "workspace/evidence_index_dry_runs/" in content


def test_runbook_exists():
    assert RUNBOOK_PATH.exists(), f"{RUNBOOK_PATH} が存在しません"


def test_runbook_contains_required_sections():
    content = _read_runbook()
    missing = [s for s in REQUIRED_RUNBOOK_SECTIONS if s not in content]
    assert not missing, f"不足しているセクション: {missing}"


def test_runbook_states_no_commit_policy():
    content = _read_runbook()
    assert "実データ・生成物は一切Gitにcommitしない" in content


def test_runbook_states_raw_text_exclusion_fields():
    content = _read_runbook()
    for field_name in ("text", "rawText", "raw", "rawCommand", "args"):
        assert f"`{field_name}`" in content


def test_runbook_states_workspace_only_output():
    content = _read_runbook()
    assert "workspace/evidence_index_dry_runs/" in content
    assert "knowledge/evidence/stories/" in content


def test_runbook_states_evidence_id_skip_policy():
    content = _read_runbook()
    assert "missing_block_id" in content
    assert "新しいID生成ルールはこのスクリプトで追加しない" in content


def test_runbook_references_actual_script_name():
    content = _read_runbook()
    assert "build_evidence_index_candidates.py" in content
    assert "validate_evidence_index.py" in content
    assert "render_wiki.py" in content


def test_runbook_does_not_promote_to_knowledge_directory():
    content = _read_runbook()
    promotion_section = content.split("# 7. ", 1)[1].split("# 8. ", 1)[0]
    assert "本ドキュメントでは行わない" in content.split("# 7. ", 1)[0] or (
        "本ドキュメントでは行わない" in promotion_section
    )


def test_evidence_index_design_links_to_runbook():
    content = EVIDENCE_INDEX_DESIGN_PATH.read_text(encoding="utf-8")
    assert "Evidence_Index_Generation_Dry_Run.md" in content


def test_tasks_md_lists_next_pr_candidates():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "evidence-index-generation-review" in content
    assert "evidence-index-promotion-policy" in content
    assert "internal-review-evidence-packet-design" in content
