"""release scope normalize CLIのsource revision gateテスト。"""

from __future__ import annotations

import pytest

from scripts import normalize_release_scope as cli


def test_source_revision_requires_fetched_clean_main(monkeypatch) -> None:
    source = "a" * 40
    responses = {
        (
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            "refs/heads/main:refs/remotes/origin/main",
        ): "",
        ("status", "--porcelain"): "",
        ("branch", "--show-current"): "main",
        ("rev-parse", "HEAD"): source,
        ("rev-parse", "origin/main"): source,
    }
    monkeypatch.setattr(cli, "_git", lambda *args: responses[args])
    cli._verify_source_revision(source)

    responses[("rev-parse", "origin/main")] = "b" * 40
    with pytest.raises(ValueError, match="origin/main"):
        cli._verify_source_revision(source)


def test_source_revision_rejects_dirty_or_non_main_checkout(monkeypatch) -> None:
    source = "a" * 40
    responses = {
        (
            "fetch",
            "--quiet",
            "--no-tags",
            "origin",
            "refs/heads/main:refs/remotes/origin/main",
        ): "",
        ("status", "--porcelain"): "changed",
    }
    monkeypatch.setattr(cli, "_git", lambda *args: responses[args])
    with pytest.raises(ValueError, match="dirty"):
        cli._verify_source_revision(source)

    responses[("status", "--porcelain")] = ""
    responses[("branch", "--show-current")] = "feature"
    with pytest.raises(ValueError, match="not main"):
        cli._verify_source_revision(source)
