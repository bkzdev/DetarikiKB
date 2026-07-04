"""
tests/scripts/test_render_wiki.py
scripts/render_wiki.py のCLIスモークテスト。

合成fixture (tests/fixtures/wiki/synthetic_merged_collection.json) のみを
入力に使い、出力先は常にtmp_pathにする。実データ由来のfixtureは使わない。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "render_wiki.py"
FIXTURE_PATH = (
    PROJECT_ROOT / "tests" / "fixtures" / "wiki" / "synthetic_merged_collection.json"
)


def test_cli_generates_expected_markdown_files(tmp_path):
    output_dir = tmp_path / "wiki_out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(FIXTURE_PATH),
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "index.md").is_file()
    assert (output_dir / "stories" / "index.md").is_file()
    assert (output_dir / "stories" / "EP_TEST_001.md").is_file()
    assert (output_dir / "stories" / "EP_TEST_002.md").is_file()
    assert (output_dir / "characters" / "CHAR_TEST_RAIN.md").is_file()
    assert (output_dir / "reports" / "unresolved.md").is_file()
    # canonicalIdが無いキャラクターの個別ページは生成されない
    assert not (output_dir / "characters" / "UNRESOLVED_CHAR_TEST_0001.md").exists()


def test_cli_generated_episode_page_has_expected_content(tmp_path):
    """Episode pageにcandidateCounts表・related characters・front matter
    が含まれることをCLI経由で確認する。"""
    output_dir = tmp_path / "wiki_out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(FIXTURE_PATH),
            "--output",
            str(output_dir),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    episode_page = (output_dir / "stories" / "EP_TEST_001.md").read_text(
        encoding="utf-8"
    )
    assert 'page_type: "episode"' in episode_page
    assert 'episode_id: "EP_TEST_001"' in episode_page
    assert "## Candidate Counts" in episode_page
    assert "## Related Characters" in episode_page
    assert "Test Character Rain" in episode_page
    assert "textExcerpt" not in episode_page


def test_cli_with_validate_flag_succeeds_on_valid_fixture(tmp_path):
    output_dir = tmp_path / "wiki_out"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(FIXTURE_PATH),
            "--output",
            str(output_dir),
            "--validate",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "index.md").is_file()


def test_cli_missing_input_returns_exit_1(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(tmp_path / "does_not_exist.json"),
            "--output",
            str(tmp_path / "wiki_out"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1


def test_cli_invalid_json_returns_exit_1(tmp_path):
    bad_input = tmp_path / "not_json.json"
    bad_input.write_text("{ this is not valid json", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(bad_input),
            "--output",
            str(tmp_path / "wiki_out"),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1


def test_cli_validate_rejects_schema_invalid_collection(tmp_path):
    invalid_input = tmp_path / "invalid_collection.json"
    invalid_input.write_text('{"schemaVersion": "0.1.0"}', encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(invalid_input),
            "--output",
            str(tmp_path / "wiki_out"),
            "--validate",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2


def test_cli_clean_flag_removes_stale_output(tmp_path):
    output_dir = tmp_path / "wiki_out"
    output_dir.mkdir(parents=True)
    stale_file = output_dir / "stale.md"
    stale_file.write_text("stale content", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--input",
            str(FIXTURE_PATH),
            "--output",
            str(output_dir),
            "--clean",
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()
    assert (output_dir / "index.md").is_file()
