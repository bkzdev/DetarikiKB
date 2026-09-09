# Public Production Environment Gate

Version: 0.3
Status: Implemented and rehearsed
Updated: 2026-09-09

---

# 1. 目的

`.github/workflows/public-production-gate.yml`は、手動指定した`main`上のrevisionについて、commit済み匿名合成public inputのdual-build / exposure gateを再実行し、検証済みZensical siteだけをGitHub Pagesへ配備する。production deployは保護された`github-pages` environmentの人間承認後にだけ実行する。

本段階は匿名合成siteによるdeploy / rollback rehearsal専用である。実public input、`knowledge/public/`、実データ由来のMarkdown / HTML、private mappingを参照・upload・deployせず、`publish-ready`判定も行わない。

# 2. 初回dispatch前の人間設定

workflowを一度でもdispatchする前に、repository管理者がGitHubのSettings > Environmentsで`github-pages` environmentを明示的に作成し、次を確認する。未設定のenvironmentをjobから参照すると意図した保護なしで作成され得る。

- required reviewerはrepository ownerの`bkzdev`だけを設定する
- deployment branch / tag ruleを`main`に限定する
- solo運用のためself-reviewを許可し、administrator bypassは禁止する
- environment secret / variableは登録しない
- workflowがdefault branchへmergeされた後、GitHub PagesのSourceをGitHub Actionsへ設定する
- custom domainは設定しない

2026-09-08のユーザー判断により、権限者がowner 1名だけの現状では別reviewer必須にすると承認経路が成立しないため、solo運用としてowner自身のreviewを許可する。これは承認省略ではなく、workflow dispatch後に同じ人間がenvironment画面で承認する運用である。administrator bypass、`main`限定、完全SHA、匿名合成input、全preflight gateは緩和しない。

preflightはGitHubのread-only REST APIからenvironment snapshotとbranch policyを取得し、required reviewerがrepository owner 1名だけ、self-review許可、administrator bypass禁止、custom branch policyが`main`だけ、という状態を匿名codeで再検証する。API取得または設定検証に失敗した場合はartifactをuploadせず、environment jobを開始しない。dispatch者の自己申告は承認根拠にしない。

# 3. Source revisionとrollback digest gate

必須inputの`source_sha`は小文字40桁の完全SHAだけを受け付ける。workflowは任意入力をcheckoutする前にtrusted `main`を取得し、`scripts/check_public_production_source.py`で次をfail-closedに検証してからdetached checkoutする。

1. `origin/main`がcommitとして解決できる
2. 指定SHAがcommitとして存在する
3. 指定SHAが`origin/main`のancestorである
4. checkout後の`HEAD`が指定SHAと完全一致する

任意inputの`expected_tree_sha256`は、小文字64桁のZensical site tree SHA-256である。指定SHAがpreflight時点の`origin/main`先端と一致する通常deployでは空欄にできるが、過去SHAの再配備では必須とする。したがって初回Aと変更版Bでは空欄にし、Aへのrollback時は初回Aのjob summaryに記録された値を指定する。過去SHAでの省略、形式不正、再生成したtree digestとの不一致は、artifact uploadより前に`production-rollback-digest-required`、`production-expected-digest-invalid`、`production-output-digest-mismatch`のいずれかで停止する。

CLIとworkflow固有の診断は固定の匿名status / error codeだけを出し、入力SHAやpathを診断へ展開しない。Git commandもquiet modeで実行する。checkout actionは完全修飾`refs/heads/main`、full history、`persist-credentials: false`とし、外部actionは検証時のcommit SHAへ固定する。

# 4. 合成build、artifact、deployment record

preflight jobは`tests/fixtures/canonical_timeline_public_input/approved_synthetic_input.json`だけを`$RUNNER_TEMP/dkb-production-gate`へ展開し、次を順に実行する。

1. MkDocs / Zensical strict build
2. generator別detached manifest / exposure scan
3. manifest pair比較
4. source revisionとrollback digest要否・値の照合
5. 検証済みZensical siteだけを1日保持の`github-pages` artifactとしてupload

MkDocs siteはdual-build比較用でありuploadしない。detached manifestもsite treeやPages artifactへ含めない。代わりに、公開して差し支えないsource SHA、Zensical manifest SHA-256、Zensical tree SHA-256、gate結果をGitHub Actions job summaryへdeployment recordとして保存する。internal input digest、private path、mappingは記録しない。

workflow全体の既定権限は`contents: read`だけである。`deploy` jobだけが`contents: read`、`pages: write`、`id-token: write`を持つ。`github-pages` environmentの人間承認後、GitHub Pages REST APIから設定を認証付きでread-only取得し、SourceがGitHub Actions（`build_type: workflow`）、custom domain未設定、URLがrepository既定のHTTPS URLであることを固定codeで検証してから`actions/deploy-pages`を実行する。API取得・設定・deploy actionが返すURLの不一致は公開を開始または成功扱いにせず停止する。設定確認をpreflightへ置くにはPages権限をdeploy承認前へ広げる必要があるため、匿名合成artifactのupload後・保護environment内のdeploy直前に限定する。完了後のjob summaryには同じdigest、検証済みPage URL、source SHA、成功状態を記録する。

# 5. 通常dispatch

GitHub PagesのSourceがGitHub Actionsであり、§2のenvironment設定が完了していることを確認してから、`main`上の既知revisionを指定する。

```powershell
gh workflow run public-production-gate.yml --ref main -f source_sha=<40文字のmain上SHA>
```

期待結果は、preflightの全gate通過、`deploy` jobのreview待ち、人間承認後のPages deploy成功である。未承認のまま放置したrun、preflight失敗run、deploy失敗runから次のproduction deployを開始しない。

# 6. A→B→A rollback rehearsal

rollback rehearsalは同じworkflowを3回独立して実行する。1 run内で3回deployして承認を共有すると通常のrollback経路を検証できないため採用しない。

1. **A**: workflow実装を含む既知正常SHAをdispatchし、environmentで承認する。成功後にPage URL、表示マーカー、job summaryのZensical tree SHA-256を記録する。
2. **B**: 匿名合成fixtureの目視可能な表示マーカーだけを変更した後続SHAを、別runとしてdispatch・承認する。同じURLでBの表示とAとは異なるtree SHA-256を確認する。
3. **Aへrollback**: Aの`source_sha`と、手順1で記録した`expected_tree_sha256`を指定して別runをdispatch・承認する。同じURLでAの表示へ戻り、tree SHA-256が手順1と一致することを確認する。

```powershell
gh workflow run public-production-gate.yml --ref main `
  -f source_sha=<Aの40文字SHA> `
  -f expected_tree_sha256=<Aの64文字tree SHA-256>
```

各runは直前runのdeploy完了と表示確認後に開始する。各deployが独立したenvironment承認とGitHub deployment履歴を持つことで、実障害時に使う「既知正常SHAを全gateから再生成して再配備する」経路そのものを検証する。失敗時は新規deployを停止し、現在のdeployment、失敗revision、workflow run、artifact、履歴を自動削除しない。hosting切替や強制rollbackも行わない。

# 7. 次工程

A→B→A rehearsalと表示確認を完了した。次は実データpublic projectionをignored workspaceで生成し、人間が公開対象、label、最終表示をpush前に確認する。実public inputの専用PRと初回実content deployはさらに後の独立gateであり、匿名合成rehearsalの成功だけでは開始しない。

# 8. 実施記録

2026-09-09に、同じproduction workflowと同じPage URLを使う3つの独立runでA→B→A rehearsalを完了した。各runは`github-pages` environmentで個別に承認し、preflight、artifact upload、Pages設定検査、deployをすべて通過した。

| 段階 | Source SHA | Zensical tree SHA-256 | Workflow run | 表示確認 |
|---|---|---|---|---|
| A | `af1e0aab6e249b3f7f942fb10d64719d40bfafdc` | `c3d191356516f67d81c0b5efadbd3870e48059eeb0dfc5a5fea02f09cd9fa662` | [34304395322](https://github.com/bkzdev/DetarikiKB/actions/runs/34304395322) | `合成公開ビルド` |
| B | `014c42d88ac9352b29eb216a73c16c19cbb17f8e` | `01b2d948b2cff8b018839e0810f2f52255a451e20838edc2906f7b2551936577` | [34322601680](https://github.com/bkzdev/DetarikiKB/actions/runs/34322601680) | `合成公開ビルド B` |
| Aへrollback | `af1e0aab6e249b3f7f942fb10d64719d40bfafdc` | `c3d191356516f67d81c0b5efadbd3870e48059eeb0dfc5a5fea02f09cd9fa662` | [34323175235](https://github.com/bkzdev/DetarikiKB/actions/runs/34323175235) | `合成公開ビルド`へ復帰 |

Aとrollback後Aのtree digestは一致し、Bだけが異なる。公開URLは3回とも`https://bkzdev.github.io/DetarikiKB/`で、rollback後に元の見出しと説明文、およびCanonical Timelineへの導線を目視確認した。AとBのartifactを再取得してそれぞれ18 file・7 routeを確認し、漏えい検査対象外のfileやrouteは検出されなかった。rollback後Aはpreflightが再生成したtree digestを既知のA digestと照合してからdeployした。

初回実行前の設定検査を承認前に行おうとしたrun [34303547281](https://github.com/bkzdev/DetarikiKB/actions/runs/34303547281) は、権限境界によりPages APIが404となってpreflightで停止し、deployしなかった。この結果を受けてPR #283でPages設定検査を承認後のprotected deploy jobへ移し、以後の3 runを成功させた。失敗runとdeployment履歴は削除していない。

Bの目視マーカーはrehearsal専用だったため、完了後に生成コードを通常のA表示へ戻した。live siteは先にAの既知正常SHAへrollback済みであり、このcleanup自体は追加deployを要求しない。
