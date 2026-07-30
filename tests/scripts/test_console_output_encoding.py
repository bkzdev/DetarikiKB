"""
tests/scripts/test_console_output_encoding.py

real data dry-run trial (docs/runbooks/Real_Data_Dry_Run.md) で判明した回帰:
scripts/normalize_story.py と scripts/check_script_compatibility.py の
コンソールサマリー表示に絵文字 (✅/⚠️/🔶/🚫) が含まれており、Windows既定の
cp932コンソール (日本語版Windowsの既定コードページ) では
`print()` 自体が `UnicodeEncodeError` を送出していた。

この例外は `except Exception` で捕捉され、JSON Schema検証やパーサー自体は
成功しているにもかかわらず「検証中にエラーが発生しました」という
誤ったエラーメッセージ・非ゼロ終了コードになっていた
(check_script_compatibility.py側は未捕捉のtracebackで終了コード1)。

CLAUDE.md はcheck_script_compatibility.pyの終了コード
(0: compatible, 1: needs_update, 2: blocked) を意味のあるシグナルとして
文書化しているため、この回帰は特に重要 (cp932コンソールでは常に
「クラッシュ由来の1」と「本来の状態としての1(needs_update)」が
区別できなくなる)。

`PYTHONIOENCODING=cp932` を子プロセスに渡すことで、OSのロケールに依らず
cp932コンソールを再現する (Linux CI環境でも回帰を検知できる)。
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
NORMALIZE_SCRIPT = PROJECT_ROOT / "scripts" / "normalize_story.py"
CHECK_COMPAT_SCRIPT = PROJECT_ROOT / "scripts" / "check_script_compatibility.py"

BASIC_DIALOGUE_FIXTURE = (
    PROJECT_ROOT / "tests" / "fixtures" / "parser" / "basic_dialogue.dec"
)
UNKNOWN_CHAR_FIXTURE = (
    PROJECT_ROOT / "tests" / "fixtures" / "parser" / "unknown_char.dec"
)


def _cp932_env() -> dict[str, str]:
    import os

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp932"
    return env


def _run_with_cp932_output(
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    """CP932出力をreader threadを使わずに回収する。"""
    # Windows版Python 3.14では、text modeのPIPEを読むsubprocess reader
    # threadが稀に不安定になる。子プロセスのPYTHONIOENCODING=cp932という
    # 回帰条件は維持し、file-backedなbinary handleへ書かせて終了後にdecodeする。
    with (
        tempfile.TemporaryFile() as stdout_file,
        tempfile.TemporaryFile() as stderr_file,
    ):
        completed = subprocess.run(
            args,
            stdout=stdout_file,
            stderr=stderr_file,
            env=_cp932_env(),
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            args=completed.args,
            returncode=completed.returncode,
            stdout=stdout_file.read().decode("cp932"),
            stderr=stderr_file.read().decode("cp932"),
        )


def test_check_script_compatibility_cli_survives_cp932_console(tmp_path):
    """warning/needs_update ステータス (絵文字分岐を通る) でもcp932コンソールで
    クラッシュしないこと。"""
    result = _run_with_cp932_output(
        [
            sys.executable,
            str(CHECK_COMPAT_SCRIPT),
            str(UNKNOWN_CHAR_FIXTURE),
            "--output",
            str(tmp_path),
        ]
    )

    assert "UnicodeEncodeError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    # blocked (exit 2) にはならないはず (blocked相当の入力ではないため)
    assert result.returncode in (0, 1), result.stderr


def test_normalize_story_cli_survives_cp932_console(tmp_path):
    """compatible ステータス (✅ 成功 / ✅ compatible 分岐を通る) でも
    cp932コンソールでクラッシュしないこと。"""
    result = _run_with_cp932_output(
        [
            sys.executable,
            str(NORMALIZE_SCRIPT),
            "--input",
            str(BASIC_DIALOGUE_FIXTURE),
            "--story-id",
            "TEST_CONSOLE_ENCODING",
            "--episode-id",
            "TEST_CONSOLE_ENCODING_E01",
            "--category",
            "OTHER",
            "--output",
            str(tmp_path),
            "--validate",
            "--check-compat",
            "--compat-report-output",
            str(tmp_path / "compat_reports"),
        ]
    )

    assert "UnicodeEncodeError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
