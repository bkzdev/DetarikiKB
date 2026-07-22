# Internal Review Evidence Packet Operations Runbook（Packet運用手順）

Version: 0.1
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Internal_Review_Evidence_Packet_Operations.md`

---

# 1. Purpose（目的）

Internal Review Evidence Packet（以下、Packet）を、固定local root
`workspace/review_packets/evidence/` の中だけで安全に生成、確認、期限管理、cleanupする手順を定義する。

Packetはraw text・raw command・内部IDを含みうるhuman review補助資料であり、Public Evidence Index、公開Wiki、Git、promotionの入力ではない。Packetそのもの、およびinventory/cleanupの出力・review noteはすべて非commitである。

このrunbookで扱うoperations CLIは単一である。

```powershell
uv run python scripts/manage_internal_review_evidence_packets.py inventory
uv run python scripts/manage_internal_review_evidence_packets.py cleanup --packet-id <opaque-packet-id>
```

---

# 2. Preconditions（事前条件）

- `docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`を先に読み、PacketとPublic Evidence Indexの境界を理解していること。
- Packet generatorの必須入力であるNormalized Story、Public-safe candidate、projection mappingは、同じprojection作業の組としてoperatorが選ぶこと。現行実装は同一process invocationを機械証明しない。
- `workspace/review_packets/evidence/` がnetwork drive、クラウド同期folder、共有ACL配下ではないことを**operator自身が生成前に確認**すること。OS・同期製品横断の自動判定、同期停止、ACL強制はCLIの保証範囲外である。
- Packet、mapping、review noteをメール、chat、issue、PR添付、外部共有先へコピーしないこと。
- console、shell history、review note、reportへraw本文、raw command、内部ID、title、sourceKey、絶対pathを転記しないこと。

generator、validator、operations CLIはfixed root、Git ignore、tracked file、symlink/junction/reparse point等をfail-closedに検査する。これらの機械検査がPASSしても、network/sync/ACLの運用責任はoperatorから移らない。

---

# 3. Standard flow（標準フロー）

| Step | 操作 | 成果物・判断 |
|---|---|---|
| 1 | generate | fixed ignored rootに新規Packetを生成する |
| 2 | validate | 既存validatorでschema・bundle整合を確認する |
| 3 | inventory | safe aggregateだけで期限・件数・状態を確認する |
| 4 | human review | Packetをローカルで確認し、別のreview noteへDecisionを記録する |
| 5 | cleanup dry-run | 明示した1 packetIdだけを削除予定として再確認する |
| 6 | cleanup execute | operatorが削除を判断した場合だけ実削除する |

Packetの存在、validator PASS、review noteの作成は、いずれも`Approved for promotion`を意味しない。promotion check/copyは従来どおりPublic-safe candidateとreview noteだけを入力とし、Packetのraw componentを読まない。

---

# 4. Generate and validate（生成と検証）

## 4.1 Generate

実データの入力path・内部IDをこのrunbookへ記録せず、ローカル環境で必要最小限の入力を指定する。

```powershell
uv run python scripts/generate_internal_review_evidence_packet.py `
    --normalized-input <local-normalized-input> `
    --public-candidate <local-public-safe-candidate> `
    --projection-mapping <local-projection-mapping.csv>
```

保持期間は既定14日である。変更する場合も`--retention-days`は1〜30日の範囲だけを指定する。contextはPhase 5.4時点でも常に空であり、context opt-inは提供しない。

## 4.2 Validate

generatorが返したopaque `packetId`だけを使い、既存bundleをread-onlyで検証する。

```powershell
uv run python scripts/validate_internal_review_evidence_packet.py `
    --packet-id <opaque-packet-id>
```

`packet-expired`はwarningであり、validatorのexit codeを失敗へ変えない。ただし期限切れPacketを新規reviewの根拠として使わず、必要なら最新の入力snapshotから再生成する。

---

# 5. Inventory and human review（棚卸しと人間レビュー）

## 5.1 Inventory

```powershell
uv run python scripts/manage_internal_review_evidence_packets.py inventory
```

inventoryはPacketのsensitive componentをconsoleへ出さない。表示してよいのはopaque `packetId`、created/expires時刻、active/expired warning、story/entry/component件数、合計size、manifest digest、validationのsafe aggregateだけである。

fixed rootにunknown/temp entryがあれば、名前を表示せずconfig errorとして停止する。operatorはその場でroot配下を探索・削除せず、生成失敗または中断した操作を調査する。期限切れはwarningであり、明示したPacketのcleanupは可能である。

## 5.2 Human review and review note

reviewerはPacket fileをローカルで直接確認し、Decision、reviewer、reviewedAtを既存workflowの別review noteへ記録する。review noteに記録してよいPacket参照は`packetId`、manifest digest、safeな件数・PASS/FAIL・抽象化した所見だけである。

- raw本文、raw command、内部ID mapping、title、sourceKey、absolute pathをreview noteへ転記しない。
- review完了、中止、candidate差し替えのいずれでも、Packetを自動削除しない。operatorがcleanup対象と判断する。
- digest不一致、validation failure、期限切れPacketは新しい承認の根拠に使わず、必要なら再生成する。
- review noteの取込、Decisionの自動判定、`human-review-required`の自動分類変更は行わない。

---

# 6. Cleanup（削除）

cleanupは**1回に1 Packetだけ**を扱う。`--packet-id`はopaque IDを明示指定し、root全体、directory path、glob、期限切れ全件の一括削除は受け付けない。

## 6.1 Dry-run（既定）

```powershell
uv run python scripts/manage_internal_review_evidence_packets.py cleanup `
    --packet-id <opaque-packet-id>
```

`--execute`がない限り削除しない。対象component数、合計size、manifest digestなどsafe aggregateだけを確認する。raw本文、raw command、内部ID、local pathは表示されない。

## 6.2 Execute（明示削除）

```powershell
uv run python scripts/manage_internal_review_evidence_packets.py cleanup `
    --packet-id <opaque-packet-id> `
    --execute
```

execute直前にもroot解決、Git ignore/tracked状態、symlink/junction/reparse point、対象bundleのvalidityを再検査する。対象がinvalid、検査不能、root外へresolve、または途中で状態が変化した場合はfail-closedで削除しない。

invalid PacketはCLIで削除できない。cleanup失敗時はroot外へ移動したり、安易な手動削除へ切り替えたりしない。safe error codeだけを記録し、生成・中断操作とfilesystem境界を確認してから別途対応を判断する。

cleanupは通常のfilesystem削除であり、SSD、backup、journalに対するsecure eraseは保証しない。削除後もPublic Evidence Indexとreview noteは残るが、Packetのraw内容・mappingは残らない。後日の再照合が必要なら、最新のsource snapshotから新規Packetを再生成する。

---

# 7. Exit codes and failure handling（終了コードと障害時対応）

| 状況 | 扱い |
|---|---|
| inventory成功、またはcleanup dry-run/execute成功 | exit 0 |
| Packet validation failure・invalid target | exit 1、cleanupしない |
| packetId不正、root/Git/reparse point検査失敗、未知/temp entry、IO/config error | exit 2、cleanupしない |
| `expiresAt`超過 | warning。inventoryに表示し、明示cleanupまたは再生成を判断する |

期限切れ・review中止・candidate差し替え・digest不一致は既存Packetの修復や上書きでは解決しない。Packetをcleanup対象として扱い、必要なら最新入力から別のopaque `packetId`で再生成する。

---

# 8. Commit safety checklist（commit前確認）

- [ ] `workspace/review_packets/`、`workspace/local_inputs/`、review note、inventory/cleanup出力がcommit対象に含まれていない
- [ ] `git status --short`でPacket由来の生成物やlocal reportが出ていない
- [ ] review noteにraw本文、raw command、内部ID、title、sourceKey、absolute pathを転記していない
- [ ] PacketをPublic Evidence Index、Wiki、PR添付、外部共有へ渡していない

---

# 9. Non-goals（このrunbookとPhase 5.4で行わないこと）

- 実データPacketの生成・commit
- raw内容、mapping、Packetの外部共有
- network/sync/ACLの自動検知・停止・強制、暗号化、OS permission強化
- context opt-inまたはcontext自動収集
- review noteの取込、Decisionの自動承認、review statusによる自動cleanup
- Packetからのpromotion、`promote_evidence_index.py --execute`、Public Evidence Index/Registry/renderer/schemaの変更
- secure eraseの保証

---

# 10. References（関連ドキュメント）

- `docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`
- `docs/runbooks/Evidence_Index_Promotion_Check.md`
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`
- `docs/runbooks/AI_PR_Playbook.md`
