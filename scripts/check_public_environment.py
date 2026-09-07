#!/usr/bin/env python3
"""Public production environmentの保護設定snapshotを匿名検証する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="public environment protection gate")
    parser.add_argument("--environment-json", required=True, type=Path)
    parser.add_argument("--branch-policies-json", required=True, type=Path)
    return parser.parse_args(argv)


def _check_protection(environment: object) -> str | None:
    if not isinstance(environment, dict) or environment.get("name") != "github-pages":
        return "production-environment-invalid"
    rules = environment.get("protection_rules")
    if not isinstance(rules, list):
        return "production-environment-protection-invalid"
    reviewer_rules = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("type") == "required_reviewers"
    ]
    if len(reviewer_rules) != 1:
        return "production-environment-reviewers-invalid"
    reviewer_rule = reviewer_rules[0]
    if reviewer_rule.get("prevent_self_review") is not True:
        return "production-environment-self-review-enabled"
    reviewers = reviewer_rule.get("reviewers")
    if not isinstance(reviewers, list) or not reviewers:
        return "production-environment-reviewers-invalid"
    if environment.get("can_admins_bypass") is not False:
        return "production-environment-admin-bypass-enabled"
    if environment.get("deployment_branch_policy") != {
        "protected_branches": False,
        "custom_branch_policies": True,
    }:
        return "production-environment-branch-mode-invalid"
    return None


def _check_branch_policy(branch_policies: object) -> str | None:
    if not isinstance(branch_policies, dict):
        return "production-environment-branch-policy-invalid"
    policies = branch_policies.get("branch_policies")
    if not isinstance(policies, list) or len(policies) != 1:
        return "production-environment-branch-policy-invalid"
    policy = policies[0]
    if not isinstance(policy, dict) or policy.get("name") != "main":
        return "production-environment-branch-policy-invalid"
    if policy.get("type", "branch") != "branch":
        return "production-environment-branch-policy-invalid"
    return None


def check_environment(environment: object, branch_policies: object) -> str | None:
    """Return an anonymous blocking code, or ``None`` for the fixed policy."""

    return _check_protection(environment) or _check_branch_policy(branch_policies)


def _read_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(argv)
    try:
        environment = _read_json(arguments.environment_json)
        branch_policies = _read_json(arguments.branch_policies_json)
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("status=blocked code=production-environment-snapshot-invalid")
        return 1
    code = check_environment(environment, branch_policies)
    if code is not None:
        print(f"status=blocked code={code}")
        return 1
    print("status=clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
