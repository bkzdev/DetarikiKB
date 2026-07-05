"""
tests/docs/test_mkdocs_site_preview.py
MkDocs local preview構成 (mkdocs.yml / docs/site_preview/ /
docs/runbooks/MkDocs_Local_Preview.md) の軽量な整合性テスト。

実キャラ名・実プロフィール値・実ストーリー本文が紛れ込んでいないこと、
commit禁止方針が明記されていることを確認する。実際のmkdocsビルドは
CI (.github/workflows/ci.yml) の `mkdocs build --strict` で確認する
(このテストファイルではビルド自体は行わない)。
"""

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
MKDOCS_CONFIG_PATH = PROJECT_ROOT / "mkdocs.yml"
SITE_PREVIEW_DIR = PROJECT_ROOT / "docs" / "site_preview"
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "MkDocs_Local_Preview.md"

# 実データ由来のキャラクター名が紛れ込んでいないことの簡易チェック
# (tests/docs/test_wiki_output_design_docs.py と同じ確認パターン)
_REAL_CHARACTER_NAMES = ("レイン", "赤城陽菜")


def test_mkdocs_config_exists():
    assert MKDOCS_CONFIG_PATH.is_file()


def test_mkdocs_config_is_valid_yaml_with_expected_fields():
    with open(MKDOCS_CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    assert config["site_name"]
    assert config["docs_dir"] == "docs/site_preview"
    assert config["theme"]["name"] == "material"
    assert config["nav"] == [{"Home": "index.md"}]


def test_site_preview_index_exists():
    index_path = SITE_PREVIEW_DIR / "index.md"
    assert index_path.is_file()


def test_site_preview_states_no_real_data_commit_policy():
    content = (SITE_PREVIEW_DIR / "index.md").read_text(encoding="utf-8")
    assert "実データ" in content
    assert "commit" in content


def test_site_preview_does_not_contain_real_character_names():
    content = (SITE_PREVIEW_DIR / "index.md").read_text(encoding="utf-8")
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


def test_site_preview_only_contains_synthetic_or_doc_files():
    """docs/site_preview/配下に、実データ由来render_wiki.py出力らしき
    ファイル (characters/等のサブディレクトリ) が紛れ込んでいないことを
    確認する。"""
    entries = list(SITE_PREVIEW_DIR.iterdir())
    assert all(entry.is_file() for entry in entries), (
        f"docs/site_preview/配下にサブディレクトリが見つかりました "
        f"(render_wiki.py出力の混入を疑う): {entries}"
    )


def test_runbook_exists():
    assert RUNBOOK_PATH.is_file()


def test_runbook_states_workspace_wiki_preview_not_committed():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    assert "workspace/wiki_preview/" in content
    assert "commitしない" in content or "commit禁止" in content


def test_runbook_does_not_contain_real_character_names():
    content = RUNBOOK_PATH.read_text(encoding="utf-8")
    for name in _REAL_CHARACTER_NAMES:
        assert name not in content


def test_gitignore_covers_mkdocs_build_output():
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "site/" in gitignore
