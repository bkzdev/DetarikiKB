"""Internal Review Evidence Packet operations CLI の合成・安全境界テスト。

実データや実raw DECは一切使わない。統合テストはgitignore済み固定root内に
既知のopaque packetIdだけを一時配置し、テストが作成した正確なdirectoryだけを
cleanupする。root全体の削除・列挙には依存しない。
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "manage_internal_review_evidence_packets.py"
FIXTURE = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "internal_review_evidence_packet"
    / "valid_bundle"
)
PACKET_ROOT = PROJECT_ROOT / "workspace" / "review_packets" / "evidence"

ACTIVE_PACKET = "erp-20990101T000000Z-a1b2c3d4"
EXPIRED_PACKET = "erp-20990102T000000Z-b1c2d3e4"
SECOND_PACKET = "erp-20990103T000000Z-c1d2e3f4"
RAW_MARKER = "SENSITIVE_PACKET_RAW_MARKER"
INTERNAL_MARKER = "SENSITIVE_INTERNAL_ID_MARKER"
ABSOLUTE_MARKER = r"C:\\secret\\sensitive-source.dec"


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _load_module():
    spec = importlib.util.spec_from_file_location("packet_operations", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _refresh_component_digest(bundle: Path, relative_path: str) -> None:
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256((bundle / relative_path).read_bytes()).hexdigest()
    for component in manifest["components"]:
        if component["relativePath"] == relative_path:
            component["sha256"] = digest
            break
    else:
        raise AssertionError(f"component not found: {relative_path}")
    _write_json(manifest_path, manifest)


def _install_bundle(packet_id: str, *, expired: bool = False) -> Path:
    """既存fixture本体を触らず、固定ignored root内に有効なbundleを複製する。"""
    destination = PACKET_ROOT / packet_id
    assert not destination.exists(), f"test packet already exists: {packet_id}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, destination)

    manifest_path = destination / "manifest.json"
    report_path = destination / "reports" / "validation.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest["packetId"] = packet_id
    report["packetId"] = packet_id
    if expired:
        manifest["createdAt"] = "2000-01-01T00:00:00Z"
        manifest["expiresAt"] = "2000-01-02T00:00:00Z"
    _write_json(report_path, report)
    _write_json(manifest_path, manifest)
    _refresh_component_digest(destination, "reports/validation.json")
    return destination


def _remove_exact(path: Path) -> None:
    """テストが作成したopaque packet directoryだけを削除する。"""
    assert path.parent == PACKET_ROOT
    assert path.name.startswith(("erp-", ".tmp-", "unknown-"))
    if path.exists():
        shutil.rmtree(path)


def _tree_snapshot(root: Path) -> tuple[dict[str, bytes], int, str]:
    files = {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }
    return (
        files,
        sum(len(value) for value in files.values()),
        hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest(),
    )


def _assert_sensitive_not_echoed(result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    for marker in (RAW_MARKER, INTERNAL_MARKER, ABSOLUTE_MARKER):
        assert marker not in output
    assert "Traceback" not in output


def test_inventory_missing_root_succeeds_without_creating_it(
    monkeypatch: pytest.MonkeyPatch,
):
    """inventoryはrootが未作成でも副作用なく空集計を返す。"""
    module = _load_module()
    # repo外のtmp_pathではなく、既にignoreされているworkspace/local_inputs配下を
    # 使う。これによりGit boundaryも実運用と同じ経路で確認できる。
    missing_root = (
        PROJECT_ROOT
        / "workspace"
        / "local_inputs"
        / "evidence_packet_operations_tests"
        / "missing-root"
    )
    if missing_root.exists():
        shutil.rmtree(missing_root)
    monkeypatch.setattr(module, "_PACKET_ROOT", missing_root)

    assert module.main(["inventory"]) == 0
    assert not missing_root.exists()


def test_inventory_empty_root_succeeds_without_creating_packets(
    monkeypatch: pytest.MonkeyPatch,
):
    module = _load_module()
    empty_root = (
        PROJECT_ROOT
        / "workspace"
        / "local_inputs"
        / "evidence_packet_operations_tests"
        / "empty-root"
    )
    if empty_root.exists():
        shutil.rmtree(empty_root)
    empty_root.mkdir(parents=True)
    monkeypatch.setattr(module, "_PACKET_ROOT", empty_root)
    try:
        assert module.main(["inventory"]) == 0
        assert list(empty_root.iterdir()) == []
    finally:
        empty_root.rmdir()


def test_inventory_reports_active_and_expired_bundles_as_safe_aggregates():
    active = _install_bundle(ACTIVE_PACKET)
    expired = _install_bundle(EXPIRED_PACKET, expired=True)
    try:
        result = _run_cli("inventory")

        assert result.returncode == 0, result.stderr
        output = result.stdout + result.stderr
        for packet_id, expiry in (
            (ACTIVE_PACKET, "active"),
            (EXPIRED_PACKET, "expired"),
        ):
            assert f"packet={packet_id}" in output
            assert f"expiry={expiry}" in output
        active_files, active_bytes, active_digest = _tree_snapshot(active)
        assert "stories=1" in output
        assert "entries=1" in output
        assert f"components={len(active_files) - 1}" in output
        assert f"bytes={active_bytes}" in output
        assert f"manifestSha256={active_digest}" in output
        assert (
            "mode=inventory status=ok packets=2 valid=2 invalid=0 expired=1" in output
        )
        _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(active)
        _remove_exact(expired)


def test_inventory_invalid_bundle_fails_without_echoing_sensitive_manifest_values():
    packet = _install_bundle(ACTIVE_PACKET)
    try:
        manifest_path = packet / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["generatorVersion"] = (
            f"{RAW_MARKER} {INTERNAL_MARKER} {ABSOLUTE_MARKER}"
        )
        _write_json(manifest_path, manifest)

        result = _run_cli("inventory")

        assert result.returncode == 1
        output = result.stdout + result.stderr
        assert "status=invalid" in output
        assert "mode=inventory status=invalid" in output
        _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(packet)


@pytest.mark.parametrize(
    "name",
    [
        "unknown-SENSITIVE_PACKET_RAW_MARKER",
        ".tmp-erp-20990104T000000Z-d1e2f3a4",
    ],
)
def test_inventory_rejects_unrecognized_or_temporary_direct_child_without_echoing_name(
    name: str,
):
    direct_child = PACKET_ROOT / name
    assert not direct_child.exists()
    direct_child.mkdir(parents=True)
    try:
        result = _run_cli("inventory")

        assert result.returncode == 2
        output = result.stdout + result.stderr
        assert name not in output
        assert "mode=inventory status=config-error" in output
        _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(direct_child)


def test_cleanup_dry_run_is_byte_for_byte_unchanged_and_reports_exact_aggregates():
    packet = _install_bundle(ACTIVE_PACKET)
    try:
        before = _tree_snapshot(packet)
        result = _run_cli("cleanup", "--packet-id", ACTIVE_PACKET)

        assert result.returncode == 0, result.stderr
        assert _tree_snapshot(packet) == before
        output = result.stdout + result.stderr
        assert "mode=dry-run" in output
        assert f"packet={ACTIVE_PACKET}" in output
        assert "deleted=false" in output
        assert "stories=1" in output
        assert "entries=1" in output
        assert f"components={len(before[0]) - 1}" in output
        assert f"bytes={before[1]}" in output
        assert f"manifestSha256={before[2]}" in output
        _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(packet)


def test_cleanup_execute_removes_only_explicit_packet_and_allows_unexpired_packet():
    selected = _install_bundle(ACTIVE_PACKET)
    untouched = _install_bundle(SECOND_PACKET)
    try:
        result = _run_cli("cleanup", "--packet-id", ACTIVE_PACKET, "--execute")

        assert result.returncode == 0, result.stderr
        assert not selected.exists()
        assert untouched.exists()
        assert "mode=execute" in result.stdout + result.stderr
        assert "deleted=true" in result.stdout + result.stderr
        _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(selected)
        _remove_exact(untouched)


def test_cleanup_rejects_invalid_bundle_missing_and_unsafe_packet_id_without_deleting():
    packet = _install_bundle(ACTIVE_PACKET)
    try:
        story_path = packet / "stories" / "story-0001.json"
        story_path.write_text(
            f'{{"sensitive":"{RAW_MARKER} {INTERNAL_MARKER} {ABSOLUTE_MARKER}"}}',
            encoding="utf-8",
        )
        _refresh_component_digest(packet, "stories/story-0001.json")
        invalid = _run_cli("cleanup", "--packet-id", ACTIVE_PACKET, "--execute")
        assert invalid.returncode == 1
        assert packet.exists()
        _assert_sensitive_not_echoed(invalid)

        missing = _run_cli("cleanup", "--packet-id", SECOND_PACKET, "--execute")
        assert missing.returncode == 2
        _assert_sensitive_not_echoed(missing)

        for unsafe in ("../SENSITIVE_PACKET_RAW_MARKER", "*", r"C:\\secret", ""):
            result = _run_cli("cleanup", "--packet-id", unsafe, "--execute")
            assert result.returncode == 2
            if unsafe:
                assert unsafe not in result.stdout + result.stderr
            _assert_sensitive_not_echoed(result)
    finally:
        _remove_exact(packet)


def test_help_and_unknown_argument_do_not_echo_sensitive_argument_values():
    help_result = _run_cli("cleanup", "--help")
    assert help_result.returncode == 0
    assert "--packet-id" in help_result.stdout

    unsafe = RAW_MARKER
    unknown = _run_cli("inventory", "--unknown", unsafe)
    assert unknown.returncode == 2
    assert unsafe not in unknown.stdout + unknown.stderr
    _assert_sensitive_not_echoed(unknown)


@pytest.mark.parametrize(
    "boundary_code",
    ["path-is-not-git-ignored", "tracked-packet-path-rejected"],
)
def test_cleanup_rejects_nonignored_or_tracked_target_before_delete(
    boundary_code: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """Git境界がnonignored/trackedなら内容を扱わず、対象を残してexit 2にする。"""
    packet = _install_bundle(ACTIVE_PACKET)
    module = _load_module()

    def reject_git_boundary(*_paths: Path) -> None:
        raise module.packet_validator.ConfigError(boundary_code)

    monkeypatch.setattr(module, "_check_git_paths", reject_git_boundary)
    try:
        assert module.main(["cleanup", "--packet-id", ACTIVE_PACKET, "--execute"]) == 2
        assert packet.exists()
        captured = capsys.readouterr()
        output = captured.out + captured.err
        assert f"code={boundary_code}" in output
        _assert_sensitive_not_echoed(
            subprocess.CompletedProcess([], 2, stdout=output, stderr="")
        )
    finally:
        _remove_exact(packet)


def test_cleanup_execute_refuses_when_predelete_snapshot_changes(
    monkeypatch: pytest.MonkeyPatch,
):
    """最初のinspection後にmanifestが変われば、削除前の再inspectionで止める。"""
    packet = _install_bundle(ACTIVE_PACKET)
    module = _load_module()
    original_inspect = module._inspect_packet
    calls = 0

    def inspect_then_mutate(packet_id: str):
        nonlocal calls
        result = original_inspect(packet_id)
        calls += 1
        if calls == 1:
            manifest_path = packet / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["generatorVersion"] = "test-fixture-after-first-inspection"
            _write_json(manifest_path, manifest)
        return result

    monkeypatch.setattr(module, "_inspect_packet", inspect_then_mutate)
    try:
        assert module.main(["cleanup", "--packet-id", ACTIVE_PACKET, "--execute"]) == 2
        assert packet.exists()
    finally:
        _remove_exact(packet)


def test_cleanup_execute_rejects_reparse_injected_after_snapshot(
    monkeypatch: pytest.MonkeyPatch,
):
    """削除直前のpreflightでreparse pointになった対象を削除しない。"""
    packet = _install_bundle(ACTIVE_PACKET)
    module = _load_module()
    original_inspect = module._inspect_packet
    original_reparse = module._is_reparse
    calls = 0

    def inspect_then_inject_reparse(packet_id: str):
        nonlocal calls
        result = original_inspect(packet_id)
        calls += 1
        if calls == 2:
            monkeypatch.setattr(
                module,
                "_is_reparse",
                lambda path: path == packet or original_reparse(path),
            )
        return result

    monkeypatch.setattr(module, "_inspect_packet", inspect_then_inject_reparse)
    try:
        assert module.main(["cleanup", "--packet-id", ACTIVE_PACKET, "--execute"]) == 2
        assert packet.exists()
    finally:
        _remove_exact(packet)


def test_cleanup_rejects_broken_link_ancestor_guard_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    """generator由来のlexists-based ancestor検査が失敗したら削除しない。"""
    packet = _install_bundle(ACTIVE_PACKET)
    module = _load_module()
    original_check = module._check_ancestors
    calls = 0

    def reject_during_final_preflight(path: Path) -> None:
        nonlocal calls
        original_check(path)
        calls += 1
        if calls > 4:
            raise module.packet_validator.ConfigError("reparse-point-rejected")

    monkeypatch.setattr(module, "_check_ancestors", reject_during_final_preflight)
    try:
        assert module.main(["cleanup", "--packet-id", ACTIVE_PACKET, "--execute"]) == 2
        assert packet.exists()
    finally:
        _remove_exact(packet)


def test_cleanup_delete_failure_is_safe_config_error_and_keeps_packet(
    monkeypatch: pytest.MonkeyPatch,
):
    packet = _install_bundle(ACTIVE_PACKET)
    module = _load_module()

    def fail_delete(_path: Path) -> None:
        raise PermissionError("do not expose this filesystem detail")

    try:
        # shutil moduleはprocess全体で共有されるため、テストcleanup前に確実に
        # monkeypatchを戻す局所contextを使う。
        with monkeypatch.context() as scoped:
            scoped.setattr(module.shutil, "rmtree", fail_delete)
            assert (
                module.main(["cleanup", "--packet-id", ACTIVE_PACKET, "--execute"]) == 2
            )
        assert packet.exists()
    finally:
        _remove_exact(packet)
