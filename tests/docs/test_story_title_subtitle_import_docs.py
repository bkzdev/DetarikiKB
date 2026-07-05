"""
tests/docs/test_story_title_subtitle_import_docs.py
story title/subtitle import設計 (Story_Manifest_Design.md §11 拡張・
docs/runbooks/Story_Title_Subtitle_Import.md・
docs/templates/story_title_subtitle_candidates_template.yaml) の
軽量な整合性テスト。

実イベント名・実タイトル・実URLが含まれていないこと、DEC本文から
subtitleを推測しない方針・AI-generated titleとの分離方針が明記されて
いることを確認する。
"""

import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN_DOC_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_Manifest_Design.md"
)
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "Story_Title_Subtitle_Import.md"
CANDIDATE_TEMPLATE_PATH = (
    PROJECT_ROOT
    / "docs"
    / "templates"
    / "story_title_subtitle_candidates_template.yaml"
)

_REAL_CHARACTER_NAMES = ("レイン", "赤城陽菜")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# ----------------------------------------------------------------
# Story_Manifest_Design.md の拡張内容
# ----------------------------------------------------------------


def test_design_doc_has_new_subsections():
    content = _read(DESIGN_DOC_PATH)
    for heading in (
        "## 11.4 story title と episode subtitle の違い",
        "## 11.5 source種別設計",
        "## 11.6 official titleとAI-generated titleの分離",
        "## 11.7 import candidate",
        "## 11.8 複数sourceが矛盾した場合の扱い",
        "## 11.9 表記ゆれ",
        "## 13.1 source tracking",
    ):
        assert heading in content, f"見出しが見つかりません: {heading}"


def test_design_doc_lists_all_source_types():
    content = _read(DESIGN_DOC_PATH)
    for source_type in (
        "manual",
        "official_game_ui",
        "official_announcement",
        "wiki_story_list",
        "wiki_event_page",
        "imported_candidate",
        "unknown",
    ):
        assert source_type in content


def test_design_doc_states_dec_body_not_inferred_for_title_or_subtitle():
    content = _read(DESIGN_DOC_PATH)
    assert "DEC本文からは自動推測しない" in content or "自動推測しない" in content


def test_design_doc_states_ai_generated_title_separation():
    content = _read(DESIGN_DOC_PATH)
    assert "AI生成タイトル" in content or "AI-generated" in content
    assert "分離" in content


def test_design_doc_states_candidate_before_manifest_update():
    content = _read(DESIGN_DOC_PATH)
    assert "reviewStatus" in content
    assert "pending" in content
    assert "へ直接書き込まない" in content


def test_design_doc_does_not_reference_real_character_names():
    content = _read(DESIGN_DOC_PATH)
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


# ----------------------------------------------------------------
# runbook
# ----------------------------------------------------------------


def test_runbook_exists():
    assert RUNBOOK_PATH.is_file()


def test_runbook_states_dec_body_not_inferred():
    content = _read(RUNBOOK_PATH)
    assert "DEC本文からtitle/subtitleを推測する" in content


def test_runbook_states_ai_title_generation_forbidden():
    content = _read(RUNBOOK_PATH)
    assert "AIに公式タイトルを生成させる" in content


def test_runbook_states_external_list_values_start_as_candidate():
    content = _read(RUNBOOK_PATH)
    assert "確認なしに" in content or "candidate" in content.lower()
    assert "confirmed" in content.lower()


def test_runbook_states_commit_forbidden_items():
    content = _read(RUNBOOK_PATH)
    assert "commit禁止対象" in content
    assert "workspace/story_manifest/" in content
    assert "実HTML" in content or "raw HTML" in content


def test_runbook_does_not_contain_real_character_names():
    content = _read(RUNBOOK_PATH)
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


# ----------------------------------------------------------------
# candidate template
# ----------------------------------------------------------------


def test_candidate_template_exists():
    assert CANDIDATE_TEMPLATE_PATH.is_file()


def test_candidate_template_is_synthetic_only():
    content = _read(CANDIDATE_TEMPLATE_PATH)
    assert "合成データ" in content
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content
    # 実URLを含まないこと (http(s)://で始まる文字列が無い)
    assert "http://" not in content
    assert "https://" not in content


def test_candidate_template_review_status_is_pending():
    import yaml

    with open(CANDIDATE_TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    for story in document["candidates"]:
        for episode in story["episodes"]:
            assert episode["reviewStatus"] == "pending"


def test_candidate_template_document_type():
    import yaml

    with open(CANDIDATE_TEMPLATE_PATH, encoding="utf-8") as f:
        document = yaml.safe_load(f)
    assert document["documentType"] == "story_title_subtitle_candidates"


def test_candidate_template_is_not_gitignored():
    """テンプレートファイル名が.gitignoreの
    `story_title_subtitle_candidates_*.yaml`パターン自身に誤って一致し、
    commitできなくなっていないことを確認する
    (character_confirmed_batch_input_template.yamlで過去に起きた
    不具合と同種)。"""
    result = subprocess.run(
        [
            "git",
            "check-ignore",
            str(CANDIDATE_TEMPLATE_PATH),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    # git check-ignore はignore対象なら0、対象外なら1を返す
    assert result.returncode == 1, (
        f"テンプレートがgitignoreされています: {result.stdout}"
    )
