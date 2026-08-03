#!/usr/bin/env python3
"""story manifestから1 story限定のcanonical order review packetを生成する。"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

packet_validator = importlib.import_module(
    "scripts.validate_canonical_order_review_packet"
)

_MANIFEST_SCHEMA_PATH = _PROJECT_ROOT / "schemas" / "story_manifest.schema.json"
_PACKET_HEADER = """\
# Canonical Order Review Packet (local internal / auto-generated)
#
# commitAllowed: false。packet自体と人間確認前の値はcommitしないでください。
# episodeNumber・配列順・ファイル名からcanonicalOrderを推測しないでください。
# source manifestの該当episodeと根拠を個別に確認し、確認できない場合は
# pending / rejected / needs_more_contextのままにします。
# このpacketをvalidにしてもmanifestへ自動反映されません。
"""


class ContentError(Exception):
    """入力内容をechoしてはいけない検証エラー。"""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="story manifestから1 storyのcanonical order review packetを生成する"
    )
    parser.add_argument("--manifest", required=True)
    parser.add_argument(
        "--story-index",
        type=int,
        required=True,
        help="manifest stories配列内の1始まりindex（IDをCLIへ露出しない）",
    )
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--review-batch-id", required=True)
    parser.add_argument("--retention-days", type=int, default=14)
    parser.add_argument("--quiet", "-q", action="store_true")
    return parser.parse_args(argv)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _utc_z(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def _packet_id(created_at: datetime) -> str:
    return f"corp-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(4)}"


def _load_manifest(path: Path) -> tuple[dict[str, Any], bytes]:
    packet_validator.check_repository_input(path)
    try:
        payload = path.read_bytes()
        manifest = yaml.safe_load(payload.decode("utf-8"))
        schema = json.loads(_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft7Validator.check_schema(schema)
    except (
        OSError,
        UnicodeError,
        yaml.YAMLError,
        json.JSONDecodeError,
        SchemaError,
    ) as exc:
        raise ContentError("manifest-unreadable") from exc
    if list(Draft7Validator(schema).iter_errors(manifest)):
        raise ContentError("manifest-schema-invalid")
    assert isinstance(manifest, dict)
    return manifest, payload


def _normalize_current_canonical_order(episode: dict[str, Any]) -> tuple[Any, str, Any]:
    if "canonicalOrderStatus" not in episode:
        return None, "unassigned", None
    return (
        episode["canonicalOrder"],
        episode["canonicalOrderStatus"],
        episode["canonicalOrderSource"],
    )


def build_packet(
    manifest: dict[str, Any],
    manifest_payload: bytes,
    *,
    story_index: int,
    review_batch_id: str,
    created_at: datetime,
    retention_days: int,
) -> dict[str, Any]:
    if story_index < 1 or story_index > len(manifest["stories"]):
        raise ContentError("story-index-out-of-range")
    if retention_days < 1 or retention_days > 90:
        raise ContentError("retention-days-invalid")
    story = manifest["stories"][story_index - 1]
    if not story["episodes"]:
        raise ContentError("story-has-no-episodes")

    episodes = []
    for position, episode in enumerate(story["episodes"], start=1):
        current_order, current_status, current_source = (
            _normalize_current_canonical_order(episode)
        )
        episodes.append(
            {
                "reviewEpisodeKey": f"episode-{position:04d}",
                "episodeId": episode["episodeId"],
                "manifestEpisodeIndex": position,
                "episodeNumber": episode["episodeNumber"],
                "currentCanonicalOrder": current_order,
                "currentCanonicalOrderStatus": current_status,
                "currentCanonicalOrderSource": current_source,
                "candidateCanonicalOrder": None,
                "candidateSource": None,
                "evidenceSummary": "",
                "humanReviewStatus": "pending",
                "humanConfirmedCanonicalOrder": None,
                "humanConfirmedSource": None,
                "reviewerNotes": "",
            }
        )

    return {
        "schemaVersion": "0.1",
        "documentType": "canonical_order_review_packet",
        "packetId": _packet_id(created_at),
        "reviewBatchId": review_batch_id,
        "classification": "local_internal",
        "commitAllowed": False,
        "createdAt": _utc_z(created_at),
        "expiresAt": _utc_z(created_at + timedelta(days=retention_days)),
        "generatedFrom": {
            "manifestSha256": hashlib.sha256(manifest_payload).hexdigest()
        },
        "story": {
            "reviewStoryKey": "story-0001",
            "storyId": story["storyId"],
            "manifestStoryIndex": story_index,
            "category": story["category"],
            "episodeCount": len(episodes),
        },
        "episodes": episodes,
    }


def _write_no_clobber(path: Path, packet: dict[str, Any]) -> None:
    packet_validator._check_fixed_root(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    packet_validator._check_fixed_root(path)
    if packet_validator._lexists(path):
        raise packet_validator.ConfigError("packet-already-exists")

    temporary = path.parent / f".tmp-{secrets.token_hex(8)}.yaml"
    try:
        packet_validator._check_fixed_root(temporary)
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(_PACKET_HEADER)
            yaml.safe_dump(packet, handle, allow_unicode=True, sort_keys=False)
        packet_validator._check_fixed_root(temporary)
        result = packet_validator.validate_packet_path(temporary)
        if not result.is_valid:
            raise ContentError(result.issue_codes[0])
        packet_validator._check_fixed_root(temporary)
        packet_validator._check_fixed_root(path)
        if packet_validator._lexists(path):
            raise packet_validator.ConfigError("packet-already-exists")
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise packet_validator.ConfigError("packet-already-exists") from exc
        except OSError as exc:
            raise packet_validator.ConfigError("packet-publish-failed") from exc
    finally:
        try:
            if packet_validator._lexists(temporary):
                packet_validator._check_fixed_root(temporary)
                temporary.unlink()
        except (OSError, packet_validator.ConfigError):
            pass


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        manifest, payload = _load_manifest(Path(args.manifest))
        created_at = _utc_now()
        packet = build_packet(
            manifest,
            payload,
            story_index=args.story_index,
            review_batch_id=args.review_batch_id,
            created_at=created_at,
            retention_days=args.retention_days,
        )
        output_path = packet_validator.packet_path(args.output_name)
        _write_no_clobber(output_path, packet)
        if not args.quiet:
            print(
                "[canonical-order-review] status=created "
                f"episodes={len(packet['episodes'])} output={args.output_name}"
            )
        return 0
    except packet_validator.ConfigError as exc:
        print(
            f"[canonical-order-review] status=config_error code={exc.code}",
            file=sys.stderr,
        )
        return 2
    except ContentError as exc:
        print(
            f"[canonical-order-review] status=invalid code={exc.code}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
