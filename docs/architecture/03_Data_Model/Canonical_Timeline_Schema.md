# Canonical Timeline Schema契約

Version: 0.1

Status: Implemented schema and semantic consistency contract

Schema: `schemas/canonical_timeline.schema.json`

---

# 1. 目的

`Canonical_Timeline_Scope_Decision.md`で採択したEVENT限定・partial order・5状態分離・human-confirmed gate・2 story単位review・internal-onlyの初期profileを、合成fixtureで検証可能なJSON Schemaへ固定する。

本書とschemaはデータ表現を定義し、`agents/extractor/canonical_timeline_consistency.py`はschema-validな単一documentに対するsemantic consistencyだけを検査する。実candidateの生成、inventoryからの変換、実edgeの作成、人間判断の取り込み、promotion、保存先、公開は実装しない。

---

# 2. Document契約

rootは次だけを持つ。

| field | 契約 |
|---|---|
| `schemaVersion` | `"0.1"` |
| `documentType` | `"canonical_timeline"` |
| `scopeStoryCategory` | `"EVT"`固定 |
| `visibility` | `"internal_only"`固定 |
| `nodes` | EVENT episode参照の配列 |
| `edges` | cross-story関係候補・review結果の配列 |

`additionalProperties: false`とし、global整数、表示順、公開用fieldを受理しない。空の`nodes` / `edges`はschema上validとするが、実artifact生成CLIはまだ存在しない。

---

# 3. Node

nodeは次の複合参照だけで表す。

```json
{
  "storyId": "EVT_TEST_STORY_A",
  "episodeId": "EVT_TEST_STORY_A_E01",
  "storyCategory": "EVT"
}
```

- nodeの運用上の識別子は`(storyId, episodeId)`であり、global node integerを導入しない
- `canonicalOrder` / `releaseOrder` / `displayOrder` / `episodeNumber` / `sequence` / `globalOrder`を持たない
- nodeの重複はJSON Schemaだけでは複合keyの一意性を検査できないため、semantic validatorで検出する

既存`canonicalOrder`は引き続きstory-localであり、このnodeへコピー・換算しない。

---

# 4. Edge

edgeは`from` / `to`のEpisode参照、`relationState`、`adoptionStatus`、`reviewStatus`、candidate provenance、人間判断を分離して保持する。v0.1ではedge IDを新設しない。

## 4.1 Relation state

`relationState`は次の5値を区別する。

| state | 意味 | `stateReason` |
|---|---|---|
| `before` | fromがtoより前 | `null` |
| `after` | fromがtoより後 | `null` |
| `same_time` | 明示的根拠により同時 | `null` |
| `unknown` | 根拠不足で関係を決めない | 非空文字列必須 |
| `conflict` | 複数根拠が両立しない | 非空文字列必須 |

unknown / conflictをnullや欠落へ潰さない。`same_time`を数値一致から推定しない。

## 4.2 Reviewとadoption

`reviewStatus`と`adoptionStatus`は別fieldとする。review済みでもpromotion前の状態を保持できるよう、`confirmed + candidate`を許容する。

| reviewStatus | humanDecision | adoptionStatus | relationState |
|---|---|---|---|
| `pending` | `null` | `candidate` | 5状態 |
| `confirmed` | 必須 | `candidate`または`canonical` | `before` / `after` / `same_time`だけ |
| `rejected` | 必須 | `candidate` | 5状態 |
| `needs_more_context` | 必須 | `candidate` | 5状態 |

`adoptionStatus: "canonical"`はknown relationかつ`reviewStatus: "confirmed"`かつ`humanDecision`ありの場合だけ許容する。schemaが通ることだけでpromotionは起きない。review結果の取り込みとpromotionは別tool・別PRの責務である。

`humanDecision`はreviewer、決定日時、非逐語のevidence summaryを必須とする。`rejected` / `needs_more_context`も人間判断結果なので、decision provenanceなしでは保存しない。

`decidedAt`はJSON Schemaの`format: "date-time"`とRFC 3339形式のpatternを併用し、format checkerの有無だけに依存せず明らかな不正値を拒否する。

---

# 5. Candidate provenance

各edgeは`candidateProvenance`に最低1件のcandidate provenanceを持つ。conflictは複数根拠の不一致なので最低2件を要求する。

candidate provenanceは少なくとも次を保持する。

- 元candidateの`candidateId`、`evidenceIds`、`sourceType`、confidence、`extractionRun`
- 元観測の`sourceEpisode` / `targetEpisode`複合参照
- 元観測の`observedRelation`

これにより、story pairを無向group化したinventoryから後続artifactを作る場合も、元candidateの方向を失わない。local source pathは長期識別子にせず、candidate / Evidence / extraction runとepisode複合参照をprovenanceの正とする。

---

# 6. Schemaとsemantic validationの境界

Draft 7 JSON Schema v0.1はfield型・enum・必須field・状態組合せを検証する。`validate_canonical_timeline_consistency()`は、schema validation済みの単一dictを変更せず、複数要素を横断する次の不変則を決定的なerror findingとして検査する。

- `(storyId, episodeId)` nodeの重複
- edgeの`from` / `to`が`nodes`に存在すること
- edgeの`from.storyId`と`to.storyId`が異なること。同一story edgeは現行v0.5の責務であり、cross-story graphへ入れない
- 自己edge
- 完全同一edge recordの重複。両端とrelationが同じでもprovenance等が異なる複数観測は重複として破棄しない
- `adoptionStatus: canonical`かつ`reviewStatus: confirmed`のbefore / after / same_timeだけを使ったcycle
- canonical same-time class内のbefore / after矛盾。推移的なsame-time classも同値関係として扱う
- conflict provenanceがedgeの両端を指すことと、観測方向を保って正規化した根拠が実際に2種類以上の両立不能なrelationを含むこと

before / afterはgraph検査のためにだけ有向辺へ正規化し、入力edgeを書き換えない。unknown / conflict、pending、rejected、needs_more_context、`confirmed + candidate`はcanonical graphへ入れず、推論やwinner選択に使わない。実装は再帰に依存しないため、大きな合成graphでもPythonの再帰上限に依存しない。

semantic validatorはschema検証、file I/O、CLI、report永続化、relationやedgeの生成・反転・dedup、review / promotionを行わない。`candidateId` / `evidenceIds` / `extractionRun`の外部candidateへの解決、source confidenceによる採否、unknownの解消、conflict winner選択も、入力corpusと運用契約が未確定なので対象外とする。

---

# 7. Inventoryとの境界

`schemas/cross_story_constraint_inventory.schema.json`は既存Stage A candidateを判定せず収集する入力inventoryである。本schemaは将来のreview・promotion後を含む状態表現であり、inventory reportを自動変換するものではない。

- inventory candidate 0件からnode / edgeを生成しない
- inventoryのrelationを反転・winner選択しない
- inventoryの`candidateObservationCount`やconfidenceをpromotion条件にしない
- actual edgeを作る前に、対象・関係・根拠を人間確認する

---

# 8. Internal-only

canonical Timeline artifactは初期profileでinternal-onlyである。v0.1 schemaは`visibility: "internal_only"`だけを受理し、Wiki / public projectionを定義しない。

review packetのデータ契約は`Canonical_Timeline_Review_Packet.md`で定義する。固定workspace root、v0.2の90日retention、read-only validator、pending packet builderまで実装済みである。human-confirmedなknown relationを非実行proposalとして保持する契約は`Canonical_Timeline_Promotion_Plan.md`で分離し、in-memory projector、cross-document semantic validator、既存artifactへのread-only preflightまで実装済みである。plan CLI / file I/O / executor、canonical artifactへのpromotion copy、公開用IDは未決定で、実データartifactやreview packet / plan / reportはcommitしない。

---

# 9. Non-goals

- 実node / edge / global値の生成・commit
- `canonicalOrder`等のstory間比較・補完・再採番
- candidate生成、自然文推定、LLM / provider実装
- relation / edgeを入力へ反映する反転、same-time class / transitive edge artifact生成、推移閉包、winner / score算出
- canonical artifactのCLI / report、human decision import、promotion plan CLI / file I/O / executor
- EVENT以外へのscope拡張
- renderer、Wiki、public projection
- 既存v0.5 check、inventory、manifest、Stage A / B schemaの変更

---

# 10. 検証

合成`TEST_*`値だけで、5 relation stateのvalid表現、review / adoption / human decisionのconditional、unknown / conflictのreasonとprovenance、EVENT / internal-only固定、禁止順序field・余分fieldの拒否、Draft 7 schema自体の妥当性を検証する。semantic consistency testでは、§6の各rule、canonical以外をgraphへ混ぜない境界、入力不変、入力順に依存しない決定性、再帰に依存しない大規模graphを検証する。

```powershell
uv run pytest tests/schemas/test_canonical_timeline_schema.py tests/extractor/test_canonical_timeline_consistency.py
```

実データfixture、実artifact、内部ID・タイトル・pathは使用しない。

---

# 11. 関連文書

- `Canonical_Timeline_Scope_Decision.md`
- `Timeline.md`
- `Canonical_Timeline_Review_Packet.md`
- `Canonical_Timeline_Promotion_Plan.md`
- `../../runbooks/Cross_Story_Constraint_Inventory.md`
- `../../runbooks/Timeline_Consistency_Check.md`
- `../07_Wiki/Timeline_Page.md`
