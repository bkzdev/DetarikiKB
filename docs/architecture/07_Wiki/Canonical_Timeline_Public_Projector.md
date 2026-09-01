# Canonical Timeline Public Projector

Version: 0.1
Status: Implemented
Project: Detariki Knowledge Base (DKB)
Implementation: `agents/extractor/canonical_timeline_public_projection.py`

---

# 1. 目的

`Canonical_Timeline_Public_Projection_Schema.md`で固定した公開専用documentを、internal canonical Timelineを変更せず決定的に構成する。

本実装は純粋関数であり、file I/O、schema file読み込み、Public ID Registry照合、CLI、renderer、publish-ready判定を行わない。schema-validなinternal documentと人間確認済みmappingを前提とし、不整合時は空projectionと匿名safe aggregate reportを返してfail-closedにする。これらの外部照合は`Canonical_Timeline_Public_Preflight.md`で実装済みである。

---

# 2. API

```python
build_canonical_timeline_public_projection(
    document,
    public_episode_mapping,
) -> {
    "projection": {...},
    "report": {...},
}
```

cross-documentの完全一致は次の純粋validatorで確認できる。

```python
validate_canonical_timeline_public_projection_consistency(
    projection,
    document,
    public_episode_mapping,
) -> list[dict]
```

どちらも入力dictとmappingを変更しない。

---

# 3. 入力契約

## 3.1 Internal canonical document

`schemas/canonical_timeline.schema.json` v0.1に適合済みの単一documentを受け取る。projector内では`validate_canonical_timeline_consistency()`を再実行し、baseline findingが1件でもあれば部分projectionを返さない。

JSON Schema検証自体は後続preflightの責務である。本APIはmalformed documentの汎用validatorではない。

## 3.2 Public Episode mapping

mapping keyはinternal composite keyの`(storyId, episodeId)`とする。valueは次の4 fieldだけを持つ。

| field | 条件 |
|---|---|
| `publicStoryId` | public ID pattern |
| `publicEpisodeId` | public ID pattern |
| `storyLabel` | 1〜200文字、改行なし |
| `episodeLabel` | 1〜200文字、改行なし |

mappingはinternal IDとpublic metadataをjoinする内部入力であり、public projectionやsafe reportへそのまま転記しない。Public ID Registryは設計上internal IDを持たないため、Registryとprivate mappingの正確な照合は後続preflightで行う。

projectorは公開対象relationの両端について次を検査する。

- mapping欠落0
- valueの4 field allowlist・ID形式・label制約
- distinct internal Episode間の`publicEpisodeId`一意性
- 1 internal Storyが1 `publicStoryId`だけに対応すること
- 1 `publicStoryId`が1 internal Storyだけに対応すること
- 同一`publicStoryId`の`storyLabel`一意性

relationに接続しないinternal nodeと未使用mapping entryは出力しない。

---

# 4. Relation適格性

次の3条件をすべて満たすedgeだけを個別relationとして投影する。

- `adoptionStatus == "canonical"`
- `reviewStatus == "confirmed"`
- `relationState in {"before", "after", "same_time"}`

`unknown` / `conflict`は個別に投影せず、internal canonical artifact内の件数だけを`unresolvedRelationSummary`とreportへ残す。knownでもcandidateまたは未確認のedgeは投影せず、`ineligibleKnownRelationCount`としてreportへ残す。

---

# 5. 決定的component生成

1. 適格edgeの両端を非有向に接続してconnected componentを作る
2. nodeとrelationをpublic fieldへ新しく構成する
3. node、relation、componentをcanonical JSON表現でsortする
4. sort後のcomponentへ`component-0001`から連番を付ける

internal配列順、mapping挿入順、dict key順は出力に影響しない。component keyや配列順はchronologyを表さない。

relation stateは変換・推測せず元edgeの値を維持し、label keyだけを固定mappingで付与する。

| state | label key |
|---|---|
| `before` | `timeline_before` |
| `after` | `timeline_after` |
| `same_time` | `timeline_same_time` |

---

# 6. Safe aggregate report

reportは次の形だけを返す。

```json
{
  "status": "clean",
  "counts": {},
  "findings": []
}
```

`counts`はinput node / relation、eligible relation、ineligible known relation、unknown / conflict relation、projected component / node / relationの非識別件数だけを持つ。

`findings[]`は固定`rule`と`count`だけを持つ。internal Story/Episode ID、public ID、label、relation両端、reason、provenance、path、digestを含めない。

---

# 7. Fail-closed動作

次のいずれかが発生した場合、`status: blocked`、固定ruleと件数、`components: []`、`unresolvedRelationSummary: null`を返す。

- baseline canonical semantic finding
- 適格endpointのpublic mapping欠落・不正
- public Episode ID重複
- internal / public Story対応の競合
- 同一public Storyのlabel競合
- 複数internal edgeが同一public relationへ写る重複
- 4桁component key容量超過

blocked時のprojectionもschema-validな`projection_candidate`であるが、publish-readyではない。後続workflowはreport statusが`clean`でなければ出力を渡してはならない。

---

# 8. Cross-document validator

`validate_canonical_timeline_public_projection_consistency()`は、同じsource / mappingから再構成した決定的projectionと検査対象をcanonical JSON表現で完全比較する。

- 一致時: finding 0
- source / mappingがblocking: builderと同じsafe finding
- 出力差分: `canonical_timeline_public_projection_mismatch` 1件

差分内容や値はfindingへ出力しない。

---

# 9. 合成fixture検証

`tests/extractor/test_canonical_timeline_public_projection.py`で、relation適格性、定型label key、component生成、unknown / conflict aggregate、入力不変・決定性、mapping / baselineのfail-closed、schema適合、cross-document一致、report非露出を固定する。

合成ID・合成label・合成provenanceだけを使い、実artifactや実mappingは使用しない。

---

# 10. Non-goals

- file loader / writer / CLI
- canonical / public schemaの変更
- Public ID Registryとprivate mappingの照合
- public label sourceのallowlist照合
- 禁止marker・internal ID・path・URL・digestの再帰exposure scan
- publish-ready判定
- renderer、`timelines/index.md`、URLの変更
- 実データprojection / preview
- hosting、deploy、rollback実行

---

# 11. 次段階

read-only preflightは`Canonical_Timeline_Public_Preflight.md`で実装済みである。次PRは合成fixtureだけで`timelines/index.md` rendererとlink checkを実装する。

---

# 12. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `Canonical_Timeline_Public_Projection_Schema.md`
- `Canonical_Timeline_Public_Preflight.md`
- `../03_Data_Model/Canonical_Timeline_Schema.md`
- `../06_AI/Public_ID_Registry_Design.md`
- `Timeline_Page.md`
- `Wiki_Output_Design.md`
- `../../runbooks/AI_PR_Playbook.md`
