"""Internal Review Evidence Packet operations runbookの軽量な契約テスト。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUNBOOK_PATH = (
    PROJECT_ROOT / "docs" / "runbooks" / "Internal_Review_Evidence_Packet_Operations.md"
)


def _read_runbook() -> str:
    return RUNBOOK_PATH.read_text(encoding="utf-8")


def test_packet_operations_runbook_exists_and_has_required_sections():
    assert RUNBOOK_PATH.is_file()
    content = _read_runbook()
    for heading in (
        "# 1. Purpose（目的）",
        "# 2. Preconditions（事前条件）",
        "# 3. Standard flow（標準フロー）",
        "# 4. Generate and validate（生成と検証）",
        "# 5. Inventory and human review（棚卸しと人間レビュー）",
        "# 6. Cleanup（削除）",
        "# 7. Exit codes and failure handling（終了コードと障害時対応）",
        "# 9. Non-goals（このrunbookとPhase 5.4で行わないこと）",
    ):
        assert heading in content


def test_packet_operations_runbook_keeps_local_operator_responsibilities():
    content = _read_runbook()
    for term in (
        "network drive",
        "クラウド同期folder",
        "共有ACL",
        "operator自身が生成前に確認",
        "raw本文、raw command、内部ID、title、sourceKey、絶対pathを転記しない",
        "外部共有先へコピーしない",
    ):
        assert term in content


def test_packet_operations_runbook_defines_single_safe_cli_contract():
    content = _read_runbook()
    for term in (
        "manage_internal_review_evidence_packets.py inventory",
        "cleanup --packet-id <opaque-packet-id>",
        "cleanupは**1回に1 Packetだけ**を扱う",
        "`--execute`がない限り削除しない",
        "unknown/temp entry",
        "名前を表示せずconfig error",
        "invalid PacketはCLIで削除できない",
        "期限切れはwarning",
    ):
        assert term in content


def test_packet_operations_runbook_defines_required_workflow_and_non_goals():
    content = _read_runbook()
    for term in (
        "generate",
        "validate",
        "inventory",
        "human review",
        "review note",
        "cleanup dry-run",
        "cleanup execute",
        "secure eraseは保証しない",
        "root外へ移動したり、安易な手動削除へ切り替えたりしない",
        "実データPacketの生成・commit",
        "context opt-in",
        "review noteの取込",
        "Packetからのpromotion",
    ):
        assert term in content
