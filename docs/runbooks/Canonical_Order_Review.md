# Canonical Order Review運用手順

Version: 0.1

対象: episode-level `canonicalOrder`の初回・増分人間レビュー

CLI:

- `scripts/build_canonical_order_review_packet.py`
- `scripts/validate_canonical_order_review_packet.py`

---

## 1. 目的

`canonicalOrder`の未確認候補を`story_manifest.yaml`へ混入させず、1 storyずつ人間が根拠を確認するためのlocal-only packetを作る。正となる保存先は引き続きstory manifestのepisode entryであり、このpacketは正ではない。

packetの生成、schema検証、`humanReviewStatus: confirmed`の記入はいずれもmanifestへの自動反映を起動しない。反映は人間確認後の別操作とする。

## 2. 安全境界

- 実packetは固定root `workspace/review_packets/canonical_order/`だけへ生成し、`classification: local_internal` / `commitAllowed: false`とする。packet、実manifest候補、実データ由来の確認メモはcommitしない
- 1 packetは1 storyだけを対象にする。一括confirmed化や複数storyをまとめた判断はしない
- packetには`storyId` / `episodeId`をlocal internal IDとして含めるが、raw path、source filename、source key、DEC本文、セリフ、raw commandは複写しない。対応するrawファイルは入力manifestをローカルで参照して特定する
- `evidenceSummary` / source `note` / `reviewerNotes`は非逐語の短い根拠要約だけにする。内部ID、source key、絶対・UNC path、`.dec`名、raw command、本文の転載を入れない。validatorはpacket内ID・path風文字列・raw markerを機械検出するが、packetへ意図的に複写しないsource keyそのものは照合値を持たないため完全には検出できず、人間レビューでも確認する
- CLIとvalidatorはIDや入力内容をstdout / stderrへ表示せず、件数と固定error codeだけを出す
- packetは既存ファイルを上書きしない。既定の保持期間は14日、指定可能範囲は1〜90日とする

## 3. 前提

入力manifestは`schemas/story_manifest.schema.json`に適合している必要がある。実raw配置から候補を作る場合は、本文を読まない既存builderを使い、ignored領域へ置く。

```powershell
uv run python scripts/build_story_manifest_candidates.py `
  --raw-root data/raw `
  --output workspace/story_manifest/canonical_order_review_001/story_manifest_candidates.yaml `
  --quiet
```

対象storyはmanifestの`stories`配列をローカルで確認し、1始まりのindexで選ぶ。`--story-index`を使うのは、内部story IDをCLI引数やprocess logへ載せないためである。

## 4. Packet生成

```powershell
uv run python scripts/build_canonical_order_review_packet.py `
  --manifest workspace/story_manifest/canonical_order_review_001/story_manifest_candidates.yaml `
  --story-index 1 `
  --output-name canonical_order_review_batch_001.yaml `
  --review-batch-id canonical-order-review-batch-001
```

generatorは入力manifestのdigest、story / episodeのlocal internal ID、manifest内index、現行canonical値だけを転記する。`candidateCanonicalOrder`、候補出典、根拠要約、人間レビュー欄は空のまま生成し、`episodeNumber`や配列順から値を提案しない。

## 5. 候補記入

候補を用意できるepisodeだけ、次をpacketへ記入する。

- `candidateCanonicalOrder`: 整数の候補値
- `candidateSource`: `official` / `manual` / `ai_inferred` / `unknown`。`ai_inferred`は0〜1の`confidence`必須
- `evidenceSummary`: 原文を転載しない、500文字以内の根拠要約

候補はあくまで未確認値である。release order、display order、`episodeNumber`、manifest配列順、ファイル名だけを根拠に補完しない。同一値はsame-timeを意味する可能性があるためschema上許容するが、値の重複だけからsame-timeを逆推論しない。

## 6. 人間レビュー

人間は入力manifestから対象rawファイルを特定し、各episodeの根拠を個別に確認する。`humanReviewStatus`は次のいずれかにする。

| 値 | 意味 |
|---|---|
| `pending` | 未確認 |
| `confirmed` | 値と出典を人間が確認した |
| `rejected` | 候補を採用しない |
| `needs_more_context` | 判断材料が不足している |

`confirmed`の場合だけ`humanConfirmedCanonicalOrder`と`humanConfirmedSource`を必須とする。その他のstatusでは両方をnullのままにする。候補値と確認値は異なってよい。reviewer、確認日、保留・拒否理由は`reviewerNotes`へ本文を転載しない範囲で短く残す。

この判断では、次を明示的に確認する。

1. review対象が同じ1 story内のepisode集合である
2. 値の根拠がrelease / display / episode numberの機械的代用ではない
3. 候補がAI由来なら、人間が根拠を確認しており、source typeとconfidenceが保持される
4. 判断できないepisodeを推測でconfirmedにしていない

## 7. 検証

```powershell
uv run python scripts/validate_canonical_order_review_packet.py `
  --packet-name canonical_order_review_batch_001.yaml
```

validatorはschema、cross-field条件、episode key / manifest indexの重複と順序、禁止されたpath・raw marker・内部IDのfree-text混入をblocking検査する。同じconfirmed値を複数episodeへ割り当てることは現仕様ではrejectしない。

## 8. Manifest反映

validator PASS後も自動反映しない。`humanReviewStatus: confirmed`のepisodeだけを、入力manifestの対応entryへ人間確認済み値として手動反映する。

```yaml
canonicalOrder: 10
canonicalOrderStatus: confirmed
canonicalOrderSource:
  sourceType: ai_inferred
  confidence: 0.7
  note: 人間確認済みの非逐語な根拠要約。
```

未確認episodeは3field全省略、または`canonicalOrder: null` / `canonicalOrderStatus: unassigned` / `canonicalOrderSource: null`の3点セットを維持する。packet自体、candidate値、raw path、本文をmanifestへコピーしない。

## 9. 反映後の再検証

反映対象だけをmanifest strict modeでnormalizeし、Stage A extractionを再生成した後、対象storyの全episodeを含めてv0.5 checkを再実行する。

```powershell
uv run python scripts/check_timeline_consistency.py `
  --input workspace/dry_runs/<RUN_ID>/extracted/ `
  --recursive `
  --report-output workspace/dry_runs/<RUN_ID>/timeline_consistency/report.json
```

確認項目は、値競合、同一story内relative constraintとの不整合、missing / comparable / ambiguous分類、`readyForCanonicalReview`である。readiness trueは総順序やcanonical Timelineの確定を意味しない。入力不足のpartial batchで判断しない。

## 10. Non-goals

- canonicalOrderの自動生成、自動confirmed化、自動manifest反映
- release / display / episode numberからの補完
- 複数story横断比較、連番性・一意性・総順序の決定
- Wiki / Knowledge Graphへの表示
- raw本文を含む既存Internal Review Evidence Packetとの統合

## 11. 合成テンプレート

構造例は`docs/templates/canonical_order_review_packet_template.yaml`を参照する。このテンプレートは合成ID・合成根拠だけで構成され、実packetとは異なりcommit可能である。
