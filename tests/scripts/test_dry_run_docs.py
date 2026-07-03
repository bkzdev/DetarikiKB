"""
tests/scripts/test_dry_run_docs.py
実データdry-run手順 (docs/runbooks/Real_Data_Dry_Run.md) と .gitignore の
軽量な整合性テスト。

実データ・生成物をcommitしないルールが.gitignoreへ機械的に反映されている
こと、手順書に必須セクションが揃っていることを確認する。
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
GITIGNORE_PATH = PROJECT_ROOT / ".gitignore"
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "Real_Data_Dry_Run.md"

# .gitignoreに含まれているべき最低限のパターン
# (ユーザー指示の「最低限、以下が除外されていること」に対応)
REQUIRED_GITIGNORE_PATTERNS = (
    "data/raw/**/*.dec",
    "data/raw/**/*.txt",
    "data/normalized/**/*.json",
    "data/extracted/**/*.json",
    "data/reports/**/*.json",
    "data/reports/**/*.md",
    "workspace/dry_runs/",
    "*.log",
    ".env",
)

# Real_Data_Dry_Run.md に含まれているべき必須セクション見出し
REQUIRED_RUNBOOK_SECTIONS = (
    "目的",
    "前提",
    "実データをcommitしないルール",
    "推奨ローカルディレクトリ構成",
    "入力配置例",
    "normalized JSON生成手順",
    "extraction JSON生成手順",
    "extraction validation手順",
    "merge手順",
    "manual overrideを使う場合の手順",
    "report確認ポイント",
    "よく見るwarning",
    "dry-run後の掃除方法",
    "commit前チェックリスト",
)


def test_gitignore_contains_required_patterns():
    content = GITIGNORE_PATH.read_text(encoding="utf-8")
    missing = [p for p in REQUIRED_GITIGNORE_PATTERNS if p not in content]
    assert not missing, f".gitignoreに不足しているパターン: {missing}"


def test_gitignore_does_not_broadly_exclude_test_fixtures():
    # tests/fixtures/parser/CAB-csl_script_*.dec のような、実データ全文を
    # 狙い撃ちした既存の狭いパターンは許容する (小さい自作fixtureを
    # commitできなくする "tests/fixtures/" や "tests/fixtures/**" の
    # ような広いignoreパターンが無いことだけを確認する)。
    lines = [
        line.strip()
        for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    broad_patterns = {"tests/fixtures/", "tests/fixtures/**", "tests/fixtures"}
    assert not (broad_patterns & set(lines))


def test_real_data_dry_run_doc_exists():
    assert RUNBOOK_PATH.exists(), f"{RUNBOOK_PATH} が存在しません"


def test_real_data_dry_run_doc_contains_required_sections():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_RUNBOOK_SECTIONS if s not in content]
    assert not missing, f"Real_Data_Dry_Run.mdに不足しているセクション: {missing}"


def test_real_data_dry_run_doc_lists_report_fields_to_check():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    required_report_fields = (
        "report.inputResults",
        "report.candidateCounts",
        "report.mergedEntityCounts",
        "report.unresolvedEntityCounts",
        "report.conflictCounts",
        "report.warningCounts",
        "report.relationshipTypeSummary",
        "report.canonicalIdSummary",
        "report.manualOverrides",
        "sourceDocuments",
    )
    missing = [f for f in required_report_fields if f not in content]
    assert not missing, f"report確認ポイントに不足しているフィールド: {missing}"


def test_real_data_dry_run_doc_contains_actual_cli_script_names():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    for script_name in (
        "normalize_story.py",
        "extract_story.py",
        "validate_extraction_json.py",
        "merge_extractions.py",
        "check_dry_run_inputs.py",
    ):
        assert script_name in content, f"{script_name} への言及が見つかりません"


def test_real_data_dry_run_doc_does_not_reference_committing_generated_data():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "実データ・生成物は一切Gitにcommitしない" in content
