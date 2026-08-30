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
CANONICAL_TIMELINE_PROMOTION_PLAN_DOC_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "03_Data_Model"
    / "Canonical_Timeline_Promotion_Plan.md"
)
CANONICAL_TIMELINE_REVIEW_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Canonical_Timeline_Review.md"
)
CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Canonical_Timeline_Promotion.md"
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
        "canonical artifact report、human decision import、promotion plan builder CLI",
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
        "v0.2は`expiresAt = createdAt + 90日`を必須",
        "期限切れでもvalidatorはexit 0を維持",
        "scripts/build_canonical_timeline_review_packet.py",
        "既定はdry-run",
        "replace-free",
        "--render-review-brief",
    ):
        assert required in content


def test_canonical_timeline_review_packet_contract_keeps_values_and_outputs_out():
    content = _read(CANONICAL_TIMELINE_REVIEW_PACKET_DOC_PATH)
    for required in (
        "Normalized Story本文からのcandidate推定",
        "review import、promotion plan builder CLI、自動promotion",
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
        "validatorはfileを書き換えず",
        "network / remote schema fetchへfallbackしない",
        "reviewEdgeKey`重複",
        "storyPair`外、同一story、self",
        "実際に2種類以上の両立不能なrelation",
        "完全同一ReviewEdge record",
        "provenance、status、decision等が異なる観測は重複として削除・統合しない",
        "free-text",
        "fixed issue code",
        "scripts/build_canonical_timeline_review_packet.py",
        "--story-pair-index",
        "--execute",
        "--render-review-brief",
        "作成時刻から90日",
        "期限切れはwarningだけでexit 0",
        "validatorもbuilderも期限切れpacketを削除・変更しない",
        "Normalized Storyからのagent-assisted候補抽出",
        "LLM provider実装や自然文からの自動大量抽出を意味しない",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-review-packet-validator`" in tasks
    assert "file / report writeは0" in tasks
    assert "PR #248" in tasks
    assert "promotion executor" in tasks

    decision = _read(DECISION_FRAME_PATH)
    assert "~~**read-only validator**~~" in decision
    assert "~~**review packet builder**~~" in decision


def test_canonical_timeline_promotion_plan_contract_is_nonexecuting_and_internal():
    content = _read(CANONICAL_TIMELINE_PROMOTION_PLAN_DOC_PATH)
    for required in (
        "schemas/canonical_timeline_promotion_plan.schema.json",
        "confirmed",
        "before` / `after` / `same_time",
        "humanDecision",
        "proposed_canonical_edge",
        "not_executed",
        "expiredAtPlanning: true",
        "warning-only",
        "自動削除",
        "sourceEdge",
        "全`candidateProvenance`",
        "network / remote schema fetchへ依存しない",
        '`adoptionStatus: "canonical"`はplanに置かず',
        "build_canonical_timeline_promotion_plan",
        "validate_canonical_timeline_promotion_plan_consistency",
        "preflight_canonical_timeline_promotion",
        "baseline_invalid",
        "仮document、仮edge、node、provenance本文は返却しない",
        "promotion plan builder CLI",
        "cycle / same-time矛盾 / 完全record重複",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-first-cross-story-sample`" in tasks
    assert "plan / packet SHA-256を指定" in tasks

    decision = _read(DECISION_FRAME_PATH)
    assert "~~**promotion plan contract**~~" in decision
    assert "~~**promotion plan projector / semantic validator**~~" in decision
    assert "~~**promotion read-only preflight**~~" in decision
    assert "~~**promotion executor**~~" in decision

    for path in (
        CANONICAL_TIMELINE_SCHEMA_DOC_PATH,
        CANONICAL_TIMELINE_REVIEW_PACKET_DOC_PATH,
        CANONICAL_TIMELINE_REVIEW_RUNBOOK_PATH,
        TIMELINE_MODEL_PATH,
    ):
        assert "Canonical_Timeline_Promotion_Plan.md" in _read(path)


def test_canonical_timeline_promotion_executor_is_explicit_and_local_only():
    content = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    for required in (
        "scripts/apply_canonical_timeline_promotion.py",
        "workspace/canonical_timeline/canonical_timeline.json",
        "defaultはdry-run",
        "--expected-plan-sha256",
        "--expected-packet-sha256",
        "--expected-artifact-sha256",
        "history",
        "atomic replace",
        "自動rollbackしない",
        "初回小規模sample（2026-08-28）",
        "2 nodes / 1 edge",
        "schema error 0",
        "semantic finding 0",
        "ユーザーの明示承認",
        "実story / episode / Evidence ID、本文、path、digestは文書化・commitしていない",
    ):
        assert required in content

    tasks = _read(TASKS_PATH)
    assert "`codex/canonical-timeline-first-cross-story-sample`" in tasks
    assert "生成物非commit" in tasks


def test_delegated_timeline_review_and_project_milestones_are_recorded():
    decision = _read(DECISION_FRAME_PATH)
    runbook = _read(CANONICAL_TIMELINE_REVIEW_RUNBOOK_PATH)
    tasks = _read(TASKS_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for content in (decision, runbook):
        assert "user-delegated-agent-review" in content
        assert "親agent" in content
        assert "独立監査agent" in content
        assert "1 edgeごと" in content
        assert "unknown` / `conflict" in content

    assert "`codex/canonical-timeline-milestones-and-second-sample`" in tasks
    assert "4 nodes / 2 edges" in tasks
    for required in (
        "# DKB v1 マイルストーン",
        "M1 基盤と安全境界",
        "M4 Canonical curation",
        "M6 公開準備",
        "1 edgeごとの承認要求は行わず",
        "TASKS.md",
    ):
        assert required in milestones

    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    for required in (
        "2件目と委任review（2026-08-28）",
        "confidence 0.99",
        "4 nodes / 2 edges",
        "schema error 0",
        "semantic finding 0",
        "1 edgeごとのユーザー確認を行わない",
        "旧artifactはhistoryへsnapshot",
    ):
        assert required in promotion


def test_first_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-003`",
        "10 nodes / 5 edges",
        "schema error 0",
        "semantic finding 0",
        "3個のignored v0.2 packet / plan",
    ):
        assert required in tasks

    for required in (
        "初回小規模batch（2026-08-28）",
        "3組を別々のv0.2 packet / plan",
        "毎回直前artifactをhistoryへsnapshot",
        "10 nodes / 5 edges",
        "総順序化",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_second_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-004`",
        "16 nodes / 8 edges",
        "8 distinct story pair",
        "既存story pairと重複する候補1組",
        "除外前の中間artifactも内容digest名のhistory snapshotとして復元",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "2回目の小規模batch（2026-08-28）",
        "未登録の明示接続1組へ差し替え",
        "16 nodes / 8 edges",
        "8 distinct story pair",
        "同一batch内の未完了追加の是正",
        "除外前の中間artifactも内容digest名のhistory snapshotとして復元",
        "既存canonical値の変更",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_third_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-005`",
        "22 nodes / 11 edges",
        "11 distinct story pair",
        "作業開始時の既存16 nodes / 8 edgesは内容不変",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "3回目の小規模batch（2026-08-28）",
        "既存8 story pairとの重複がない",
        "22 nodes / 11 edges",
        "11 distinct story pair",
        "既存16 nodes / 8 edgesは内容不変",
        "既存canonical値の変更・rollback",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_fourth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-006`",
        "28 nodes / 14 edges",
        "14 distinct story pair",
        "作業開始時の既存22 nodes / 11 edgesは内容不変",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "4回目の小規模batch（2026-08-28）",
        "既存11 story pairとの重複がない",
        "28 nodes / 14 edges",
        "14 distinct story pair",
        "既存22 nodes / 11 edgesは内容不変",
        "既存canonical値の変更・rollback",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_fifth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-007`",
        "34 nodes / 17 edges",
        "17 distinct story pair",
        "作業開始時の既存28 nodes / 14 edgesは内容不変",
        "別候補1組は`unknown`としてpacket化せず除外",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "5回目の小規模batch（2026-08-29）",
        "別候補1組は`unknown`",
        "既存14 story pairとの重複がない",
        "34 nodes / 17 edges",
        "17 distinct story pair",
        "既存28 nodes / 14 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_sixth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-008`",
        "40 nodes / 20 edges",
        "20 distinct story pair",
        "作業開始時の既存34 nodes / 17 edgesは内容不変",
        "別候補1組は`unknown`としてpacket化せず除外",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "6回目の小規模batch（2026-08-29）",
        "別候補1組は`unknown`",
        "既存17 story pairとの重複がない",
        "40 nodes / 20 edges",
        "20 distinct story pair",
        "既存34 nodes / 17 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_seventh_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-009`",
        "46 nodes / 23 edges",
        "23 distinct story pair",
        "作業開始時の既存40 nodes / 20 edgesは内容不変",
        "別候補1組は`needs_more_context`相当としてpacket化せず除外",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "7回目の小規模batch（2026-08-29）",
        "別候補1組は`needs_more_context`相当",
        "既存20 story pairとの重複がない",
        "46 nodes / 23 edges",
        "23 distinct story pair",
        "既存40 nodes / 20 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_eighth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-010`",
        "48 nodes / 24 edges",
        "24 distinct story pair",
        "作業開始時の既存46 nodes / 23 edgesは内容不変",
        "別候補5組は`needs_more_context`相当としてpacket化せず保留",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "8回目の小規模batch（2026-08-29）",
        "別候補5組は`needs_more_context`相当",
        "既存23 story pairとの重複がない",
        "48 nodes / 24 edges",
        "24 distinct story pair",
        "既存46 nodes / 23 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_ninth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-011`",
        "54 nodes / 27 edges",
        "27 distinct story pair",
        "作業開始時の既存48 nodes / 24 edgesは内容不変",
        "別候補3組は`needs_more_context`相当としてpacket化せず保留",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "9回目の小規模batch（2026-08-29）",
        "別候補3組は`needs_more_context`相当",
        "既存24 story pairとの重複がない",
        "54 nodes / 27 edges",
        "27 distinct story pair",
        "既存48 nodes / 24 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_tenth_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-012`",
        "60 nodes / 32 edges",
        "32 distinct story pair",
        "作業開始時の既存54 nodes / 27 edgesは内容不変",
        "別候補1組は`unknown`としてpacket化せず保留",
        "共有済みepisode nodeを再利用",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "10回目の小規模batch（2026-08-30）",
        "別候補1組は`unknown`",
        "既存27 story pairとの重複がない",
        "60 nodes / 32 edges",
        "32 distinct story pair",
        "既存54 nodes / 27 edgesは内容不変",
        "共有済みepisode nodeを再利用",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


def test_eleventh_delegated_timeline_batch_is_recorded_anonymously():
    tasks = _read(TASKS_PATH)
    promotion = _read(CANONICAL_TIMELINE_PROMOTION_RUNBOOK_PATH)
    milestones = _read(
        PROJECT_ROOT / "docs/architecture/01_Project/Project_Milestones.md"
    )

    for required in (
        "`codex/canonical-timeline-batch-013`",
        "62 nodes / 33 edges",
        "33 distinct story pair",
        "作業開始時の既存60 nodes / 32 edgesは内容不変",
        "別候補5組は`unknown`としてpacket化せず保留",
        "schema error 0",
        "semantic finding 0",
    ):
        assert required in tasks

    for required in (
        "11回目の小規模batch（2026-08-30）",
        "別候補5組は`unknown`",
        "既存32 story pairとの重複がない",
        "62 nodes / 33 edges",
        "33 distinct story pair",
        "既存60 nodes / 32 edgesは内容不変",
        "保留候補の自動確定",
        "public projection",
    ):
        assert required in promotion

    assert "合計33関係を反映済み" in milestones
    assert "11回の小規模batch運用を実証済み" in milestones


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
