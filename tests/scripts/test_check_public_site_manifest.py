"""public site manifest CLIの合成テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.check_public_site_manifest as checker
from agents.wiki_generator.public_site_manifest import PublicSiteError


def _configure(monkeypatch, tmp_path: Path) -> tuple[list[str], Path, Path]:
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<h1>公開</h1>", encoding="utf-8")
    public_input = tmp_path / "public-input.json"
    public_input.write_text("{}", encoding="utf-8")
    lock = tmp_path / "uv.lock"
    lock.write_text("synthetic-lock", encoding="utf-8")
    config = tmp_path / "zensical.yml"
    config.write_text("synthetic-config", encoding="utf-8")
    output = tmp_path / "manifest.json"
    manifest = {
        "schemaVersion": "0.1",
        "documentType": "public_site_manifest",
        "visibility": "public",
        "artifactStatus": "verified_build_candidate",
        "deploymentAuthorized": False,
    }
    monkeypatch.setattr(
        checker, "build_public_site_manifest", lambda *_args, **_kwargs: manifest
    )
    args = [
        "--site-dir",
        str(site),
        "--public-input",
        str(public_input),
        "--source-sha",
        "a" * 40,
        "--lock-file",
        str(lock),
        "--generator-name",
        "zensical",
        "--generator-version",
        "0.0.57",
        "--config",
        str(config),
    ]
    return args, output, site


def test_default_dry_run_writes_nothing(monkeypatch, tmp_path, capsys) -> None:
    args, output, _site = _configure(monkeypatch, tmp_path)
    assert checker.main(args) == 0
    assert not output.exists()
    captured = capsys.readouterr()
    assert "status=dry_run manifest_sha256=" in captured.out
    assert str(tmp_path) not in captured.out + captured.err


def test_explicit_write_is_no_clobber(monkeypatch, tmp_path, capsys) -> None:
    args, output, _site = _configure(monkeypatch, tmp_path)
    write_args = args + ["--manifest-output", str(output), "--write-manifest"]
    if not checker._SECURE_DIR_FD_WRITE_SUPPORTED:
        assert checker.main(write_args) == 1
        assert (
            "code=manifest-output-secure-write-unavailable" in capsys.readouterr().err
        )
        assert not output.exists()
        return
    assert checker.main(write_args) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["visibility"] == "public"
    assert checker.main(write_args) == 1
    captured = capsys.readouterr()
    assert "code=manifest-output-exists" in captured.err
    assert str(tmp_path) not in captured.out + captured.err


@pytest.mark.parametrize(
    "extra",
    (
        ["--write-manifest"],
        ["--manifest-output", "manifest.json"],
    ),
)
def test_output_arguments_must_be_paired(monkeypatch, tmp_path, capsys, extra) -> None:
    args, _output, _site = _configure(monkeypatch, tmp_path)
    assert checker.main(args + extra) == 2
    assert "code=manifest-output-arguments-invalid" in capsys.readouterr().err


def test_blocked_gate_does_not_leak_path_or_marker(
    monkeypatch, tmp_path, capsys
) -> None:
    args, _output, _site = _configure(monkeypatch, tmp_path)

    def blocked(*_args, **_kwargs):
        raise PublicSiteError("rendered-exposure-blocked")

    monkeypatch.setattr(checker, "build_public_site_manifest", blocked)
    assert checker.main(args) == 1
    captured = capsys.readouterr()
    assert "code=rendered-exposure-blocked" in captured.err
    assert str(tmp_path) not in captured.out + captured.err


def test_manifest_cannot_be_written_inside_scanned_site(
    monkeypatch, tmp_path, capsys
) -> None:
    args, _output, site = _configure(monkeypatch, tmp_path)
    output = site / "manifest.json"
    assert (
        checker.main(args + ["--manifest-output", str(output), "--write-manifest"]) == 1
    )
    assert "code=manifest-output-inside-site" in capsys.readouterr().err
    assert not output.exists()


def test_failed_manifest_write_removes_partial_output(
    monkeypatch, tmp_path, capsys
) -> None:
    args, output, _site = _configure(monkeypatch, tmp_path)
    if not checker._SECURE_DIR_FD_WRITE_SUPPORTED:
        pytest.skip("secure dir-fd output is unavailable")

    def fail_sync(_descriptor):
        raise OSError("synthetic fsync failure")

    monkeypatch.setattr(checker.os, "fsync", fail_sync)
    write_args = args + ["--manifest-output", str(output), "--write-manifest"]
    assert checker.main(write_args) == 1
    assert "code=manifest-output-unavailable" in capsys.readouterr().err
    assert not output.exists()


def test_input_symlink_is_rejected_when_supported(
    monkeypatch, tmp_path, capsys
) -> None:
    args, _output, _site = _configure(monkeypatch, tmp_path)
    target = Path(args[3])
    actual = tmp_path / "actual.json"
    actual.write_text("{}", encoding="utf-8")
    target.unlink()
    try:
        target.symlink_to(actual)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    assert checker.main(args) == 1
    assert "code=public-input-unavailable" in capsys.readouterr().err
