"""Canonical order review runbookの安全契約を固定する。"""

import json
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK = PROJECT_ROOT / "docs" / "runbooks" / "Canonical_Order_Review.md"
TEMPLATE = (
    PROJECT_ROOT / "docs" / "templates" / "canonical_order_review_packet_template.yaml"
)
SCHEMA = PROJECT_ROOT / "schemas" / "canonical_order_review_packet.schema.json"


def test_runbook_keeps_unreviewed_values_out_of_manifest():
    content = RUNBOOK.read_text(encoding="utf-8")

    for phrase in (
        "1 packetは1 story",
        "commitAllowed: false",
        "raw path、source filename、source key、DEC本文",
        "release order、display order、`episodeNumber`",
        "validator PASS後も自動反映しない",
        "humanReviewStatus: confirmed",
        "v0.5 check",
    ):
        assert phrase in content


def test_synthetic_template_matches_schema_and_contains_no_raw_location():
    packet = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    assert list(Draft7Validator(schema).iter_errors(packet)) == []
    content = TEMPLATE.read_text(encoding="utf-8")
    assert "rawPath:" not in content
    assert "sourceFileName:" not in content
    assert ".dec" not in content
