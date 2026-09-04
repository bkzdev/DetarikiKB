# Canonical Timeline Public Preflight

Version: 0.1
Status: Implemented
Project: Detariki Knowledge Base (DKB)
Implementation: `agents/extractor/canonical_timeline_public_preflight.py`

---

# 1. 目的

`Canonical_Timeline_Public_Projector.md`が構成した公開projection候補について、rendererへ渡す前のread-only gateを一つに集約する。

本preflightは入力を変更せず、artifact write、CLI、renderer、`publish-ready`への状態変更、hosting、deployを行わない。成功時もprojectionの`publishStatus`は`projection_candidate`のままである。

---

# 2. API

```python
canonical_timeline_public_preflight_input_digests(
    document,
    projection,
    public_episode_mapping,
    public_id_registry,
    public_label_source,
) -> dict[str, str]

preflight_canonical_timeline_public_projection(
    document,
    projection,
    public_episode_mapping,
    public_id_registry,
    public_label_source,
    expected_input_digests,
) -> {
    "status": "clean" | "blocked",
    "publishStatus": "projection_candidate",
    "findings": [{"rule": "...", "count": 1}],
}
```

reportは固定ruleと非識別件数だけを持つ。内部ID、public ID、label、path、URL、digest、schema error path/messageは返さない。

---

# 3. 入力とdigest pin

5入力を同一検査単位として扱う。

1. internal canonical Timeline document
2. public projection candidate
3. private Episode mapping（internal composite keyからpublic metadataへの対応）
4. Public ID Registry
5. public label source

helperはdict key順やprivate mapping挿入順に依存しないcanonical JSON表現からSHA-256を計算する。preflightは5件すべてを期待値と照合し、1件でも不一致なら他の内容検査へ進まず`blocked`にする。digest値自体はreportへ出力しない。

`public_label_source`は次の内部入力である。

```json
{
  "storyLabels": {"PUBLIC_STORY_ID": "公開確認済みStory label"},
  "episodeLabels": {"PUBLIC_EPISODE_ID": "公開確認済みEpisode label"}
}
```

このsourceとprivate mappingは公開artifactではなく、実運用時もworkspace限定・commit禁止とする。

---

# 4. 検査順序

## 4.1 Digest pin

pin / private mapping keyのshape不正は固定`input_invalid` ruleで、pin不一致は固定`input_digest_mismatch` ruleで、後続検査を行わずfail-closedにする。

## 4.2 Schema

repository内の次の3 schemaをread-onlyで読み込む。

- `schemas/canonical_timeline.schema.json`
- `schemas/canonical_timeline_public_projection.schema.json`
- `schemas/public_id_registry.schema.json`

errorの内容は公開safe reportへ転記せず、schemaごとの件数だけを残す。

## 4.3 Projector / canonical semantic

`build_canonical_timeline_public_projection()`を再実行する。canonical semantic finding、mapping欠落・不正・競合、公開relation重複等によりprojectorが`blocked`なら、その固定rule/countを引き継ぎ、部分的に先へ進まない。

## 4.4 Registry / private mapping

- Registry全体の`publicStoryId` / `publicEpisodeId`重複0
- projectionに現れる`(publicStoryId, publicEpisodeId)`がRegistryの同じStory配下に存在する
- EVENT限定projectionなので、対応するRegistry Storyの`category`は`event`

Registryはプロジェクト全体を含むため、projectionで未使用の正規entryは許容する。

## 4.5 Public label source

projectionに現れるStory / Episode labelは、対応するpublic IDをkeyにしたsource値と完全一致しなければならない。欠落・不一致はそれぞれ匿名件数でblockする。未使用source entryは許容する。

## 4.6 Cross-document完全一致

`validate_canonical_timeline_public_projection_consistency()`で、projectionが同じinternal document / private mappingから再構成した結果と完全一致することを確認する。

## 4.7 Exposure scan

projectionのcanonical JSON表現を対象に、次をblocking scanする。

- internal `storyId` / `episodeId`
- candidate / evidence ID
- internal reason / decision free text（短文も公開labelとの完全一致で検査）
- `.dec`、script command marker
- URL / `file://`
- Windows / Unix user path marker
- SHA-256形状のdigest

検出値や場所はreportへ載せず、出現件数だけを返す。schema allowlistを通るlabel文字列へ内部値が混入する場合の最終防波堤である。

---

# 5. Fail-closed report

全検査を通過した場合だけ`status: clean`となる。ただしpreflightは公開承認ではなく、`publishStatus: projection_candidate`を固定する。

findingは同じruleを集約し、rule名で決定的にsortする。入力配列・dict・mappingの順序に依存せず、入力を変更しない。

---

# 6. 合成fixture検証

`tests/extractor/test_canonical_timeline_public_preflight.py`で、clean path、digest pin、3 schema、projector block、Registry重複/不一致、label source、cross-document mismatch、internal value / marker exposure、入力不変を検証する。

実artifact、実Registry entry、実mapping、実labelはfixtureに使用しない。

---

# 7. Non-goals

- file loader / writer / CLI
- private mapping / public label sourceの永続形式確定
- Public ID Registry、canonical / public schemaの変更
- projectionの`publish-ready`化
- renderer、`timelines/index.md`、Story / Episode page、URLの変更
- 実データprojection / preflight / preview
- hosting、deploy、rollback実行

---

# 8. 永続化境界

`timelines/index.md` renderer、local visual review、public input envelope / promotionは実装済みである。clean reportと5入力digestは`workspace/public_wiki_inputs/`のpush前reviewに使うが、public inputへは転記しない。`Canonical_Timeline_Public_Input.md`とpromotion runbookを正とする。

---

# 9. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `Canonical_Timeline_Public_Projection_Schema.md`
- `Canonical_Timeline_Public_Projector.md`
- `Canonical_Timeline_Public_Renderer.md`
- `Canonical_Timeline_Public_Input.md`
- `../06_AI/Public_ID_Registry_Design.md`
- `Timeline_Page.md`
- `Wiki_Output_Design.md`
- `../../runbooks/AI_PR_Playbook.md`
