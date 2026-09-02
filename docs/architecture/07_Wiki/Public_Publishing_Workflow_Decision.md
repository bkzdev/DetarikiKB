# Public Publishing Workflow Decision（公開基盤・配備判断枠）

Version: 0.1
Status: Proposed
Review date: 2026-09-02
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

public-safeなWiki生成物を将来公開する場合のstatic site generator、hosting、trigger、deploy gate、rollbackを一枚に集約する。本Decisionは推奨案を提示するdocs-only判断枠であり、採択、公開設定追加、実データ生成、hosting account接続、deployを行わない。

---

# 2. 現状と制約

- repositoryはGitHub上のpublic repositoryで、`main`へのpushとPRで既存GitHub Actions CIが動く
- rendererはportableなMarkdownを生成し、theme固有syntaxへ深く依存しない
- local previewはMkDocs 1.6.1 / Material for MkDocs 9.7.6で成功している
- Canonical Timelineは`projection_candidate`のままで、実データ公開承認を得ていない
- PR buildからpublic deployへ直結させず、公開操作は人間判断を必要とする
- 実artifact、private mapping、実データ由来生成物をrepositoryや通常のCI artifactへ混入させない
- public repositoryではbranch push自体が外部公開になるため、実public-safe入力も人間確認前にpushしない
- failure時は現在の公開物を変更せず、既知の正常revisionへ戻せることを受入条件とする

---

# 3. 公式情報の確認結果

2026-09-02時点で次を確認した。

- [GitHub Pages custom workflow](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)はbuild artifactのuploadとdeploy jobを分離でき、`github-pages` environmentと`pages: write` / `id-token: write`を使う
- [GitHub deployment environment](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments)はbranch制限、approval、secret access gateを持てる
- [GitHub Pages limits](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)は公開site 1 GB、deploy 10分、soft bandwidth 100 GB/月等を定める
- [Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/configuration/git-integration/)はbranch previewとGit status checkを提供するが、GitHub Appによる外部account接続が必要である
- [Cloudflare Pages rollback](https://developers.cloudflare.com/pages/configuration/rollbacks/)は成功済みproduction deploymentへの即時rollbackを提供する
- [Cloudflare Pages overview](https://developers.cloudflare.com/pages/)は新規projectにWorkersを主要platformとして案内している
- [Material for MkDocsのMkDocs 2.0評価](https://squidfunk.github.io/mkdocs-material/blog/2026/02/18/mkdocs-2.0/)はMaterialとMkDocs 2.0が非互換で、Material 9.7.5以降がMkDocsを`<2`へ制限したことを説明する
- [Zensical roadmap](https://zensical.org/about/roadmap/)は`mkdocs.yml`とMaterial互換を掲げる一方、現時点ではalphaでfeature parity作業中と明記する

外部serviceの仕様・料金・制限は変更されうるため、実装PR開始時に再確認する。

---

# 4. 判断項目

## P1. 初期hosting

| 候補 | 内容 | 評価 |
|---|---|---|
| A | GitHub Pages custom Actions | repository・CI・deployment履歴をGitHub内に集約でき、外部credential不要。初期限定公開に最小構成 |
| B | Cloudflare Pages Git integration | previewと即時rollbackが強いが、外部GitHub App接続と別dashboard運用が増える |
| C | Cloudflare Workers static assets | Cloudflareの新規推奨経路だが、現段階の純static siteには運用面が過剰 |

**推奨: A。** 現行public repositoryとGitHub Actionsを利用し、まずvendor境界と権限を増やさない。GitHub Pagesの容量・帯域・build時間が実測で不足する、custom domain / CDN要件が具体化する、または即時rollbackの運用価値が再配備方式を明確に上回る場合だけB/Cを再評価する。

## P2. Static site generator

| 候補 | 内容 | 評価 |
|---|---|---|
| A | MkDocs 1.6.1 + Material 9.7.xをlock固定 | 現在の表示・test資産を再利用できるが、長期保守期限が不透明 |
| B | Zensicalへ即移行 | `mkdocs.yml`互換経路があるがalphaで、今回同時採用は変更軸を増やす |
| C | VitePress / Docusaurus / Astro等へ移行 | 長期候補だがNode toolchain・theme・search・link挙動の再検証が必要 |

**推奨: Aを暫定採用し、公開前にBの合成dual-build spikeを必須化する。** `uv.lock`を必ず使い、MkDocs 2へ自動更新しない。Zensicalで既存合成Wikiをbuildし、page数、link、見出し、検索、desktop / 390px表示、内部値露出検査が同等に通る場合は、公開実装前の別DecisionでA継続かB移行を確定する。CはA/Bが要件を満たさない場合のfallbackとする。

## P3. Triggerとenvironment

| 候補 | 内容 |
|---|---|
| A | PR / main pushはbuild-only。production deployは`workflow_dispatch`と明示`source_sha`だけ |
| B | `main` mergeごとに自動production deploy |

**推奨: A。** 初期段階でmergeを公開承認の代用にしない。deploy jobは`github-pages` environmentを使用し、実装時に利用可能ならrequired reviewerと`main` revision制約を設定する。fork PR、任意branch、未指定SHAからproduction artifactを作らない。

## P4. Build / deploy分離

**推奨:** internal情報を扱うtrusted local preparationと、commit済みpublic-safe入力だけを扱うhosted workflowを分離する。

```text
trusted local:
internal artifact + private mapping
  -> generate public projection candidate
  -> complete fail-closed preflight
  -> local visual review
  -> human approval before any push
  -> dedicated content PRでpublic-safe構造化入力だけを昇格

GitHub Actions:
resolve immutable source SHA
  -> load committed public-safe structured input only
  -> public schema / semantic / exposure checks
  -> render public Markdown
  -> schema / semantic / link / exposure checks
  -> mkdocs build --strict
  -> rendered HTML exposure scan
  -> manifest + digest
  -> upload Pages artifact
  -> protected deploy job
```

internal artifact、private mapping、local preflight report、実Wiki Markdown / HTMLをrepositoryや通常artifactへ渡さない。public-safe構造化入力の保存path・review metadata・promotion手順は後続schema PRで固定する。deploy jobは全gate成功時だけ開始し、build途中やwarning付きbest-effort artifactを公開しない。

## P5. 必須deploy gate

最低限、次をすべて満たす。

trusted local promotionでは次の1〜4を満たす。

1. Canonical Timeline internal schema / semantic checkがclean
2. internal input digest pinとprojector outputが一致
3. public preflightが完全な`clean` reportを返す
4. 人間がpublic-safe構造化入力をpush前に確認する

hosted build / deployでは次の5〜12を満たす。

5. `source_sha`が完全なcommit SHAで、許可された`main`履歴へ到達可能
6. dependency installが`uv sync --locked`で再現可能
7. commit済みpublic inputのschema / semantic / review metadataがclean
8. projection / rendererの決定性が一致
9. public ID / label completeness、一意性、link targetがclean
10. MarkdownとHTMLの内部ID、path、raw text、private marker exposureが0
11. `mkdocs build --strict`がMkDocs validation warning 0で成功し、outputがhosting limit内（Materialが出すtoolchain将来互換warningはP2の移行gateで別管理）
12. deployment manifestにsource SHA、lock digest、public input digest、output digest、gate結果を記録

deployment manifestは公開siteへ含める情報とGitHub deployment recordを分離し、internal input digest、private input path、mappingを含めない。internal input digestを持つlocal preflight reportは非commitのまま保持する。

## P6. PR preview

**推奨: 初期版ではpublic PR previewを生成しない。** forkや未採択contentから生成物を外部公開する経路を作らない。通常PRでは合成fixtureだけを使うbuild-only検証に限定する。人間がpush前承認した専用public content PRだけはcommit済みpublic-safe入力を検査するが、site artifactをupload・deployせず、logへlabelや本文を列挙しない。

## P7. Rollback

GitHub Pagesには本Decisionで依存できる「任意の過去deploymentを即時復帰」契約を置かない。代わりに次を採用候補とする。

1. 最終正常deployのsource SHAとmanifest digestをdeployment recordへ保存
2. 障害時はproduction workflowをその既知SHAで手動再実行
3. 同じlock・全gateからsiteを再生成し、output digestを照合
4. protected deploy jobで再配備
5. 現在の不良revisionや過去recordを削除しない

rollback rehearsalは合成contentで初回公開前に行い、正常版A→変更版B→A再配備でURL、digest、表示を確認する。rollback失敗時は新規deployを停止し、hosting切替や履歴削除を自動実行しない。

## P8. Publish authorization

Decision採択、workflow実装、合成rehearsal、実public-safe入力のpush、実データpublishは別gateとする。実装が完成しても`projection_candidate`を自動的に`publish-ready`へ変えない。実contentはpush前に公開対象とlabelを、初回production deploy直前にURLと最終表示を人間が確認する。

---

# 5. 推奨初期profile

```text
P1=A  GitHub Pages custom Actions
P2=A  MkDocs 1.6.1 + Material 9.7.xを暫定lock、Zensical dual-buildを公開前必須
P3=A  build-onlyとmanual production deployを分離
P4    trusted local projection -> 承認済みpublic input -> hosted build -> protected deploy
P5    local internal gateとhosted public gateを分離し、source / public input / output digestを固定
P6    public PR previewなし
P7    既知正常SHAからの検証付き再配備
P8    Decision / implementation / rehearsal / publishを別承認
```

---

# 6. 採択後の段階案

1. Zensical合成dual-build spikeとgenerator継続判断
2. public-safe構造化入力の保存schema、push前review metadata、local promotion手順を合成fixtureで固定
3. deploy前site manifest / exposure scan契約を合成fixtureで実装
4. build-only GitHub Actions workflowを実装
5. manual production workflowとenvironment gateを実装
6. 合成siteでdeploy / rollback rehearsal
7. 実データpublic projectionをignored workspaceで生成し、人間がpush前確認
8. 専用public content PRをmerge後、対象revisionと最終表示を確認して初回production deploy

各段階は小さいPRに分ける。第6段階までは実データや実公開contentを使わず、第7・第8段階は改めて人間判断を求める。

---

# 7. 採択に必要な確認

推奨P1〜P8を一括採択するかを人間が確認する。個別に変更する場合は、hosting、generator、production trigger、rollbackの4項目だけをまとめて再判断する。採択前はworkflow file、GitHub Pages設定、environment、外部service接続を変更しない。

---

# 8. Non-goals

- GitHub Pages / Cloudflare / custom domainの設定変更
- GitHub App導入、Cloudflare account接続、API token作成
- workflow実装、artifact upload、environment作成
- Zensicalその他generatorのdependency追加
- 実public projection / Wiki生成物の作成・commit・upload
- `publish-ready`への状態変更
- deploy、rollback、公開URL作成

---

# 9. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `Canonical_Timeline_Public_Preflight.md`
- `Canonical_Timeline_Public_Renderer.md`
- `Canonical_Timeline_Public_Preview.md`
- `Wiki_Output_Design.md`
- `Story_URL_Structure_Decision.md`
- `../../runbooks/AI_PR_Playbook.md`
