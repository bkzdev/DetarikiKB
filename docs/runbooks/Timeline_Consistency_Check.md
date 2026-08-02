# Timeline整合性チェック運用手順

Version: 0.5

対象: Stage A `episode_extraction` JSON群

CLI: `scripts/check_timeline_consistency.py`

---

## 1. 目的

複数episodeの`TimelineCandidate`を候補単位で横断検査する。`kind: "relative_order"`では`same_time`を同値classへ縮約し、同一class内の前後制約とclass間の有向循環を検出する。`kind: "explicit_order"`では、同一episodeの同一metadata fieldに複数の値が観測された競合を検出する。さらに、同一story内で一意に定まる`canonicalOrder`だけを`relative_order`と照合し、story単位のcanonical review準備状況を監査する。矛盾は人間レビューが必要なwarning、準備状況はinformationalな独立reportとして残し、採用値やcanonical timelineは決定しない。

このcheckはStage B mergeの前に行う。merge後のtimeline entryは`sourceTimelineId`で複数candidateを集約し、代表`relativeTo` / `relation`だけを持ちうるため、循環検査の入力にするとcandidateごとの出自を失う。`agents/extractor/timeline_consistency.py`は検証済みStage A documentを直接受け取り、candidate ID・Evidence ID・入力pathをfindingへ保持する。

現行rule-based extractorは`explicit_order` / `temporal_marker`だけを生成し、`relative_order`を生成しない。このため通常の現行出力では`checkedCandidateCount: 0`が正常である。一方、episode metadata由来の`explicit_order`は数値競合検査の対象になる。本checkは自然文推定を開始するものではない。

## 2. 対象と正規化

- `kind: "relative_order"`, `relation: "same_time"`: 所属documentの`episodeId`と`relativeTo`を無向にUnion-Findで結合する。一方向の観測だけでも同じclassとし、推移関係も縮約する
- `kind: "relative_order"`, `relation: "before"`: 所属documentの`episodeId → relativeTo`
- `kind: "relative_order"`, `relation: "after"`: `relativeTo → 所属documentのepisodeId`
- 2 episode以上のsame-time class内にbefore/afterがある場合は`timeline_relative_order_within_same_time_class`とする。class内edgeはclass間graphへ重ねて入れず、二重報告しない
- 異なるclass間のstrongly connected component、およびsame-time根拠の無い従来の自己loopを`timeline_relative_order_cycle`として1 findingにまとめる
- 同じ有向辺を表す複数candidateはgraph上では1辺だが、全candidate / Evidence observationを保持する
- 同じsame-time pairを表す逆向き・重複candidateはUnion-Find上で1接続として扱うが、全observationを保持する
- `relativeTo`が今回の入力集合に無い場合は部分batchとして正当になりうるため、矛盾にせず`ignoredCandidates[].reason: "target_not_loaded"`へ保持する
- `relativeTo` / `relation`欠落、未対応relationは`ignoredCandidates`へ保持し、黙って破棄しない。v0.1互換のためschemaは`same_time_not_checked`も受理するが、v0.5 CLIは生成しない

### 2.1 Episode metadata順序値

- `kind: "explicit_order"`かつ`scope: "episode"`で、`orderField`が`canonicalOrder` / `releaseOrder` / `displayOrder`、`orderValue`が数値の候補だけを比較対象にする
- 比較keyは`(episodeId, orderField)`とする。異なるepisodeや異なるfieldの値は比較しない
- 同じkeyで異なる値を2つ以上観測した場合は`timeline_episode_order_field_value_conflict`とする。同じ値の重複観測は競合にしない
- 値の優先順位やwinnerは決定せず、値は初出順の重複なし一覧、observationは重複を含む全件を保持する
- 対象外scope、欠落field、未対応field、欠落値は、それぞれ`unsupported_scope` / `missing_order_field` / `unsupported_order_field` / `missing_order_value`として`numericIgnoredObservations`へ保持する
- findingとignored observationは入力path、episode ID、candidate ID、Evidence ID、`extractionRun`を保持する

`orderValue` / `timePosition`のScene・Block内での意味や、3つのepisode metadata field間の優先順位は定義されていないため、fieldをまたぐ比較は行わない。

### 2.2 Canonical chronology制約

2026-08-01の人間判断で、`canonicalOrder`だけを作中時系列の数値表現として`relative_order`と照合する方針を採用した。

- 対象は同一`storyId`内のrelative candidateだけとする。cross-storyの制約は`cross_story_constraint`として未検査のまま保持する
- source / target episodeの`canonicalOrder`がそれぞれ1 distinct値に定まる場合だけ比較する。同じ値の重複observationは許容し、全件を保持する
- `relation: "same_time"`はsource値 `==` target値、`before`はsource値 `<` target値、`after`はsource値 `>` target値を要求する
- 違反は`timeline_canonical_order_relative_constraint_conflict`としてwarning findingにする
- `canonicalOrder`が無い場合は`missing_source_canonical_order` / `missing_target_canonical_order`、複数distinct値がある場合は`ambiguous_source_canonical_order` / `ambiguous_target_canonical_order`として未検査にする
- 曖昧な値からwinnerを選ばない。既存の同一field値競合findingとcanonical constraintの未検査記録を併存させる
- `releaseOrder` / `displayOrder`は補完・fallback・比較に使わない
- finding / 未検査記録はrelative candidateと両端の全canonical observationについて、入力path、story / episode ID、candidate ID、Evidence ID、`extractionRun`を保持する

### 2.3 Canonical review準備状況

- 入力済みdocumentを`storyId`ごとにまとめ、各loaded episodeの`canonicalOrder` distinct値が0件なら`missingEpisodeIds`、1件なら`comparableEpisodeIds`、2件以上なら`ambiguousEpisodes`へ分類する
- `ambiguousEpisodes`は全値と全observationを保持し、winnerを選ばない。`releaseOrder` / `displayOrder`による補完もしない
- 観測値は数値昇順の`observedOrderBuckets`へまとめる。同じ値を持つ複数episodeは合法であり、そこから`same_time`制約を逆推論しない
- 全loaded episodeがcomparableで、かつそのstoryの`canonicalConstraintFindingCount`が0件の場合だけ`readyForCanonicalReview: true`とする
- readinessは「人間がcanonical timelineをレビューできるだけの入力が揃った」ことだけを示し、値の連番性・一意性・総順序、canonical timelineの確定や昇格を意味しない
- cross-storyとして未検査のconstraintはstory内readinessを阻害しない。`readyForCanonicalReview: false`だけではstatusやexit codeを変更しない

縮約は入力初出順を代表元決定に使うUnion-Find、循環探索は反復Kosaraju法で行い、Pythonの再帰上限に依存しない。episode数を`V`、before/after数を`E`、same-time数を`S`、canonical observation数を`C`、canonical値bucket数を`B`とすると、readinessのbucket数値sortを含む計算量は`O(V + E + S + C + B log B)`である。順序保持listのmembershipにはsetを併用し、同一story・同一値bucketが大きくても二乗探索にしない。

## 3. 実行方法

repo rootから実行する。

```powershell
uv run python scripts/check_timeline_consistency.py `
  --input data/extracted/_raw/ `
  --recursive `
  --report-output workspace/dry_runs/<RUN_ID>/timeline_consistency/report.json
```

複数file・directory・glob patternを混在指定できる。

```powershell
uv run python scripts/check_timeline_consistency.py `
  --input "tests/fixtures/extraction/*.json" another/extraction.json
```

入力は既存のStage B merge gateと同じく、`schemas/extraction.schema.json`と`run_semantic_validation()`のerror検証を通す。schema/semantic errorのあるdocumentはgraphへ入れず、`inputResults`へ`invalid`として保持する。semantic warningだけのdocumentは検査対象に含める。

## 4. Report契約

`--report-output`指定時は`schemas/timeline_consistency_report.schema.json`準拠の`schemaVersion: "0.5"` JSONを出力する。更新後schemaは過去のv0.1 / v0.2 / v0.3 / v0.4 reportも受理する。

- `status: "passed"`: 入力がすべてvalidで矛盾findingなし
- `status: "needs_review"`: relative order、同一field値競合、canonical constraintのfindingが1件以上あり
- `status: "invalid_input"`: invalidまたは解決不能な入力あり。valid入力の検査結果も破棄せず同じreportへ残す
- `checkedCandidateCount`: graph edgeとして検査したcandidate observation数
- `distinctEdgeCount`: 重複排除後の有向辺数
- `checkedSameTimeCandidateCount` / `distinctSameTimeEdgeCount`: 検査したsame-time observation数 / 無向pair重複排除後の数
- `sameTimeClassCount`: 2 episode以上を含む非自明なsame-time class数
- `distinctClassEdgeCount`: 縮約後の循環graphに入った異なる有向class edge数
- `ignoredCandidates`: 検査対象にできなかったrelative orderと理由・provenance
- `findings[].candidateRefs`: before/afterとsame-timeを含む関与candidateの入力path・episode ID・candidate ID・Evidence ID
- `findings[].edges`: `before` / `after`の元観測と正規化後の向き
- `findings[].sameTimeEdges` / `sameTimeClassEpisodeIds`: 縮約根拠の全same-time観測 / findingに関与する非自明classの構成
- `explicitOrderCandidateCount`: 入力中の全`explicit_order`候補数
- `numericEpisodeObservationCount` / `numericEpisodeOrderGroupCount`: 検査対象になったobservation数 / `(episodeId, orderField)` group数
- `numericIgnoredObservations`: 検査対象にできなかった`explicit_order`と理由・provenance
- `numericFindings`: 同一episode・同一fieldの値競合。異なる値の一覧と全observationを保持する
- `canonicalOrderObservationCount`: canonical constraint検査用に収集した`canonicalOrder` observation数
- `canonicalConstraintCandidateCount` / `canonicalConstraintCheckedCount`: canonical chronologyの候補constraint数 / 両端が一意で実際に比較した数
- `canonicalConstraintIgnoredCandidates`: cross-story、値欠落、値曖昧により比較しなかったconstraintと理由・全provenance
- `canonicalConstraintFindings`: `canonicalOrder`と同一story内relative constraintの不整合
- `canonicalReadinessStoryCount` / `canonicalReadyStoryCount`: 監査したstory数 / `readyForCanonicalReview: true`のstory数
- `canonicalReadinessStories`: loaded episode一覧、comparable / missing / ambiguous分類、値bucket、既存canonical constraint finding数、review準備判定

Reportは内部IDとlocal pathを含みうる生成物であり、`workspace/dry_runs/`配下に置いてcommitしない。repo内外を問わず同directory外、入力directory内、入力fileと同じpathへの出力は拒否する。既存reportは上書きしない。入力を1件も解決できない場合はexit code 2とし、空reportを生成しない。

## 5. Exit code

| Code | 意味 |
|---:|---|
| `0` | 入力がすべてvalidで矛盾なし。ignored candidate / observationだけでは失敗にしない |
| `1` | relative order、同一field値競合、canonical constraintのfindingあり、またはinvalid / skipped inputあり |
| `2` | 入力を1件も解決できない、設定不正、report schema/output失敗 |

部分batchで`target_not_loaded`がある場合は、対象episodeを追加した全体batchで再実行してから順序整合性を判断する。
canonical readinessがfalseであることだけでは失敗にせず、reportを人間レビュー対象の入力inventoryとして利用する。

## 6. Non-goals

- 自然文やLLMによる`relative_order`生成
- `canonicalOrder` / `releaseOrder` / `displayOrder`間の換算・優先順位付け・1列への統合
- Scene・Blockの`orderValue` / `timePosition`をepisode横断の値として解釈すること
- cross-storyの`canonicalOrder`比較
- 値の連番性・一意性・総順序の判定
- `temporal_marker`の意味解釈
- Stage Bの既存`timeline_conflict`（同一`sourceTimelineId`内の`orderValue`相違）の変更
- merged entity / merge reportへのfinding書き戻し
- canonical timelineの確定、manual override、Wiki / Knowledge Graph表示

## 7. 検証

```powershell
uv run pytest tests/extractor/test_timeline_consistency.py `
  tests/extractor/test_timeline_numeric_consistency.py `
  tests/extractor/test_timeline_canonical_constraints.py `
  tests/extractor/test_timeline_canonical_readiness.py `
  tests/scripts/test_check_timeline_consistency.py `
  tests/docs/test_timeline_consistency_docs.py
```

2・3 node cycle、自己loop、before/after正規化、same-timeの推移縮約・class内矛盾・class間cycle、同一episode・同一fieldの数値競合、同一storyのcanonical constraint、canonical review準備状況、値欠落・曖昧・cross-storyの不破棄、release/display非代用、重複観測、部分batch、invalid input、1500 episodeの非再帰走査、v0.1〜v0.5 report schema・no-clobber安全策を合成データだけで検証する。
