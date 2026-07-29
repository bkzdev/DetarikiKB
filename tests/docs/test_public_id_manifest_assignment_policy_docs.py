"""Public ID assignment policy documentation contract tests."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "Public_ID_Manifest_Assignment.md"
MANIFEST_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "05_Parser" / "Story_Manifest_Design.md"
)
REGISTRY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Public_ID_Registry_Design.md"
)
PUBLIC_ID_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Public_ID_Policy.md"
)
EVIDENCE_INDEX_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Evidence_Index_Design.md"
)
PROMOTION_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Promotion_Policy.md"
)
SUMMARY_GENERATION_PLAN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Story_Summary_Generation_Plan.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(content: str, heading: str, next_heading: str) -> str:
    return content.split(heading, 1)[1].split(next_heading, 1)[0]


def test_runbook_defines_human_reviewed_semi_automatic_policy():
    content = _read(RUNBOOK_PATH)
    assert "候補生成・照合は半自動、確定と永続化は人間レビュー必須" in content
    assert "自動反映してはならない" in content
    assert "reviewRequired: true" in content


def test_runbook_defines_lifecycle_authority_boundary():
    content = _read(RUNBOOK_PATH)
    authority = _section(content, "# 3. 権威とライフサイクル", "# 4.")
    assert "private allocation mappingの正" in authority
    assert "人間確認済みの内部運用上の正" in authority
    assert "予約済みとなる公開IDの不変な正" in authority
    assert "下流のEvidence Index / Summaryが未公開でも予約済み・不変" in authority
    assert "Registryからmanifestへの自動backfillも行わない" in authority


def test_runbook_uses_manifest_episode_number_as_authority():
    content = _read(RUNBOOK_PATH)
    episode_assignment = _section(content, "# 5. publicEpisodeIdの候補作成", "# 6.")
    assert "{publicStoryId}_E{episodeNumber:02d}" in episode_assignment
    assert "人間確認済み`story_manifest.yaml`の`episodeNumber`" in episode_assignment
    assert "entry初出順" in episode_assignment
    assert "ヒューリスティック" in episode_assignment
    assert "不一致はblocking" in episode_assignment


def test_runbook_blocks_unsafe_published_reordering():
    content = _read(RUNBOOK_PATH)
    published_section = _section(content, "## 7.2 Registry登録済みの場合", "# 8.")
    assert "末尾への新規episode追加" in published_section
    assert "途中挿入" in published_section
    assert "blocking" in published_section
    assert "専用のmigration設計" in published_section
    assert "再利用禁止" in content


def test_runbook_preserves_private_data_boundary_and_non_goals():
    content = _read(RUNBOOK_PATH)
    non_goals = _section(content, "# 2. 対象とNon-goals", "# 3.")
    registry_update = _section(content, "## 6.4 Registryへ手動登録する", "# 7.")
    assert "実データ由来の`story_manifest.yaml`" in non_goals
    assert "commit" in non_goals
    assert "自動更新するwriterの実装" in non_goals
    assert "internal ID、sourceKey、raw path、title、subtitleが混入していない" in (
        registry_update
    )


def test_runbook_treats_event_and_raid_numbering_tables_as_private_authority():
    content = _read(RUNBOOK_PATH)
    story_assignment = _section(content, "## 4.1 EVENT / RAID", "## 4.2")
    assert "publicStoryId private allocation mappingについては正" in (story_assignment)
    assert "番号表の割当から逸脱せず" in story_assignment
    assert "独自採番せずblocking" in story_assignment


def test_related_design_docs_reference_assignment_runbook():
    for path in (
        MANIFEST_DESIGN_PATH,
        REGISTRY_DESIGN_PATH,
        PUBLIC_ID_POLICY_PATH,
        EVIDENCE_INDEX_DESIGN_PATH,
        PROMOTION_POLICY_PATH,
        SUMMARY_GENERATION_PLAN_PATH,
    ):
        assert "Public_ID_Manifest_Assignment.md" in _read(path)


def test_registry_design_closes_assignment_open_questions():
    content = _read(REGISTRY_DESIGN_PATH)
    open_questions = content.split("# 8. Open Questions", 1)[1]
    assert "public-id-manifest-assignment-policy" in open_questions
    assert "人間確認済み`story_manifest.yaml`の`episodeNumber`" in open_questions
    assert "自動copy / backfillは行わない" in open_questions


def test_manifest_examples_follow_current_public_id_policy():
    public_id_section = _read(MANIFEST_DESIGN_PATH).split(
        "## 13.2 public ID fields", 1
    )[1]
    assert "EVENT_042_990101" in public_id_section
    assert "RAID_005_990202" in public_id_section
    assert "MAIN_S01_C02` | `MAIN_S01_C02_E01` | `null`" in public_id_section
    assert "OTHER_SAMPLE_SOURCE_E01` | `null`" in public_id_section


def test_tasks_marks_assignment_policy_complete():
    content = _read(TASKS_PATH)
    assert "`codex/public-id-manifest-assignment-policy`" in content
    assert "~~**public-id-manifest-assignment-policy**~~" in content
