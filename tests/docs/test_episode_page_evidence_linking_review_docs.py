"""Episode page Summary/Evidence導線レビューのdocs契約テスト。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
STORY_PAGE = PROJECT_ROOT / "docs/architecture/07_Wiki/Story_Page_Design.md"
WIKI_OUTPUT = PROJECT_ROOT / "docs/architecture/07_Wiki/Wiki_Output_Design.md"
SUMMARY_DESIGN = PROJECT_ROOT / "docs/architecture/06_AI/Story_Summary_Design.md"
EVIDENCE_DESIGN = PROJECT_ROOT / "docs/architecture/06_AI/Evidence_Index_Design.md"
TASKS = PROJECT_ROOT / "TASKS.md"
AI_CONTEXT = PROJECT_ROOT / "AI_CONTEXT.md"


def _contents() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STORY_PAGE, WIKI_OUTPUT, SUMMARY_DESIGN, EVIDENCE_DESIGN)
    )


def test_review_records_limited_episode_page_contract():
    content = STORY_PAGE.read_text(encoding="utf-8")
    for required in (
        "episode-page-evidence-linking-review",
        "episode-page-summary-evidence-linking",
        "対象Episode",
        "Episode Summary本文",
        "Story Summaryの再掲",
        "generationStatus: generated",
        "review.status: reviewed",
        "approved",
        "内部/公開ID",
        "空本文",
        "placeholder",
    ):
        assert required in content
    assert "合成fixtureで回帰テスト" in content
    assert "別作業としてlocal manual review" in content


def test_review_records_evidence_ref_resolution_contract():
    content = EVIDENCE_DESIGN.read_text(encoding="utf-8")
    for required in (
        "Story別Evidence page",
        "公開ID優先",
        "backtick fallback",
        "`evidenceRefs`は空",
        "public-safe projection",
    ):
        assert required in content


def test_review_excludes_unapproved_expansions():
    content = _contents()
    for excluded in (
        "general Story Evidence index link",
        "Episode別Evidence page",
        "episode絞込anchor",
        "schema/storage/CLI option/path変更",
    ):
        assert excluded in content


def test_tasks_records_review_follow_up_and_packet_trial_fail_closed():
    content = TASKS.read_text(encoding="utf-8")
    for required in (
        "episode-page-evidence-linking-review",
        "episode-page-summary-evidence-linking",
        "internal-review-evidence-packet-first-real-trial",
        "非shared ACLを確認できず",
        "cross-consistent snapshotを構成する必須3入力組も確認できなかった",
        "Packetは生成せず",
        "権限変更・異なるsnapshotの寄せ集めは行っていない",
        "ACL是正後",
    ):
        assert required in content


def test_canonical_context_records_review_complete_and_next_implementation():
    content = AI_CONTEXT.read_text(encoding="utf-8")
    for required in (
        "episode-page-evidence-linking-review",
        "対象Episodeの表示可能なEpisode Summary本文と直下の`evidenceRefs`だけ",
        "episode-page-summary-evidence-linking",
        "Episode pageへの表示は未実装",
    ):
        assert required in content
