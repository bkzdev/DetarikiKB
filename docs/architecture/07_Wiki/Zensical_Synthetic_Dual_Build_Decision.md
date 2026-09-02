# Zensical Synthetic Dual-Build Decision

Version: 0.2
Status: Accepted
Decision date: 2026-09-02
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

`Public_Publishing_Workflow_Decision.md`で採択したP2の移行gateとして、同じ匿名合成WikiをMkDocs / MaterialとZensicalでbuildし、公開実装へ進むgeneratorを確定する。本Decisionはgenerator実装方針だけを決める。dependency、標準build、workflow、GitHub Pages、実content、`publish-ready`、deployは変更しない。

---

# 2. 公式情報の再確認

2026-09-02に公式一次情報を再確認した。

- [PyPI Zensical 0.0.57](https://pypi.org/project/zensical/0.0.57/)は2026-08-21公開の確認時点最新package versionであり、source repositoryにも[Zensical v0.0.57 tag](https://github.com/zensical/zensical/tree/v0.0.57)が存在する
- [Get started](https://zensical.org/docs/get-started/)はPython仮想環境と`pip`または`uv`での導入を案内する。uv symlink modeは現時点で非対応である
- [Compatibility](https://zensical.org/compatibility/)と[Configuration](https://zensical.org/compatibility/configuration/)は既存`mkdocs.yml`、Markdown、URL / anchor、CSS / JavaScriptの互換経路を示す
- [Build](https://zensical.org/docs/usage/build/)は`zensical build -f <config> --clean --strict`を提供する
- [Feature parity](https://zensical.org/compatibility/features/)ではsearch、explicit navigation、directory URL、link validation、strict modeを対応済みとする
- [FAQ](https://zensical.org/docs/community/faqs/)は必要featureが実装済みならproduction利用可能とする一方、0.0.xの理由をAPIの大きな変更と説明し、1.0の予定日は示していない
- [CLI compatibility](https://zensical.org/compatibility/cli/)では`--site-dir`や`gh-deploy`等の未対応optionがあり、MkDocs plugin互換も段階的である

Zensicalの0.0.x状態とmodule / plugin互換の進行中というリスクは残るため、採用時もversionを完全固定し、upgradeを明示的な互換検証なしで行わない。

---

# 3. Spike条件

## 3.1 入力

- `tests/fixtures/wiki/synthetic_merged_collection.json`
- 合成character profile、Story Summary、Evidence Index fixture
- `canonical_timeline_public_projection`の有効な合成fixtureからrendererで生成した`timelines/index.md`
- Timeline link先となる4つの合成placeholder page

実データ、実タイトル、実URL、internal artifact、private mappingは使わない。Markdown、config、HTML、比較結果は`workspace/wiki_preview/zensical_dual_build/`だけへ生成し、commitしない。

## 3.2 固定versionと実行

```powershell
uv run mkdocs build --strict --clean -f workspace/wiki_preview/zensical_dual_build/mkdocs.synthetic.yml
uvx --from "zensical==0.0.57" zensical build --strict --clean -f workspace/wiki_preview/zensical_dual_build/zensical.synthetic.yml
```

MkDocs baselineはlock済みのMkDocs 1.6.1 / Material 9.7.6を使った。Zensical側は同じdocs / nav / search / directory URL設定を読み、出力先だけを分離し、Material相当の比較用に`theme.variant: classic`を指定した。`uvx`の隔離環境を使い、`pyproject.toml`と`uv.lock`は変更していない。

---

# 4. 結果

| 検査 | MkDocs / Material | Zensical 0.0.57 | 判定 |
|---|---:|---:|---|
| strict build | exit 0 | exit 0、issue 0 | PASS |
| 入力Markdown page | 24 | 24 | PASS |
| HTML route（404を含む） | 25 | 25 | PASS |
| route差分 | - | 0 | PASS |
| h1〜h6見出し | 119 | 119 | PASS |
| search index entry | 118 | 118 | PASS |
| search UIを持つHTML | 25 | 25 | PASS |
| Canonical Timeline内部link | clean | clean | PASS |
| Timeline禁止marker露出 | 0 | 0 | PASS |

禁止markerは`storyId`、`episodeId`、`candidateId`、`evidenceIds`、`humanDecision`、内部component key、ローカル絶対path、`.dec`を対象に、両方のTimeline HTMLで0件を確認した。searchは両方で合成Story titleを入力し、Story / Episode / Evidence / indexを横断する結果が表示されることを確認した。

## 4.1 Visual check

- desktop 1280×720: header、navigation、本文、table、目次、search UIを表示できた
- mobile 390×844: HomeとCanonical Timelineの双方でviewport幅375pxに対してscroll幅375px、横overflow 0だった
- Canonical TimelineのStory / Episode link、関係文、unknown / conflict aggregateは欠落しなかった
- Zensical classicとMaterialの主要layoutは同等だった。product footerと目次label（`On this page` / `Table of contents`）にはgenerator固有の差があるが、情報欠落や導線不良ではない

画面確認はlocalhostから行った。スクリーンショットとsite出力は検証用生成物であり非commitとする。

---

# 5. Decision

**公開実装へ進むgeneratorはZensical（B）とする。** 今回の要件であるportable Markdown、explicit nav、directory URL、search、link validation、strict build、desktop / 390px表示がすべて合成検証を通り、route・見出し・search entryもbaselineと一致した。現在のprojectはthird-party MkDocs pluginやtemplate overrideに依存しておらず、既知の互換gapへ触れない。

次のimplementation PRではZensical 0.0.57をexact pinし、合成buildを標準化する。移行完了までは既存MkDocs / Material buildをbaselineとして残し、両方が通る状態で切替を検証する。Zensical upgradeはversionごとにこの受入観点を再実行する。

2026-09-02に後続実装を完了した。`pyproject.toml` / `uv.lock`でZensical 0.0.57をexact pinし、`zensical.yml`と`Wiki_Dual_Build.md`を追加した。既存CIと標準検証はcommit済み合成`docs/site_preview/`をMkDocs / MaterialとZensicalの両方でstrict buildする。MkDocs baselineは維持し、両generatorの生成HTMLはcommitしない。

このDecisionはgenerator実装へ進む技術判断であり、実public-safe入力のpush、公開範囲、公開URL、production deployを承認しない。`projection_candidate`も維持する。

---

# 6. 残余リスクと停止条件

- 0.0.xではAPI変更が続くためexact pinを外さない
- third-party plugin、template override、absolute link等を導入する場合は互換性を再評価する
- strict build、route、見出し、search、link、露出、mobile表示のいずれかが退行した場合はZensical標準化を停止し、MkDocs baselineを維持する
- build結果の一致は公開内容の承認を意味しない。実contentは別のpush前review gateを必要とする

---

# 7. Non-goals

- spike時点で未実施だったZensical dependency追加・`uv.lock`更新・CI dual-build化は後続実装で完了
- `mkdocs.yml`の削除、MkDocs / Material baselineの廃止
- GitHub Pages / environment / artifact uploadの設定
- 実データ、実public-safe入力、実Wiki Markdown / HTMLの生成・commit・push
- `publish-ready`化、deploy、rollback rehearsal

---

# 8. 関連文書

- `Public_Publishing_Workflow_Decision.md`
- `Canonical_Timeline_Public_Preview.md`
- `Canonical_Timeline_Public_Renderer.md`
- `../../runbooks/AI_PR_Playbook.md`
- `../../runbooks/Wiki_Dual_Build.md`
