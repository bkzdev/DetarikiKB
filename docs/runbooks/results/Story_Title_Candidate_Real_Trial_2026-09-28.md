# 公式タイトル候補の実入力試行（2026-09-28）

## 範囲

公開された運営元の告知から、v1 release scope内の1 storyに対応するイベント名を1件選び、ignored workspace内のCSVへ転記した。出典の参照先と実タイトル、内部IDを含むCSV・生成YAML・manifestはcommitしない。告知のイベント名がゲーム内Story titleと完全に一致するかは未確認であり、値の確定や公開は行わない。

## 結果

`build_story_title_subtitle_candidates.py`を`official_announcement`入力、既存manifest照合つきで実行した。story候補1件、manifest一致1件、episode候補0件を生成した。既存manifestのtitleは未設定、metadataStatusは`pending`のままである。

初回出力では、episode候補には`reviewStatus: pending`が付く一方、story単位のみの候補には付かなかった。設計の「全候補はpending」と異なるため、story候補にも同fieldを追加し、合成テストを拡充した。同じ実CSVから再生成し、story候補の`reviewStatus: pending`を確認した。manifestとのID一致はタイトルの正しさを意味しない。

実データ由来の表示タイトル・サブタイトルはrelease scope全2,840 episodeで未投入、metadataStatusも全件`pending`だった。したがって、Story pageのEpisodeリンクにおける実タイトル間の優先順位は今回検証できない。候補の人間確認とmanifest反映が行われた後、改めて確認する。

## 境界

実CSV・candidate YAML・出典URL・実タイトルはignored workspace限定。`story_manifest.yaml`の変更、`confirmed`化、Normalized Story / KB / Wikiの再生成、公開input・deployは行っていない。
