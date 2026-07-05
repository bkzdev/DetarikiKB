"""
tests/docs/test_mkdocs_local_preview_dry_run_docs.py
MkDocs local preview dry-run手順
(docs/runbooks/MkDocs_Local_Preview_Dry_Run.md・
docs/templates/mkdocs_local_preview_result_template.md) の軽量な
整合性テスト。

実キャラ名・実タイトル・実URLが含まれていないこと、実データ生成物を
commitしない方針・目視確認が別途必要である方針・source text exposure
checkが明記されていることを確認する。
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "MkDocs_Local_Preview_Dry_Run.md"
EXISTING_RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "MkDocs_Local_Preview.md"
RESULT_TEMPLATE_PATH = (
    PROJECT_ROOT / "docs" / "templates" / "mkdocs_local_preview_result_template.md"
)

_REAL_CHARACTER_NAMES = ("レイン", "赤城陽菜")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------
# runbook本体
# ----------------------------------------------------------------


def test_runbook_exists():
    assert RUNBOOK_PATH.is_file()


def test_runbook_states_build_success_is_not_visual_confirmation():
    content = _read(RUNBOOK_PATH)
    assert "目視" in content
    assert "別問題である" in content or "別途必要" in content


def test_runbook_states_source_text_exposure_check():
    content = _read(RUNBOOK_PATH)
    assert "source text exposure check" in content
    assert "ローカル絶対パス" in content
    assert "元セリフ全文" in content or "dialogue" in content.lower()


def test_runbook_states_no_commit_of_real_generated_data():
    content = _read(RUNBOOK_PATH)
    assert "workspace/wiki_preview/" in content
    assert "commitしない" in content


def test_runbook_lists_recommended_local_sample():
    content = _read(RUNBOOK_PATH)
    assert "推奨ローカルサンプル" in content
    assert "unresolved" in content.lower()


def test_runbook_references_character_profiles():
    content = _read(RUNBOOK_PATH)
    assert "character_profiles.yaml" in content


def test_runbook_mentions_title_subtitle_fallback():
    content = _read(RUNBOOK_PATH)
    assert "fallback" in content.lower()
    assert "title" in content.lower() and "subtitle" in content.lower()


def test_runbook_does_not_contain_real_character_names():
    content = _read(RUNBOOK_PATH)
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


def test_runbook_does_not_contain_real_external_urls():
    """`http://127.0.0.1:8000/` (mkdocs serveのローカル開発サーバーURL) は
    許容するが、それ以外の外部URL (実Wiki等) は含まれていないことを
    確認する。"""
    content = _read(RUNBOOK_PATH)
    assert "https://" not in content
    for line in content.splitlines():
        if "http://" in line:
            assert "127.0.0.1" in line, f"外部URLらしき記述: {line}"


# ----------------------------------------------------------------
# result template
# ----------------------------------------------------------------


def test_result_template_exists():
    assert RESULT_TEMPLATE_PATH.is_file()


def test_result_template_has_expected_sections():
    content = _read(RESULT_TEMPLATE_PATH)
    for heading in (
        "## Run Info",
        "## Build Checks",
        "## Visual Checks",
        "## Source Safety Checks",
        "## Findings",
    ):
        assert heading in content, f"見出しが見つかりません: {heading}"


def test_result_template_is_blank_and_synthetic_only():
    """テンプレートは空欄のままであり、実施結果 (実イベント名等) が
    書き込まれていないことを確認する。"""
    content = _read(RESULT_TEMPLATE_PATH)
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content
    assert "http://" not in content
    assert "https://" not in content


def test_result_template_states_not_to_commit_actual_results():
    content = _read(RESULT_TEMPLATE_PATH)
    assert "commit" in content.lower()


def test_result_template_is_not_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", str(RESULT_TEMPLATE_PATH)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"テンプレートがgitignoreされています: {result.stdout}"
    )


def test_dry_run_runbook_is_not_gitignored():
    result = subprocess.run(
        ["git", "check-ignore", str(RUNBOOK_PATH)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, f"runbookがgitignoreされています: {result.stdout}"


# ----------------------------------------------------------------
# 既存runbookの更新内容
# ----------------------------------------------------------------


def test_existing_runbook_references_dry_run_result_template():
    content = _read(EXISTING_RUNBOOK_PATH)
    assert "MkDocs_Local_Preview_Dry_Run.md" in content
    assert "mkdocs_local_preview_result_template.md" in content


def test_existing_runbook_states_visual_check_is_separate_from_build():
    content = _read(EXISTING_RUNBOOK_PATH)
    assert "目視" in content
