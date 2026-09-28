# 話者ラベル実データ確認（2026-09-28）

## 範囲と方法

v1 release scopeの既存Normalized Story 2,840 episodeをローカルで読み取り専用に走査した。`labelAnalysis`の分類とラベル頻度を集計し、頻出のgroup候補とambiguous候補を確認した。実データ・本文・ファイル名・個別IDはcommitしない。既存のrelease artifactや公開サイトは再生成しない。

## 観測と対応

解析済みラベル出現5,033件の既存分類は、`single_speaker` 4,409、`speaker_group` 296、`ambiguous_speaker` 156、`generic_speaker` 120、`speaker_with_modifier` 50、`speaker_group_with_modifier` 2だった。頻出group候補の確認では、明確な区切り記号を複数話者に用いる既存判定の誤検出は見つからなかった。ただし全group候補を人手で確認した結果ではない。

単独の疑問符だけを使った匿名話者表記143件が`single_speaker`/`not_applicable`になっており、通常の単独人物候補へ流れる検出漏れを確認した。うち141件は`name_command`、2件は`ch_talk_name`由来で、複数カテゴリに分布した。全角・半角の単独疑問符を`generic_speaker`/`needs_review`へ分類するよう修正し、ParserからStage Aの特殊話者候補への経路を合成テストで固定した。人物IDの自動確定は行わない。

中点を含むラベルには複数話者候補と固有呼称らしい候補の両方があり、既存の`ambiguous_speaker`/`needs_review`を維持した。役割名・集合名など他の`single_speaker`候補には意味判定が必要なものがあるため、文字列規則での一括generic化は行わない。これらは未確認のまま保持する。

この修正は今後のnormalize時に反映される。既存のignored release artifact、Stage A/B集計、公開成果物の件数が更新されたとは主張しない。次に全量再生成を行う際は、分類分布とspecial speaker候補の差分を再測定する。
