# DKB v1 マイルストーン

Status: Living roadmap

この文書は、細かなPR履歴ではなく「プロジェクト全体がどこまで進み、何が残っているか」を短く示す。日々の作業順と詳細は`../../../TASKS.md`、完了済みPRの履歴は`../../project_history/`を正とする。

## v1の完成像

Raw Scriptを安全に正規化し、根拠・不明情報・内部IDを失わずにKnowledge Baseへ統合し、公開可能な情報だけをWikiとして再現可能に生成できる状態をv1の完成とする。全コンテンツを一度に完全公開することや、AI推測だけで未確定情報を埋めることは完成条件に含めない。

## 全体状況

| Milestone | 状態 | 完了の目安 | 現在の要点 |
|---|---|---|---|
| M1 基盤と安全境界 | 完了 | schema、匿名化、非commit境界、PR/検証手順が固定される | parser・KB・Wikiを進める共通契約は整備済み |
| M2 Parser / Normalized Story | ほぼ完了 | 主要カテゴリを再現可能に正規化し、unknownを不破棄で診断できる | 主経路とstandalone / embedded互換性は実装済み。v1 release scopeの再生成・匿名品質集計を待つ |
| M3 Extraction / Merge / 内部KB | 進行中 | candidateとprovenanceを保持して主要entityを統合できる | Stage A、8種entityの最小merge、Evidence・Summary基盤は実装済み。実corpusの充足は継続 |
| M4 Canonical curation | 進行中 | ID・profile・story内順序・story間Timelineをreview可能な形で保持できる | EVENT story内順序は完了。story間Timelineは基盤と15回の小規模batch運用を実証済み |
| M5 Wiki / 閲覧体験 | 完了 | public-safeなStory/Episode/Character/Evidenceページを一貫生成できる | Phase 1 / 2のpage・index・公開Relationship表示を実装し、合成全体siteの機械検査と人間目視を完了 |
| M6 公開準備 | 完了 | 公開範囲、ホスティング、更新・rollback、漏えい検査を決定し、限定公開できる | 実データpublic inputの初回配備、desktop / 390px表示、既知正常rollback digestまで確認済み |
| M7 v1リリースと継続運用 | 進行中 | 再生成手順、品質指標、障害対応、定期更新が運用できる | checklist草案を作成済み。v1判定はM2〜M5の完了確認後に行う |

## 現在地と直近の区切り

現在の主対象はM5へ移っている。M4ではCanonical Timelineのschema、semantic check、review packet、promotion plan、安全なlocal executorを完成させ、実データへ合計40関係を反映済みである。M5ではPhase 1のStory / Episode / Character / Evidenceに続き、Phase 2のLocation / Item / Lore / Event page・各indexとTop page導線を実装した。

次の切りのよい到達点は次の3つである。

1. ~~Location / Item / Lore / Event pageと各indexを合成fixture、strict build、独立監査で確定し、M5 Phase 2の共通実装パターンにする。~~ 完了。
2. ~~Relationship公開v1 taxonomy、Stage Bのfail-closed gateとreview queue、Character / Organization page双方のRelationship sectionと相互リンクを実装する。~~ 完了。
3. ~~明示接続候補の初回走査完了を受け、公開用Timelineの目的・表示粒度・unknown/conflict表現を判断し、public projection schema・projector・preflight・rendererを合成fixtureで固定する。~~ 公開profileの採択、protected Pages gate、匿名合成siteのA→B→A rollback rehearsal、実データpublic projectionのpush前review・初回public input昇格・workflow実入力切替・初回実content deployを完了した。公開表示と新しい既知正常rollback digestも確認済みで、M6を完了とする。

M5は2026-09-15に完了した。schema-validな合成全体site 30 routeをすべてHTTP 200・browser warning / error 0で確認し、代表11 routeは390px幅で横overflow 0、内部path・raw command・合成raw markerの露出0を機械検査した。ユーザーによるローカル表示の軽量目視でも全体印象に問題なしと確認し、後続へ進む判断を受けた。

M7は`docs/runbooks/V1_Release_Readiness.md`の草案作成により着手した。これは既存runbookの実行順、品質証跡、blocking条件、release record、rollbackへの導線を整理するもので、M2〜M5の未完了項目を完了扱いしない。

## 人間確認を求める場面

通常の高信頼な本文判定と、検証済みinternal artifactへの可逆な反映は、ユーザーの委任により親agentと独立監査agentが判断する。次の場合だけ人間へまとめて確認する。

- 親agentと監査agentの結論が一致しない、またはconfidenceが高信頼基準を満たさない
- `unknown` / `conflict`を解消するために作品解釈や追加資料が必要
- 公開範囲、表示仕様、scope拡張など成果物の意味が変わる
- 公開、削除、rollback、既存canonical値の変更など不可逆または影響の大きい操作

これにより、1 edgeごとの承認要求は行わず、保留事項が生じた場合だけマイルストーン単位でまとめて確認する。
