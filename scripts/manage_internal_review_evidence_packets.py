#!/usr/bin/env python3
"""Internal Review Evidence Packet の安全なinventory/cleanup CLI。

Packetにはraw本文と内部IDが含まれうる。このCLIは固定root配下のopaqueな
packetIdだけを扱い、consoleにはsafe metadataと固定error codeだけを出す。
cleanupはdry-runが既定で、--executeなしではfilesystemを変更しない。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

packet_validator = importlib.import_module(
    "scripts.validate_internal_review_evidence_packet"
)
packet_generator = importlib.import_module(
    "scripts.generate_internal_review_evidence_packet"
)


_PACKET_ROOT = _PROJECT_ROOT / "workspace" / "review_packets" / "evidence"


def _configure_console_encoding() -> None:
    """Windowsのlocaleに依存せず、safe console出力をUTF-8に固定する。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


class SafeArgumentParser(argparse.ArgumentParser):
    """任意引数の値をerror messageへ含めないArgumentParser。"""

    def error(self, message: str) -> None:
        del message
        self.exit(
            2,
            "[packet-operations] status=config-error code=cli-arguments-invalid\n",
        )


class SinglePacketIdAction(argparse.Action):
    """cleanupが一度に受け取るpacketIdを1件に固定する。"""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str,
        option_string: str | None = None,
    ) -> None:
        del option_string
        if getattr(namespace, self.dest, None) is not None:
            parser.error("duplicate packet id")
        setattr(namespace, self.dest, values)


@dataclass(frozen=True)
class PacketMeasurement:
    packet_id: str
    created_at: str
    expires_at: str
    expiry: str
    story_count: int
    entry_count: int
    component_count: int
    bundle_bytes: int
    manifest_sha256: str
    warning_count: int
    error_count: int

    def snapshot(self) -> tuple[str, str, str, int, int, int, int, str, int, int]:
        return (
            self.created_at,
            self.expires_at,
            self.expiry,
            self.story_count,
            self.entry_count,
            self.component_count,
            self.bundle_bytes,
            self.manifest_sha256,
            self.warning_count,
            self.error_count,
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = SafeArgumentParser(
        description="Internal Review Evidence Packetを安全にinventory/cleanupする"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", add_help=True)
    cleanup = commands.add_parser("cleanup", add_help=True)
    cleanup.add_argument(
        "--packet-id",
        required=True,
        action=SinglePacketIdAction,
        help="固定root直下のopaque packetIdを1件だけ指定する",
    )
    cleanup.add_argument(
        "--execute",
        action="store_true",
        help="実際にPacket directoryを削除する（既定はdry-run）",
    )
    return parser.parse_args(argv)


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _call_generator_guard(name: str, *args: Any) -> Any:
    """generatorの堅牢なfilesystem guardを共通のConfigErrorへ変換する。"""
    try:
        return getattr(packet_generator, name)(*args)
    except packet_generator.ConfigError as exc:
        raise packet_validator.ConfigError(exc.code) from exc


def _check_ancestors(path: Path) -> None:
    _call_generator_guard("_check_ancestors", path)


def _check_git_paths(*paths: Path) -> None:
    _call_generator_guard("_check_git_paths", paths)


def _is_reparse(path: Path) -> bool:
    return bool(_call_generator_guard("_is_reparse", path))


def _check_tree_no_links(path: Path) -> None:
    _call_generator_guard("_check_tree_no_links", path)


def _preflight_root() -> bool:
    """固定rootを作らずに検査し、存在するかを返す。"""
    _check_ancestors(_PACKET_ROOT)
    _check_git_paths(_PACKET_ROOT)
    if not _lexists(_PACKET_ROOT):
        return False
    if _is_reparse(_PACKET_ROOT) or not _PACKET_ROOT.is_dir():
        raise packet_validator.ConfigError("packet-root-invalid")
    return True


def _packet_directory(packet_id: str) -> Path:
    if not packet_validator._PACKET_ID_PATTERN.fullmatch(packet_id):
        raise packet_validator.ConfigError("packet-id-invalid")
    return _PACKET_ROOT / packet_id


def _safe_packet_id(packet_id: str) -> str | None:
    if packet_validator._PACKET_ID_PATTERN.fullmatch(packet_id):
        return packet_id
    return None


def _preflight_packet(packet_dir: Path) -> None:
    """既存Packetをbroken linkも含めてfail-closedに検査する。"""
    _check_ancestors(_PACKET_ROOT)
    _check_ancestors(packet_dir)
    try:
        resolved_root = _PACKET_ROOT.resolve()
        resolved_packet = packet_dir.resolve()
        resolved_packet.relative_to(resolved_root)
    except (OSError, ValueError) as exc:
        raise packet_validator.ConfigError("path-outside-fixed-root") from exc
    if not _lexists(packet_dir):
        raise packet_validator.ConfigError("input-not-found")
    if _is_reparse(packet_dir):
        raise packet_validator.ConfigError("reparse-point-rejected")
    if not packet_dir.is_dir():
        raise packet_validator.ConfigError("packet-path-invalid")
    _check_git_paths(_PACKET_ROOT, packet_dir)
    _check_tree_no_links(packet_dir)


def _load_valid_manifest(packet_dir: Path) -> tuple[dict[str, Any], bytes]:
    manifest_path = packet_dir / "manifest.json"
    try:
        payload = manifest_path.read_bytes()
        manifest = json.loads(payload.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise packet_validator.ConfigError("manifest-read-failed") from exc
    if not isinstance(manifest, dict):
        raise packet_validator.ConfigError("manifest-read-failed")
    return manifest, payload


def _measurement_from_valid_packet(
    packet_id: str,
    packet_dir: Path,
    story_count: int,
    entry_count: int,
    warning_count: int,
    expired: bool,
) -> PacketMeasurement:
    manifest, manifest_bytes = _load_valid_manifest(packet_dir)
    components = manifest.get("components")
    if not isinstance(components, list):
        raise packet_validator.ConfigError("manifest-read-failed")

    bundle_bytes = len(manifest_bytes)
    for component in components:
        if not isinstance(component, dict) or not isinstance(
            component.get("relativePath"), str
        ):
            raise packet_validator.ConfigError("manifest-read-failed")
        component_path = packet_validator._safe_component_target(
            packet_dir, component["relativePath"]
        )
        if _is_reparse(component_path) or not component_path.is_file():
            raise packet_validator.ConfigError("component-path-invalid")
        try:
            bundle_bytes += len(component_path.read_bytes())
        except OSError as exc:
            raise packet_validator.ConfigError("component-read-failed") from exc

    expires_at = manifest.get("expiresAt")
    created_at = manifest.get("createdAt")
    if (
        not isinstance(created_at, str)
        or not isinstance(expires_at, str)
        or packet_validator._parse_utc_z(created_at) is None
        or packet_validator._parse_utc_z(expires_at) is None
    ):
        raise packet_validator.ConfigError("manifest-read-failed")
    expiry = "expired" if expired else "active"
    return PacketMeasurement(
        packet_id=packet_id,
        created_at=created_at,
        expires_at=expires_at,
        expiry=expiry,
        story_count=story_count,
        entry_count=entry_count,
        component_count=len(components),
        bundle_bytes=bundle_bytes,
        manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
        warning_count=warning_count,
        error_count=0,
    )


def _inspect_packet(packet_id: str) -> tuple[PacketMeasurement | None, int]:
    packet_dir = _packet_directory(packet_id)
    _preflight_packet(packet_dir)
    result = packet_validator.validate_packet_directory(packet_dir, packet_id)
    if result.errors:
        return None, len(result.errors)
    measurement = _measurement_from_valid_packet(
        packet_id,
        packet_dir,
        result.story_count,
        result.entry_count,
        len(result.warnings),
        any(issue.code == "packet-expired" for issue in result.warnings),
    )
    return measurement, 0


def _print_valid(measurement: PacketMeasurement, *, mode: str | None = None) -> None:
    fields = [
        f"packet={measurement.packet_id}",
        "status=valid",
        f"createdAt={measurement.created_at}",
        f"expiresAt={measurement.expires_at}",
        f"expiry={measurement.expiry}",
        f"stories={measurement.story_count}",
        f"entries={measurement.entry_count}",
        f"components={measurement.component_count}",
        f"bytes={measurement.bundle_bytes}",
        f"manifestSha256={measurement.manifest_sha256}",
        f"warnings={measurement.warning_count}",
        f"errors={measurement.error_count}",
    ]
    if mode is not None:
        fields.append(f"mode={mode}")
        fields.append("deleted=false")
    print("[packet-operations] " + " ".join(fields))


def _print_invalid(packet_id: str, error_count: int) -> None:
    print(
        f"[packet-operations] packet={packet_id} status=invalid "
        f"warnings=0 errors={error_count}"
    )


def _print_config_error(code: str, packet_id: str | None = None) -> None:
    suffix = f" packet={packet_id}" if packet_id is not None else ""
    print(
        f"[packet-operations] status=config-error code={code}{suffix}",
        file=sys.stderr,
    )


def _inventory_children() -> tuple[list[str], int]:
    packet_ids: list[str] = []
    unknown_count = 0
    try:
        with os.scandir(_PACKET_ROOT) as children:
            for child in children:
                child_path = Path(child.path)
                if _is_reparse(child_path):
                    unknown_count += 1
                elif child.is_dir(follow_symlinks=False) and (
                    packet_validator._PACKET_ID_PATTERN.fullmatch(child.name)
                ):
                    packet_ids.append(child.name)
                else:
                    unknown_count += 1
    except OSError as exc:
        raise packet_validator.ConfigError("packet-root-enumeration-failed") from exc
    return sorted(packet_ids), unknown_count


def _inventory() -> int:
    if not _preflight_root():
        print(
            "[packet-operations] mode=inventory status=ok packets=0 "
            "valid=0 invalid=0 expired=0 unrecognized=0"
        )
        return 0

    packet_ids, unknown_count = _inventory_children()
    result_code = 2 if unknown_count else 0
    valid_count = 0
    invalid_count = 0
    expired_count = 0
    config_error_count = 0
    for packet_id in packet_ids:
        try:
            measurement, error_count = _inspect_packet(packet_id)
        except packet_validator.ConfigError as exc:
            _print_config_error(exc.code, packet_id)
            result_code = 2
            config_error_count += 1
            continue
        if measurement is None:
            _print_invalid(packet_id, error_count)
            invalid_count += 1
            if result_code == 0:
                result_code = 1
        else:
            _print_valid(measurement)
            valid_count += 1
            if measurement.expiry == "expired":
                expired_count += 1
    if unknown_count or config_error_count:
        status = "config-error"
    elif invalid_count:
        status = "invalid"
    else:
        status = "ok"
    print(
        f"[packet-operations] mode=inventory status={status} "
        f"packets={len(packet_ids)} valid={valid_count} invalid={invalid_count} "
        f"expired={expired_count} unrecognized={unknown_count}"
    )
    return result_code


def _cleanup(packet_id: str, execute: bool) -> int:
    safe_packet_id = _safe_packet_id(packet_id)
    try:
        measurement, error_count = _inspect_packet(packet_id)
    except packet_validator.ConfigError as exc:
        _print_config_error(exc.code, safe_packet_id)
        return 2
    if measurement is None:
        _print_invalid(packet_id, error_count)
        return 1

    mode = "execute" if execute else "dry-run"
    _print_valid(measurement, mode=mode)
    if not execute:
        return 0

    try:
        current, error_count = _inspect_packet(packet_id)
    except packet_validator.ConfigError as exc:
        _print_config_error(exc.code, safe_packet_id)
        return 2
    if current is None:
        _print_config_error("target-state-changed", safe_packet_id)
        return 2
    if current.snapshot() != measurement.snapshot():
        _print_config_error("target-state-changed", safe_packet_id)
        return 2

    packet_dir = _packet_directory(packet_id)
    try:
        _preflight_packet(packet_dir)
        shutil.rmtree(packet_dir)
        if _lexists(packet_dir):
            raise OSError
    except (packet_validator.ConfigError, OSError) as exc:
        code = (
            exc.code
            if isinstance(exc, packet_validator.ConfigError)
            else "delete-failed"
        )
        _print_config_error(code, safe_packet_id)
        return 2
    print(
        f"[packet-operations] packet={packet_id} status=deleted "
        "mode=execute deleted=true"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    _configure_console_encoding()
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    try:
        if args.command == "inventory":
            return _inventory()
        return _cleanup(args.packet_id, args.execute)
    except packet_validator.ConfigError as exc:
        _print_config_error(exc.code)
        return 2


if __name__ == "__main__":
    sys.exit(main())
