# Cross-story Constraint Inventory運用手順

Version: 0.1

対象: Stage A `episode_extraction` JSON群

CLI: `scripts/build_cross_story_constraint_inventory.py`

---

## 1. 目的

`Canonical_Timeline_Scope_Decision.md`で採択した初期profileに従い、EVENTの異なるstoryを参照する既存`kind: "relative_order"`候補を、2 storyの組ごとに内部review queueへ集計する。

このinventoryは候補の発見・判定・昇格を行わない。`before` / `after` / `same_time`を反転・統合せず、candidate ID、Evidence ID、`sourceType`、`confidence`、`extractionRun`、source / target入力pathを観測ごとに保持する。同じcandidateや同じ関係が複数回観測されても重複排除しない。

現行v0.5 `scripts/check_timeline_consistency.py`は同一story内の整合性とreadinessを扱う。本CLIはcross-story候補の非判定inventoryだけを扱う別契約であり、v0.5 CLI・schema・status・exit codeを変更しない。

---

## 2. Scopeと分類

- source documentは`storyCategory: "EVT"`だけを対象とする。初期scopeを切り替えるCLI optionは設けない
- target解決にはvalidな全入力documentを使い、`episodeId`から全document参照を引く
- targetが一意の別EVENT storyに属する場合だけ、無向の`storyIds` 2件をgroup keyとして`storyPairs`へ格納する
- group keyだけを無向にする。各candidateのsource、target、`relation`は元の方向のまま保持する
- targetが一意の同一storyなら`sameStoryCandidateCount`へ数える。同一story候補の検査はv0.5の責務なので、本reportへ候補本体を重複収録しない
- target documentが入力に無ければ`target_not_loaded`、EVENT外にしか無ければ`target_out_of_scope`として`unresolvedTargets`へ保持する
- 同じtarget episode IDが複数storyへ解決される場合は、source story自身と別storyの混在も含め、`ambiguous_target_story`として全target document参照を保持する。cross-storyと決め打ちしない
- `relativeTo`欠落、`relation`欠落、未対応relationは`missing_relative_to` / `missing_relation` / `unsupported_relation`として`invalidRelativeCandidates`へ保持する
- EVENT外のvalid documentは`outOfScopeDocumentRefs`へ保持する
- invalid / skipped inputは`inputResults`へ残し、候補分析から除外する

対応relationは`before` / `after` / `same_time`だけである。same-time class、推移閉包、有向cycle、winner、score、edge statusは作らない。

---

## 3. 実行方法

repo rootから、Stage A出力のfile・directory・globを指定する。

```powershell
uv run python scripts/build_cross_story_constraint_inventory.py `
  --input workspace/dry_runs/<RUN_ID>/stage_a/ `
  --recursive `
  --report-output workspace/dry_runs/<RUN_ID>/cross_story_inventory/report.json
```

入力は`schemas/extraction.schema.json`とsemantic validationを通ったdocumentだけを分析する。reportは`schemas/cross_story_constraint_inventory.schema.json`で検証してから書き出す。

`--report-output`はrepo内では`workspace/dry_runs/`配下だけを許可する。入力file / directory内への出力と既存reportの上書きは禁止する。reportは内部IDとlocal pathを含むinternal-only artifactであり、commitしない。stdout / stderrには件数だけを出し、内部ID・入力path・出力pathを表示しない。

---

## 4. Report契約

reportの識別子は次の通り。

- `schemaVersion: "0.1"`
- `documentType: "cross_story_constraint_inventory"`
- `scopeStoryCategory: "EVT"`
- `status: "passed"`: 全入力がvalid。候補0件、未解決target、曖昧targetがあっても失敗にしない
- `status: "invalid_input"`: invalidまたはskipped inputが1件以上ある

主要集計:

- `relativeOrderCandidateCount`: scope内sourceから見つけたrelative candidate観測数
- `crossStoryCandidateObservationCount`: 一意の異story targetへ解決できた観測数。重複を含む
- `distinctStoryPairCount`: 無向の2 story group数
- `sameStoryCandidateCount`: 一意の同一story targetへ解決した観測数
- `unresolvedTargetCount`: `target_not_loaded` / `target_out_of_scope`の合計
- `ambiguousTargetStoryCount`: `ambiguous_target_story`の件数
- `invalidRelativeCandidateCount`: 欠落・未対応fieldを持つrelative candidate数

`storyPairs[].relationCounts`は観測された原relationの件数であり、関係の整合・正しさ・canonical性を表さない。`candidates`は観測を重複込みで保持する。`targetDocumentRefs`はtargetのstoryを`episodeId`だけで決め打ちしないためのprovenanceである。

reportには`canonicalOrder`、`releaseOrder`、`displayOrder`、global order値、canonical edge、review / promotion statusを含めない。

---

## 5. Exit code

| code | 意味 |
|---:|---|
| 0 | 入力がすべてvalid。候補の有無や分類結果は問わない |
| 1 | invalidまたはskipped inputあり。valid入力のinventoryはreportへ保持する |
| 2 | 入力0件、設定不正、schema検証失敗、report出力失敗 |

候補が存在するだけでwarningやfailureにしない。inventoryはまだhuman-confirmed edgeではない。

---

## 6. Non-goals

- 自然文・公開順・ファイル名・ID・タイトルからcross-story候補を生成すること
- story-local `canonicalOrder`をstory間で比較、再採番、補完すること
- `before` / `after`の反転、same-time class、推移閉包、cycle findingを作ること
- candidateを評価してwinner、score、edge status、canonical artifactを作ること
- review packet、human decision取り込み、promotionを実装すること
- EVENT以外へscopeを拡張すること
- Wiki / public projectionへ表示すること

実データinventoryが空でも正常である。現行rule-based extractorは通常`relative_order`を生成しないため、空を理由に自然文自動推定を追加しない。

---

## 7. 検証

合成fixtureだけで、3 relation、逆方向観測、同一candidate / edgeの重複保持、同一story、target未読込、EVENT外target、複数target story、source storyとの混在、invalid relative candidate、invalid / skipped document、EVENT外document、空inventory、入力順の決定性、全provenance保持、schema、glob / recursive入力、exit code、internal-only出力、no-clobber、stdout / stderr非漏えいを検証する。

```powershell
uv run pytest `
  tests/extractor/test_cross_story_constraint_inventory.py `
  tests/scripts/test_build_cross_story_constraint_inventory.py
```

---

## 8. 初回実データdry-run（2026-08-23）

全EVENTの最終readiness確認で生成したlocal Stage A corpusを入力に、同じinventoryを独立2 run実行した。

- resolved / valid / invalid / skipped input: 537 / 537 / 0 / 0
- in-scope EVENT document: 537
- relative candidate / cross-story observation / story pair: 0 / 0 / 0
- same-story / unresolved / ambiguous / invalid relative candidate: 0 / 0 / 0 / 0
- 両runとも`status: "passed"`で、v0.1 schema検証を通過した
- 両reportはbyte-identicalで、SHA-256は`1D9E1BCC44B6AB0AAC7E81D91AC460E76E5A38B803A6D13613D40368FCE3CE7F`だった

report本体は内部IDとlocal pathを含むため`workspace/dry_runs/`だけに保持し、commitしない。0件は現行rule-based extractorの既知挙動と一致し、値の欠落や実装失敗を意味しない。この結果から候補・edge・global順序を補完しない。

---

## 9. 次のgate

このinventoryは既存candidateをreview可能な単位へ並べるだけである。実際のedge reviewへ進む前に、承認済みcross-story根拠を持つ小規模local sampleが必要になる。候補が無い場合は、根拠の入手方法とsource別のcandidate生成可否を人間が判断する。

関連する正本:

- `docs/architecture/03_Data_Model/Canonical_Timeline_Scope_Decision.md`
- `docs/runbooks/Timeline_Consistency_Check.md`
- `docs/runbooks/Canonical_Order_Review.md`
