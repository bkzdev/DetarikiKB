#!/usr/bin/env python3
"""Stage Aの明示的cross-story候補からreview packetを安全に構築する。"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from agents.extractor.canonical_timeline_review_packet_builder import (  # noqa: E402
    RETENTION_DAYS,
    PacketBuildError,
    build_canonical_timeline_review_packet,
)
from agents.merger.engine import MergeEngine  # noqa: E402
from agents.merger.input_resolver import resolve_input_entries  # noqa: E402
from scripts import validate_canonical_timeline_review_packet as validator  # noqa: E402


class BuilderConfigError(Exception):
    """内部値をechoしない固定codeの設定・write error。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "検証済みEVENT Stage Aの明示的relative_order 1 story pairを、"
            "pending review packetへ変換する"
        )
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        nargs="+",
        help="Stage A JSON file、directory、globを1つ以上指定",
    )
    parser.add_argument("--recursive", "-r", action="store_true")
    parser.add_argument(
        "--story-pair-index",
        type=int,
        required=True,
        help="決定的に並べたstory pairの1-based index",
    )
    parser.add_argument(
        "--packet-name",
        required=True,
        help="固定workspace root直下の安全なpacket basename",
    )
    parser.add_argument(
        "--review-batch-id",
        required=True,
        help="titleを含まないopaque review batch ID",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="検証済みpacketを固定workspace rootへno-clobberで書き込む",
    )
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _load_documents(
    raw_inputs: list[str],
    *,
    recursive: bool,
) -> tuple[list[tuple[str, dict[str, Any]]], int, int, int]:
    engine = MergeEngine()
    documents: list[tuple[str, dict[str, Any]]] = []
    resolved_count = 0
    invalid_count = 0
    skipped_count = 0

    for entry in resolve_input_entries(raw_inputs, recursive=recursive):
        if entry.path is None:
            skipped_count += 1
            continue
        resolved_count += 1
        validator.check_repository_input(entry.path)
        result = engine.validate_file(entry.path)
        if not result.is_valid:
            invalid_count += 1
            continue
        assert result.document is not None
        documents.append((result.source, result.document))

    return documents, resolved_count, invalid_count, skipped_count


def _serialized_packet(packet: dict[str, Any]) -> bytes:
    return (
        json.dumps(packet, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _recheck_publish_boundary(target: Path, *, require_available: bool) -> None:
    checked_target = validator.packet_path(target.name)
    if checked_target != target or (require_available and target.exists()):
        raise BuilderConfigError("packet-target-unavailable")


def _publish_packet(target: Path, packet: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    # mkdir後もrootからleafまでを再検査し、reparse raceを安全側で拒否する。
    _recheck_publish_boundary(target, require_available=True)

    payload = _serialized_packet(packet)
    temp_path = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    temporary_created = False
    try:
        descriptor = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        temporary_created = True
        with os.fdopen(descriptor, "wb") as temp_file:
            _recheck_publish_boundary(target, require_available=True)
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        # hard linkの作成はtargetが既存なら失敗する。os.replaceや上書き
        # fallbackを使わず、同一directory内でreplace-freeに公開する。
        _recheck_publish_boundary(target, require_available=True)
        os.link(temp_path, target)
    except FileExistsError as exc:
        raise BuilderConfigError("packet-target-unavailable") from exc
    except OSError as exc:
        raise BuilderConfigError("atomic-publish-failed") from exc
    finally:
        if temporary_created:
            # cleanup対象の祖先が差し替わっていないことを確認できない場合は、
            # 意図しない場所を削除するより一時fileを残して安全側で失敗する。
            try:
                _recheck_publish_boundary(target, require_available=False)
            except (BuilderConfigError, validator.ConfigError) as exc:
                raise BuilderConfigError("temporary-cleanup-unsafe") from exc
            try:
                temp_path.unlink(missing_ok=True)
            except OSError as exc:
                raise BuilderConfigError("temporary-cleanup-failed") from exc


def _validate_packet(packet: dict[str, Any], created_at: datetime) -> Any:
    result = validator.validate_packet_document(packet, current_time=created_at)
    if not result.is_valid or result.warning_codes:
        raise BuilderConfigError("generated-packet-invalid")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        documents, resolved_count, invalid_count, skipped_count = _load_documents(
            args.input,
            recursive=args.recursive,
        )
        if resolved_count == 0:
            raise BuilderConfigError("no-input-resolved")
        if invalid_count or skipped_count:
            print(
                "[canonical-timeline-review-builder] status=invalid_input "
                f"resolved={resolved_count} valid={len(documents)} "
                f"invalid={invalid_count} skipped={skipped_count}",
                file=sys.stderr,
            )
            return 1

        target = validator.packet_path(args.packet_name)
        if target.exists():
            raise BuilderConfigError("packet-target-unavailable")

        created_at = _utc_now()
        packet = build_canonical_timeline_review_packet(
            documents,
            story_pair_index=args.story_pair_index,
            review_batch_id=args.review_batch_id,
            created_at=created_at,
        )
        validation_result = _validate_packet(packet, created_at)
        if args.execute:
            _publish_packet(target, packet)

        if not args.quiet:
            mode = "written" if args.execute else "dry_run"
            print(
                "[canonical-timeline-review-builder] "
                f"status={mode} resolved={resolved_count} valid={len(documents)} "
                f"selected_story_pairs={1 if validation_result.edge_count else 0} "
                f"edges={validation_result.edge_count} "
                f"observations={validation_result.provenance_count} "
                f"retention_days={RETENTION_DAYS}"
            )
        return 0
    except PacketBuildError as exc:
        print(
            "[canonical-timeline-review-builder] status=no_selection "
            f"code={exc.code} story_pairs={exc.available_story_pairs}",
            file=sys.stderr,
        )
        return 1
    except (BuilderConfigError, validator.ConfigError) as exc:
        print(
            f"[canonical-timeline-review-builder] status=config_error code={exc.code}",
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError):
        print(
            "[canonical-timeline-review-builder] status=config_error "
            "code=builder-failed",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
