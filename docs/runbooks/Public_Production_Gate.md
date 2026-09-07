# Public Production Environment Gate

Version: 0.1
Status: Implemented
Updated: 2026-09-08

---

# 1. 目的

`.github/workflows/public-production-gate.yml`は、手動指定した`main`上のrevisionについて、commit済み匿名合成public inputのdual-build / exposure gateを再実行し、保護された`github-pages` environmentの承認待ちを通す。本段階はproduction workflowの承認境界だけを固定するもので、artifact upload、GitHub Pages設定変更、site deploy、公開URL生成は行わない。

# 2. 初回dispatch前の人間設定

workflowを一度でもdispatchする前に、repository管理者がGitHubのSettings > Environmentsで`github-pages` environmentを明示的に作成し、次を確認する。未設定のenvironmentをjobから参照すると意図した保護なしで作成され得る。

- required reviewerを1名以上設定する
- deployment branch / tag ruleを`main`に限定する
- 利用可能ならself-reviewを禁止し、administrator bypassも禁止する
- environment secret / variableは登録しない
- GitHub PagesのSourceはまだGitHub Actionsへ切り替えない（第7段階で扱う）

reviewerの選定とrepository設定変更はこのPRの自動化範囲外である。設定画面の現在値を人間が確認するまでworkflowを実行しない。preflightはGitHubのread-only REST APIからenvironment snapshotとbranch policyを取得し、required reviewerが1名以上、self-review禁止、administrator bypass禁止、custom branch policyが`main`だけ、という状態を匿名codeで再検証する。API取得または設定検証に失敗した場合はenvironment jobを開始しない。dispatch者の自己申告は承認根拠にしない。

# 3. Source revision gate

inputの`source_sha`は小文字40桁の完全SHAだけを受け付ける。workflowは任意入力をcheckoutする前にtrusted `main`を取得し、`scripts/check_public_production_source.py`で次をfail-closedに検証してからdetached checkoutする。

1. `origin/main`がcommitとして解決できる
2. 指定SHAがcommitとして存在する
3. 指定SHAが`origin/main`のancestorである
4. checkout後の`HEAD`が指定SHAと完全一致する

CLIとworkflow固有の診断は固定の匿名status / error codeだけを出し、入力SHAやpathを診断へ展開しない。Git commandもquiet modeで実行する。checkout actionは完全修飾`refs/heads/main`、full history、`persist-credentials: false`とし、外部actionは検証時のcommit SHAへ固定する。

# 4. 合成buildとenvironment gate

preflight jobは`tests/fixtures/canonical_timeline_public_input/approved_synthetic_input.json`だけを`$RUNNER_TEMP/dkb-production-gate`へ展開し、MkDocs / Zensical strict build、generator別detached manifest / exposure scan、manifest pair比較を実行する。実public input、`knowledge/public/`、実site、secretは参照しない。

preflight通過後の`production-gate` jobだけが`github-pages` environmentを参照する。承認後にsource SHAの引継ぎを再確認し、`deployment_authorized=false`を記録して終了する。workflow全体の権限は`contents: read`だけであり、Pages / OIDC書込権限、artifact upload、configure / deploy action、environment URLを持たない。このjobの成功は公開承認や`publish-ready`判定ではない。

# 5. 設定後のrehearsal手順

本workflowがdefault branchへmergeされ、§2の人間確認が完了した後にだけ、`main`上の既知revisionを完全SHAで指定する。

```powershell
gh workflow run public-production-gate.yml --ref main -f source_sha=<40文字のmain上SHA>
```

期待結果は、preflightの全gate通過、`production-gate`のreview待ち、承認後の`deployment_authorized=false`である。一時site / manifestはrunner temp内だけに生成されるが、永続artifact、upload、deploy、公開URLは生成されない。

# 6. 次工程

次は別PRで、匿名合成siteだけを対象にPages artifact upload / deployと既知正常SHAへのrollback rehearsalを実装する。その前に§2のenvironment保護とGitHub Pages Source変更の影響を人間が画面で確認する。実public inputのpushと実データdeployはさらに後の独立gateとする。
