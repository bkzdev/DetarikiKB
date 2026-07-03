"""
tests/scripts/test_check_dry_run_inputs.py
scripts/check_dry_run_inputs.py (実データdry-run手順の補助スクリプト、
docs/runbooks/Real_Data_Dry_Run.md) のテスト。

scripts/ 配下はパッケージ化されていないため、importlibでファイルパスから
直接moduleとして読み込む (既存のscripts/配下テストはsubprocess経由の
CLIスモークテストのみだったため、純粋関数の単体テストはこの方式で追加する)。

実データ・data/extracted/生成物は使わず、本ファイル内で組み立てる自作の
最小fixture (tmp_path) のみを使う。
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_dry_run_inputs.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_dry_run_inputs", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return _load_module()


# ----------------------------------------------------------------
# 1. ignored directory候補を検出できる (check_directories)
# ----------------------------------------------------------------


def test_check_directories_detects_existing_dirs(module, tmp_path):
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "extracted").mkdir(parents=True)
    # data/normalized, data/reports, workspace は作らない

    result = module.check_directories(tmp_path)

    assert result["data/raw"] is True
    assert result["data/extracted"] is True
    assert result["data/normalized"] is False
    assert result["data/reports"] is False
    assert result["workspace"] is False


def test_check_directories_covers_all_dry_run_directories(module):
    assert set(module.DRY_RUN_DIRECTORIES) == {
        "data/raw",
        "data/normalized",
        "data/extracted",
        "data/reports",
        "workspace",
    }


# ----------------------------------------------------------------
# 2. tracked禁止パターンの判定ができる (classify_forbidden_paths)
# ----------------------------------------------------------------


def test_classify_forbidden_paths_detects_dec_and_json_generated_files(module):
    tracked = [
        "data/raw/main/real_script.dec",
        "data/normalized/main/MAIN_S01_C02_E01.json",
        "data/extracted/_raw/MAIN_S01_C02_E01.extraction.json",
        "data/reports/script_compatibility_report.json",
        "data/reports/script_compatibility_report.md",
        "workspace/dry_runs/20260703_000000/merged_knowledge_collection.json",
        ".env",
        "debug.log",
    ]

    findings = module.classify_forbidden_paths(tracked)
    flagged_paths = {path for path, _reason in findings}

    assert flagged_paths == set(tracked)


def test_classify_forbidden_paths_allows_gitkeep_and_env_example(module):
    tracked = [
        "data/raw/main/.gitkeep",
        "data/normalized/.gitkeep",
        "data/extracted/.gitkeep",
        "data/reports/.gitkeep",
        ".env.example",
    ]

    findings = module.classify_forbidden_paths(tracked)

    assert findings == []


def test_classify_forbidden_paths_allows_synthetic_test_fixtures(module):
    # tests/fixtures/ 配下の合成データはcommit対象として許容される
    # (このスクリプトのパターンはdata/*.dec等のみを対象とし、
    # tests/fixtures/ は判定対象に含めていない)
    tracked = [
        "tests/fixtures/extraction/minimal_episode_extraction.json",
        "tests/fixtures/merger/overrides/manual_overrides_valid.json",
    ]

    findings = module.classify_forbidden_paths(tracked)

    assert findings == []


def test_classify_forbidden_paths_allows_normal_source_files(module):
    tracked = [
        "agents/merger/engine.py",
        "docs/runbooks/Real_Data_Dry_Run.md",
        "scripts/check_dry_run_inputs.py",
    ]

    findings = module.classify_forbidden_paths(tracked)

    assert findings == []


# ----------------------------------------------------------------
# 3. synthetic fixtureだけでdry-run statusが実行できる
#    (count_json_files / find_extraction_candidates)
# ----------------------------------------------------------------


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_count_json_files_counts_recursively(module, tmp_path):
    _write_json(tmp_path / "a.json", {"documentType": "episode_extraction"})
    _write_json(tmp_path / "sub" / "b.json", {"documentType": "episode_extraction"})
    (tmp_path / "not_json.txt").write_text("hello", encoding="utf-8")

    assert module.count_json_files(tmp_path) == 2


def test_count_json_files_returns_zero_for_missing_directory(module, tmp_path):
    assert module.count_json_files(tmp_path / "does_not_exist") == 0


def test_find_extraction_candidates_filters_by_document_type(module, tmp_path):
    _write_json(tmp_path / "extraction.json", {"documentType": "episode_extraction"})
    _write_json(
        tmp_path / "other.json", {"documentType": "merged_knowledge_collection"}
    )
    (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")

    candidates = module.find_extraction_candidates(tmp_path)

    assert len(candidates) == 1
    assert candidates[0].name == "extraction.json"


def test_find_extraction_candidates_empty_for_missing_directory(module, tmp_path):
    assert module.find_extraction_candidates(tmp_path / "does_not_exist") == []


# ----------------------------------------------------------------
# 4. schema validation対象候補を列挙できる (--show-commands / --count-json CLI)
# ----------------------------------------------------------------


def test_cli_show_commands_lists_validation_and_merge_commands():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--show-commands"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "validate_extraction_json.py" in result.stdout
    assert "merge_extractions.py" in result.stdout
    assert "normalize_story.py" in result.stdout


def test_cli_count_json_reports_extraction_candidates(tmp_path):
    _write_json(
        tmp_path / "ep01.extraction.json", {"documentType": "episode_extraction"}
    )
    _write_json(tmp_path / "unrelated.json", {"documentType": "something_else"})

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--count-json", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "JSON 2" in result.stdout
    assert "episode_extraction" in result.stdout
    assert "ep01.extraction.json" in result.stdout


# ----------------------------------------------------------------
# 5. CLI: 現在のリポジトリ自体に対する実行 (git tracked禁止パターンが
#    実際に0件であることの確認。このリポジトリ自体が既存ルールを
#    守れていることの回帰確認でもある)
# ----------------------------------------------------------------


def test_cli_default_run_against_this_repo_finds_no_forbidden_tracked_paths():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--quiet"],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stderr
