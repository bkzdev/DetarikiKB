from __future__ import annotations

import subprocess
from unittest.mock import Mock, patch

from scripts.check_public_production_source import check_source, main

VALID_SHA = "a" * 40


def _result(returncode: int) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, "", "")


def test_check_source_accepts_commit_on_origin_main() -> None:
    with patch("scripts.check_public_production_source.subprocess.run") as run:
        run.side_effect = [_result(0), _result(0), _result(0)]

        assert check_source(VALID_SHA) is None

    assert [call.args[0] for call in run.call_args_list] == [
        ["git", "rev-parse", "--verify", "origin/main^{commit}"],
        ["git", "cat-file", "-e", f"{VALID_SHA}^{{commit}}"],
        ["git", "merge-base", "--is-ancestor", VALID_SHA, "origin/main"],
    ]
    assert all(call.kwargs["capture_output"] for call in run.call_args_list)


def test_check_source_rejects_noncanonical_sha_without_running_git() -> None:
    with patch("scripts.check_public_production_source.subprocess.run") as run:
        assert check_source("A" * 40) == "production-source-sha-invalid"
        assert check_source("a" * 39) == "production-source-sha-invalid"
    run.assert_not_called()


def test_check_source_reports_each_git_failure_anonymously() -> None:
    cases = [
        ([_result(1)], "production-main-ref-unavailable"),
        ([_result(0), _result(1)], "production-source-commit-unavailable"),
        ([_result(0), _result(0), _result(1)], "production-source-not-on-main"),
    ]
    for results, expected in cases:
        with patch(
            "scripts.check_public_production_source.subprocess.run", side_effect=results
        ):
            assert check_source(VALID_SHA) == expected


def test_check_source_reports_unavailable_git() -> None:
    with patch(
        "scripts.check_public_production_source.subprocess.run",
        side_effect=FileNotFoundError,
    ):
        assert check_source(VALID_SHA) == "production-git-unavailable"


def test_main_prints_only_fixed_status(capsys) -> None:
    with patch(
        "scripts.check_public_production_source.check_source",
        Mock(return_value="production-source-not-on-main"),
    ):
        assert main([VALID_SHA]) == 1
    assert capsys.readouterr().out == (
        "status=blocked code=production-source-not-on-main\n"
    )


def test_main_reports_clean_without_echoing_source(capsys) -> None:
    with patch(
        "scripts.check_public_production_source.check_source", Mock(return_value=None)
    ):
        assert main([VALID_SHA]) == 0
    output = capsys.readouterr().out
    assert output == "status=clean\n"
    assert VALID_SHA not in output
