from __future__ import annotations

import json

from scripts.check_public_environment import check_environment, main


def _environment() -> dict:
    return {
        "name": "github-pages",
        "can_admins_bypass": False,
        "protection_rules": [
            {
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [{"type": "User", "reviewer": {"id": 1}}],
            },
            {"type": "branch_policy"},
        ],
        "deployment_branch_policy": {
            "protected_branches": False,
            "custom_branch_policies": True,
        },
    }


def _branch_policies() -> dict:
    return {"total_count": 1, "branch_policies": [{"name": "main", "type": "branch"}]}


def test_check_environment_accepts_fixed_protected_configuration() -> None:
    assert check_environment(_environment(), _branch_policies()) is None


def test_check_environment_rejects_missing_or_weak_protection() -> None:
    mutations = [
        ("production-environment-invalid", lambda env: env.update(name="other")),
        (
            "production-environment-reviewers-invalid",
            lambda env: env.update(protection_rules=[]),
        ),
        (
            "production-environment-self-review-enabled",
            lambda env: env["protection_rules"][0].update(prevent_self_review=False),
        ),
        (
            "production-environment-reviewers-invalid",
            lambda env: env["protection_rules"][0].update(reviewers=[]),
        ),
        (
            "production-environment-admin-bypass-enabled",
            lambda env: env.update(can_admins_bypass=True),
        ),
        (
            "production-environment-branch-mode-invalid",
            lambda env: env.update(deployment_branch_policy=None),
        ),
    ]
    for expected, mutate in mutations:
        environment = _environment()
        mutate(environment)
        assert check_environment(environment, _branch_policies()) == expected


def test_check_environment_rejects_nonexclusive_main_branch_policy() -> None:
    for policies in (
        {"branch_policies": []},
        {"branch_policies": [{"name": "main"}, {"name": "release/*"}]},
        {"branch_policies": [{"name": "release/*"}]},
        {"branch_policies": [{"name": "main", "type": "tag"}]},
    ):
        assert (
            check_environment(_environment(), policies)
            == "production-environment-branch-policy-invalid"
        )


def test_main_reads_snapshots_without_exposing_them(tmp_path, capsys) -> None:
    environment_path = tmp_path / "environment.json"
    policies_path = tmp_path / "policies.json"
    environment_path.write_text(json.dumps(_environment()), encoding="utf-8")
    policies_path.write_text(json.dumps(_branch_policies()), encoding="utf-8")
    assert (
        main(
            [
                "--environment-json",
                str(environment_path),
                "--branch-policies-json",
                str(policies_path),
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "status=clean\n"


def test_main_rejects_invalid_snapshot_anonymously(tmp_path, capsys) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("not-json", encoding="utf-8")
    assert (
        main(
            [
                "--environment-json",
                str(invalid),
                "--branch-policies-json",
                str(invalid),
            ]
        )
        == 1
    )
    assert capsys.readouterr().out == (
        "status=blocked code=production-environment-snapshot-invalid\n"
    )
