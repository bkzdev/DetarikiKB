"""v1 release candidateの匿名rehearsal recordを構築・検証する。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_public_input import (
    validate_canonical_timeline_public_input,
)
from agents.wiki_generator.public_site_manifest import (
    validate_public_site_manifest_pair,
)

_SHA1 = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_RUN_URL = re.compile(r"https://github\.com/[^/]+/[^/]+/actions/runs/[0-9]+")
_PUBLIC_URL = re.compile(r"https://[^\s]+")


class ReleaseCandidateError(ValueError):
    """候補record生成を拒否した匿名code。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _validate_schema(document: dict[str, Any], schema_path: Path, code: str) -> None:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = list(Draft7Validator(schema).iter_errors(document))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError("release-schema-unavailable") from exc
    if errors:
        raise ReleaseCandidateError(code)


def _workflow_evidence(
    evidence: dict[str, Any], candidate_sha: str, expected_workflow: str
) -> dict[str, str]:
    if set(evidence) != {"workflow", "headSha", "conclusion", "runUrl"}:
        raise ReleaseCandidateError("release-workflow-evidence-invalid")
    if (
        evidence["workflow"] != expected_workflow
        or evidence["headSha"] != candidate_sha
        or evidence["conclusion"] != "success"
        or not isinstance(evidence["runUrl"], str)
        or _RUN_URL.fullmatch(evidence["runUrl"]) is None
    ):
        raise ReleaseCandidateError("release-workflow-evidence-invalid")
    return dict(evidence)


def _validate_quality_chain(
    candidate_sha: str,
    normalization_report: dict[str, Any],
    normalization_digest: str,
    knowledge_report: dict[str, Any],
    knowledge_digest: str,
    curation_report: dict[str, Any],
) -> None:
    if any(
        report.get("sourceRevision") != candidate_sha
        for report in (normalization_report, knowledge_report, curation_report)
    ):
        raise ReleaseCandidateError("release-quality-source-mismatch")
    if knowledge_report["normalizationReportSha256"] != normalization_digest:
        raise ReleaseCandidateError("release-m2-m3-digest-mismatch")
    if (
        curation_report["inputDigests"]["normalizationReportSha256"]
        != normalization_digest
        or curation_report["inputDigests"]["knowledgeReportSha256"] != knowledge_digest
    ):
        raise ReleaseCandidateError("release-m3-m4-digest-mismatch")
    if not curation_report["reviewable"]:
        raise ReleaseCandidateError("release-curation-not-reviewable")


def _validate_public_build(
    candidate_sha: str,
    lock_digest: str,
    public_input_digest: str,
    mkdocs_manifest: dict[str, Any],
    zensical_manifest: dict[str, Any],
) -> None:
    if validate_public_site_manifest_pair(mkdocs_manifest, zensical_manifest):
        raise ReleaseCandidateError("release-public-build-pair-invalid")
    for manifest in (mkdocs_manifest, zensical_manifest):
        if (
            manifest["sourceRevision"]["value"] != candidate_sha
            or manifest["lockSha256"] != lock_digest
            or manifest["publicInputSha256"] != public_input_digest
        ):
            raise ReleaseCandidateError("release-public-build-input-mismatch")


def _validate_rollback(
    source_sha: str, tree_sha256: str, run_url: str, public_url: str
) -> None:
    if (
        _SHA1.fullmatch(source_sha) is None
        or _SHA256.fullmatch(tree_sha256) is None
        or _RUN_URL.fullmatch(run_url) is None
        or _PUBLIC_URL.fullmatch(public_url) is None
    ):
        raise ReleaseCandidateError("release-rollback-evidence-invalid")


def _public_input_metadata(payload: bytes) -> tuple[str, str]:
    try:
        document = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError("release-public-input-invalid") from exc
    if (
        not isinstance(document, dict)
        or validate_canonical_timeline_public_input(document)
        or document.get("buildStatus") != "approved_for_build"
    ):
        raise ReleaseCandidateError("release-public-input-invalid")
    return document["documentType"], document["contentType"]


def build_release_candidate_record(
    *,
    candidate_sha: str,
    lock_bytes: bytes,
    public_input_bytes: bytes,
    normalization_report: dict[str, Any],
    normalization_report_bytes: bytes,
    knowledge_report: dict[str, Any],
    knowledge_report_bytes: bytes,
    curation_report: dict[str, Any],
    curation_report_bytes: bytes,
    mkdocs_manifest: dict[str, Any],
    zensical_manifest: dict[str, Any],
    main_ci: dict[str, Any],
    public_build: dict[str, Any],
    rollback_source_sha: str,
    rollback_tree_sha256: str,
    rollback_run_url: str,
    public_url: str,
    validated_at: str,
    schema_root: Path,
) -> dict[str, Any]:
    """同一candidateに結び付いたrelease rehearsal recordを構築する。"""

    if _SHA1.fullmatch(candidate_sha) is None:
        raise ReleaseCandidateError("release-candidate-sha-invalid")
    try:
        parsed_time = datetime.fromisoformat(validated_at.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ReleaseCandidateError("release-validation-time-invalid") from exc
    if parsed_time.tzinfo is None:
        raise ReleaseCandidateError("release-validation-time-invalid")
    for document, schema_name, code in (
        (
            normalization_report,
            "release_scope_normalization_report.schema.json",
            "release-normalization-report-invalid",
        ),
        (
            knowledge_report,
            "release_scope_knowledge_report.schema.json",
            "release-knowledge-report-invalid",
        ),
        (
            curation_report,
            "release_scope_curation_readiness_report.schema.json",
            "release-curation-report-invalid",
        ),
    ):
        _validate_schema(document, schema_root / schema_name, code)

    normalization_digest = sha256_bytes(normalization_report_bytes)
    knowledge_digest = sha256_bytes(knowledge_report_bytes)
    _validate_quality_chain(
        candidate_sha,
        normalization_report,
        normalization_digest,
        knowledge_report,
        knowledge_digest,
        curation_report,
    )
    lock_digest = sha256_bytes(lock_bytes)
    public_input_digest = sha256_bytes(public_input_bytes)
    public_input_type, public_content_type = _public_input_metadata(public_input_bytes)
    _validate_public_build(
        candidate_sha,
        lock_digest,
        public_input_digest,
        mkdocs_manifest,
        zensical_manifest,
    )
    _validate_rollback(
        rollback_source_sha, rollback_tree_sha256, rollback_run_url, public_url
    )

    record = {
        "schemaVersion": "0.1",
        "documentType": "v1_release_candidate_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "rehearsal_complete",
        "candidate": {
            "sourceSha": candidate_sha,
            "lockSha256": lock_digest,
            "publicInputSha256": public_input_digest,
            "validatedAt": validated_at,
        },
        "scope": {
            "categoryEpisodeCounts": normalization_report["categoryEpisodeCounts"],
            "publicInputDocumentType": public_input_type,
            "publicInputContentType": public_content_type,
            "exclusions": [
                "raw_and_private_artifacts",
                "unreviewed_public_content",
                "production_deploy",
            ],
        },
        "qualityEvidence": {
            "normalizationReportSha256": normalization_digest,
            "knowledgeReportSha256": knowledge_digest,
            "curationReportSha256": sha256_bytes(curation_report_bytes),
            "normalizedEpisodeCount": normalization_report["normalizedEpisodeCount"],
            "mergedEntityCount": sum(knowledge_report["mergedEntityCounts"].values()),
            "curationReviewable": True,
            "curationFullyConfirmed": curation_report["fullyConfirmed"],
        },
        "publicBuild": {
            "mkdocsManifestSha256": sha256_bytes(canonical_json_bytes(mkdocs_manifest)),
            "zensicalManifestSha256": sha256_bytes(
                canonical_json_bytes(zensical_manifest)
            ),
            "mkdocsTreeSha256": mkdocs_manifest["output"]["treeSha256"],
            "zensicalTreeSha256": zensical_manifest["output"]["treeSha256"],
            "routeCount": len(mkdocs_manifest["output"]["routes"]),
            "dualBuildStatus": "passed",
        },
        "hostedChecks": {
            "mainCi": _workflow_evidence(main_ci, candidate_sha, "CI"),
            "publicBuild": _workflow_evidence(
                public_build,
                candidate_sha,
                "Public Build (Reviewed Input, No Deploy)",
            ),
        },
        "production": {
            "candidateGateStatus": "pending_human_approval",
            "knownRollback": {
                "sourceSha": rollback_source_sha,
                "treeSha256": rollback_tree_sha256,
                "runUrl": rollback_run_url,
                "publicUrl": public_url,
            },
        },
        "finalDecision": "pending",
    }
    _validate_schema(
        record,
        schema_root / "v1_release_candidate_record.schema.json",
        "release-candidate-record-invalid",
    )
    return record


__all__ = [
    "ReleaseCandidateError",
    "build_release_candidate_record",
    "canonical_json_bytes",
    "sha256_bytes",
]
