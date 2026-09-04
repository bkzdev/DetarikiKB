"""生成済みpublic siteをfail-closedに検査しdetached manifestを構築する。"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from jsonschema import Draft7Validator

from agents.extractor.canonical_timeline_public_input import (
    validate_canonical_timeline_public_input,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST_SCHEMA = _PROJECT_ROOT / "schemas" / "public_site_manifest.schema.json"
_SCAN_POLICY_VERSION = "0.1"
_MAX_SITE_BYTES = 1_000_000_000
_PUBLIC_DATA_SUFFIXES = {".json", ".svg", ".txt", ".webmanifest", ".xml"}
_PUBLIC_DATA_NAMES = {"LICENSE"}
_MEDIA_TYPES = {
    ".css": "text/css",
    ".gz": "application/gzip",
    ".html": "text/html",
    ".ico": "image/x-icon",
    ".inv": "application/octet-stream",
    ".js": "text/javascript",
    ".json": "application/json",
    ".map": "application/json",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".txt": "text/plain",
    ".webmanifest": "application/manifest+json",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".xml": "application/xml",
}
_EXPOSURE_RULES = {
    "rendered_internal_field_marker": re.compile(
        r"(?<![a-z0-9_])(?:storyid|episodeid|documentid|blockid|sceneid|"
        r"candidateid|evidenceids?|humandecision|sourcefile|sourcekey|rawtext|"
        r"extractionrun)(?![a-z0-9_])"
    ),
    "rendered_private_marker": re.compile(
        r"(?<![a-z0-9_])(?:local_internal|internal_only|commitallowed|"
        r"preflightinputdigests|internaldocument|reviewername)(?![a-z0-9_])"
    ),
    "rendered_raw_script_marker": re.compile(
        r"@(?:chtalk|scenariocos)[a-z0-9_]*|\$num\d+|"
        r"(?<![a-z0-9_])[^\s/\\\"'<>]+\.dec(?![a-z0-9_])"
    ),
    "rendered_local_path_marker": re.compile(
        r"file://|(?<![a-z0-9])[a-z]:/|(?:^|[\s\"'=])/(?:home|users|workspace|tmp)/|"
        r"(?<![a-z0-9_])data/raw/"
    ),
    "rendered_digest_marker": re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])"),
}


class PublicSiteError(ValueError):
    """公開site gateを拒否した匿名code。"""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class _PublicHTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_comment(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, _tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.extend(value for _name, value in attrs if value is not None)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _is_reparse(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        (getattr(info, "st_file_attributes", 0) or 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _read_stable_file(path: Path) -> bytes:
    try:
        before = path.lstat()
        if _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            raise PublicSiteError("site-tree-unsafe-entry")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            payload = stream.read()
        after = path.lstat()
        if _identity(before) != _identity(opened) or _identity(opened) != _identity(
            after
        ):
            raise PublicSiteError("site-tree-changed-during-scan")
        return payload
    except PublicSiteError:
        raise
    except OSError as exc:
        raise PublicSiteError("site-file-unavailable") from exc


def _normalized_variants(
    payload: bytes, profile: str, relative: str | None = None
) -> tuple[str, ...]:
    try:
        decoded = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PublicSiteError("scanned-document-not-utf8") from exc
    variants = [decoded]
    if profile == "html":
        parser = _PublicHTMLText()
        try:
            parser.feed(decoded)
            parser.close()
        except Exception as exc:
            raise PublicSiteError("html-parse-failed") from exc
        variants.extend((" ".join(parser.parts), "".join(parser.parts)))
    if profile == "public-data" and relative is not None:
        suffix = Path(relative).suffix.lower()
        if suffix in {".json", ".webmanifest"}:
            try:
                parsed = json.loads(decoded)
            except json.JSONDecodeError as exc:
                raise PublicSiteError("public-data-json-invalid") from exc
            variants.append(json.dumps(parsed, ensure_ascii=False, sort_keys=True))
    normalized = []
    for value in variants:
        for _iteration in range(2):
            value = html.unescape(unquote(value))
        canonical = unicodedata.normalize("NFKC", value).replace("\\", "/").lower()
        visible = "".join(
            character
            for character in canonical
            if unicodedata.category(character) != "Cf"
        )
        normalized.extend((visible, re.sub(r"[_-]", "", visible)))
    return tuple(normalized)


def _exposure_findings(
    payload: bytes, profile: str, relative: str | None = None
) -> dict[str, int]:
    variants = _normalized_variants(payload, profile, relative)
    return {
        rule: maximum
        for rule, pattern in _EXPOSURE_RULES.items()
        if (maximum := max(len(pattern.findall(value)) for value in variants))
    }


def _scan_profile(relative: str) -> str:
    if Path(relative).suffix.lower() == ".html":
        return "html"
    path = Path(relative)
    if path.suffix.lower() in _PUBLIC_DATA_SUFFIXES or path.name in _PUBLIC_DATA_NAMES:
        return "public-data"
    return "binary-asset"


def _route(relative: str) -> str:
    folded = relative.casefold()
    if folded == "index.html":
        return "/"
    if folded.endswith("/index.html"):
        return f"/{relative[: -len('index.html')]}"
    return f"/{relative}"


def _media_type(relative: str) -> str | None:
    path = Path(relative)
    if path.name in _PUBLIC_DATA_NAMES:
        return "text/plain"
    return _MEDIA_TYPES.get(path.suffix.lower())


def _site_paths(site_root: Path) -> list[Path]:
    try:
        root_info = site_root.lstat()
    except OSError as exc:
        raise PublicSiteError("site-root-unavailable") from exc
    if _is_reparse(root_info) or not stat.S_ISDIR(root_info.st_mode):
        raise PublicSiteError("site-root-invalid")

    try:
        return sorted(
            site_root.rglob("*"),
            key=lambda path: path.relative_to(site_root).as_posix().encode("utf-8"),
        )
    except OSError as exc:
        raise PublicSiteError("site-tree-unavailable") from exc


def _site_file_record(
    site_root: Path, path: Path, observed_casefold: set[str]
) -> tuple[dict[str, Any], str | None] | None:
    relative = path.relative_to(site_root).as_posix()
    try:
        info = path.lstat()
    except OSError as exc:
        raise PublicSiteError("site-entry-unavailable") from exc
    folded = relative.casefold()
    if folded in observed_casefold:
        raise PublicSiteError("site-path-case-collision")
    observed_casefold.add(folded)
    if _exposure_findings(relative.encode("utf-8"), "path"):
        raise PublicSiteError("rendered-exposure-blocked")
    if _is_reparse(info):
        raise PublicSiteError("site-tree-unsafe-entry")
    if stat.S_ISDIR(info.st_mode):
        return None
    if not stat.S_ISREG(info.st_mode):
        raise PublicSiteError("site-tree-unsafe-entry")
    media_type = _media_type(relative)
    if media_type is None:
        raise PublicSiteError("site-file-type-unsupported")
    payload = _read_stable_file(path)
    profile = _scan_profile(relative)
    if profile != "binary-asset" and _exposure_findings(payload, profile, relative):
        raise PublicSiteError("rendered-exposure-blocked")
    record = {
        "path": relative,
        "sha256": _sha256(payload),
        "sizeBytes": len(payload),
        "mediaType": media_type,
        "scanProfile": profile,
    }
    return record, _route(relative) if path.suffix.lower() == ".html" else None


def _walk_site(site_root: Path) -> tuple[list[dict[str, Any]], list[str], int, int]:
    files: list[dict[str, Any]] = []
    routes: list[str] = []
    observed_casefold: set[str] = set()
    for path in _site_paths(site_root):
        result = _site_file_record(site_root, path, observed_casefold)
        if result is None:
            continue
        record, route = result
        files.append(record)
        if route is not None:
            routes.append(route)
    if not files or "/" not in routes:
        raise PublicSiteError("site-entrypoint-missing")
    total_bytes = sum(item["sizeBytes"] for item in files)
    if total_bytes > _MAX_SITE_BYTES:
        raise PublicSiteError("site-size-limit-exceeded")
    scanned = sum(item["scanProfile"] != "binary-asset" for item in files)
    return files, sorted(routes), total_bytes, scanned


def _manifest_validator() -> Draft7Validator:
    try:
        schema = json.loads(_MANIFEST_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicSiteError("manifest-schema-unavailable") from exc
    return Draft7Validator(schema)


def _file_classification_is_valid(item: dict[str, Any]) -> bool:
    media_type = _media_type(item["path"])
    return (
        media_type is not None
        and item["mediaType"] == media_type
        and item["scanProfile"] == _scan_profile(item["path"])
    )


def _manifest_inventory_error(output: dict[str, Any]) -> str | None:
    files = output["files"]
    if any("\\" in item["path"] for item in files):
        return "public-site-manifest-file-path-invalid"
    if files != sorted(files, key=lambda item: item["path"].encode("utf-8")):
        return "public-site-manifest-file-order-invalid"
    if output["routes"] != sorted(output["routes"]):
        return "public-site-manifest-route-order-invalid"
    if any("\\" in route for route in output["routes"]):
        return "public-site-manifest-route-path-invalid"
    if output["treeSha256"] != _sha256(canonical_json_bytes(files)):
        return "public-site-manifest-tree-digest-mismatch"
    if len({item["path"].casefold() for item in files}) != len(files):
        return "public-site-manifest-file-path-invalid"
    if not all(_file_classification_is_valid(item) for item in files):
        return "public-site-manifest-file-classification-invalid"
    expected_routes = sorted(
        _route(item["path"]) for item in files if item["scanProfile"] == "html"
    )
    if output["routes"] != expected_routes:
        return "public-site-manifest-route-inventory-mismatch"
    if (
        output["fileCount"] != len(files)
        or output["htmlDocumentCount"] != len(expected_routes)
        or output["scannedDocumentCount"]
        != sum(item["scanProfile"] != "binary-asset" for item in files)
        or output["totalBytes"] != sum(item["sizeBytes"] for item in files)
    ):
        return "public-site-manifest-count-mismatch"
    return None


def validate_public_site_manifest(manifest: dict[str, Any]) -> tuple[str, ...]:
    try:
        errors = list(_manifest_validator().iter_errors(manifest))
    except PublicSiteError as exc:
        return (exc.code,)
    except Exception:
        return ("manifest-schema-unavailable",)
    if errors:
        return ("public-site-manifest-invalid",)
    if error := _manifest_inventory_error(manifest["output"]):
        return (error,)
    return ()


def validate_public_site_manifest_pair(
    mkdocs_manifest: dict[str, Any], zensical_manifest: dict[str, Any]
) -> tuple[str, ...]:
    """Dual-build manifest間で一致必須のpublic契約を検証する。"""
    if validate_public_site_manifest(mkdocs_manifest) or validate_public_site_manifest(
        zensical_manifest
    ):
        return ("public-site-manifest-pair-invalid",)
    if (
        mkdocs_manifest["generator"]["name"] != "mkdocs-material"
        or zensical_manifest["generator"]["name"] != "zensical"
    ):
        return ("public-site-manifest-pair-generator-invalid",)
    for field in ("sourceRevision", "lockSha256", "publicInputSha256"):
        if mkdocs_manifest[field] != zensical_manifest[field]:
            return ("public-site-manifest-pair-input-mismatch",)
    if mkdocs_manifest["output"]["routes"] != zensical_manifest["output"]["routes"]:
        return ("public-site-manifest-pair-route-mismatch",)
    return ()


def build_public_site_manifest(
    site_root: Path,
    *,
    source_sha: str,
    lock_bytes: bytes,
    public_input_bytes: bytes,
    generator_name: str,
    generator_version: str,
    config_bytes: bytes,
) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise PublicSiteError("source-revision-invalid")
    try:
        public_input = json.loads(public_input_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PublicSiteError("public-input-invalid") from exc
    if not isinstance(public_input, dict) or validate_canonical_timeline_public_input(
        public_input
    ):
        raise PublicSiteError("public-input-invalid")

    snapshot = _walk_site(site_root)
    if _walk_site(site_root) != snapshot:
        raise PublicSiteError("site-tree-changed-during-scan")
    files, routes, total_bytes, scanned = snapshot
    manifest = {
        "schemaVersion": "0.1",
        "documentType": "public_site_manifest",
        "visibility": "public",
        "artifactStatus": "verified_build_candidate",
        "deploymentAuthorized": False,
        "sourceRevision": {"algorithm": "sha1", "value": source_sha},
        "lockSha256": _sha256(lock_bytes),
        "publicInputSha256": _sha256(public_input_bytes),
        "generator": {
            "name": generator_name,
            "version": generator_version,
            "configSha256": _sha256(config_bytes),
        },
        "scanPolicyVersion": _SCAN_POLICY_VERSION,
        "gateResults": {
            "publicInput": "clean",
            "siteTree": "clean",
            "renderedExposure": "clean",
        },
        "output": {
            "fileCount": len(files),
            "htmlDocumentCount": len(routes),
            "scannedDocumentCount": scanned,
            "totalBytes": total_bytes,
            "treeSha256": _sha256(canonical_json_bytes(files)),
            "routes": routes,
            "files": files,
            "findings": [],
        },
    }
    if findings := validate_public_site_manifest(manifest):
        raise PublicSiteError(findings[0])
    return manifest


__all__ = [
    "PublicSiteError",
    "build_public_site_manifest",
    "canonical_json_bytes",
    "validate_public_site_manifest",
    "validate_public_site_manifest_pair",
]
