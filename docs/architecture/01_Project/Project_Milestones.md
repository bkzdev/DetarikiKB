# DKB v1 マイルストーン

Status: Living roadmap

この文書は、細かなPR履歴ではなく「プロジェクト全体がどこまで進み、何が残っているか」を短く示す。日々の作業順と詳細は`../../../TASKS.md`、完了済みPRの履歴は`../../project_history/`を正とする。

## v1の完成像

Raw Scriptを安全に正規化し、根拠・不明情報・内部IDを失わずにKnowledge Baseへ統合し、公開可能な情報だけをWikiとして再現可能に生成できる状態をv1の完成とする。全コンテンツを一度に完全公開することや、AI推測だけで未確定情報を埋めることは完成条件に含めない。

## 全体状況

| Milestone | 状態 | 完了の目安 | 現在の要点 |
|---|---|---|---|
| M1 基盤と安全境界 | 完了 | schema、匿名化、非commit境界、PR/検証手順が固定される | parser・KB・Wikiを進める共通契約は整備済み |
| M2 Parser / Normalized Story | 完了 | 主要カテゴリを再現可能に正規化し、unknownを不破棄で診断できる | release scope 511 story・2,840 normalized episodeを全件schema-validで再生成し、invalid / skipped 0と匿名品質集計を確認済み |
| M3 Extraction / Merge / 内部KB | 完了 | candidateとprovenanceを保持して主要entityを統合できる | release scope 2,840 episodeをStage A / Bへ全件再生成し、invalid / skipped 0、全4,778 entityのEvidence / source candidate保持を確認済み |
| M4 Canonical curation | 完了 | ID・profile・story内順序・story間Timelineをreview可能な形で保持できる | release scope全体の確定・保留・conflict・scope差を匿名横断reportで説明可能。全値確定とは分離 |
| M5 Wiki / 閲覧体験 | 完了 | public-safeなStory/Episode/Character/Evidenceページを一貫生成できる | Phase 1 / 2のpage・index・公開Relationship表示を実装し、合成全体siteの機械検査と人間目視を完了 |
| M6 公開準備 | 完了 | 公開範囲、ホスティング、更新・rollback、漏えい検査を決定し、限定公開できる | 実データpublic inputの初回配備、desktop / 390px表示、既知正常rollback digestまで確認済み |
| M7 v1リリースと継続運用 | 完了 | 再生成手順、品質指標、障害対応、定期更新が運用できる | 同一candidateで全gate、protected deploy、公開後確認、release / rollback recordを完了 |

## 現在地と直近の区切り

M1〜M7は完了し、DKB v1を2026-09-21にreleaseした。candidate SHA
`a18122cb1ae8e196d1b5bdf4de0fc77061453277`でM2〜M4を再生成し、main CI、dual public build、
人間目視、protected production deploy、公開後確認、既知正常rollback更新まで完了した。詳細は
[v1 Release Record](../../releases/V1_Release_Record_2026-09-21.md)を正とする。

v1までに完了した主要な到達点は次の3つである。

1. ~~Location / Item / Lore / Event pageと各indexを合成fixture、strict build、独立監査で確定し、M5 Phase 2の共通実装パターンにする。~~ 完了。
2. ~~Relationship公開v1 taxonomy、Stage Bのfail-closed gateとreview queue、Character / Organization page双方のRelationship sectionと相互リンクを実装する。~~ 完了。
3. ~~明示接続候補の初回走査完了を受け、公開用Timelineの目的・表示粒度・unknown/conflict表現を判断し、public projection schema・projector・preflight・rendererを合成fixtureで固定する。~~ 公開profileの採択、protected Pages gate、匿名合成siteのA→B→A rollback rehearsal、実データpublic projectionのpush前review・初回public input昇格・workflow実入力切替・初回実content deployを完了した。公開表示と新しい既知正常rollback digestも確認済みで、M6を完了とする。

M5は2026-09-15に完了した。schema-validな合成全体site 30 routeをすべてHTTP 200・browser warning / error 0で確認し、代表11 routeは390px幅で横overflow 0、内部path・raw command・合成raw markerの露出0を機械検査した。ユーザーによるローカル表示の軽量目視でも全体印象に問題なしと確認し、後続へ進む判断を受けた。

M2は2026-09-16に完了した。release scopeのmanifest 511 story・2,696 episodeと、動的判定したH_scene例外変種144 episodeを一括normalizeし、合計2,840 episodeのschema error、invalid、skippedはいずれも0だった。匿名集計ではunknown block 379件を66 episodeで不破棄保持し、未解決speakerやbranch issueも件数として可視化した。compatibilityの`needs_update` 2件はCHAR_HSの孤立したbranch marker 3件を保持・診断したもので、入力skipや破棄ではない。実Normalized Storyと個別対応はignored workspaceに限定した。

M3は2026-09-17に完了した。M2匿名reportをattestationとして同じ2,840 episodeをStage A / Bへno-clobberで一括再生成し、Extraction schema / semantic error、merge invalid / skippedはいずれも0だった。Character 9,684件・Location 3,250件のcandidateからCharacter 1,528件・Location 3,250件を統合し、4,778 entityすべてでEvidenceRefとSourceCandidateを保持した。canonical IDは184件、未解決entityは4,594件、Character conflictは3件で、0に見せず匿名集計へ残した。構造化入力の無い他6 entity種は0件であり、黙示破棄ではない。H_sceneは本体74 episode・例外変種144 episodeを処理し、重複block 6,017件を既存dedup契約に従って除外した。実Extraction / merged collection / 完全reportはignored workspaceに限定した。

M4は2026-09-17に完了した。M2 / M3の同一入力digestを固定し、canonical ID、Character Profile、release scope全体のstory内順序、internal story間Timelineを1つの匿名readiness reportへ集約した。Canonical Timelineには合計40関係を反映済みで、15回の小規模batch運用を実証済みである。4領域はすべてschema / semantic validationを通過し`reviewable: true`、保留を残すため`fullyConfirmed: false`だった。canonical ID保留4,594 entity、観測source character IDの未登録3件、profile保留178 Character、story内順序保留511 story、story間Timelineの現scope外7 nodeを0と見せず保持した。これは「全値を確定する」完了ではなく、「確定と保留をreview可能に保持する」というM4完了条件に対応する。実artifactと詳細reportはignored workspaceに限定した。

M7は同一candidate SHAへM2→M3→M4のsource revision / digest連鎖、dual public build、
hosted CI、protected production、公開後確認、rollbackを束縛して完了した。以後は
`docs/runbooks/V1_Release_Readiness.md`の変更triggerに従って必要なgateだけを再実行し、
新しいproduction成功時はmachine-readable rollback recordを更新する。

## 人間確認を求める場面

通常の高信頼な本文判定と、検証済みinternal artifactへの可逆な反映は、ユーザーの委任により親agentと独立監査agentが判断する。次の場合だけ人間へまとめて確認する。

- 親agentと監査agentの結論が一致しない、またはconfidenceが高信頼基準を満たさない
- `unknown` / `conflict`を解消するために作品解釈や追加資料が必要
- 公開範囲、表示仕様、scope拡張など成果物の意味が変わる
- 公開、削除、rollback、既存canonical値の変更など不可逆または影響の大きい操作

これにより、1 edgeごとの承認要求は行わず、保留事項が生じた場合だけマイルストーン単位でまとめて確認する。
