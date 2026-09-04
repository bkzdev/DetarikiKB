# Public Build-Only Workflow

Version: 0.1
Status: Implemented
Updated: 2026-09-04

---

# 1. 目的

`.github/workflows/public-build.yml`は、commit済みの匿名合成public inputだけからpublic-only Markdownを生成し、MkDocs / Zensicalのdual-buildとdetached site manifest / exposure gateを検証する。PRと`main` pushの回帰検査であり、artifact upload、Pages設定、production deploy、公開承認を行わない。

# 2. 固定入力と一時出力

入力は`tests/fixtures/canonical_timeline_public_input/approved_synthetic_input.json`へ固定する。このfixtureはschema-validな`approved_for_build` envelopeだが、匿名合成データだけを含み、実public inputや実データの公開承認を表さない。

`scripts/prepare_public_build.py`はenvelope schema / payload digestとpublic-only semantic gateを検証し、`$RUNNER_TEMP/dkb-public-build`配下へ次を生成する。

- public-only Markdown source（landing、Canonical Timeline、合成Story / Episode stub）
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
2. 合成public inputから一時source / configを準備
3. MkDocs strict build
4. Zensical strict build
5. checked-out 40桁commit SHA、`uv.lock`、合成input、実configを束縛して両siteをscan
6. site外の一時directoryへ各detached manifestをno-clobber作成
7. `scripts/compare_public_site_manifests.py`でsource revision、lock / input digest、HTML route setの一致を確認

theme asset差があるためgenerator間のtree digestやconfig digest一致は要求しない。manifestはCI job内の一時検証物で、artifactとしてuploadしない。

# 5. Security boundary / Non-goals

- `permissions: contents: read`以外を付与しない
- `pull_request_target`や`workflow_dispatch`を使わない
- `actions/upload-artifact`、Pages artifact、deploy actionを使わない
- environment、secret、OIDC、`pages: write`、`id-token: write`を使わない
- `knowledge/public/`の正式保存先や実public inputを読み込まない
- site、manifest、生成Markdown / HTMLをcommitまたは外部公開しない
- `publish-ready`へ変更しない

JS / CSS / source map等のvendor assetは既存site manifest方針どおり全文marker scanを行わない。将来、任意contentをこれらへ埋め込む変更時はasset allowlist / digest固定またはscan方針を再設計する。

# 6. 次工程

次はmanual production workflowとGitHub Pages environment gateを、build-only workflowから分離したPRで実装する。その段階でも合成siteだけを使い、artifact upload / deployの実行とrollback rehearsalはさらに別gateとして扱う。
