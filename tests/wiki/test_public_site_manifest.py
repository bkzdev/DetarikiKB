"""Public site manifest / rendered exposure scanの合成契約テスト。"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

import agents.wiki_generator.public_site_manifest as site_manifest
from agents.extractor.canonical_timeline_public_input import (
    build_canonical_timeline_public_input,
    canonical_json_sha256,
)
from agents.wiki_generator.public_site_manifest import (
    PublicSiteError,
    build_public_site_manifest,
    validate_public_site_manifest,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent
PROJECTION_PATH = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "canonical_timeline_public_projection"
    / "valid_projection.json"
)


def _public_input_bytes() -> bytes:
    projection = json.loads(PROJECTION_PATH.read_text(encoding="utf-8"))
    digest = canonical_json_sha256(projection)
    digests = {
        "internalDocument": "1" * 64,
        "projection": digest,
        "publicEpisodeMapping": "2" * 64,
        "publicIdRegistry": "3" * 64,
        "publicLabelSource": "4" * 64,
    }
    review = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_input_review",
        "classification": "local_internal",
        "commitAllowed": False,
        "decision": "approved_for_build",
        "reviewedAt": "2099-01-01T00:00:00Z",
        "reviewerType": "human",
        "projectionSha256": digest,
        "preflightStatus": "clean",
        "preflightInputDigests": digests,
        "checks": {
            "projectionSchemaValid": True,
            "projectionSemanticsReviewed": True,
            "internalExposureClear": True,
            "visualReviewCompleted": True,
        },
    }
    preflight = {
        "schemaVersion": "0.1",
        "documentType": "canonical_timeline_public_preflight_record",
        "classification": "local_internal",
        "commitAllowed": False,
        "status": "clean",
        "publishStatus": "projection_candidate",
        "inputDigests": digests,
        "findings": [],
    }
    document = build_canonical_timeline_public_input(
        projection, review, preflight, digest
    )
    return (json.dumps(document, ensure_ascii=False, sort_keys=True) + "\n").encode()


def _site(root: Path, *, index: str = "<h1>合成公開サイト</h1>") -> Path:
    (root / "stories" / "PUBLIC_EVENT_01").mkdir(parents=True)
    (root / "search").mkdir()
    (root / "assets").mkdir()
    (root / "index.html").write_text(
        f"<!doctype html><html><body>{index}</body></html>", encoding="utf-8"
    )
    (root / "stories" / "PUBLIC_EVENT_01" / "index.html").write_text(
        '<a href="/">合成エピソード</a>', encoding="utf-8"
    )
    (root / "search" / "search_index.json").write_text(
        json.dumps({"docs": [{"title": "合成検索", "text": "公開内容"}]}),
        encoding="utf-8",
    )
    (root / "sitemap.xml").write_text(
        "<urlset><url><loc>https://example.invalid/</loc></url></urlset>",
        encoding="utf-8",
    )
    (root / "assets" / "bundle.js").write_bytes(b"vendor-script")
    (root / "assets" / "favicon.png").write_bytes(b"synthetic-png")
    return root


def _build(root: Path, **overrides) -> dict:
    arguments = {
        "source_sha": "a" * 40,
        "lock_bytes": b"synthetic-lock",
        "public_input_bytes": _public_input_bytes(),
        "generator_name": "zensical",
        "generator_version": "0.0.57",
        "config_bytes": b"synthetic-config",
    }
    arguments.update(overrides)
    return build_public_site_manifest(root, **arguments)


def test_clean_site_builds_deterministic_public_manifest(tmp_path) -> None:
    root = _site(tmp_path / "site")
    first = _build(root)
    second = _build(root)

    assert first == second
    assert validate_public_site_manifest(first) == ()
    assert first["artifactStatus"] == "verified_build_candidate"
    assert first["deploymentAuthorized"] is False
    assert first["gateResults"] == {
        "publicInput": "clean",
        "siteTree": "clean",
        "renderedExposure": "clean",
    }
    assert first["output"]["routes"] == ["/", "/stories/PUBLIC_EVENT_01/"]
    assert first["output"]["htmlDocumentCount"] == 2
    assert first["output"]["scannedDocumentCount"] == 4
    assert first["output"]["findings"] == []
    assert [item["path"] for item in first["output"]["files"]] == sorted(
        item["path"] for item in first["output"]["files"]
    )


@pytest.mark.parametrize(
    "marker",
    (
        "storyId",
        "candidateId",
        "local_internal",
        "@ChTalk12",
        "$num3",
        "secret.dec",
        "file:///private/source",
        "C:\\private\\source",
        "/home/operator/private",
        "data/raw/event",
        "a" * 64,
    ),
)
def test_html_exposure_markers_fail_closed_without_value_in_error(
    tmp_path, marker
) -> None:
    root = _site(tmp_path / "site", index=f"<p>{marker}</p>")
    with pytest.raises(PublicSiteError) as captured:
        _build(root)
    assert captured.value.code == "rendered-exposure-blocked"
    assert marker not in str(captured.value)


@pytest.mark.parametrize(
    "encoded",
    (
        "story&#73;d",
        "story%49d",
        "sto<span>ryId</span>",
        "sto\u200bryId",
        '<a href="file&#58;///private">safe label</a>',
        "ＳＴＯＲＹＩＤ",
    ),
)
def test_html_encoding_and_split_nodes_cannot_hide_markers(tmp_path, encoded) -> None:
    root = _site(tmp_path / "site", index=encoded)
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)


def test_public_field_names_and_vendor_script_are_not_false_positives(tmp_path) -> None:
    root = _site(
        tmp_path / "site",
        index='<script src="/assets/bundle.js"></script><p>publicStoryId</p>',
    )
    (root / "assets" / "bundle.js").write_text(
        "const storyId = 'vendor-internal-name-not-public-data';", encoding="utf-8"
    )
    assert validate_public_site_manifest(_build(root)) == ()


def test_search_data_is_scanned_but_unselected_binary_asset_is_not(tmp_path) -> None:
    root = _site(tmp_path / "site")
    search = root / "search" / "search_index.json"
    search.write_text(json.dumps({"text": "episodeId"}), encoding="utf-8")
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)

    search.write_text(json.dumps({"text": "公開"}), encoding="utf-8")
    (root / "assets" / "favicon.png").write_bytes(b"storyId")
    assert validate_public_site_manifest(_build(root)) == ()


@pytest.mark.parametrize("relative", ("metadata.json", "assets/label.svg"))
def test_all_browser_readable_text_assets_are_scanned(tmp_path, relative) -> None:
    root = _site(tmp_path / "site")
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    content = (
        '{"label": "storyId"}' if target.suffix == ".json" else "<text>storyId</text>"
    )
    target.write_text(content, encoding="utf-8")
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)


def test_json_unicode_escape_cannot_hide_marker(tmp_path) -> None:
    root = _site(tmp_path / "site")
    (root / "metadata.json").write_text(r'{"label": "story\u0049d"}', encoding="utf-8")
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)


def test_uppercase_html_extension_is_scanned(tmp_path) -> None:
    root = _site(tmp_path / "site")
    (root / "page.HTML").write_text("<p>storyId</p>", encoding="utf-8")
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)


@pytest.mark.parametrize("relative", ("storyId.html", "data/raw/private.txt"))
def test_public_file_path_cannot_expose_internal_marker(tmp_path, relative) -> None:
    root = _site(tmp_path / "site")
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("公開", encoding="utf-8")
    with pytest.raises(PublicSiteError, match="rendered-exposure-blocked"):
        _build(root)


def test_missing_entrypoint_unknown_type_and_invalid_utf8_are_blocked(tmp_path) -> None:
    root = _site(tmp_path / "site")
    (root / "index.html").unlink()
    with pytest.raises(PublicSiteError, match="site-entrypoint-missing"):
        _build(root)

    root = _site(tmp_path / "unknown")
    (root / "asset.bin").write_bytes(b"x")
    with pytest.raises(PublicSiteError, match="site-file-type-unsupported"):
        _build(root)

    root = _site(tmp_path / "utf8")
    (root / "index.html").write_bytes(b"\xff")
    with pytest.raises(PublicSiteError, match="scanned-document-not-utf8"):
        _build(root)


def test_symlink_entry_is_rejected_when_supported(tmp_path) -> None:
    root = _site(tmp_path / "site")
    target = tmp_path / "outside.txt"
    target.write_text("public", encoding="utf-8")
    link = root / "linked.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(PublicSiteError, match="site-tree-unsafe-entry"):
        _build(root)


def test_manifest_validator_rejects_digest_order_and_authorization_changes(
    tmp_path,
) -> None:
    manifest = _build(_site(tmp_path / "site"))
    manifest["output"]["treeSha256"] = "0" * 64
    assert validate_public_site_manifest(manifest) == (
        "public-site-manifest-tree-digest-mismatch",
    )

    manifest = _build(tmp_path / "site")
    manifest["output"]["files"].reverse()
    assert validate_public_site_manifest(manifest) == (
        "public-site-manifest-file-order-invalid",
    )

    manifest = _build(tmp_path / "site")
    manifest["deploymentAuthorized"] = True
    assert validate_public_site_manifest(manifest) == ("public-site-manifest-invalid",)


def test_manifest_validator_rejects_route_and_count_mismatch(tmp_path) -> None:
    manifest = _build(_site(tmp_path / "site"))
    manifest["output"]["routes"] = ["/"]
    assert validate_public_site_manifest(manifest) == (
        "public-site-manifest-route-inventory-mismatch",
    )

    manifest = _build(tmp_path / "site")
    manifest["output"]["totalBytes"] += 1
    assert validate_public_site_manifest(manifest) == (
        "public-site-manifest-count-mismatch",
    )


def test_manifest_validator_rejects_file_classification_mismatch(tmp_path) -> None:
    manifest = _build(_site(tmp_path / "site"))
    html = next(
        item for item in manifest["output"]["files"] if item["path"] == "index.html"
    )
    html["scanProfile"] = "binary-asset"
    manifest["output"]["treeSha256"] = site_manifest._sha256(
        site_manifest.canonical_json_bytes(manifest["output"]["files"])
    )
    assert validate_public_site_manifest(manifest) == (
        "public-site-manifest-file-classification-invalid",
    )


def test_tree_change_between_complete_scans_is_rejected(monkeypatch, tmp_path) -> None:
    root = _site(tmp_path / "site")
    original = site_manifest._walk_site
    calls = 0

    def changing_walk(site_root):
        nonlocal calls
        calls += 1
        result = original(site_root)
        if calls == 2:
            files, routes, total, scanned = result
            changed_files = [dict(item) for item in files]
            changed_files[0]["sha256"] = "0" * 64
            return changed_files, routes, total, scanned
        return result

    monkeypatch.setattr(site_manifest, "_walk_site", changing_walk)
    with pytest.raises(PublicSiteError, match="site-tree-changed-during-scan"):
        _build(root)


def test_invalid_public_input_source_revision_and_generator_are_rejected(
    tmp_path,
) -> None:
    root = _site(tmp_path / "site")
    with pytest.raises(PublicSiteError, match="public-input-invalid"):
        _build(root, public_input_bytes=b"{}")
    with pytest.raises(PublicSiteError, match="source-revision-invalid"):
        _build(root, source_sha="short")
    with pytest.raises(PublicSiteError, match="public-site-manifest-invalid"):
        _build(root, generator_name="unknown")
    with pytest.raises(PublicSiteError, match="public-site-manifest-invalid"):
        _build(root, generator_version="C:/private")


def test_root_symlink_is_rejected_when_supported(tmp_path) -> None:
    actual = _site(tmp_path / "actual")
    link = tmp_path / "linked-site"
    try:
        os.symlink(actual, link, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")
    with pytest.raises(PublicSiteError, match="site-root-invalid"):
        _build(link)
