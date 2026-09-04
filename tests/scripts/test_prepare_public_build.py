"""public build準備CLIの合成テスト。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import scripts.prepare_public_build as preparer

PROJECT_ROOT = Path(__file__).parent.parent.parent
INPUT_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_input"
    / "approved_synthetic_input.json"
)


def test_prepare_writes_public_source_and_two_temp_configs(tmp_path, capsys) -> None:
    output = tmp_path / "public-build"
    assert (
        preparer.main(["--public-input", str(INPUT_PATH), "--output-root", str(output)])
        == 0
    )
    captured = capsys.readouterr()
    assert "status=prepared file_count=6" in captured.out
    assert str(tmp_path) not in captured.out + captured.err
    assert (output / "source" / "timelines" / "index.md").is_file()
    assert (output / "manifests").is_dir()
    for name, expected_site in (
        ("mkdocs-public.yml", "site-mkdocs"),
        ("zensical-public.yml", "site-zensical"),
    ):
        config = yaml.safe_load((output / name).read_text(encoding="utf-8"))
        assert config["docs_dir"] == "source"
        assert config["site_dir"] == expected_site


def test_prepare_is_no_clobber_and_errors_are_anonymous(tmp_path, capsys) -> None:
    output = tmp_path / "public-build"
    args = ["--public-input", str(INPUT_PATH), "--output-root", str(output)]
    assert preparer.main(args) == 0
    assert preparer.main(args) == 1
    captured = capsys.readouterr()
    assert "code=public-build-output-exists" in captured.err
    assert str(tmp_path) not in captured.out + captured.err


def test_output_inside_repository_is_rejected(capsys) -> None:
    output = PROJECT_ROOT / "workspace" / "synthetic-public-build"
    assert (
        preparer.main(["--public-input", str(INPUT_PATH), "--output-root", str(output)])
        == 1
    )
    assert "code=public-build-output-inside-repository" in capsys.readouterr().err
    assert not output.exists()


def test_invalid_and_symlink_input_are_rejected_when_supported(
    tmp_path, capsys
) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({}), encoding="utf-8")
    output = tmp_path / "invalid-output"
    assert (
        preparer.main(["--public-input", str(invalid), "--output-root", str(output)])
        == 1
    )
    assert not output.exists()

    link = tmp_path / "input-link.json"
    try:
        link.symlink_to(INPUT_PATH)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    assert (
        preparer.main(["--public-input", str(link), "--output-root", str(output)]) == 1
    )
    assert "code=public-build-input-unavailable" in capsys.readouterr().err
