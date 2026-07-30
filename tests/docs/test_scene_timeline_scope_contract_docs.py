"""Scene Timelineのscope・集約契約が設計文書間で維持されることを確認する。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
PIPELINE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Pipeline.md"
)
RESULT_SCHEMA_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Result_Schema.md"
)
MERGED_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Merged_Knowledge_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_pipeline_defines_scene_timeline_input_and_evidence_contract():
    content = _read(PIPELINE_PATH)
    for required in (
        '`scope: "scene"`',
        "`sceneRefs`",
        "Scene ID自体をEvidenceRef",
        "別Sceneの値を混ぜない",
        "値を破棄しない",
        "自然文",
        "推定しない",
    ):
        assert required in content


def test_extraction_result_defines_scene_refs_and_semantic_validation():
    content = _read(RESULT_SCHEMA_PATH)
    for required in (
        "| `scope`",
        "| `sceneRefs`",
        '`scope: "scene"`では1件以上必須',
        "`sourceId` / `sceneId`",
        "semantic validation",
        "Stage Aのidentityはscopeをまたいで混ぜない",
    ):
        assert required in content


def test_merged_design_defines_conservative_scene_aggregation():
    content = _read(MERGED_DESIGN_PATH)
    for required in (
        "`sourceTimelineId`は唯一のscope横断自動集約キー",
        "merged `scope: null`",
        "conflictではなく複数粒度のprovenance",
        '`scope: "scene"`候補はcandidate単位',
        "`sceneRefs`",
        "同じlabel / markerTypeだけで広範に自動統合しない",
    ):
        assert required in content


def test_tasks_marks_scene_timeline_extraction_complete():
    content = _read(TASKS_PATH)
    assert "`codex/scene-timeline-extraction`" in content
    assert (
        "~~Scene直下のTimeline情報抽出"
        '（`scope: "scene"`のschema・集約契約を先に設計する）~~'
    ) in content
