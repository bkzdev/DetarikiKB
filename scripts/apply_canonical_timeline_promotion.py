#!/usr/bin/env python3
"""Canonical Timeline promotion planを固定local artifactへ安全に反映する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry, Resource

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.canonical_timeline_consistency import (  # noqa: E402
    validate_canonical_timeline_consistency,
)
from agents.extractor.canonical_timeline_promotion_plan import (  # noqa: E402
    validate_canonical_timeline_promotion_plan_consistency,
)
from agents.extractor.canonical_timeline_promotion_preflight import (  # noqa: E402
    _build_preflight_document,
    preflight_canonical_timeline_promotion,
)
from scripts import (  # noqa: E402
    validate_canonical_timeline_review_packet as packet_validator,  # noqa: E402
)

_WORKSPACE_ROOT = _PROJECT_ROOT / "workspace" / "canonical_timeline"
_TARGET = _WORKSPACE_ROOT / "canonical_timeline.json"
_HISTORY = _WORKSPACE_ROOT / "history"
_PLAN_ROOT = _WORKSPACE_ROOT / "plans"
_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "canonical_timeline"
_INPUT_NAME = re.compile(r"^canonical_timeline_[a-z0-9][a-z0-9_-]{0,63}\.json$")
_SCHEMA_PATHS = tuple(
    _PROJECT_ROOT / "schemas" / name
    for name in (
        "canonical_timeline.schema.json",
        "canonical_timeline_review_packet.schema.json",
        "canonical_timeline_promotion_plan.schema.json",
    )
)


class PromotionError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class ExecutionResult:
    current_digest: str
    proposed_digest: str
    node_count: int
    edge_count: int
    warnings: tuple[str, ...] = ()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Canonical Timeline promotionを固定workspaceへ適用する"
    )
    parser.add_argument("--plan-name", required=True)
    parser.add_argument("--packet-name", required=True)
    parser.add_argument("--create-seed", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-artifact-sha256")
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-packet-sha256")
    return parser.parse_args(argv)


def _is_reparse(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as exc:
        raise PromotionError("path-inspection-failed") from exc
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _relative(path: Path) -> Path:
    try:
        return path.absolute().relative_to(_PROJECT_ROOT.absolute())
    except ValueError as exc:
        raise PromotionError("input-outside-repository") from exc


def _check_ancestors(path: Path) -> None:
    relative = _relative(path)
    current = _PROJECT_ROOT
    if _is_reparse(current):
        raise PromotionError("reparse-point-rejected")
    for part in relative.parts:
        current = current / part
        if not current.exists():
            break
        if _is_reparse(current):
            raise PromotionError("reparse-point-rejected")


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise PromotionError("git-command-failed") from exc


def _check_untracked(path: Path, *, target: bool = False) -> None:
    relative = _relative(path)
    _check_ancestors(path)
    text = relative.as_posix()
    tracked = _git(["ls-files", "--", text])
    if tracked.returncode or tracked.stdout.strip():
        raise PromotionError("tracked-path-rejected")
    ignored = _git(["check-ignore", "--no-index", "-q", "--", text])
    if ignored.returncode:
        raise PromotionError("path-is-not-git-ignored")
    if not target and (not path.is_file() or _is_reparse(path)):
        raise PromotionError("input-file-invalid")


def _safe_workspace_input(name: str, root: Path) -> Path:
    if not _INPUT_NAME.fullmatch(name):
        raise PromotionError("input-name-invalid")
    path = root / name
    _check_untracked(path)
    try:
        path.resolve().relative_to(_PROJECT_ROOT)
    except (OSError, ValueError) as exc:
        raise PromotionError("input-outside-repository") from exc
    return path


def _load_json(path: Path, code: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromotionError(code) from exc
    if not isinstance(value, dict):
        raise PromotionError(code)
    return value


def _read_json_bytes(path: Path, code: str) -> tuple[dict[str, Any], bytes]:
    try:
        payload = path.read_bytes()
        value = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PromotionError(code) from exc
    if not isinstance(value, dict):
        raise PromotionError(code)
    return value, payload


def _validators() -> dict[str, Draft7Validator]:
    schemas = [_load_json(path, "schema-unavailable") for path in _SCHEMA_PATHS]
    try:
        registry = Registry().with_resources(
            [(schema["$id"], Resource.from_contents(schema)) for schema in schemas]
        )
        return {
            schema["properties"]["documentType"]["const"]: Draft7Validator(
                schema, registry=registry, format_checker=FormatChecker()
            )
            for schema in schemas
        }
    except Exception as exc:  # schema loading must fail closed
        raise PromotionError("schema-unavailable") from exc


def _schema_valid(validator: Draft7Validator, value: Any) -> bool:
    try:
        return not list(validator.iter_errors(value))
    except Exception:
        return False


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _serialize(document: dict[str, Any]) -> bytes:
    return (
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode()


def _validate_inputs(
    plan: dict[str, Any], packet: dict[str, Any], validators: dict[str, Draft7Validator]
) -> tuple[str, ...]:
    if not _schema_valid(validators["canonical_timeline_promotion_plan"], plan):
        raise PromotionError("plan-schema-invalid")
    if not _schema_valid(validators["canonical_timeline_review_packet"], packet):
        raise PromotionError("packet-schema-invalid")
    packet_result = packet_validator.validate_packet_document(packet)
    if not packet_result.is_valid:
        raise PromotionError("packet-semantic-invalid")
    if validate_canonical_timeline_promotion_plan_consistency(plan, packet):
        raise PromotionError("plan-semantic-invalid")
    return packet_result.warning_codes


def _candidate(plan: dict[str, Any], existing: dict[str, Any] | None) -> dict[str, Any]:
    baseline = existing or {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline",
        "scopeStoryCategory": "EVT",
        "visibility": "internal_only",
        "nodes": [],
        "edges": [],
    }
    preflight = preflight_canonical_timeline_promotion(plan, baseline)
    if preflight["status"] != "clean":
        raise PromotionError("preflight-blocked")
    document, _ = _build_preflight_document(plan, baseline)
    return document


def _validate_result(
    document: dict[str, Any], validators: dict[str, Draft7Validator]
) -> None:
    if not _schema_valid(validators["canonical_timeline"], document):
        raise PromotionError("result-schema-invalid")
    if validate_canonical_timeline_consistency(document):
        raise PromotionError("result-semantic-invalid")


def _project_from_paths(
    plan_path: Path,
    packet_path: Path,
    validators: dict[str, Draft7Validator],
    existing: dict[str, Any] | None,
    expected_plan: str,
    expected_packet: str,
) -> tuple[dict[str, Any], bytes, tuple[str, ...]]:
    _check_untracked(plan_path)
    _check_untracked(packet_path)
    plan, plan_bytes = _read_json_bytes(plan_path, "plan-json-invalid")
    packet, packet_bytes = _read_json_bytes(packet_path, "packet-json-invalid")
    if _digest(plan_bytes) != expected_plan or _digest(packet_bytes) != expected_packet:
        raise PromotionError("input-digest-mismatch")
    warnings = _validate_inputs(plan, packet, validators)
    document = _candidate(plan, existing)
    _validate_result(document, validators)
    return document, _serialize(document), warnings


def _prepare_target() -> None:
    _WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    _HISTORY.mkdir(parents=True, exist_ok=True)
    _check_untracked(_TARGET, target=True)
    _check_untracked(_HISTORY, target=True)


def _write_temp(parent: Path, payload: bytes, name: str) -> Path:
    path = parent / f".{name}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def _seed(
    payload: bytes, document: dict[str, Any], warnings: tuple[str, ...]
) -> ExecutionResult:
    if _TARGET.exists():
        raise PromotionError("seed-target-exists")
    temp = _write_temp(_WORKSPACE_ROOT, payload, _TARGET.name)
    try:
        os.link(temp, _TARGET)
    except FileExistsError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise PromotionError("seed-target-exists") from exc
    except OSError as exc:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise PromotionError("atomic-publish-failed") from exc
    cleanup_warning: str | None = None
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        cleanup_warning = "seed-applied-temporary-cleanup-failed"
    return ExecutionResult(
        "none",
        _digest(payload),
        len(document["nodes"]),
        len(document["edges"]),
        warnings + ((cleanup_warning,) if cleanup_warning else ()),
    )


def _update(  # noqa: C901
    expected: str,
    expected_plan: str,
    expected_packet: str,
    plan_path: Path,
    packet_path: Path,
    validators: dict[str, Draft7Validator],
) -> ExecutionResult:
    if not _TARGET.is_file() or _is_reparse(_TARGET):
        raise PromotionError("artifact-unavailable")
    try:
        old = _TARGET.read_bytes()
    except OSError as exc:
        raise PromotionError("artifact-read-failed") from exc
    old_digest = _digest(old)
    if old_digest != expected:
        raise PromotionError("artifact-digest-mismatch")
    lock = _WORKSPACE_ROOT / ".canonical_timeline.lock"
    try:
        lock_fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise PromotionError("artifact-lock-unavailable") from exc
    nonce = secrets.token_hex(16).encode("ascii")
    applied = False
    cleanup_warning: str | None = None
    temporary_cleanup_warning: str | None = None
    try:
        with os.fdopen(lock_fd, "wb") as lock_file:
            lock_file.write(nonce)
            lock_file.flush()
            os.fsync(lock_file.fileno())
        _check_untracked(_TARGET, target=True)
        _check_untracked(_HISTORY, target=True)
        old = _TARGET.read_bytes()
        if _digest(old) != expected:
            raise PromotionError("artifact-digest-mismatch")
        existing = _load_json(_TARGET, "artifact-json-invalid")
        if not _schema_valid(validators["canonical_timeline"], existing) or (
            validate_canonical_timeline_consistency(existing)
        ):
            raise PromotionError("artifact-invalid")
        document, payload, input_warnings = _project_from_paths(
            plan_path, packet_path, validators, existing, expected_plan, expected_packet
        )
        old_digest = _digest(old)
        snapshot = _HISTORY / f"{old_digest}.json"
        if snapshot.exists():
            if (
                not snapshot.is_file()
                or _is_reparse(snapshot)
                or snapshot.read_bytes() != old
            ):
                raise PromotionError("history-snapshot-conflict")
        else:
            temp_snapshot = _write_temp(_HISTORY, old, snapshot.name)
            try:
                os.link(temp_snapshot, snapshot)
            finally:
                temp_snapshot.unlink(missing_ok=True)
        temp = _write_temp(_WORKSPACE_ROOT, payload, _TARGET.name)
        try:
            _check_untracked(_TARGET, target=True)
            _check_untracked(_HISTORY, target=True)
            if _digest(_TARGET.read_bytes()) != expected:
                raise PromotionError("artifact-digest-mismatch")
            os.replace(temp, _TARGET)
            applied = True
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError as exc:
                if applied:
                    temporary_cleanup_warning = (
                        "update-applied-temporary-cleanup-failed"
                    )
                else:
                    raise PromotionError("temporary-cleanup-failed") from exc
    finally:
        try:
            if not lock.is_file() or _is_reparse(lock) or lock.read_bytes() != nonce:
                raise PromotionError("lock-ownership-mismatch")
            lock.unlink()
        except OSError as exc:
            if applied:
                cleanup_warning = "update-applied-lock-cleanup-failed"
            else:
                raise PromotionError("lock-cleanup-failed") from exc
        except PromotionError:
            if applied:
                cleanup_warning = "update-applied-lock-ownership-mismatch"
            else:
                raise
    return ExecutionResult(
        old_digest,
        _digest(payload),
        len(document["nodes"]),
        len(document["edges"]),
        input_warnings
        + tuple(
            warning
            for warning in (temporary_cleanup_warning, cleanup_warning)
            if warning
        ),
    )


def main(argv: list[str] | None = None) -> int:  # noqa: C901
    try:
        args = parse_args(argv)
        if args.create_seed and args.expected_artifact_sha256:
            raise PromotionError("seed-expected-digest-forbidden")
        if args.execute and (
            not args.expected_plan_sha256 or not args.expected_packet_sha256
        ):
            raise PromotionError("expected-input-sha256-required")
        if not args.create_seed and args.execute and not args.expected_artifact_sha256:
            raise PromotionError("expected-artifact-sha256-required")
        plan_path = _safe_workspace_input(args.plan_name, _PLAN_ROOT)
        packet_path = _safe_workspace_input(args.packet_name, _PACKET_ROOT)
        plan, plan_bytes = _read_json_bytes(plan_path, "plan-json-invalid")
        packet, packet_bytes = _read_json_bytes(packet_path, "packet-json-invalid")
        plan_digest = _digest(plan_bytes)
        packet_digest = _digest(packet_bytes)
        if args.execute and (
            plan_digest != args.expected_plan_sha256
            or packet_digest != args.expected_packet_sha256
        ):
            raise PromotionError("input-digest-mismatch")
        validators = _validators()
        warnings = _validate_inputs(plan, packet, validators)
        existing: dict[str, Any] | None = None
        current_digest = "none"
        if args.create_seed:
            _check_untracked(_TARGET, target=True)
            if _TARGET.exists():
                raise PromotionError("seed-target-exists")
        else:
            _check_untracked(_TARGET, target=True)
            if not _TARGET.exists():
                raise PromotionError("artifact-unavailable")
            existing = _load_json(_TARGET, "artifact-json-invalid")
            try:
                current_digest = _digest(_TARGET.read_bytes())
            except OSError as exc:
                raise PromotionError("artifact-read-failed") from exc
            if not _schema_valid(
                validators["canonical_timeline"], existing
            ) or validate_canonical_timeline_consistency(existing):
                raise PromotionError("artifact-invalid")
        document = _candidate(plan, existing)
        _validate_result(document, validators)
        payload = _serialize(document)
        execution_result: ExecutionResult | None = None
        if args.execute:
            _prepare_target()
            if args.create_seed:
                document, payload, warnings = _project_from_paths(
                    plan_path,
                    packet_path,
                    validators,
                    None,
                    args.expected_plan_sha256,
                    args.expected_packet_sha256,
                )
                execution_result = _seed(payload, document, warnings)
            else:
                execution_result = _update(
                    args.expected_artifact_sha256,
                    args.expected_plan_sha256,
                    args.expected_packet_sha256,
                    plan_path,
                    packet_path,
                    validators,
                )
        if execution_result:
            warnings = execution_result.warnings
            current_digest = execution_result.current_digest
            payload = b""
            proposed_digest = execution_result.proposed_digest
            node_count, edge_count = (
                execution_result.node_count,
                execution_result.edge_count,
            )
        else:
            proposed_digest = _digest(payload)
            node_count, edge_count = len(document["nodes"]), len(document["edges"])
        mode = "written" if args.execute else "dry_run"
        print(
            "[canonical-timeline-promotion] "
            f"status={mode} plan_sha256={plan_digest} packet_sha256={packet_digest} "
            f"current_artifact_sha256={current_digest} "
            f"proposed_artifact_sha256={proposed_digest} "
            f"nodes={node_count} edges={edge_count}"
        )
        for warning in warnings:
            print(
                f"[canonical-timeline-promotion] status=warning code={warning}",
                file=sys.stderr,
            )
        return 0
    except PromotionError as exc:
        print(
            f"[canonical-timeline-promotion] status=error code={exc.code}",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError):
        print(
            "[canonical-timeline-promotion] status=error code=promotion-failed",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
