# Canonical Timeline Promotion Plan契約

Version: 0.1

Status: Implemented schema contract, in-memory projector, semantic validator, and read-only preflight

Schema: `schemas/canonical_timeline_promotion_plan.schema.json`

---

# 1. 目的

人間確認済みのCanonical Timeline review edgeを、canonical artifactへまだ書き込まない「反映候補」として表現する。promotion planはinternal-onlyの非実行artifactであり、canonical Timelineの正でも、実行指示でもない。

schema契約に加え、検証済みpacketからplanを構築する純粋関数、planとpacketのcross-document整合性を検査する純粋関数、既存canonical Timelineへ仮想追加した場合を検査するread-only preflightを実装する。CLI / file I/O、canonical artifactの生成・更新、promotion実行は未実装である。

---

# 2. 入力gate

projectorが入力として扱えるのは、schemaとreview packet semantic validatorを通ったv0.2 review packetのうち、次をすべて満たすedgeだけである。

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

`expiredAtPlanning: true`もschema-validである。期限切れはwarning-onlyであり、自動削除、自動却下、confirmed decisionの取消し、自動promotionの理由にしない。projectorはplan作成時刻と`expiresAt`を比較して期限状態を記録する。入力前に元packetをread-only validatorへ通し、`expiresAt = createdAt + 90日`を確認する。

schema単独ではsource packet本体とのcross-document照合や90日差分計算を行わない。cross-document照合は本契約のsemantic validator、90日差分は入力前のreview packet validatorが担当する。

---

# 5. Plan entry

各entryは次だけを保持する。

- packet内の追跡用`planEntryKey`
- `proposedAction: "proposed_canonical_edge"`
- `executionStatus: "not_executed"`
- 元ReviewEdge全体を保持する`sourceEdge`

`sourceEdge`はreview packet schemaのReviewEdgeをoffline external referenceとして再利用し、さらにconfirmed + known relation + humanDecision必須へ制限する。`reviewEdgeKey`、`from` / `to`、relation、state reason、全candidate provenance、human decisionをそのまま保持する。

`build_canonical_timeline_promotion_plan`は適格edgeを内容で決定的にsortし、`plan-entry-0001`から連番を付けてdeep copyする。入力packetとedgeは変更しない。適格edgeが0件、v0.2以外、timezone情報のない作成時刻は固定codeで拒否する。

relationの反転、winner選択、dedup、same-time class化、複数packet統合、cycle解決、edge ID採番は行わない。`adoptionStatus: "canonical"`はplanに置かず、confirmed reviewとcanonical adoptionを分離する。

---

# 6. Schemaとsemanticの境界

consumerはpromotion plan、review packet、canonical Timelineの3 schemaをrepo内`referencing.Registry`へ登録し、network / remote schema fetchへ依存しない。

`agents/extractor/canonical_timeline_promotion_plan.py`は次の純粋関数を提供する。

- `build_canonical_timeline_promotion_plan`: 検証済みv0.2 packetから非実行planを構築する
- `validate_canonical_timeline_promotion_plan_consistency`: planと元packetを変更せず、固定ruleの決定的findingを返す

semantic validatorは次を確認する。

- source packetのID・batch・version・作成日時・期限とstory pairが元packetから完全複写されていること
- `expiredAtPlanning`がplan作成時刻とpacket期限の比較結果に一致すること
- packet内の全適格edgeとplan entryが欠落・余分・改変なく1対1対応すること
- `planEntryKey`と`sourceEdge.reviewEdgeKey`が一意であること

`agents/extractor/canonical_timeline_promotion_preflight.py`の`preflight_canonical_timeline_promotion`は、既存canonical Timelineがsemantic-validであることをfail-closedで確認した後、plan edgeをメモリ内だけで`adoptionStatus: "canonical"`の仮edgeへdeep copyする。不足nodeも仮documentへ一意に追加し、既存validatorでcycle / same-time矛盾 / 完全record重複を検査する。

仮document、仮edge、node、provenance本文は返却しない。結果は`clean` / `blocked`、固定rule、関連する`planEntryKey`、件数だけのsafe aggregateである。baselineが不正な場合は詳細を返さず、固定`baseline_invalid` findingだけでplan評価を停止する。

不一致時もwinnerを選ばず、元packet・provenance・human decisionを削除しない。

---

# 7. Non-goals

- CLI / report / file I/O、workspaceへのplan保存
- `--execute`、canonical artifact write、promotion executor
- preflight結果からの自動adoption、自動copy、canonical artifact更新
- candidate生成、Normalized Story本文の自動推定、LLM / provider実装
- humanDecision自動記入、relation反転、winner / score、dedup、複数packet統合
- global integer、total order、story-local `canonicalOrder`比較・補完
- retention cleanup、期限切れによる自動却下・削除
- EVENT外拡張、renderer、Wiki、public projection
- 実packet / plan / artifact、実データfixture、workspace生成物のcommit

---

# 8. 検証

合成`TEST_*`値だけで、Draft 7妥当性、offline external reference、EVENT / internal-only / plan-only、confirmed known relation + humanDecision gate、元edge / provenance保持、v0.2 source packet、期限切れ状態の保持、禁止field拒否、projectionの決定性と入力不変、cross-document改変・欠落・余分・重複検出、preflightの仮node追加・cycle / same-time矛盾 / 完全重複・baseline fail-closed・safe aggregateを検証する。

```powershell
uv run pytest tests/schemas/test_canonical_timeline_promotion_plan_schema.py tests/extractor/test_canonical_timeline_promotion_plan.py tests/extractor/test_canonical_timeline_promotion_preflight.py
```

---

# 9. 関連文書

- `Canonical_Timeline_Scope_Decision.md`
- `Canonical_Timeline_Schema.md`
- `Canonical_Timeline_Review_Packet.md`
- `../../runbooks/Canonical_Timeline_Review.md`
