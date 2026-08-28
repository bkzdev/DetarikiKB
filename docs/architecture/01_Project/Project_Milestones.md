# DKB v1 マイルストーン

Status: Living roadmap

この文書は、細かなPR履歴ではなく「プロジェクト全体がどこまで進み、何が残っているか」を短く示す。日々の作業順と詳細は`../../../TASKS.md`、完了済みPRの履歴は`../../project_history/`を正とする。

## v1の完成像

Raw Scriptを安全に正規化し、根拠・不明情報・内部IDを失わずにKnowledge Baseへ統合し、公開可能な情報だけをWikiとして再現可能に生成できる状態をv1の完成とする。全コンテンツを一度に完全公開することや、AI推測だけで未確定情報を埋めることは完成条件に含めない。

## 全体状況

| Milestone | 状態 | 完了の目安 | 現在の要点 |
|---|---|---|---|
| M1 基盤と安全境界 | 完了 | schema、匿名化、非commit境界、PR/検証手順が固定される | parser・KB・Wikiを進める共通契約は整備済み |
| M2 Parser / Normalized Story | ほぼ完了 | 主要カテゴリを再現可能に正規化し、unknownを不破棄で診断できる | 主経路は実装済み。残る互換性差分と長尾commandを小さく解消中 |
| M3 Extraction / Merge / 内部KB | 進行中 | candidateとprovenanceを保持して主要entityを統合できる | Stage A、8種entityの最小merge、Evidence・Summary基盤は実装済み。実corpusの充足は継続 |
| M4 Canonical curation | 進行中 | ID・profile・story内順序・story間Timelineをreview可能な形で保持できる | EVENT story内順序は完了。story間Timelineは基盤完了、実データ小規模検証中 |
| M5 Wiki / 閲覧体験 | 進行中 | public-safeなStory/Episode/Character/Evidenceページを一貫生成できる | 基本rendererとlocal previewは実装済み。残entityページ・関係表示・全体目視確認が残る |
| M6 公開準備 | 未着手 | 公開範囲、ホスティング、更新・rollback、漏えい検査を決定し、限定公開できる | internal/public分離は済み。公開方式とTimeline projectionは別decision待ち |
| M7 v1リリースと継続運用 | 未着手 | 再生成手順、品質指標、障害対応、定期更新が運用できる | M2〜M6の完了後にrelease checklistを固定する |

## 現在地と直近の区切り

現在の主対象はM4である。Canonical Timelineのschema、semantic check、review packet、promotion plan、安全なlocal executorは完成している。実データでは2件の関係を反映済みで、次は複数の高信頼関係を小さなbatchで検証する。

次の切りのよい到達点は次の3つである。

1. 高信頼なstory間関係を親agentと独立監査agentの一致で小規模batch化する。
2. 各batchをdry-run / preflight / semantic check後にinternal artifactへ反映し、矛盾0を確認する。
3. 十分なsampleが揃ったら、公開用Timelineの目的・表示粒度・unknown/conflict表現を人間が決定する。

## 人間確認を求める場面

通常の高信頼な本文判定と、検証済みinternal artifactへの可逆な反映は、ユーザーの委任により親agentと独立監査agentが判断する。次の場合だけ人間へまとめて確認する。

- 親agentと監査agentの結論が一致しない、またはconfidenceが高信頼基準を満たさない
- `unknown` / `conflict`を解消するために作品解釈や追加資料が必要
- 公開範囲、表示仕様、scope拡張など成果物の意味が変わる
- 公開、削除、rollback、既存canonical値の変更など不可逆または影響の大きい操作

これにより、1 edgeごとの承認要求は行わず、保留事項が生じた場合だけマイルストーン単位でまとめて確認する。
