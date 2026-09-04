"""detached public site manifest比較CLIの境界テスト。"""

from __future__ import annotations

import json

import scripts.compare_public_site_manifests as comparer


def test_compare_cli_reports_only_clean_status(monkeypatch, capsys) -> None:
    manifests = iter(({"kind": "mkdocs"}, {"kind": "zensical"}))
    monkeypatch.setattr(comparer, "_load", lambda _path: next(manifests))
    monkeypatch.setattr(
        comparer, "validate_public_site_manifest_pair", lambda _left, _right: ()
    )
    assert (
        comparer.main(
            ["--mkdocs-manifest", "left.json", "--zensical-manifest", "right.json"]
        )
        == 0
    )
    assert capsys.readouterr().out == "status=clean\n"


def test_compare_cli_reports_anonymous_block(monkeypatch, capsys) -> None:
    manifests = iter(({"kind": "mkdocs"}, {"kind": "zensical"}))
    monkeypatch.setattr(comparer, "_load", lambda _path: next(manifests))
    monkeypatch.setattr(
        comparer,
        "validate_public_site_manifest_pair",
        lambda _left, _right: ("public-site-manifest-pair-route-mismatch",),
    )
    assert (
        comparer.main(
            ["--mkdocs-manifest", "left.json", "--zensical-manifest", "right.json"]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "code=public-site-manifest-pair-route-mismatch" in captured.err
    assert "left.json" not in captured.out + captured.err


def test_compare_cli_rejects_invalid_json(tmp_path, capsys) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text("not-json", encoding="utf-8")
    right.write_text(json.dumps({}), encoding="utf-8")
    assert (
        comparer.main(
            ["--mkdocs-manifest", str(left), "--zensical-manifest", str(right)]
        )
        == 1
    )
    captured = capsys.readouterr()
    assert "code=public-site-manifest-input-invalid" in captured.err
    assert str(tmp_path) not in captured.out + captured.err
