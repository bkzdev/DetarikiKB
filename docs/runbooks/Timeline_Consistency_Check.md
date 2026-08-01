# Timeline整合性チェック運用手順

Version: 0.2

対象: Stage A `episode_extraction` JSON群

CLI: `scripts/check_timeline_consistency.py`

---

## 1. 目的

複数episodeの`TimelineCandidate(kind: "relative_order")`が表す`same_time` / `before` / `after`制約を候補単位で横断検査する。`same_time`を同値classへ縮約し、同一class内の前後制約とclass間の有向循環を、人間レビューが必要なwarningとして独立reportへ残す。

このcheckはStage B mergeの前に行う。merge後のtimeline entryは`sourceTimelineId`で複数candidateを集約し、代表`relativeTo` / `relation`だけを持ちうるため、循環検査の入力にするとcandidateごとの出自を失う。`agents/extractor/timeline_consistency.py`は検証済みStage A documentを直接受け取り、candidate ID・Evidence ID・入力pathをfindingへ保持する。

現行rule-based extractorは`explicit_order` / `temporal_marker`だけを生成し、`relative_order`を生成しない。このため通常の現行出力では`checkedCandidateCount: 0`が正常である。本checkは手動入力または将来の明示的なAI抽出が`relative_order`を生成した場合の非破壊な受け皿であり、自然文推定を開始するものではない。

## 2. 対象と正規化

- `kind: "relative_order"`, `relation: "same_time"`: 所属documentの`episodeId`と`relativeTo`を無向にUnion-Findで結合する。一方向の観測だけでも同じclassとし、推移関係も縮約する
- `kind: "relative_order"`, `relation: "before"`: 所属documentの`episodeId → relativeTo`
- `kind: "relative_order"`, `relation: "after"`: `relativeTo → 所属documentのepisodeId`
- 2 episode以上のsame-time class内にbefore/afterがある場合は`timeline_relative_order_within_same_time_class`とする。class内edgeはclass間graphへ重ねて入れず、二重報告しない
- 異なるclass間のstrongly connected component、およびsame-time根拠の無い従来の自己loopを`timeline_relative_order_cycle`として1 findingにまとめる
- 同じ有向辺を表す複数candidateはgraph上では1辺だが、全candidate / Evidence observationを保持する
- 同じsame-time pairを表す逆向き・重複candidateはUnion-Find上で1接続として扱うが、全observationを保持する
- `relativeTo`が今回の入力集合に無い場合は部分batchとして正当になりうるため、矛盾にせず`ignoredCandidates[].reason: "target_not_loaded"`へ保持する
- `relativeTo` / `relation`欠落、未対応relationは`ignoredCandidates`へ保持し、黙って破棄しない。v0.1互換のためschemaは`same_time_not_checked`も受理するが、v0.2 CLIは生成しない

縮約は入力初出順を代表元決定に使うUnion-Find、循環探索は反復Kosaraju法で行い、Pythonの再帰上限に依存しない。計算量はepisode数を`V`、before/after数を`E`、same-time数を`S`として`O(V + E + S)`である。

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

`--report-output`指定時は`schemas/timeline_consistency_report.schema.json`準拠の`schemaVersion: "0.2"` JSONを出力する。更新後schemaは過去のv0.1 reportも受理する。

- `status: "passed"`: 入力がすべてvalidで循環なし
- `status: "needs_review"`: 1件以上の循環findingあり
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

Reportは内部IDとlocal pathを含みうる生成物であり、`workspace/dry_runs/`配下に置いてcommitしない。repo内外を問わず同directory外、入力directory内、入力fileと同じpathへの出力は拒否する。既存reportは上書きしない。入力を1件も解決できない場合はexit code 2とし、空reportを生成しない。

## 5. Exit code

| Code | 意味 |
|---:|---|
| `0` | 入力がすべてvalidで循環なし。`target_not_loaded`等のignored candidateだけでは失敗にしない |
| `1` | 循環あり、またはinvalid / skipped inputあり |
| `2` | 入力を1件も解決できない、設定不正、report schema/output失敗 |

部分batchで`target_not_loaded`がある場合は、対象episodeを追加した全体batchで再実行してから順序整合性を判断する。

## 6. Non-goals

- 自然文やLLMによる`relative_order`生成
- `canonicalOrder` / `releaseOrder` / `displayOrder` / Scene・Blockの数値順序を1列へ統合すること
- `temporal_marker`の意味解釈
- Stage Bの既存`timeline_conflict`（同一`sourceTimelineId`内の`orderValue`相違）の変更
- merged entity / merge reportへのfinding書き戻し
- canonical timelineの確定、manual override、Wiki / Knowledge Graph表示

## 7. 検証

```powershell
uv run pytest tests/extractor/test_timeline_consistency.py `
  tests/scripts/test_check_timeline_consistency.py `
  tests/docs/test_timeline_consistency_docs.py
```

2・3 node cycle、自己loop、before/after正規化、same-timeの推移縮約・class内矛盾・class間cycle、重複観測、部分batch、invalid input、1500 episodeの非再帰走査、v0.1/v0.2 report schema・no-clobber安全策を合成データだけで検証する。
