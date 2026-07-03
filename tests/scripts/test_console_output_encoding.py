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


def test_check_script_compatibility_cli_survives_cp932_console(tmp_path):
    """warning/needs_update ステータス (絵文字分岐を通る) でもcp932コンソールで
    クラッシュしないこと。"""
    result = subprocess.run(
        [
            sys.executable,
            str(CHECK_COMPAT_SCRIPT),
            str(UNKNOWN_CHAR_FIXTURE),
            "--output",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=_cp932_env(),
    )

    assert "UnicodeEncodeError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    # blocked (exit 2) にはならないはず (blocked相当の入力ではないため)
    assert result.returncode in (0, 1), result.stderr


def test_normalize_story_cli_survives_cp932_console(tmp_path):
    """compatible ステータス (✅ 成功 / ✅ compatible 分岐を通る) でも
    cp932コンソールでクラッシュしないこと。"""
    result = subprocess.run(
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
        ],
        capture_output=True,
        text=True,
        env=_cp932_env(),
    )

    assert "UnicodeEncodeError" not in result.stderr, result.stderr
    assert "Traceback" not in result.stderr, result.stderr
    assert result.returncode == 0, result.stderr
