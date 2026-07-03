"""
tests/scripts/test_check_invisible_unicode.py
scripts/check_invisible_unicode.py のテスト。

日本語・全角記号・罫線・矢印・通常のUnicode引用符は検出対象にならない
こと (「2バイト文字だからNG」にはしないこと)、bidi override/control・
zero-width系・BOMは確実に検出されること、除外ディレクトリ配下は
走査されないことを重点的に確認する。

実データ・data/extracted/生成物は使わず、本ファイル内で組み立てる
tmp_path上の自作テキストのみを使う。
"""

import importlib.util
import subprocess
import sys
from pathlib import Path, PurePosixPath
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_invisible_unicode.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_invisible_unicode", SCRIPT_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # dataclass (Finding) が `from __future__ import annotations` 由来の
    # 文字列注釈をsys.modules経由で解決するため、実行前にsys.modulesへ
    # 登録しておく必要がある。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return _load_module()


# ----------------------------------------------------------------
# 1. 許可される文字 (日本語・全角記号・矢印・罫線・通常の引用符)
# ----------------------------------------------------------------


def test_japanese_text_passes(module):
    text = "これは日本語のテキストです。テスト用の説明文。"
    findings = module.scan_text(Path("dummy.md"), text)
    assert findings == []


def test_fullwidth_symbols_arrows_box_drawing_pass(module):
    text = "→←↑↓　【】〜『』「」━─│┌┐└┘※①②③ＡＢＣ１２３"
    findings = module.scan_text(Path("dummy.md"), text)
    assert findings == []


def test_normal_unicode_quotes_pass(module):
    text = "“Hello” and ‘world’ with – en dash"
    findings = module.scan_text(Path("dummy.md"), text)
    assert findings == []


def test_mixed_japanese_and_ascii_code_passes(module):
    text = (
        "def greet(name: str) -> str:\n"
        '    """挨拶を返す。"""\n'
        '    return f"こんにちは、{name}さん"\n'
    )
    findings = module.scan_text(Path("dummy.py"), text)
    assert findings == []


# ----------------------------------------------------------------
# 2. 検出されるべき危険な文字
# ----------------------------------------------------------------


def test_detects_rtl_override(module):
    text = f'name = "a{chr(0x202E)}b"'
    findings = module.scan_text(Path("dummy.py"), text)
    assert len(findings) == 1
    assert findings[0].codepoint == 0x202E
    assert "RIGHT-TO-LEFT OVERRIDE" in findings[0].name


def test_detects_zero_width_space(module):
    text = f'zw = "a{chr(0x200B)}b"'
    findings = module.scan_text(Path("dummy.py"), text)
    assert len(findings) == 1
    assert findings[0].codepoint == 0x200B
    assert "ZERO WIDTH SPACE" in findings[0].name


def test_detects_bom(module):
    text = f"{chr(0xFEFF)}y = 2"
    findings = module.scan_text(Path("dummy.py"), text)
    assert len(findings) == 1
    assert findings[0].codepoint == 0xFEFF


def test_detects_soft_hyphen(module):
    text = f"word{chr(0x00AD)}break"
    findings = module.scan_text(Path("dummy.md"), text)
    assert len(findings) == 1
    assert findings[0].codepoint == 0x00AD


def test_detects_all_bidi_isolates(module):
    for codepoint in (0x2066, 0x2067, 0x2068, 0x2069):
        text = f"x{chr(codepoint)}y"
        findings = module.scan_text(Path("dummy.py"), text)
        assert len(findings) == 1, f"U+{codepoint:04X} was not detected"
        assert findings[0].codepoint == codepoint


# ----------------------------------------------------------------
# 3. 検出時にfile/line/column/codepointが出る
# ----------------------------------------------------------------


def test_finding_reports_line_column_codepoint_and_excerpt(module):
    text = f"line one\nline t{chr(0x200B)}wo\nline three"
    findings = module.scan_text(Path("some/file.py"), text)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.path == Path("some/file.py")
    assert finding.line == 2
    assert finding.column == 7
    assert finding.codepoint == 0x200B
    assert "line t" in finding.excerpt
    formatted = finding.format()
    assert "some/file.py:2:7" in formatted
    assert "U+200B" in formatted


# ----------------------------------------------------------------
# 4. 除外ディレクトリは走査しない (is_excluded / iter_target_files)
# ----------------------------------------------------------------


@pytest.mark.parametrize(
    "rel_path",
    [
        ".venv/lib/site.py",
        "venv/lib/site.py",
        "__pycache__/module.pyc",
        ".pytest_cache/README.md",
        ".git/config",
        "node_modules/pkg/index.js",
        "data/raw/main/example.dec",
        "data/normalized/main/EP01.json",
        "data/extracted/_raw/EP01.json",
        "data/reports/report.json",
        "workspace/dry_runs/20260703_000000/merged.json",
    ],
)
def test_is_excluded_matches_excluded_paths(module, rel_path):
    assert module.is_excluded(PurePosixPath(rel_path)) is True


@pytest.mark.parametrize(
    "rel_path",
    [
        "agents/merger/engine.py",
        "docs/runbooks/Real_Data_Dry_Run.md",
        "data/embeddings/vector.json",
        "workspace/reviews/notes.md",
    ],
)
def test_is_excluded_allows_normal_paths(module, rel_path):
    assert module.is_excluded(PurePosixPath(rel_path)) is False


def test_iter_target_files_skips_excluded_directories(module, tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bad.py").write_text(f"x{chr(0x202E)}", encoding="utf-8")
    (tmp_path / "data" / "raw").mkdir(parents=True)
    (tmp_path / "data" / "raw" / "bad.py").write_text(
        f"x{chr(0x202E)}", encoding="utf-8"
    )
    (tmp_path / "normal").mkdir()
    (tmp_path / "normal" / "clean.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "normal" / "dirty.py").write_text(f"x{chr(0x202E)}", encoding="utf-8")

    targets = module.iter_target_files(tmp_path)
    target_names = {p.relative_to(tmp_path).as_posix() for p in targets}

    assert target_names == {"normal/clean.py", "normal/dirty.py"}


def test_scan_paths_only_reports_findings_outside_excluded_dirs(module, tmp_path):
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "bad.py").write_text(f"x{chr(0x202E)}", encoding="utf-8")
    (tmp_path / "normal").mkdir()
    (tmp_path / "normal" / "dirty.py").write_text(f"x{chr(0x202E)}", encoding="utf-8")

    findings = module.scan_paths([tmp_path])

    assert len(findings) == 1
    assert findings[0].path.name == "dirty.py"


# ----------------------------------------------------------------
# 5. CLI: exit code
# ----------------------------------------------------------------


def test_cli_exit_zero_when_no_findings(tmp_path):
    (tmp_path / "clean.md").write_text(
        "日本語のテキストと→矢印だけ。", encoding="utf-8"
    )

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--path", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "No dangerous invisible Unicode characters found." in result.stdout


def test_cli_exit_one_when_findings_present(tmp_path):
    (tmp_path / "dirty.py").write_text(f"x{chr(0x202E)}y", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--path", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Found invisible Unicode characters:" in result.stdout
    assert "U+202E" in result.stdout


def test_cli_exit_two_when_path_does_not_exist(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--path",
            str(tmp_path / "does_not_exist.py"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_cli_default_run_against_this_repo_finds_no_dangerous_characters():
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )
    assert result.returncode == 0, result.stdout + result.stderr
