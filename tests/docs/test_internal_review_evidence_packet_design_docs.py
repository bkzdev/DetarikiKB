"""Internal Review Evidence Packet設計文書の軽量な整合性テスト。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
DESIGN_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Internal_Review_Evidence_Packet_Design.md"
)
EVIDENCE_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Evidence_Index_Design.md"
)
PUBLIC_ID_POLICY_PATH = (
    PROJECT_ROOT
    / "docs"
    / "architecture"
    / "06_AI"
    / "Evidence_Index_Public_ID_Policy.md"
)
REGISTRY_DESIGN_PATH = (
    PROJECT_ROOT / "docs" / "architecture" / "06_AI" / "Public_ID_Registry_Design.md"
)
AI_CONTEXT_PATH = PROJECT_ROOT / "AI_CONTEXT.md"
TASKS_PATH = PROJECT_ROOT / "TASKS.md"


def _read_design() -> str:
    return DESIGN_PATH.read_text(encoding="utf-8")


def test_packet_design_doc_exists_and_has_required_sections():
    assert DESIGN_PATH.is_file()
    content = _read_design()
    for heading in (
        "# 1. Background",
        "# 2. Goals",
        "# 3. Non-goals",
        "# 4. Trust boundaryと責務分離",
        "# 5. Bundle単位と保存layout",
        "# 6. 入力とsource snapshot",
        "# 7. Data model",
        "# 8. 内部ID・公開ID mapping policy",
        "# 9. Raw contentとcontext policy",
        "# 10. Generationとvalidation boundary",
        "# 11. Human reviewとpromotion workflow",
        "# 12. Access、retention、cleanup",
        "# 13. Security / failure model",
        "# 14. Implementation phases",
        "# 15. Open questions",
    ):
        assert heading in content


def test_packet_design_separates_public_and_internal_contracts():
    content = _read_design()
    assert "別schema・別loader/validator・別CLI" in content
    assert "visibility.public: false" in content
    assert "論理的なread-only境界" in content
    assert "commitAllowed" in content
    assert '"commitAllowed": false' in content


def test_packet_design_fixes_local_bundle_layout_without_internal_ids_in_names():
    content = _read_design()
    assert "workspace/review_packets/evidence/" in content
    assert "erp-YYYYMMDDTHHMMSSZ-<8 lowercase hex>" in content
    assert "manifest.json" in content
    assert "mappings/evidence-id-map.csv" in content
    assert "story-0001.json" in content
    assert "file名にはsourceKey、story title、内部/公開IDを使わない" in content


def test_packet_design_reuses_projection_mapping_contract():
    content = _read_design()
    for field in (
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
    ):
        assert field in content
    assert "cross-consistent snapshot" in content
    assert "cross-reference検証" in content
    assert "公開IDを再採番" in content
    assert "Packetのmapping tableをRegistryへ転記しない" in content


def test_packet_design_limits_raw_content_and_context():
    content = _read_design()
    assert "`public-candidate`（既定）" in content
    assert "`explicit-entry-list`" in content
    assert "全blockを無条件にraw化するmodeは設けない" in content
    assert "前後contextは既定で空" in content
    assert "前後それぞれ最大1 block" in content
    assert "最大500 Unicode code point" in content
    assert "raw DEC file全体" in content
    assert "Normalized Story/Extraction Resultの全dump" in content
    assert "rawContent.reason" in content


def test_packet_design_defines_fail_closed_output_and_safe_reporting():
    content = _read_design()
    for term in (
        "path traversal",
        "symlink",
        "junction",
        "git ls-files",
        "atomic rename",
        "final bundleを作らない",
        "raw text、raw command、内部ID",
    ):
        assert term in content


def test_packet_design_keeps_review_decision_and_promotion_separate():
    content = _read_design()
    assert "Decision、reviewer、reviewedAtは既存review noteへ記録" in content
    assert "Packetが存在するだけで`Approved for promotion`とみなさない" in content
    assert "human-review-required" in content
    assert "自動で`promotion-candidate`へ変更しない" in content


def test_packet_design_defines_ephemeral_retention_and_safe_cleanup():
    content = _read_design()
    assert "retention classは`ephemeral`固定" in content
    assert "既定保持期間は生成から14日" in content
    assert "1〜30日" in content
    assert "dry-run既定" in content
    assert "`--execute`必須" in content
    assert "secure eraseは保証しない" in content


def test_packet_design_uses_only_synthetic_example_ids():
    content = _read_design()
    assert "TEST_INTERNAL_STORY" in content
    assert "TEST_PUBLIC_001" in content
    assert "EVENT_" not in content
    assert "RAID_" not in content


def test_related_canonical_docs_link_to_packet_design():
    filename = DESIGN_PATH.name
    for path in (
        EVIDENCE_DESIGN_PATH,
        PUBLIC_ID_POLICY_PATH,
        REGISTRY_DESIGN_PATH,
        AI_CONTEXT_PATH,
    ):
        assert filename in path.read_text(encoding="utf-8")


def test_tasks_records_design_complete_and_followup_phases():
    content = TASKS_PATH.read_text(encoding="utf-8")
    assert "codex/internal-review-evidence-packet-design" in content
    assert "internal-review-evidence-packet-schema-validator" in content
    assert "internal-review-evidence-packet-generator" in content
    assert "internal-review-evidence-packet-operations" in content


def test_packet_design_records_phase_5_2_implementation_boundary():
    content = _read_design()
    for term in (
        "Phase 5.1設計確定・Phase 5.2 schema/validator実装済み",
        "internal_review_evidence_packet_validation_report.schema.json",
        "validatorは固定root配下の既存bundleを**read-only**で検査する",
        (
            "外部のsource candidate、Normalized Story、Registry入力とのcross-checkは、"
            "入力を読むPhase 5.3 generatorの責務"
        ),
        "Phase 5.2 validatorはbundle内の次を検証する",
        "| Phase 5.2: `internal-review-evidence-packet-schema-validator`",
        "**完了**",
    ):
        assert term in content


def test_canonical_status_distinguishes_validator_from_generator_and_cleanup():
    context = AI_CONTEXT_PATH.read_text(encoding="utf-8")
    tasks = TASKS_PATH.read_text(encoding="utf-8")
    assert "manifest/story/selection/safe validation reportの4 schema" in context
    assert "既存bundleを変更しないvalidatorは実装済み" in context
    assert "generator、およびcleanup運用CLIは未実装" in context
    assert "internal-review-evidence-packet-schema-validator`で実装完了" in tasks
    assert "外部入力とのcross-checkはgeneratorへ分離" in tasks
