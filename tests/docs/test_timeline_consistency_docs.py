"""Timeline横断整合性checkの設計・運用文書契約を固定する。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = PROJECT_ROOT / "docs" / "runbooks" / "Timeline_Consistency_Check.md"
CROSS_STORY_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Cross_Story_Constraint_Inventory.md"
)
PIPELINE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Pipeline.md"
)
RESULT_SCHEMA_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Extraction_Result_Schema.md"
)
MERGED_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Merged_Knowledge_Design.md"
)
DECISION_FRAME_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "03_Data_Model"
    / "Canonical_Timeline_Scope_Decision.md"
)
CANONICAL_TIMELINE_SCHEMA_DOC_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "03_Data_Model"
    / "Canonical_Timeline_Schema.md"
)
CANONICAL_TIMELINE_REVIEW_PACKET_DOC_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "03_Data_Model"
    / "Canonical_Timeline_Review_Packet.md"
)
CANONICAL_TIMELINE_REVIEW_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Canonical_Timeline_Review.md"
)
TIMELINE_MODEL_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "03_Data_Model" / "Timeline.md"
)
TIMELINE_PAGE_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Timeline_Page.md"
)
WIKI_OUTPUT_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "07_Wiki" / "Wiki_Output_Design.md"
)
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_runbook_defines_stage_a_cycle_check_contract():
    content = _read(RUNBOOK_PATH)
    for required in (
        "scripts/check_timeline_consistency.py",
        'kind: "relative_order"',
        "timeline_relative_order_cycle",
        "timeline_relative_order_within_same_time_class",
        "Union-Find",
        "反復Kosaraju法",
        "candidate ID・Evidence ID・入力path",
        "target_not_loaded",
        "timeline_episode_order_field_value_conflict",
        "numericIgnoredObservations",
        "extractionRun",
        "timeline_canonical_order_relative_constraint_conflict",
        "cross_story_constraint",
        "releaseOrder` / `displayOrder`は補完・fallback・比較に使わない",
        "readyForCanonicalReview",
        "observedOrderBuckets",
        "readinessがfalseであることだけでは失敗にせず",
    ):
        assert required in content


def test_runbook_defines_report_and_output_safety():
    content = _read(RUNBOOK_PATH)
    for required in (
        "schemas/timeline_consistency_report.schema.json",
        'status: "passed"',
        'status: "needs_review"',
        'status: "invalid_input"',
        "workspace/dry_runs/",
        "既存reportは上書きしない",
    ):
        assert required in content


def test_architecture_keeps_check_separate_from_stage_b_merge():
    for path in (PIPELINE_PATH, RESULT_SCHEMA_PATH, MERGED_DESIGN_PATH):
        content = _read(path)
        assert "scripts/check_timeline_consistency.py" in content
        assert "same_time" in content
    assert "Stage B自体は順序graphの整合性判定を行わない" in _read(MERGED_DESIGN_PATH)
    assert "この代表値はcanonical chronologyの採用値ではない" in _read(
        MERGED_DESIGN_PATH
    )


def test_tasks_records_completed_stages_and_remaining_scope():
    content = _read(TASKS_PATH)
    assert "`codex/timeline-episode-order-value-conflict`" in content
    assert "`codex/timeline-canonical-relative-consistency`" in content
    assert "`codex/timeline-canonical-coverage-readiness`" in content
    assert "timeline contradiction detectionの第1〜第5段階" in content
    assert "総順序判定、canonical Timeline確定、cross-story chronology" in content


def test_docs_record_first_real_readiness_dry_run_without_committing_reports():
    runbook = _read(RUNBOOK_PATH)
    tasks = _read(TASKS_PATH)
    for required in (
        "初回実データdry-run（2026-08-03）",
        "resolved / valid input: 733 / 733",
        "comparable / missing / ambiguous episode: 0 / 733 / 0",
        "`readyForCanonicalReview: true`: 0 / 72 story",
        "両runのreportはv0.5 schema error 0件",
        "report本体は内部IDとlocal pathを含むため"
        "`workspace/dry_runs/`だけに保持し、commitしない",
        "人間確認後に`story_manifest.yaml`へ保存",
        "個別episodeの根拠を人間が確認してmanifestへ値を割り当て",
    ):
        assert required in runbook
    assert "`codex/timeline-canonical-readiness-first-real-dry-run`" in tasks
    assert "全733 episodeでcanonical observation未付与" in tasks


def test_global_scope_decision_records_accepted_profile_and_safety_boundary():
    content = _read(DECISION_FRAME_PATH)
    for required in (
        "Status: Accepted",
        "Decision date: 2026-08-23",
        "# 2. 現在確定している境界",
        "# 4. 採択後も維持する不変則",
        "## D1. 初期global scope",
        "## D2. 順序表現",
        "## D3. 関係状態",
        "## D4. 許容するcross-story根拠",
        "## D5. Review unitとpromotion gate",
        "## D6. Internal / public出力",
        "partial order graph",
        "same_time",
        "unknown",
        "conflict",
        "cross_story_constraint",
        "provenance",
        "2026-08-23のユーザー承認",
        "# 7. 採択記録",
    ):
        assert required in content
    assert "Status: Proposed" not in content


def test_global_scope_decision_frame_rejects_implicit_global_promotion():
    content = _read(DECISION_FRAME_PATH)
    for required in (
        "既存`canonicalOrder`の数値をstory間で比較しない",
        "`releaseOrder` / `displayOrder` / `episodeNumber`",
        "winner選択",
        "自動promotionしない",
        "canonical Timelineのpromotionまたは公開",
    ):
        assert required in content


def test_timeline_docs_link_to_global_scope_decision_frame():
    for path in (
        RUNBOOK_PATH,
        TIMELINE_MODEL_PATH,
        TIMELINE_PAGE_PATH,
        WIKI_OUTPUT_DESIGN_PATH,
    ):
        assert "Canonical_Timeline_Scope_Decision.md" in _read(path)


def test_tasks_records_global_scope_decision_frame_and_adoption():
    content = _read(TASKS_PATH)
    assert "`codex/timeline-canonical-global-scope-decision-frame`" in content
    assert "docs-only、Status: Proposed" in content
    assert "`codex/timeline-canonical-global-scope-decision`" in content
    assert "Status: Accepted" in content


def test_cross_story_inventory_docs_fix_nonjudgmental_internal_contract():
    runbook = _read(CROSS_STORY_RUNBOOK_PATH)
    decision = _read(DECISION_FRAME_PATH)
    timeline_runbook = _read(RUNBOOK_PATH)
    for required in (
        "scripts/build_cross_story_constraint_inventory.py",
        "schemas/cross_story_constraint_inventory.schema.json",
        'scopeStoryCategory: "EVT"',
        "candidate ID、Evidence ID",
        "target_not_loaded",
        "target_out_of_scope",
        "ambiguous_target_story",
        "同じcandidateや同じ関係が複数回観測されても重複排除しない",
        "canonicalOrder",
        "internal-only",
        "既存reportの上書きは禁止",
        "内部ID・入力path・出力pathを表示しない",
    ):
        assert required in runbook
    for content in (decision, timeline_runbook):
        assert "Cross_Story_Constraint_Inventory.md" in content
        assert "scripts/build_cross_story_constraint_inventory.py" in content


def test_cross_story_inventory_does_not_promote_or_compare_candidates():
    content = _read(CROSS_STORY_RUNBOOK_PATH)
    for required in (
        "候補の発見・判定・昇格を行わない",
        "story-local `canonicalOrder`をstory間で比較、再採番、補完すること",
        "winner、score、edge status、canonical artifactを作ること",
        "自然文自動推定を追加しない",
    ):
        assert required in content


def test_cross_story_inventory_records_first_real_empty_dry_run_safely():
    content = _read(CROSS_STORY_RUNBOOK_PATH)
    for required in (
        "初回実データdry-run（2026-08-23）",
        "resolved / valid / invalid / skipped input: 537 / 537 / 0 / 0",
        "relative candidate / cross-story observation / story pair: 0 / 0 / 0",
        "両reportはbyte-identical",
        "内部IDとlocal pathを含むため`workspace/dry_runs/`だけに保持し、commitしない",
        "候補・edge・global順序を補完しない",
    ):
        assert required in content
    tasks = _read(TASKS_PATH)
    assert "`codex/timeline-cross-story-constraint-inventory`" in tasks
    assert "全候補分類0、両report byte-identical" in tasks


def test_canonical_timeline_schema_docs_fix_internal_contract_and_gates():
    content = _read(CANONICAL_TIMELINE_SCHEMA_DOC_PATH)
    for required in (
        "schemas/canonical_timeline.schema.json",
        'scopeStoryCategory` | `"EVT"`固定',
        'visibility` | `"internal_only"`固定',
        "`(storyId, episodeId)`",
        "before",
        "after",
        "same_time",
        "unknown",
        "conflict",
        "reviewStatus",
        "adoptionStatus",
        "confirmed + candidate",
        "humanDecision",
        "candidateProvenance",
        "conflictは複数根拠の不一致なので最低2件",
        "validate_canonical_timeline_consistency()",
        "`from.storyId`と`to.storyId`が異なること",
        "完全同一edge recordの重複",
        "canonical same-time class内のbefore / after矛盾",
        "実際に2種類以上の両立不能なrelation",
        "入力edgeを書き換えない",
        "`confirmed + candidate`はcanonical graphへ入れず",
        'format: "date-time"`とRFC 3339形式のpatternを併用',
        "実artifact生成CLIはまだ存在しない",
        "Wiki / public projectionを定義しない",
    ):
        assert required in content


def test_canonical_timeline_schema_docs_keep_existing_values_and_outputs_out():
    content = _read(CANONICAL_TIMELINE_SCHEMA_DOC_PATH)
    for required in (
        "既存`canonicalOrder`は引き続きstory-local",
        "実node / edge / global値の生成・commit",
        "candidate生成、自然文推定",
        "same-time class / transitive edge artifact生成",
        (
            "schema validationを含むCLI / report、実review packet生成、"
            "human decision import、promotion"
        ),
        "renderer、Wiki、public projection",
        "既存v0.5 check、inventory、manifest、Stage A / B schemaの変更",
    ):
        assert required in content


def test_canonical_timeline_semantic_validator_remains_pure_and_synthetic_only():
    content = _read(CANONICAL_TIMELINE_SCHEMA_DOC_PATH)
    for required in (
        "schema validation済みの単一dictを変更せず",
        "unknown / conflict、pending、rejected、needs_more_context",
        "file I/O、CLI、report永続化",
        "winner選択",
        "再帰に依存しない",
        "合成`TEST_*`値だけ",
        "tests/extractor/test_canonical_timeline_consistency.py",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-semantic-consistency`" in tasks
    assert "完全同一edge record重複" in tasks
    assert "実node / edge、review / promotion" in tasks

    decision = _read(DECISION_FRAME_PATH)
    assert "~~**consistency check**~~" in decision
    assert "canonical_timeline_consistency.py" in decision


def test_canonical_timeline_review_packet_contract_is_internal_and_non_promoting():
    content = _read(CANONICAL_TIMELINE_REVIEW_PACKET_DOC_PATH)
    for required in (
        "schemas/canonical_timeline_review_packet.schema.json",
        "相異なる2 EVENT story",
        '`classification` | `"local_internal"`固定',
        "`commitAllowed` | `false`固定",
        '`scopeStoryCategory` | `"EVT"`固定',
        '`visibility` | `"internal_only"`固定',
        "pending",
        "confirmed",
        "rejected",
        "needs_more_context",
        "unknown / conflictをconfirmedへ変換せず",
        "`adoptionStatus`はpacketに置かない",
        "confirmed edgeもreview済みcandidate",
        "candidateProvenance",
        "offline external reference",
        "networkやremote schema fetchへ依存しない",
        "workspace限定・非commit",
        "`stateReason` / `evidenceSummary` / `notes`",
        "schema単独ではpair外EpisodeRefを受理しうる",
        "validate_canonical_timeline_review_packet_consistency()",
        "実packet生成、review結果の取り込み",
    ):
        assert required in content


def test_canonical_timeline_review_packet_contract_keeps_values_and_outputs_out():
    content = _read(CANONICAL_TIMELINE_REVIEW_PACKET_DOC_PATH)
    for required in (
        "candidate生成、inventoryからの自動変換",
        "canonical artifact反映、review import、promotion",
        "global integer、total order、story-local `canonicalOrder`比較・補完",
        "renderer、Wiki、public projection",
        "実データfixture、実packet、raw / generated artifactのcommit",
        "既存canonical Timeline schema / semantic validator",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-review-packet-contract`" in tasks
    assert "packetに`adoptionStatus`を持たせず" in tasks

    decision = _read(DECISION_FRAME_PATH)
    assert "~~**review packet contract**~~" in decision
    assert "Canonical_Timeline_Review_Packet.md" in decision


def test_canonical_timeline_review_validator_is_read_only_and_non_promoting():
    content = _read(CANONICAL_TIMELINE_REVIEW_RUNBOOK_PATH)
    for required in (
        "scripts/validate_canonical_timeline_review_packet.py",
        "workspace/review_packets/canonical_timeline/",
        "Git worktree root",
        "symlink / Windows reparse point",
        "常に非変更",
        "network / remote schema fetchへfallbackしない",
        "reviewEdgeKey`重複",
        "storyPair`外、同一story、self",
        "実際に2種類以上の両立不能なrelation",
        "完全同一ReviewEdge record",
        "provenance、status、decision等が異なる観測は重複として削除・統合しない",
        "free-text",
        "fixed issue code",
        "file / report write、retention、promotion",
        "packet v0.1 schemaは`expiresAt`を持たない",
        "inventory 0件から自然文推定・LLM抽出で候補を補完しない",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-review-packet-validator`" in tasks
    assert "file / report writeは0" in tasks

    decision = _read(DECISION_FRAME_PATH)
    assert "~~**read-only validator**~~" in decision


def test_timeline_and_wiki_docs_link_schema_without_enabling_public_output():
    for path in (
        DECISION_FRAME_PATH,
        TIMELINE_MODEL_PATH,
        TIMELINE_PAGE_PATH,
        WIKI_OUTPUT_DESIGN_PATH,
    ):
        content = _read(path)
        assert "Canonical_Timeline_Schema.md" in content
        assert "internal" in content
    assert "本ページのrenderer・source・URLを変更しない" in _read(TIMELINE_PAGE_PATH)


def test_tasks_records_canonical_timeline_schema_contract():
    content = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-schema-contract`" in content
    assert "schemas/canonical_timeline.schema.json" in content
    assert "実node / edge / artifact" in content
