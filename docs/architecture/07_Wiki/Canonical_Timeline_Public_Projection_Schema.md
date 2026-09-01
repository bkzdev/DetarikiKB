# Canonical Timeline Public Projection Schema契約

Version: 0.1
Status: Accepted
Schema: `schemas/canonical_timeline_public_projection.schema.json`
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

`Canonical_Timeline_Public_Projection_Decision.md`で採択したP1〜P7を、公開専用JSON documentのfield allowlistとして固定する。

このschemaはinternal canonical artifactを公開可能と宣言するものではない。公開projectionはinternal documentの縮小コピーではなく、許可fieldだけで新しく構成する。projector、cross-document semantic validator、preflight、renderer、実データ実行、hosting、deployは後続PRとする。

---

# 2. 固定profile

| field | 固定値 | 意味 |
|---|---|---|
| `schemaVersion` | `0.1` | 初期public projection契約 |
| `documentType` | `canonical_timeline_public_projection` | internal artifactと別document |
| `visibility` | `public` | 公開用fieldだけを持つprojection候補 |
| `publishStatus` | `projection_candidate` | schema validだけではpublish-readyにしない |
| `scope` | `event` | 採択済みEVENT限定scope |
| `purpose` | `confirmed_relation_navigation` | 完全な年表ではなく関係ナビゲーション |
| `coverageNoticeKey` | `partial_confirmed_relations_only` | 網羅的・総順序ではないという定型注記key |

rootを含む全objectは`additionalProperties: false`とする。内部fieldを削除し忘れたdocumentを受理するのではなく、allowlist外fieldが1件でもあればschema errorにする。

`components: []`と`unresolvedRelationSummary: null`の空projectionも有効である。適格relationが0件の場合に、内部値へfallbackせず空の公開候補を生成できるようにする。

---

# 3. Component

`components[]`は、確認済みrelationで接続されたEpisode集合を表示単位へまとめる。

```json
{
  "componentKey": "component-0001",
  "nodes": [],
  "relations": []
}
```

- `componentKey`は`component-NNNN`形式のprojection-local keyであり、canonical IDではない
- keyの番号、componentの配列順、画面上の上下はchronologyを表さない
- 1 componentは2 node以上・1 relation以上を持つ
- exact duplicate component / node / relationは`uniqueItems`で拒否する
- 同じpublic IDを異なるlabelで重複させるケース、relation両端のnode実在、component間重複、self relationはcross-document semantic validatorで拒否する。JSON Schema単体の責務にはしない

---

# 4. Public Episode node

nodeのallowlistは次の4 fieldだけである。

| field | 必須 | 条件 |
|---|---|---|
| `publicStoryId` | yes | `^[A-Z][A-Z0-9_]*$` |
| `publicEpisodeId` | yes | `^[A-Z][A-Z0-9_]*$` |
| `storyLabel` | yes | 1〜200文字、改行なし |
| `episodeLabel` | yes | 1〜200文字、改行なし |

public IDはPublic ID Registryまたは同等の人間確認済みpublic sourceから取得する。欠落時にinternal `storyId` / `episodeId`へfallbackしない。

labelは公開許可済みmetadataだけを入力にしなければならない。schemaは型・長さ・改行禁止を保証するが、文字列の由来や本文断片を判定できない。後続preflightでallowlisted metadataとの一致、禁止marker、内部ID、URL / path等のexposure検査を必須にする。

---

# 5. Public relation

relationのallowlistは次の4 fieldだけである。

| field | 必須 | 条件 |
|---|---|---|
| `fromPublicEpisodeId` | yes | public ID pattern |
| `toPublicEpisodeId` | yes | public ID pattern |
| `relationState` | yes | `before` / `after` / `same_time` |
| `labelKey` | yes | stateに対応する定型key |

stateとlabel keyの対応をschema conditionalで固定する。

| `relationState` | `labelKey` |
|---|---|
| `before` | `timeline_before` |
| `after` | `timeline_after` |
| `same_time` | `timeline_same_time` |

rendererはlabel keyを公開文言へ変換する。projection側に自由記述labelを持たせない。

入力適格性は、internal edgeが`adoptionStatus: canonical`、`reviewStatus: confirmed`、known relationであることを後続projectorが検証する。schemaはinternal edgeを参照しないため、このcross-document条件を単独では証明しない。

---

# 6. Unknown / conflict aggregate

`unknown` / `conflict`は個別relationとして公開しない。`unresolvedRelationSummary`は次のsafe aggregate、または`null`だけを許可する。

| field | 固定・制約 |
|---|---|
| `countScope` | `canonical_artifact_only` |
| `noticeKey` | `unresolved_relations_not_shown` |
| `unknownCount` | 0以上の整数 |
| `conflictCount` | 0以上の整数 |

この件数は入力canonical artifact内だけを対象とし、全corpus・未packet化候補・将来発見される関係の総数を意味しない。個別Story pair、理由、provenance、本文、内部IDを含めない。

表示を行わないprofileでは`null`を使える。ただしprojector / preflightのinternal reportでは、除外・保留件数を黙って破棄せずsafe aggregateとして記録する。public documentの`null`はinternal情報の削除を意味しない。

---

# 7. 明示的な禁止field

`additionalProperties: false`により、少なくとも次のfield群はどの階層にも追加できない。

- internal `storyId` / `episodeId`、candidate ID、Evidence ID
- `candidateProvenance`、`humanDecision`、reviewer、confidence
- `stateReason`、自由記述reason / notes / details
- extraction run、model、prompt、timestamp
- input / artifact digest、local path、source path、URL
- story-local `canonicalOrder`、release / display / episode order
- raw本文、raw command、引用、Evidence本文

禁止語の再帰scanはJSON Schemaだけでは完全に保証できないため、後続preflightでdocument全体を検査する。schemaの役割は、内部値を入れられるfield自体を構造的に作らせないことである。

---

# 8. Schemaと後続semantic検査の責務分離

## 8.1 Schemaで保証する

- root profile固定
- 全objectのfield allowlist
- public ID形式
- labelの型・長さ・改行禁止
- known relation state（`before` / `after` / `same_time`）だけの列挙
- relation stateと定型label keyの一致
- componentの最小要素数とexact duplicate拒否
- unresolved aggregateの固定scope・非負整数
- 空projectionの許容

## 8.2 後続projector / validatorで保証する

- input digest pinとinternal canonical schema / semantic valid
- canonical adoption・confirmed review・known relation適格性
- public ID Registryとの完全一致・一意性・両端completeness
- node / relation参照、self relation、component partitionの整合
- connected componentの決定的生成と入力順非依存
- public label sourceのallowlist一致
- 内部ID、本文、path、URL、digest、禁止markerのexposure 0
- 同じ入力から同じbyte列を生成する決定性
- input document不変
- failure時にpublish-readyを返さないfail-closed動作

---

# 9. 合成fixture検証

`tests/fixtures/canonical_timeline_public_projection/valid_projection.json`は合成public IDと合成labelだけを持つ。

`tests/schemas/test_canonical_timeline_public_projection_schema.py`で次を固定する。

- Draft 7 schema自体とvalid / empty projection
- root profile全fieldの必須性と`publishStatus: projection_candidate`
- profile constとunknown field拒否
- internal ID / review / provenance / reason field拒否
- `unknown` / `conflict` relation拒否
- state / label key不一致拒否
- public ID pattern、label長・改行制約
- exact duplicate node / relation拒否
- unresolved aggregateへのID / free text混入と不正count拒否

実データfixture、実artifact、実public ID、実タイトル、本文は使用しない。

---

# 10. Non-goals

- internal canonical Timeline schemaの変更
- public projector / semantic validator / CLI / reportの実装
- renderer、`timelines/index.md`、Story page、URLの変更
- Public ID Registryや実manifestの変更
- 実データartifactを用いたprojection / preview
- individual edge、unknown、conflict、provenanceの公開
- hosting、deploy、rollback実行

---

# 11. 次段階

次PRは、検証済みinternal canonical documentとpublic ID / label mappingを入力にするpure projectorを実装する。schema validationだけで公開可能と判定せず、§8.2のcross-document semantic validatorとsafe aggregate reportを同じ実装境界で扱う。

---

# 12. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `../03_Data_Model/Canonical_Timeline_Schema.md`
- `../06_AI/Public_ID_Registry_Design.md`
- `Timeline_Page.md`
- `Wiki_Output_Design.md`
- `../../runbooks/AI_PR_Playbook.md`
