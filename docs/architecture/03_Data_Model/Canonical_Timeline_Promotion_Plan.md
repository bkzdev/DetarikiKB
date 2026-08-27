# Canonical Timeline Promotion Plan契約

Version: 0.1

Status: Implemented schema contract only

Schema: `schemas/canonical_timeline_promotion_plan.schema.json`

---

# 1. 目的

人間確認済みのCanonical Timeline review edgeを、canonical artifactへまだ書き込まない「反映候補」として表現する。promotion planはinternal-onlyの非実行artifactであり、canonical Timelineの正でも、実行指示でもない。

本契約はschemaと合成fixtureだけを実装する。plan builder / validator / CLI、review packetの読込、canonical artifactの生成・更新、promotion実行は未実装である。

---

# 2. 入力gate

将来のplannerが入力として扱えるのは、validatorを通ったv0.2 review packetのうち、次をすべて満たすedgeだけである。

- `reviewStatus: "confirmed"`
- `relationState`が`before` / `after` / `same_time`のいずれか
- 完全な`humanDecision`がある
- 元方向と全`candidateProvenance`が保持されている

`pending` / `rejected` / `needs_more_context`、`unknown` / `conflict`はplan entryへ入れない。除外したedgeを削除・変更するのではなく、元review packetを正本としてそのまま保持する。

v0.1 review packetは`expiresAt`を持たないため直接入力にせず、後続toolingでv0.2へ明示的に移行・再検証するまで対象外とする。

---

# 3. Root契約

| field | 契約 |
|---|---|
| `schemaVersion` | `"0.1"` |
| `documentType` | `"canonical_timeline_promotion_plan"` |
| `planId` | titleを含まないlocal opaque/time-based ID |
| `classification` | `"local_internal"`固定 |
| `commitAllowed` | `false`固定 |
| `scopeStoryCategory` | `"EVT"`固定 |
| `visibility` | `"internal_only"`固定 |
| `executionMode` | `"plan_only"`固定 |
| `createdAt` | RFC 3339 date-time |
| `sourcePacket` | v0.2 packetの識別・retention情報 |
| `storyPair` | 相異なる2 EVENT story |
| `entries` | 1件以上の非実行plan entry |

`additionalProperties: false`とし、global integer、total order、story-local `canonicalOrder`、release / display / episode number、public ID / URL、raw text / path用fieldを受理しない。

---

# 4. Source packetとretention

`sourcePacket`はpacket ID、review batch ID、`schemaVersion: "0.2"`、作成日時、90日保持期限、plan作成時点の期限状態`expiredAtPlanning`を保持する。

`expiredAtPlanning: true`もschema-validである。期限切れはwarning-onlyであり、自動削除、自動却下、confirmed decisionの取消し、自動promotionの理由にしない。将来のplannerは元packetをread-only validatorへ通し、`expiresAt = createdAt + 90日`を確認してから値を複写する。

schema単独ではsource packet本体とのcross-document照合や90日差分計算を行わない。これらは将来のplanner / semantic validatorの責務である。

---

# 5. Plan entry

各entryは次だけを保持する。

- packet内の追跡用`planEntryKey`
- `proposedAction: "proposed_canonical_edge"`
- `executionStatus: "not_executed"`
- 元ReviewEdge全体を保持する`sourceEdge`

`sourceEdge`はreview packet schemaのReviewEdgeをoffline external referenceとして再利用し、さらにconfirmed + known relation + humanDecision必須へ制限する。`reviewEdgeKey`、`from` / `to`、relation、state reason、全candidate provenance、human decisionをそのまま保持する。

relationの反転、winner選択、dedup、same-time class化、複数packet統合、cycle解決、edge ID採番は行わない。`adoptionStatus: "canonical"`はplanに置かず、confirmed reviewとcanonical adoptionを分離する。

---

# 6. Schemaとsemanticの境界

consumerはpromotion plan、review packet、canonical Timelineの3 schemaをrepo内`referencing.Registry`へ登録し、network / remote schema fetchへ依存しない。

Draft 7だけでは次を動的に検査できないため、将来のplanner / semantic validatorが入力を変更せず確認する。

- source packet ID・story pair・edgeが実際のv0.2 packetと一致すること
- source edgeの両端がstory pair内の異なるstoryであること
- `planEntryKey`と`sourceEdge.reviewEdgeKey`の一意性
- 同じsource edgeが複数planへ重複採用されていないこと
- plan対象edgeを既存canonical artifactへ追加した場合のcycle / same-time矛盾

不一致時もwinnerを選ばず、元packet・provenance・human decisionを削除しない。

---

# 7. Non-goals

- plan builder / validator / CLI / report / file I/O
- `--execute`、canonical artifact write、promotion executor
- candidate生成、Normalized Story本文の自動推定、LLM / provider実装
- humanDecision自動記入、relation反転、winner / score、dedup、複数packet統合
- global integer、total order、story-local `canonicalOrder`比較・補完
- retention cleanup、期限切れによる自動却下・削除
- EVENT外拡張、renderer、Wiki、public projection
- 実packet / plan / artifact、実データfixture、workspace生成物のcommit

---

# 8. 検証

合成`TEST_*`値だけで、Draft 7妥当性、offline external reference、EVENT / internal-only / plan-only、confirmed known relation + humanDecision gate、元edge / provenance保持、v0.2 source packet、期限切れ状態の保持、禁止field拒否を検証する。

```powershell
uv run pytest tests/schemas/test_canonical_timeline_promotion_plan_schema.py
```

---

# 9. 関連文書

- `Canonical_Timeline_Scope_Decision.md`
- `Canonical_Timeline_Schema.md`
- `Canonical_Timeline_Review_Packet.md`
- `../../runbooks/Canonical_Timeline_Review.md`
