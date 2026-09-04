"""Zensical合成dual-buildとgenerator判断の文書契約を固定する。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DECISION_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "07_Wiki"
    / "Zensical_Synthetic_Dual_Build_Decision.md"
)
PUBLISHING_DECISION_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "07_Wiki"
    / "Public_Publishing_Workflow_Decision.md"
)
AI_CONTEXT_PATH = PROJECT_ROOT / "AI_CONTEXT.md"
TASKS_PATH = PROJECT_ROOT / "TASKS.md"
MILESTONES_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "01_Project" / "Project_Milestones.md"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dual_build_decision_records_reproducible_synthetic_result() -> None:
    decision = _read(DECISION_PATH)

    for required in (
        "Status: Accepted",
        "Decision date: 2026-09-02",
        "Zensical v0.0.57",
        'uvx --from "zensical==0.0.57" zensical build --strict --clean',
        "MkDocs 1.6.1 / Material 9.7.6",
        "| 入力Markdown page | 24 | 24 |",
        "| HTML route（404を含む） | 25 | 25 |",
        "| h1〜h6見出し | 119 | 119 |",
        "| search index entry | 118 | 118 |",
        "route差分",
        "Timeline禁止marker露出",
        "desktop 1280×720",
        "mobile 390×844",
        "横overflow 0",
        "公開実装へ進むgeneratorはZensical（B）",
        "Zensical 0.0.57をexact pin",
        "projection_candidate",
    ):
        assert required in decision


def test_dual_build_decision_keeps_private_and_publish_boundaries() -> None:
    decision = _read(DECISION_PATH)

    for required in (
        "internal artifact、private mappingは使わない",
        "workspace/wiki_preview/zensical_dual_build/",
        "commitしない",
        "実public-safe入力のpush",
        "公開URL",
        "production deployを承認しない",
        "Zensical dependency追加・`uv.lock`更新・CI dual-build化は後続実装で完了",
        "MkDocs / Material baselineの廃止",
        "実Wiki Markdown / HTMLの生成・commit・push",
    ):
        assert required in decision


def test_handoff_docs_record_zensical_selection_and_next_step() -> None:
    publishing = _read(PUBLISHING_DECISION_PATH)
    context = _read(AI_CONTEXT_PATH)
    tasks = _read(TASKS_PATH)
    milestones = _read(MILESTONES_PATH)

    assert "Zensical_Synthetic_Dual_Build_Decision.md" in publishing
    assert "P2=B" in publishing
    assert "Zensical 0.0.57 exact pinと合成dual-buildを標準化" in publishing
    assert "Zensical_Synthetic_Dual_Build_Decision.md" in context
    assert "`codex/zensical-exact-pin-dual-build`" in tasks
    assert "`codex/zensical-synthetic-dual-build-spike`" in tasks
    assert "次はpublic-safe構造化入力の保存schema" in tasks
    assert "Zensical exact pin / dual-buildを統合済み" in milestones
