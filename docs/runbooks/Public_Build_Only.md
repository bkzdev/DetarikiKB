# Public Build-Only Workflow

Version: 0.2
Status: Implemented
Updated: 2026-09-13

---

# 1. 目的

`.github/workflows/public-build.yml`は、commit済みのレビュー済みpublic inputだけからpublic-only Markdownを生成し、MkDocs / Zensicalのdual-buildとdetached site manifest / exposure gateを検証する。PRと`main` pushの回帰検査であり、artifact upload、Pages設定、production deploy、公開承認を行わない。

# 2. 固定入力と一時出力

入力は`knowledge/public/timelines/canonical_timeline_public_input.json`へ固定する。このファイルはpush前reviewとlocal promotionを通過した`approved_for_build` envelopeである。private mapping、review / preflight record、internal artifactはhosted workflowへ渡さない。

`scripts/prepare_public_build.py`はenvelope schema / payload digestとpublic-only semantic gateを検証し、`$RUNNER_TEMP/dkb-public-build`配下へ次を生成する。

- public-only Markdown source（landing、Canonical Timeline、Story / Episode stub）
- 一時MkDocs / Zensical config
- generator別site directory
- detached manifest用directory

repository内への出力、既存output root、symlink / reparse inputはfail-closedに拒否する。CLIは成功時のfile countまたは匿名error codeだけを出し、label、public ID、path、本文をlogへ列挙しない。

# 3. Public-only semantic gate

`agents/wiki_generator/public_build.py`はhosted workflowへinternal artifactやprivate mappingを渡さず、public envelope単独で次を検査する。

- component keyの決定的な連番
- public Episode IDの一意性
- public Story IDに対するlabelの一貫性
- Story / Episode page pathの衝突なし
- relation endpointのcomponent内存在、self relation / canonical duplicate / conflictなし
- component graphの連結性
- component / node / relationのcanonical順序
- 生成Markdown linkとStory / Episode stubの完全一致

findingは固定の匿名codeだけで返す。public labelはstub headingへ書く前にHTML / Markdown escapeする。

# 4. Workflow gate

workflowは`pull_request`と`main` pushで動き、権限は`contents: read`だけとする。

1. `uv sync --locked`
2. レビュー済みpublic inputから一時source / configを準備
3. MkDocs strict build
4. Zensical strict build
5. checked-out 40桁commit SHA、`uv.lock`、レビュー済みinput、実configを束縛して両siteをscan
6. site外の一時directoryへ各detached manifestをno-clobber作成
7. `scripts/compare_public_site_manifests.py`でsource revision、lock / input digest、HTML route setの一致を確認

theme asset差があるためgenerator間のtree digestやconfig digest一致は要求しない。manifestはCI job内の一時検証物で、artifactとしてuploadしない。

# 5. Security boundary / Non-goals

- `permissions: contents: read`以外を付与しない
- `pull_request_target`や`workflow_dispatch`を使わない
- `actions/upload-artifact`、Pages artifact、deploy actionを使わない
- environment、secret、OIDC、`pages: write`、`id-token: write`を使わない
- `knowledge/public/timelines/canonical_timeline_public_input.json`以外の実artifactを読み込まない
- site、manifest、生成Markdown / HTMLをcommitまたは外部公開しない
- `publish-ready`へ変更しない

JS / CSS / source map等のvendor assetは既存site manifest方針どおり全文marker scanを行わない。将来、任意contentをこれらへ埋め込む変更時はasset allowlist / digest固定またはscan方針を再設計する。

# 6. 次工程

manual production workflowとGitHub Pages environment gateは`Public_Production_Gate.md`でbuild-only workflowから分離した。匿名合成siteによるA→B→A rollback rehearsal、実データpublic projectionのpush前review・初回input昇格、本workflowのcommit済み実inputへの切替、切替revisionのhosted build、独立environment承認による初回実content deployと公開表示確認まで完了した。通常rollbackの既知正常revisionとtree digestはproduction runbookを正とする。
