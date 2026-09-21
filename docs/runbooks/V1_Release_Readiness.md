# DKB v1 Release Readiness Checklist

Version: 1.0
Status: Released; release decision completed on 2026-09-21
Updated: 2026-09-21

---

## 1. 目的

本文書は、DKB v1の候補revisionを「再生成でき、品質状態を説明でき、安全に公開・復旧できる」と判定するための入口である。各領域の手順をここに複製せず、既存の正典runbookをどの順番で使い、何をrelease recordに残すかを定める。

このchecklistはM7の判定手順を定め、candidate
`a18122cb1ae8e196d1b5bdf4de0fc77061453277`で全gateを完了した。最終証跡は
[v1 Release Record](../releases/V1_Release_Record_2026-09-21.md)、現在のmilestone状態は
[Project Milestones](../architecture/01_Project/Project_Milestones.md)を正とする。

## 2. 固定するrelease candidate

checklistを開始する前に、次の値を1つのrelease recordへ固定する。実データ由来の内部ID、private mapping、raw path、本文はrecordやPRに記載しない。

- candidateの40文字`main` commit SHA
- 使用する`uv.lock`のcommit上の版
- 公開対象とするcommit済みpublic inputの種類とrevision
- 対象とするcontent categoryと、v1であえて含めない範囲
- 検証開始日時と担当者

candidate検証中にsource、lock、schema、dictionary、public input、renderer、workflowのいずれかが変わった場合、旧結果を流用せず、新しいcandidate SHAで必要なgateを再実行する。

`schemas/v1_release_candidate_record.schema.json`と
`scripts/build_v1_release_candidate_record.py`は、この固定を機械的に確認する。scriptはcleanな
`main`の`HEAD`と`origin/main`が指定SHAに一致する場合だけ動作し、M2→M3→M4のreport
digest連鎖、同じSHA / lock / public inputから得たMkDocs・Zensical manifest、GitHub上の
main CI / Public Build成功run、既知正常rollback先を1 recordへ束縛する。GitHub runは
記録済みrun IDをread-only APIで再取得し、workflow path、main push、head SHA、成功状態を
照合する。既知rollback runもproduction workflow、source SHA、成功状態を同じAPIで照合する。
list検索結果や手入力の成功表明だけでは通さない。

## 3. Milestone依存gate

| Milestone | v1判定前の確認 | 証跡 |
|---|---|---|
| M1 | schema、非commit境界、PR検証手順が維持されている | CI、[AI PR Playbook](AI_PR_Playbook.md) |
| M2 | release scopeのRaw Scriptが再現可能にnormalizeされ、unknownが破棄されない | compatibility report、Normalized Story schema検証 |
| M3 | release scopeのStage A / Stage Bが再生成でき、candidate・provenance・未解決情報を保持する | Extraction / merged schema検証、匿名集計 |
| M4 | release scopeのcanonical ID・profile・Timelineの確定と保留がreview可能な状態で説明できる | review / consistency reportの匿名集計 |
| M5 | 生成site全体の導線、desktop / mobile表示、文言が人間によって確認済み | [MkDocs local preview](MkDocs_Local_Preview.md)の目視記録 |
| M6 | public-safe build、exposure gate、protected production、既知正常rollback先が機能する | [Public Build](Public_Build_Only.md)、[Production Gate](Public_Production_Gate.md) |

M2〜M5のいずれかが未完了の場合、本checklistの下流をリハーサルすることはできるが、v1 release判定は行わない。

## 4. 再生成と品質証跡

### 4.1 Internal pipeline

- [x] [Real Data Dry Run](Real_Data_Dry_Run.md)の対象範囲と入力を固定する
- [x] `normalize_release_scope.py --source-sha <candidate SHA>`を使い、manifest全件とH_scene例外変種をno-clobberで一括normalizeする。schema検証失敗・episode ID重複・未処理入力があれば部分出力や完了reportを公開しない
- [x] `build_release_scope_knowledge.py`をM2匿名reportとともに使い、Stage A / Bをno-clobberで一括再生成する。M2件数・categoryとの一致、入力episode集合との一致、Extraction schema / semantic validation、Stage B invalid / skipped 0、Merged Collection schemaをすべてgateする
- [x] [Merged Collection Dry Run](Real_Data_Merged_Collection_Dry_Run.md)に従い、匿名`release_scope_knowledge_report.json`を検証する
- [x] Timelineを対象に含める場合は[Timeline Consistency Check](Timeline_Consistency_Check.md)を実行する
- [x] [Release Scope Curation Readiness](Release_Scope_Curation_Readiness.md)でcanonical ID / profile / story内・story間Timelineの確定と保留を匿名集約する
- [x] Wiki入力を再生成し、[Real Data Wiki Render](Real_Data_Wiki_Render_Dry_Run.md)の検証を実行する

実Normalized Story、Extraction、merged collection、生成Markdown / HTML、review packetは既存方針どおりworkspace限定・非commitとする。

M2の証跡には`release_scope_normalization_report.json`の匿名集計だけを転記する。
個別のstory / episode ID、raw path、本文、unknown値の列挙、manifest digest以外の
private mappingはrelease recordやPRへ含めない。report schemaは
`schemas/release_scope_normalization_report.schema.json`を正とする。

M2 baseline（2026-09-16）は511 story・manifest 2,696 episodeにH_scene例外変種
144 episodeを加えた2,840 episodeを全件処理し、Normalized Story schema error、invalid、
skippedはいずれも0だった。compatibility内訳はcompatible 2,201、warning 637、
needs_update 2。unknown block 379件（66 episode）は破棄せず保持した。needs_updateは
CHAR_HSの孤立したbranch marker 3件を2 episodeで診断した結果で、未報告skipではない。
このbaselineはM2完了の再現性証跡であり、最終candidate SHAを固定したrelease gateの
チェック済み状態を意味しない。

M3の証跡は`schemas/release_scope_knowledge_report.schema.json`準拠の匿名reportとし、
個別ID、path、本文、warning / error本文、review record内容をrelease recordやPRへ
含めない。内部のExtraction、merged collection、完全なmerge reportはworkspace限定とする。

M3 baseline（2026-09-17）はM2の2,840 episodeを全件処理し、Extraction schema / semantic
error、merge invalid / skippedはいずれも0だった。Character 9,684件・Location 3,250件の
candidateからCharacter 1,528件・Location 3,250件を統合し、全4,778 entityでEvidenceRefと
SourceCandidateを保持した。canonical ID 184件、未解決entity 4,594件、Character conflict
3件、special speaker label 403件を匿名集計で保持した。H_sceneは本体74 episode・例外変種
144 episode、重複除外block 6,017件だった。このbaselineはM3完了の再現性証跡であり、
最終candidate SHAを固定したrelease gateのチェック済み状態を意味しない。

M4 baseline（2026-09-17）は同じM2 / M3 artifactとdictionary / profile / Timelineを
横断照合し、4領域すべて`reviewable: true`、全体`fullyConfirmed: false`を確認した。
canonical ID 184件に対してCharacter 1,344件・Location 3,250件を保留し、canonical
Character 184件中profile確認済み6件・保留178件、観測source character IDの未登録3件を
匿名集計した。release scope全体の
story内順序は2,840 episode / 511 storyでfinding 0・保留511 story、story間Timelineは
72 node / 40 confirmed edge・semantic finding 0で、現scope内65 node・scope外7 nodeだった。
未解決を0と見せずreview可能に保持したためM4の完了条件を満たすが、全値確定や最終
candidate SHAのrelease gate完了を意味しない。

### 4.2 記録する品質指標

固定の新規閾値はこのchecklistで採択しない。値を隠してPASSにせず、release scopeと既存の領域別方針に対して次を匿名集計で記録する。

- 入力story / episode数、処理成功数、invalid / skipped数
- parser compatibilityの`compatible` / `warning` / `needs_update` / `blocked`内訳
- unknown command・unknown block・未解決speakerの件数と、不破棄保持の確認
- entity種類別のcandidate / merged / unresolved / conflict数
- Evidence / Summary / canonical reviewの対象数と保留数
- public projectionのnode / relation / unknown aggregate / conflict aggregate数
- 生成route数、broken link、browser warning / error、mobile overflow
- exposure finding数、public manifest / tree digest、CIとpublic-buildの結果

unknownやunresolvedが0でないこと自体は自動的な失敗ではない。破棄されず、公開対象に混入せず、制約として説明できることを確認する。

### 4.3 Blocking条件

次のいずれかがある場合はv1 candidateを通さない。

- schema / semantic validationの失敗、または入力の未報告skip
- unknown、unresolved、conflict、provenanceの黙示破棄
- public siteへの内部ID、raw command、local path、private mapping、review本文の露出
- 公開routeのbroken link、strict build失敗、重大な表示崩れ
- Playbook標準検証、PR CI、main CI、public-buildの失敗
- M5の人間目視確認が未完了
- production workflowのprotected environment承認が無い、またはrollback先を確認できない

## 5. Code / documentation gate

- [x] candidate SHA上の全PRが完了し、意図しない差分がない
- [x] [AI PR Playbook](AI_PR_Playbook.md)の標準検証一式がPASS
- [x] PR上のCIとpublic-buildがPASS
- [x] squash merge後のmainを同期し、main CIとpublic-buildがPASS
- [x] `TASKS.md`と[Project Milestones](../architecture/01_Project/Project_Milestones.md)が実状態と一致
- [x] release対象外のKnown Issuesが「未解決だが非blocking」である理由を記録
- [x] commit禁止物、実データ生成物、secretがGit履歴へ混入していない

## 6. Public release gate

### 6.1 Build-only

[Public Build-Only Workflow](Public_Build_Only.md)をcandidate SHAのPRとmain pushで通す。出力は検証用であり、artifact upload・deploy・`publish-ready`化を行わない。

- [x] commit済みレビュー済みpublic inputだけを使用
- [x] MkDocs / Zensical strict buildがPASS
- [x] generator別exposure scanがPASS
- [x] detached manifestのroute setとsource / lock / input束縛が一致
- [x] hosted workflowがprivate artifactやworkspaceを参照していない

### 6.2 Production

公開を伴う操作は[Public Production Environment Gate](Public_Production_Gate.md)を正とする。agentは許可されたdispatchのpreflight結果を確認できるが、`github-pages` environmentの人間承認を代行しない。

- [x] `main`上の完全SHAを指定
- [x] preflightでreviewed public input、environment policy、revision、digestをfail-closedに検査
- [x] protected environmentで人間がdeployを承認
- [x] 承認後、deploy直前にPages設定をread-onlyで検査
- [x] deploy後にURL、代表route、desktop / mobile表示を確認
- [x] source SHA、public-safeなdigest、workflow run URL、確認日をrelease recordへ保存

## 7. 障害時とrollback

公開後に問題を確認した場合、次の順で対応する。

1. 新しいproduction deployを開始せず、症状、現在revision、workflow run、影響routeを記録する。
2. 失敗run、deployment history、review証跡、artifactを削除しない。
3. Production Gateに記録された既知正常のsource SHAとZensical tree SHA-256を選ぶ。
4. 過去SHA用の`expected_tree_sha256`を指定し、同じpreflight・build・exposure gate・人間承認を通して再配備する。
5. URL、表示、tree digestの復帰を確認し、原因修正は別PRで行う。

hosting切替、強制push、履歴削除、未検証artifactの手動uploadを緊急rollbackの代用にしない。

## 8. 継続運用

日付だけで無条件に全データを再生成する定期jobは追加しない。次の変更triggerごとに必要な検証範囲を選び、結果をPRまたは匿名release recordに追記する。

| Trigger | 必須の再確認 |
|---|---|
| Raw Script / manifest / dictionary変更 | normalize→extract→merge、compatibilityと未解決集計 |
| parser / extractor / merger / schema変更 | 影響stage以降の再生成、schema / semantic check |
| renderer / public input / exposure rule変更 | public build、route、exposure、必要に応じて目視 |
| lock / generator / workflow変更 | 標準CI、dual-build、manifest比較、workflow権限 |
| production変更 | protected deploy、表示確認、rollback record更新 |
| 障害・セキュリティ警告 | 新deploy停止、影響調査、必要なrollback |

時間ベースの棚卸し周期、自動dependency update、自動production deployは未採択である。必要性と運用コストを実測して別途決める。

## 9. Release record

### 9.1 機械生成するrehearsal record

M2〜M4の実reportとpublic site manifestは非commitのため、rehearsal recordも
`workspace/dry_runs/`配下へno-clobberで生成し、commitしない。recordは内部ID、raw path、
本文、private mappingを含めず、digest、匿名件数、run URL、rollback情報だけを保持する。
生成時点ではproductionを実行・承認せず、`candidateGateStatus: pending_human_approval`、
`finalDecision: pending`に固定する。したがって、このrecordが生成できてもM7完了や公開承認を
意味しない。

dual public site manifestは外部fileを入力せず、CLIが候補SHAのcommitted public inputから
一時directoryへMkDocs / Zensicalをstrict buildし、既存exposure scanを通して生成する。
M2〜M4 reportはM2生成時に指定した`sourceRevision`を後段へ伝播し、candidate SHAと3 report
すべてが一致しなければ停止する。

```powershell
uv run python scripts/build_v1_release_candidate_record.py `
  --candidate-sha <40文字のmain SHA> `
  --normalization-report <M2匿名report> `
  --knowledge-report <M3匿名report> `
  --curation-report <M4匿名report> `
  --ci-run-id <main CI run ID> `
  --public-build-run-id <Public Build run ID> `
  --validated-at <UTC ISO 8601> `
  --output workspace/dry_runs/<run>/v1_release_candidate_record.json
```

候補SHAを変えた場合はmanifestとhosted runを含めてrecordを作り直す。scriptはdispatch、
deploy、artifact upload、environment承認を行わない。

既知正常rollback先は`config/public_rollback.json`をmachine-readableな正とする。変更は
production成功runのsource SHA / Zensical tree SHA-256 / Pages URLを確認した別PRでのみ行い、
release record生成時はschema検証、対象repositoryのPages URL、production workflow成功run、
source SHAをread-onlyで再照合する。任意のSHA / tree / runをCLI引数で差し替えられない。

### 9.2 最終release判断で補う記録

```text
Candidate SHA:
Scope / exclusions:
Validation date:
M1 status / evidence:
M2 status / evidence:
M3 status / evidence:
M4 status / evidence:
M5 visual review / reviewer / date:
M6 public gate evidence:
Internal regeneration summary:
Quality metrics summary:
Known non-blocking issues:
PR CI URL / result:
Main CI URL / result:
Public build URL / result:
Production run URL / result:
Public URL:
Zensical tree SHA-256:
Rollback source SHA / tree SHA-256:
Final decision: pending | released | rejected
Decision owner / date:
```

recordは公開可能な集計とURLだけを含む。internal IDやprivate artifactとの対応が必要な場合は、既存のignored workspaceに分離する。

## 10. M7完了条件

M7は次の全てを満たしたときだけ完了とする。

- M2〜M5を含むrelease scopeの依存gateが完了
- 同一candidate SHAの再生成・品質・code・public gateが全てPASS
- 人間によるM5目視確認とprotected production承認が完了
- release recordと既知正常rollback先が更新済み
- 未解決事項がblocking / non-blockingに分類され、公開範囲と非公開範囲を説明できる

candidate `a18122cb1ae8e196d1b5bdf4de0fc77061453277`は2026-09-21に全条件を満たし、
protected production deployと公開後確認を完了した。最終判断は`released`、M7は完了である。
