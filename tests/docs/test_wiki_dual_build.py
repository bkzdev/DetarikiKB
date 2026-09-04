"""Zensical exact pinとWiki dual-build標準化の構成契約を固定する。"""

import tomllib
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _load_yaml(path: str) -> dict:
    return yaml.safe_load(_read(path))


def test_zensical_is_exactly_pinned_and_locked() -> None:
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as file:
        project = tomllib.load(file)
    with (PROJECT_ROOT / "uv.lock").open("rb") as file:
        lock = tomllib.load(file)

    assert "zensical==0.0.57" in project["dependency-groups"]["dev"]
    zensical = [package for package in lock["package"] if package["name"] == "zensical"]
    assert len(zensical) == 1
    assert zensical[0]["version"] == "0.0.57"

    project_lock = next(
        package for package in lock["package"] if package["name"] == "detarikikb"
    )
    zensical_metadata = next(
        dependency
        for dependency in project_lock["metadata"]["requires-dev"]["dev"]
        if dependency["name"] == "zensical"
    )
    assert zensical_metadata["specifier"] == "==0.0.57"


def test_dual_build_configs_share_public_contract() -> None:
    mkdocs = _load_yaml("mkdocs.yml")
    zensical = _load_yaml("zensical.yml")

    for key in ("site_name", "site_description", "docs_dir", "nav"):
        assert zensical[key] == mkdocs[key]
    assert zensical["theme"] == {"name": "material", "variant": "classic"}
    assert zensical["plugins"] == ["search"]
    assert zensical["site_dir"] == "site_zensical"


def test_ci_and_standard_validation_run_both_generators() -> None:
    workflow = _read(".github/workflows/ci.yml")
    playbook = _read("docs/runbooks/AI_PR_Playbook.md")
    zensical_command = "uv run zensical build --strict --clean -f zensical.yml"

    for content in (workflow, playbook):
        assert "uv run mkdocs build --strict" in content
        assert zensical_command in content
    assert workflow.index("MkDocs build") < workflow.index("Zensical build")


def test_runbook_and_ignore_rules_keep_generated_sites_out_of_git() -> None:
    runbook = _read("docs/runbooks/Wiki_Dual_Build.md")
    gitignore = _read(".gitignore")

    for required in (
        "zensical==0.0.57",
        "docs/site_preview/",
        "site/` / `site_zensical/",
        "public-safe構造化入力",
        "artifact upload",
        "production deploy",
    ):
        assert required in runbook
    assert "site/" in gitignore
    assert "site_zensical/" in gitignore
