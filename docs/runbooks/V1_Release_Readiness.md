# DKB v1 Release Readiness Checklist

Version: 0.1 Draft
Status: Draft checklist; release decision not yet made
Updated: 2026-09-15

---

## 1. 目的

本文書は、DKB v1の候補revisionを「再生成でき、品質状態を説明でき、安全に公開・復旧できる」と判定するための入口である。各領域の手順をここに複製せず、既存の正典runbookをどの順番で使い、何をrelease recordに残すかを定める。

このchecklistの作成はM7の着手を意味するが、v1 releaseの承認やM2〜M5の完了を意味しない。現在のmilestone状態は[Project Milestones](../architecture/01_Project/Project_Milestones.md)を正とする。

## 2. 固定するrelease candidate

checklistを開始する前に、次の値を1つのrelease recordへ固定する。実データ由来の内部ID、private mapping、raw path、本文はrecordやPRに記載しない。

- candidateの40文字`main` commit SHA
- 使用する`uv.lock`のcommit上の版
- 公開対象とするcommit済みpublic inputの種類とrevision
- 対象とするcontent categoryと、v1であえて含めない範囲
- 検証開始日時と担当者

candidate検証中にsource、lock、schema、dictionary、public input、renderer、workflowのいずれかが変わった場合、旧結果を流用せず、新しいcandidate SHAで必要なgateを再実行する。

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

- [ ] [Real Data Dry Run](Real_Data_Dry_Run.md)の対象範囲と入力を固定する
- [ ] `normalize_story.py --validate`を使い、schema・compatibility検証に失敗したJSONを保存しない
- [ ] `extract_story.py --validate`を使い、複数入力は全件検証後に保存する
- [ ] [Merged Collection Dry Run](Real_Data_Merged_Collection_Dry_Run.md)に従い、Stage Bのinvalid / skippedを確認する
- [ ] Timelineを対象に含める場合は[Timeline Consistency Check](Timeline_Consistency_Check.md)を実行する
- [ ] Wiki入力を再生成し、[Real Data Wiki Render](Real_Data_Wiki_Render_Dry_Run.md)の検証を実行する

実Normalized Story、Extraction、merged collection、生成Markdown / HTML、review packetは既存方針どおりworkspace限定・非commitとする。

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

- [ ] candidate SHA上の全PRが完了し、意図しない差分がない
- [ ] [AI PR Playbook](AI_PR_Playbook.md)の標準検証一式がPASS
- [ ] PR上のCIとpublic-buildがPASS
- [ ] squash merge後のmainを同期し、main CIとpublic-buildがPASS
- [ ] `TASKS.md`と[Project Milestones](../architecture/01_Project/Project_Milestones.md)が実状態と一致
- [ ] release対象外のKnown Issuesが「未解決だが非blocking」である理由を記録
- [ ] commit禁止物、実データ生成物、secretがGit履歴へ混入していない

## 6. Public release gate

### 6.1 Build-only

[Public Build-Only Workflow](Public_Build_Only.md)をcandidate SHAのPRとmain pushで通す。出力は検証用であり、artifact upload・deploy・`publish-ready`化を行わない。

- [ ] commit済みレビュー済みpublic inputだけを使用
- [ ] MkDocs / Zensical strict buildがPASS
- [ ] generator別exposure scanがPASS
- [ ] detached manifestのroute setとsource / lock / input束縛が一致
- [ ] hosted workflowがprivate artifactやworkspaceを参照していない

### 6.2 Production

公開を伴う操作は[Public Production Environment Gate](Public_Production_Gate.md)を正とする。agentは許可されたdispatchのpreflight結果を確認できるが、`github-pages` environmentの人間承認を代行しない。

- [ ] `main`上の完全SHAを指定
- [ ] preflightでreviewed public input、environment policy、revision、digestをfail-closedに検査
- [ ] protected environmentで人間がdeployを承認
- [ ] 承認後、deploy直前にPages設定をread-onlyで検査
- [ ] deploy後にURL、代表route、desktop / mobile表示を確認
- [ ] source SHA、public-safeなdigest、workflow run URL、確認日をrelease recordへ保存

## 7. 障害時とrollback

公開後に問題を確認した場合、次の順で対応する。

1. 新しいproduction deployを開始せず、症状、現在revision、workflow run、影響routeを記録する。
2. 失敗run、deployment history、review証跡、artifactを削除しない。
3. Production Gateに記録された既知正常のsource SHAとZensical tree SHA-256を選ぶ。
4. 過去SHA用の`expected_tree_sha256`を指定し、同じpreflight・build・exposure gate・人間承認を通して再配備する。
5. URL、表示、tree digestの復帰を確認し、原因修正は別PRで行う。

hosting切替、強制push、履歴削除、未検証artifactの手動uploadを緊急rollbackの代用にしない。

## 8. 継続運用

日付だけで無条件に全データを再生成する定期jobはこの草案で追加しない。次の変更triggerごとに必要な検証範囲を選び、結果をPRまたは匿名release recordに追記する。

| Trigger | 必須の再確認 |
|---|---|
| Raw Script / manifest / dictionary変更 | normalize→extract→merge、compatibilityと未解決集計 |
| parser / extractor / merger / schema変更 | 影響stage以降の再生成、schema / semantic check |
| renderer / public input / exposure rule変更 | public build、route、exposure、必要に応じて目視 |
| lock / generator / workflow変更 | 標準CI、dual-build、manifest比較、workflow権限 |
| production変更 | protected deploy、表示確認、rollback record更新 |
| 障害・セキュリティ警告 | 新deploy停止、影響調査、必要なrollback |

時間ベースの棚卸し周期、自動dependency update、自動production deployは未採択である。必要性と運用コストを実測して別途決める。

## 9. Release record template

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

この条件が揃うまで`Status: Draft checklist; release decision not yet made`を維持する。
