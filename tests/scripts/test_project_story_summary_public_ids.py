"""
tests/scripts/test_project_story_summary_public_ids.py
scripts/project_story_summary_public_ids.py のCLIテスト。

Story Summary（`schemas/story_summary.schema.json`準拠のYAML）に
publicStoryId/publicEpisodeId中心のCompatible/Public-safe projectionを
適用するscriptを検証する。合成データのみを一時ファイル・
`tests/fixtures/story_summaries/public_id_projection/`配下の合成fixtureとして
使う。実データ・実データ由来fixtureは一切使わない。--output/--mapping-output/
--reportはいずれもtmp_path配下 (workspace相当) を使い、
knowledge/summaries/・knowledge/public_ids/への書き込みは一切発生させない。
"""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "project_story_summary_public_ids.py"
FIXTURES_DIR = (
    PROJECT_ROOT / "tests" / "fixtures" / "story_summaries" / "public_id_projection"
)


# ----------------------------------------------------------------
# synthetic document builders
# ----------------------------------------------------------------


def _episode(**overrides) -> dict:
    episode = {
        "episodeId": "SUM_TEST_A_E01",
        "publicEpisodeId": "PUB_TEST_A_E01",
        "episodeNumber": 1,
        "text": "合成テスト用のEpisode Summaryです。",
        "confidence": 0.6,
        "evidenceRefs": [],
    }
    episode.update(overrides)
    return episode


def _story_summary_entry(**overrides) -> dict:
    entry = {
        "text": "合成テスト用のStory Summaryです。",
        "confidence": 0.7,
        "evidenceRefs": [],
    }
    entry.update(overrides)
    return entry


def _document(episodes: list[dict] | None = None, **overrides) -> dict:
    data = {
        "schemaVersion": "0.1.0",
        "documentType": "story_summary",
        "storyId": "SUM_TEST_A",
        "publicStoryId": "PUB_TEST_A",
        "language": "ja",
        "generationStatus": "generated",
        "storySummary": _story_summary_entry(),
        "episodeSummaries": episodes if episodes is not None else [_episode()],
        "source": {
            "sourceType": "ai_generated",
            "model": "synthetic_test_model",
            "promptVersion": "test_v0.1",
            "generatedAt": "2026-07-08T00:00:00Z",
            "inputRefs": ["SUM_TEST_A_E01"],
        },
        "review": {
            "status": "reviewed",
            "reviewer": "synthetic_reviewer",
            "reviewedAt": "2026-07-08",
            "notes": None,
        },
        "notes": None,
    }
    data.update(overrides)
    return data


def _write(path: Path, data: dict) -> Path:
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)
    return path


def _write_evidence_mapping(path: Path, rows: list[dict]) -> Path:
    fieldnames = [
        "storyId",
        "publicStoryId",
        "episodeId",
        "publicEpisodeId",
        "evidenceId",
        "publicEvidenceId",
        "evidenceType",
        "sceneId",
        "blockId",
        "episodeOrder",
        "publicEpisodeIdSource",
        "registryMatched",
        "registryConflict",
        "registryPublicEpisodeId",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            full_row = {key: row.get(key, "") for key in fieldnames}
            writer.writerow(full_row)
    return path


def _write_registry(path: Path, stories: list[dict]) -> Path:
    return _write(path, {"registryVersion": 1, "stories": stories})


def _registry_story(public_story_id: str, episodes: list[dict], **overrides) -> dict:
    story = {
        "publicStoryId": public_story_id,
        "category": "event",
        "episodes": episodes,
    }
    story.update(overrides)
    return story


def _run_cli(*extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *extra_args],
        capture_output=True,
        text=True,
    )


def _base_args(
    tmp_path: Path,
    *,
    input_path: Path | None = None,
    output_dir: Path | None = None,
    mapping_output: Path | None = None,
    report: Path | None = None,
    extra: list[str] | None = None,
) -> list[str]:
    if input_path is None:
        input_path = _write(tmp_path / "input.yaml", _document())
    if output_dir is None:
        output_dir = tmp_path / "output"
    if mapping_output is None:
        mapping_output = tmp_path / "mapping.csv"
    if report is None:
        report = tmp_path / "report.md"
    args = [
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
        "--mapping-output",
        str(mapping_output),
        "--report",
        str(report),
    ]
    if extra:
        args.extend(extra)
    return args


def _read_document(output_dir: Path, filename: str) -> dict:
    with open(output_dir / filename, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ----------------------------------------------------------------
# compatible mode: no conversion, output filename policy
# ----------------------------------------------------------------


def test_compatible_mode_leaves_internal_ids_unchanged(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "input.yaml")
    assert doc["storyId"] == "SUM_TEST_A"
    assert doc["episodeSummaries"][0]["episodeId"] == "SUM_TEST_A_E01"


def test_compatible_mode_is_default_projection_mode(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Projection mode: compatible" in report_text


def test_compatible_output_filename_is_input_filename(tmp_path):
    input_path = _write(tmp_path / "my_custom_name.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "my_custom_name.yaml").is_file()


def test_compatible_mode_evidence_refs_unconverted_even_without_mapping(tmp_path):
    doc = _document(
        episodes=[_episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])],
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    out_doc = _read_document(output_dir, "input.yaml")
    assert out_doc["episodeSummaries"][0]["evidenceRefs"] == ["SUM_TEST_A_E01_DLG0001"]


def test_compatible_mode_evidence_refs_unconverted_even_with_mapping(tmp_path):
    doc = _document(episodes=[_episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])])
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 0, result.stderr
    out_doc = _read_document(output_dir, "input.yaml")
    assert out_doc["episodeSummaries"][0]["evidenceRefs"] == ["SUM_TEST_A_E01_DLG0001"]


# ----------------------------------------------------------------
# public-safe mode: field rewrite
# ----------------------------------------------------------------


def test_public_safe_story_id_becomes_public_story_id(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["storyId"] == "PUB_TEST_A"


def test_public_safe_public_story_id_is_kept(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["publicStoryId"] == "PUB_TEST_A"


def test_public_safe_episode_id_becomes_public_episode_id(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["episodeSummaries"][0]["episodeId"] == "PUB_TEST_A_E01"


def test_public_safe_public_episode_id_is_kept(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["episodeSummaries"][0]["publicEpisodeId"] == "PUB_TEST_A_E01"


def test_public_safe_source_input_refs_removed(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert "inputRefs" not in doc["source"]


def test_public_safe_source_other_fields_are_kept(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["source"]["sourceType"] == "ai_generated"
    assert doc["source"]["model"] == "synthetic_test_model"


def test_public_safe_review_and_notes_are_kept(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document(notes="合成テストの補足"))
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["review"]["status"] == "reviewed"
    assert doc["notes"] == "合成テストの補足"


def test_public_safe_output_filename_is_public_story_id(tmp_path):
    doc = _document(storyId="SUM_TEST_XYZ", publicStoryId="PUB_TEST_XYZ")
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "PUB_TEST_XYZ.yaml").is_file()


def test_public_safe_duplicate_target_filename_across_files_fails(tmp_path):
    input_dir = tmp_path / "input_dir"
    input_dir.mkdir()
    _write(
        input_dir / "story_a.yaml",
        _document(storyId="SUM_TEST_A", publicStoryId="PUB_SAME"),
    )
    _write(
        input_dir / "story_b.yaml",
        _document(
            storyId="SUM_TEST_B",
            publicStoryId="PUB_SAME",
            episodes=[
                _episode(episodeId="SUM_TEST_B_E01", publicEpisodeId="PUB_SAME_E01")
            ],
        ),
    )
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "PUB_SAME" in report_text
    assert "衝突" in report_text
    assert "not-promotion-ready" in report_text


# ----------------------------------------------------------------
# blocking condition 1: missing publicStoryId
# ----------------------------------------------------------------


def test_missing_public_story_id_fails_in_compatible_mode(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document(publicStoryId=None))
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "publicStoryId" in report_text
    assert "FAIL" in report_text


def test_missing_public_story_id_fails_in_public_safe_mode(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document(publicStoryId=None))
    result = _run_cli(
        *_base_args(
            tmp_path, input_path=input_path, extra=["--projection-mode", "public-safe"]
        )
    )
    assert result.returncode == 1, result.stdout


def test_missing_public_story_id_is_not_completed_by_registry(tmp_path):
    """§7.3: RegistryはpublicStoryId自体を逆引きできないため、Registry指定時
    もpublicStoryId欠落は解決されない。"""
    input_path = _write(tmp_path / "input.yaml", _document(publicStoryId=None))
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A", [{"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1}]
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout


# ----------------------------------------------------------------
# blocking condition 2: missing publicEpisodeId
# ----------------------------------------------------------------


def test_missing_public_episode_id_fails(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _document(episodes=[_episode(publicEpisodeId=None)])
    )
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "publicEpisodeId" in report_text


def test_missing_public_episode_id_not_in_registry_still_fails(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _document(episodes=[_episode(publicEpisodeId=None)])
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [{"publicEpisodeId": "PUB_TEST_A_E99", "episodeOrder": 99}],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Missing publicEpisodeId count: 1" in report_text


# ----------------------------------------------------------------
# Registry integration
# ----------------------------------------------------------------


def _two_episode_doc(*, second_public_episode_id: str | None) -> dict:
    return _document(
        episodes=[
            _episode(episodeId="SUM_TEST_A_E01", publicEpisodeId="PUB_TEST_A_E01"),
            _episode(
                episodeId="SUM_TEST_A_E02",
                publicEpisodeId=second_public_episode_id,
            ),
        ]
    )


def test_registry_completes_missing_public_episode_id(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _two_episode_doc(second_public_episode_id=None)
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "input.yaml")
    assert doc["episodeSummaries"][1]["publicEpisodeId"] == "PUB_TEST_A_E02"


def test_registry_completion_works_in_public_safe_mode(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _two_episode_doc(second_public_episode_id=None)
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc["episodeSummaries"][1]["episodeId"] == "PUB_TEST_A_E02"


def test_registry_mismatch_with_existing_public_episode_id_fails(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _two_episode_doc(second_public_episode_id="PUB_TEST_A_E02"),
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02_DIFFERENT", "episodeOrder": 2},
                ],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "一致しません" in report_text
    assert "Conflicts count: 1" in report_text


def test_existing_public_episode_id_missing_from_registry_warns_but_passes(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml",
        _two_episode_doc(second_public_episode_id="PUB_TEST_A_E02"),
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A", [{"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2}]
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Registryには" in report_text
    assert "(none)" not in report_text.split("## Warnings")[1].split("##")[0]


def test_report_contains_registry_summary(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _two_episode_doc(second_public_episode_id=None)
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A",
                [
                    {"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1},
                    {"publicEpisodeId": "PUB_TEST_A_E02", "episodeOrder": 2},
                ],
            )
        ],
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Registry" in report_text
    assert "Registry stories count: 1" in report_text
    assert "Registry episodes count: 2" in report_text
    assert "Entries with publicEpisodeId from registry: 1" in report_text


def test_no_registry_still_reports_registry_section_as_unused(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Registry path: (none)" in report_text


def test_missing_registry_path_returns_exit_2(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(tmp_path / "does_not_exist.yaml"),
    )
    assert result.returncode == 2, result.stdout


def test_invalid_registry_schema_returns_exit_2(tmp_path):
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w", encoding="utf-8") as f:
        yaml.safe_dump({"registryVersion": 1, "stories": [{"invalidField": True}]}, f)
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 2, result.stdout


# ----------------------------------------------------------------
# evidenceRefs conversion (public-safe mode only)
# ----------------------------------------------------------------


def test_evidence_refs_converted_with_matching_mapping(tmp_path):
    doc = _document(episodes=[_episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])])
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["episodeSummaries"][0]["evidenceRefs"] == ["PUB_TEST_A_E01_DLG0001"]


def test_evidence_refs_already_public_form_is_kept(tmp_path):
    doc = _document(episodes=[_episode(evidenceRefs=["PUB_TEST_A_E01_DLG0001"])])
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["episodeSummaries"][0]["evidenceRefs"] == ["PUB_TEST_A_E01_DLG0001"]


def test_evidence_refs_unresolved_clears_whole_unit(tmp_path):
    doc = _document(
        episodes=[
            _episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001", "SUM_TEST_A_E01_DLG9999"])
        ]
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["episodeSummaries"][0]["evidenceRefs"] == []
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Stories promoted without evidenceRefs: 1" in report_text
    assert "## Warnings" in report_text


def test_evidence_refs_no_mapping_specified_clears_all_in_public_safe_mode(tmp_path):
    doc = _document(episodes=[_episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])])
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["episodeSummaries"][0]["evidenceRefs"] == []


def test_evidence_refs_empty_list_stays_empty_without_warning(tmp_path):
    doc = _document(episodes=[_episode(evidenceRefs=[])])
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Stories promoted without evidenceRefs: 0" in report_text


def test_evidence_refs_story_level_conversion(tmp_path):
    doc = _document(
        storySummary=_story_summary_entry(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["storySummary"]["evidenceRefs"] == ["PUB_TEST_A_E01_DLG0001"]


def test_evidence_mapping_directory_input_merges_multiple_csv(tmp_path):
    doc = _document(
        episodes=[
            _episode(
                episodeId="SUM_TEST_A_E01",
                publicEpisodeId="PUB_TEST_A_E01",
                evidenceRefs=["SUM_TEST_A_E01_DLG0001"],
            ),
        ]
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_dir = tmp_path / "evidence_mapping_dir"
    mapping_dir.mkdir()
    _write_evidence_mapping(
        mapping_dir / "story_a.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_A_E01_DLG0001",
            }
        ],
    )
    _write_evidence_mapping(
        mapping_dir / "story_b.csv",
        [
            {
                "evidenceId": "SUM_TEST_B_E01_DLG0001",
                "publicEvidenceId": "PUB_TEST_B_E01_DLG0001",
            }
        ],
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_dir),
    )
    assert result.returncode == 0, result.stderr
    doc_out = _read_document(output_dir, "PUB_TEST_A.yaml")
    assert doc_out["episodeSummaries"][0]["evidenceRefs"] == ["PUB_TEST_A_E01_DLG0001"]


def test_missing_evidence_mapping_path_returns_exit_2(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--evidence-mapping",
        str(tmp_path / "does_not_exist.csv"),
    )
    assert result.returncode == 2, result.stdout


# ----------------------------------------------------------------
# blocking condition 5: schema validation of projected output
# ----------------------------------------------------------------


def test_projected_output_validates_against_schema_compatible(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr

    import json

    from jsonschema import Draft7Validator

    schema_path = PROJECT_ROOT / "schemas" / "story_summary.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    doc = _read_document(output_dir, "input.yaml")
    errors = list(Draft7Validator(schema).iter_errors(doc))
    assert errors == []


def test_projected_output_validates_against_schema_public_safe(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr

    import json

    from jsonschema import Draft7Validator

    schema_path = PROJECT_ROOT / "schemas" / "story_summary.schema.json"
    with open(schema_path, encoding="utf-8") as f:
        schema = json.load(f)
    doc = _read_document(output_dir, "PUB_TEST_A.yaml")
    errors = list(Draft7Validator(schema).iter_errors(doc))
    assert errors == []


def test_evidence_mapping_producing_invalid_evidence_ref_fails_schema(tmp_path):
    """--evidence-mappingが、EvidenceRef pattern (^[A-Z][A-Z0-9_]*$) に
    適合しないpublicEvidenceIdを与えた場合、projected出力のschema検証で
    blockingになることを確認する (条件5)。"""
    doc = _document(episodes=[_episode(evidenceRefs=["SUM_TEST_A_E01_DLG0001"])])
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_path = _write_evidence_mapping(
        tmp_path / "evidence_mapping.csv",
        [
            {
                "evidenceId": "SUM_TEST_A_E01_DLG0001",
                "publicEvidenceId": "not-a-valid-pattern",
            }
        ],
    )
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        ),
        "--evidence-mapping",
        str(mapping_path),
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "projected" in report_text


# ----------------------------------------------------------------
# blocking condition 6: internal ID exposure scan (public-safe mode only)
# ----------------------------------------------------------------


def test_internal_story_id_does_not_leak_into_output(tmp_path):
    doc = _document(storyId="SUM_INTERNAL_SOURCEKEY_STORY", publicStoryId="PUB_TEST_A")
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    output_text = (output_dir / "PUB_TEST_A.yaml").read_text(encoding="utf-8")
    assert "SUM_INTERNAL_SOURCEKEY_STORY" not in output_text


def test_internal_episode_id_does_not_leak_into_output(tmp_path):
    doc = _document(episodes=[_episode(episodeId="SUM_INTERNAL_SOURCEKEY_E01")])
    input_path = _write(tmp_path / "input.yaml", doc)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    output_text = (output_dir / "PUB_TEST_A.yaml").read_text(encoding="utf-8")
    assert "SUM_INTERNAL_SOURCEKEY_E01" not in output_text


def test_internal_id_leak_via_notes_is_blocked(tmp_path):
    doc = _document(
        storyId="SUM_INTERNAL_SOURCEKEY_STORY",
        notes="internal ref: SUM_INTERNAL_SOURCEKEY_STORY",
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "internal ID exposure" in report_text
    assert "not-promotion-ready" in report_text


def test_internal_id_leak_via_review_notes_is_blocked(tmp_path):
    doc = _document(storyId="SUM_INTERNAL_SOURCEKEY_STORY")
    doc["review"]["notes"] = "SUM_INTERNAL_SOURCEKEY_STORYを参照"
    input_path = _write(tmp_path / "input.yaml", doc)
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout


def test_internal_id_equal_to_public_id_is_not_flagged(tmp_path):
    """内部IDと公開IDがたまたま一致する場合は安全 (exposure scanの除外対象)。"""
    doc = _document(storyId="PUB_TEST_A", publicStoryId="PUB_TEST_A")
    input_path = _write(tmp_path / "input.yaml", doc)
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr


def test_short_internal_id_below_threshold_is_not_flagged(tmp_path):
    """4文字未満の内部IDは誤検出防止のためscan対象外。"""
    doc = _document(storyId="ABC", publicStoryId="PUB_TEST_A")
    input_path = _write(tmp_path / "input.yaml", doc)
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr


def test_exposure_scan_not_run_in_compatible_mode(tmp_path):
    """compatible modeはそもそも内部IDを保持したまま出力するため、exposure
    scanの対象外 (blockingにならない)。"""
    doc = _document(
        storyId="SUM_INTERNAL_SOURCEKEY_STORY",
        notes="internal ref: SUM_INTERNAL_SOURCEKEY_STORY",
    )
    input_path = _write(tmp_path / "input.yaml", doc)
    result = _run_cli(*_base_args(tmp_path, input_path=input_path))
    assert result.returncode == 0, result.stderr


# ----------------------------------------------------------------
# mapping output / report
# ----------------------------------------------------------------


def test_mapping_output_contains_expected_columns_and_rows(tmp_path):
    doc = _two_episode_doc(second_public_episode_id="PUB_TEST_A_E02")
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=mapping_output)
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    expected_columns = {
        "storyId",
        "publicStoryId",
        "episodeId",
        "publicEpisodeId",
        "publicEpisodeIdSource",
        "registryMatched",
        "registryConflict",
        "registryPublicEpisodeId",
        "episodeOrder",
        "evidenceRefsInputCount",
        "evidenceRefsConvertedCount",
        "evidenceRefsClearedCount",
    }
    assert expected_columns.issubset(rows[0].keys())
    assert rows[0]["episodeId"] == "SUM_TEST_A_E01"
    assert rows[0]["publicEpisodeId"] == "PUB_TEST_A_E01"


def test_mapping_output_contains_internal_ids_in_public_safe_mode_too(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            mapping_output=mapping_output,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["storyId"] == "SUM_TEST_A"
    assert rows[0]["episodeId"] == "SUM_TEST_A_E01"


def test_story_level_only_document_gets_one_mapping_row(tmp_path):
    doc = _document(episodes=[], storySummary=_story_summary_entry())
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=mapping_output)
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["storyId"] == "SUM_TEST_A"
    assert rows[0]["episodeId"] == ""


def test_document_without_story_summary_and_no_episodes_gets_no_mapping_row(tmp_path):
    doc = _document(episodes=[], storySummary=None)
    input_path = _write(tmp_path / "input.yaml", doc)
    mapping_output = tmp_path / "mapping.csv"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=mapping_output)
    )
    assert result.returncode == 0, result.stderr
    with open(mapping_output, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 0


def test_report_output_contains_required_sections(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    report_path = tmp_path / "report.md"
    result = _run_cli(*_base_args(tmp_path, input_path=input_path, report=report_path))
    assert result.returncode == 0, result.stderr
    text = report_path.read_text(encoding="utf-8")
    assert "# Story Summary Public ID Projection Report" in text
    assert "## Projection Result" in text
    assert "## Registry" in text
    assert "## Evidence Refs Conversion" in text
    assert "## Final Decision" in text
    assert "compatible projection" in text.lower()


def test_public_safe_report_contains_promotion_readiness(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    report_path = tmp_path / "report.md"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            report=report_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    text = report_path.read_text(encoding="utf-8")
    assert "## Public-safe Projection" in text
    assert "Promotion readiness: promotion-candidate" in text
    assert "publicStoryId-based" in text


def test_public_safe_report_not_promotion_ready_when_blocking_issue_present(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _document(episodes=[_episode(publicEpisodeId=None)])
    )
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_path,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 1, result.stdout
    report_text = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "Promotion readiness: not-promotion-ready" in report_text


# ----------------------------------------------------------------
# directory input / --clean / input file untouched
# ----------------------------------------------------------------


def test_directory_input_processes_all_files(tmp_path):
    input_dir = tmp_path / "input_dir"
    input_dir.mkdir()
    _write(
        input_dir / "story_a.yaml",
        _document(storyId="SUM_TEST_A", publicStoryId="PUB_A"),
    )
    _write(
        input_dir / "story_b.yaml",
        _document(
            storyId="SUM_TEST_B",
            publicStoryId="PUB_B",
            episodes=[
                _episode(episodeId="SUM_TEST_B_E01", publicEpisodeId="PUB_B_E01")
            ],
        ),
    )
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_dir, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "story_a.yaml").is_file()
    assert (output_dir / "story_b.yaml").is_file()


def test_clean_removes_stale_files_from_output_dir(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    stale_file = output_dir / "stale.yaml"
    stale_file.write_text("stale: true\n", encoding="utf-8")
    result = _run_cli(
        *_base_args(
            tmp_path, input_path=input_path, output_dir=output_dir, extra=["--clean"]
        )
    )
    assert result.returncode == 0, result.stderr
    assert not stale_file.exists()
    assert (output_dir / "input.yaml").is_file()


def test_input_file_remains_unmodified(tmp_path):
    input_path = _write(
        tmp_path / "input.yaml", _document(episodes=[_episode(publicEpisodeId=None)])
    )
    registry_path = _write_registry(
        tmp_path / "registry.yaml",
        [
            _registry_story(
                "PUB_TEST_A", [{"publicEpisodeId": "PUB_TEST_A_E01", "episodeOrder": 1}]
            )
        ],
    )
    original_bytes = input_path.read_bytes()
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir),
        "--registry",
        str(registry_path),
    )
    assert result.returncode == 0, result.stderr
    assert input_path.read_bytes() == original_bytes
    with open(input_path, encoding="utf-8") as f:
        original_data = yaml.safe_load(f)
    assert original_data["episodeSummaries"][0]["publicEpisodeId"] is None


def test_missing_input_path_returns_exit_2(tmp_path):
    result = _run_cli(
        *_base_args(tmp_path, input_path=tmp_path / "does_not_exist.yaml")
    )
    assert result.returncode == 2


def test_missing_schema_path_returns_exit_2(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path),
        "--schema",
        str(tmp_path / "does_not_exist_schema.json"),
    )
    assert result.returncode == 2


# ----------------------------------------------------------------
# safety: --output/--mapping-output/--report must never target
# knowledge/summaries/ or knowledge/public_ids/
# ----------------------------------------------------------------


def test_output_under_knowledge_summaries_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_output = (
        PROJECT_ROOT / "knowledge" / "summaries" / "stories" / "_test_reject"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=forbidden_output)
    )
    assert result.returncode == 2
    assert not forbidden_output.exists()


def test_output_under_knowledge_public_ids_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_output = PROJECT_ROOT / "knowledge" / "public_ids" / "_test_reject"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=forbidden_output)
    )
    assert result.returncode == 2
    assert not forbidden_output.exists()


def test_mapping_output_under_knowledge_summaries_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_mapping = (
        PROJECT_ROOT
        / "knowledge"
        / "summaries"
        / "stories"
        / "_test_reject_mapping.csv"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, mapping_output=forbidden_mapping)
    )
    assert result.returncode == 2
    assert not forbidden_mapping.exists()


def test_report_under_knowledge_summaries_is_rejected(tmp_path):
    input_path = _write(tmp_path / "input.yaml", _document())
    forbidden_report = (
        PROJECT_ROOT / "knowledge" / "summaries" / "stories" / "_test_reject_report.md"
    )
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, report=forbidden_report)
    )
    assert result.returncode == 2
    assert not forbidden_report.exists()


# ----------------------------------------------------------------
# committed synthetic fixtures (tests/fixtures/story_summaries/
# public_id_projection/)
# ----------------------------------------------------------------


def test_fixture_directory_dry_run_compatible_mode_passes(tmp_path):
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=FIXTURES_DIR, output_dir=output_dir)
    )
    # SUM_TEST_PROJ_MISSING_STORY / SUM_TEST_PROJ_MISSING_EPISODE are
    # expected to fail (they exercise blocking conditions 1/2), so the
    # overall directory run is expected to FAIL; individual valid files
    # are still projected and written.
    assert result.returncode == 1, result.stdout
    assert (output_dir / "SUM_TEST_PROJ_ONE.yaml").is_file()
    assert (output_dir / "SUM_TEST_PROJ_TWO.yaml").is_file()


def test_fixture_valid_files_only_pass_public_safe_mode(tmp_path):
    input_dir = tmp_path / "valid_only"
    input_dir.mkdir()
    for name in ("SUM_TEST_PROJ_ONE.yaml", "SUM_TEST_PROJ_TWO.yaml"):
        data = yaml.safe_load((FIXTURES_DIR / name).read_text(encoding="utf-8"))
        _write(input_dir / name, data)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(
            tmp_path,
            input_path=input_dir,
            output_dir=output_dir,
            extra=["--projection-mode", "public-safe"],
        )
    )
    assert result.returncode == 0, result.stderr
    assert (output_dir / "PUB_TEST_PROJ_ONE.yaml").is_file()
    assert (output_dir / "PUB_TEST_PROJ_TWO.yaml").is_file()


def test_fixture_story_only_document_is_valid_and_projects(tmp_path):
    input_path = tmp_path / "story_only.yaml"
    data = yaml.safe_load(
        (FIXTURES_DIR / "SUM_TEST_PROJ_STORY_ONLY.yaml").read_text(encoding="utf-8")
    )
    _write(input_path, data)
    output_dir = tmp_path / "output"
    result = _run_cli(
        *_base_args(tmp_path, input_path=input_path, output_dir=output_dir)
    )
    assert result.returncode == 0, result.stderr
    doc = _read_document(output_dir, "story_only.yaml")
    assert doc["episodeSummaries"] == []
    assert doc["storySummary"]["text"]
