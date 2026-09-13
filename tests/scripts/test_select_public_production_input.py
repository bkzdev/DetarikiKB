from __future__ import annotations

import subprocess
from unittest.mock import patch

from scripts.select_public_production_input import (
    LEGACY_INPUT_PATH,
    REAL_INPUT_INTRODUCTION_SHA,
    REVIEWED_INPUT_PATH,
    select_input,
)

SOURCE_SHA = "a" * 40
TRUSTED_MAIN_SHA = "b" * 40


def _result(returncode: int, stdout: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout, "")


def test_reviewed_input_is_selected_for_current_revision() -> None:
    with patch("scripts.select_public_production_input.subprocess.run") as run:
        run.side_effect = [
            _result(0, f"{SOURCE_SHA}\n"),
            _result(0, f"{REAL_INPUT_INTRODUCTION_SHA}\n"),
            _result(0, "blob\n"),
        ]
        selection, code = select_input(SOURCE_SHA, "")

    assert code is None
    assert selection is not None
    assert (selection.path, selection.profile) == (
        REVIEWED_INPUT_PATH,
        "reviewed-public-input",
    )


def test_pre_introduction_revision_can_use_digest_pinned_legacy_input() -> None:
    with patch("scripts.select_public_production_input.subprocess.run") as run:
        run.side_effect = [
            _result(0, f"{TRUSTED_MAIN_SHA}\n"),
            _result(0, f"{REAL_INPUT_INTRODUCTION_SHA}\n"),
            _result(1),
            _result(0),
            _result(0, "blob\n"),
        ]
        selection, code = select_input(SOURCE_SHA, "c" * 64)

    assert code is None
    assert selection is not None
    assert (selection.path, selection.profile) == (
        LEGACY_INPUT_PATH,
        "legacy-synthetic-rollback",
    )


def test_post_introduction_revision_without_reviewed_input_is_blocked() -> None:
    with patch("scripts.select_public_production_input.subprocess.run") as run:
        run.side_effect = [
            _result(0, f"{TRUSTED_MAIN_SHA}\n"),
            _result(0, f"{REAL_INPUT_INTRODUCTION_SHA}\n"),
            _result(1),
            _result(1),
        ]
        selection, code = select_input(SOURCE_SHA, "c" * 64)

    assert selection is None
    assert code == "production-public-input-unavailable"


def test_legacy_input_requires_expected_tree_digest() -> None:
    with patch("scripts.select_public_production_input.subprocess.run") as run:
        run.side_effect = [
            _result(0, f"{TRUSTED_MAIN_SHA}\n"),
            _result(0, f"{REAL_INPUT_INTRODUCTION_SHA}\n"),
            _result(1),
        ]
        selection, code = select_input(SOURCE_SHA, "")

    assert selection is None
    assert code == "production-public-input-unavailable"


def test_unavailable_fixed_boundary_is_blocked() -> None:
    with patch("scripts.select_public_production_input.subprocess.run") as run:
        run.side_effect = [_result(0, f"{TRUSTED_MAIN_SHA}\n"), _result(1)]
        selection, code = select_input(SOURCE_SHA, "c" * 64)

    assert selection is None
    assert code == "production-public-input-boundary-unavailable"
