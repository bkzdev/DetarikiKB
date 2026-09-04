# Wiki Dual-Build

Version: 0.1
Status: Active
Updated: 2026-09-02

---

# 1. 目的

公開Wiki generatorをZensicalへ段階移行する間、同じcommit済み合成previewをMkDocs / MaterialとZensicalでstrict buildし、設定やMarkdownの互換性退行を検出する。Zensicalを移行先、MkDocs / Materialを比較baselineとする。

この手順はbuild互換性の確認だけを扱う。実データ、public-safe入力の昇格、`publish-ready`判定、GitHub Pages artifact、production deployは扱わない。

---

# 2. 固定構成

- Zensical: `pyproject.toml`のdev dependencyで`zensical==0.0.57`へexact pinする
- Zensical config: `zensical.yml`
- MkDocs baseline config: `mkdocs.yml`
- 共通入力: `docs/site_preview/`（commit可能な合成・説明用ページだけ）
- MkDocs出力: `site/`（ignore対象）
- Zensical出力: `site_zensical/`（ignore対象）

`uv.lock`を必ず使用し、Zensicalのversionを暗黙更新しない。version更新PRではdual-build、検索、link、desktop / mobile表示、内部値露出を再確認する。

---

# 3. 標準コマンド

repository rootで実行する。

```powershell
uv sync --locked
uv run mkdocs build --strict
uv run zensical build --strict --clean -f zensical.yml
```

両方がexit 0で完了することを必須とする。Zensicalはwarningを成功扱いにせず、strict modeのissueを解消する。片方だけ失敗した場合はgenerator切替を進めず、MkDocs baselineを維持する。

---

# 4. CI

`.github/workflows/ci.yml`は通常のテスト・lint後に両buildを実行する。PRと`main` pushの双方でdual-buildが成功しなければならない。Zensical出力は検証用であり、artifact uploadやdeployには使用しない。

---

# 5. Commit境界

commitしてよいもの:

- `mkdocs.yml` / `zensical.yml`
- `docs/site_preview/`の合成・説明用source
- dual-buildを固定するtests / docs / workflow

commitしないもの:

- `site/` / `site_zensical/`の生成HTML
- `workspace/wiki_preview/`配下のpreviewと一時config
- 実データ由来Markdown / HTML
- internal artifact、private mapping、実public-safe入力

---

# 6. Site manifest / exposure gate

dual-build標準化後のpublic-safe構造化入力schema、push前review metadata、local promotionは`Canonical_Timeline_Public_Input_Promotion.md`で実装済みである。deploy前site manifest / rendered HTML exposure scanは`Public_Site_Manifest_Exposure_Scan.md`で契約化した。

後続build-only workflowではMkDocs / Zensicalの出力を別々の一時directoryへ生成し、同じ`check_public_site_manifest.py`を各siteへ適用する。theme asset差があるためtree digestの完全一致は要求せず、共通route set、exposure 0、public input / lock digest一致を要求する。manifestはsite tree外のCI一時directoryへdetached出力し、通常PRではartifact uploadしない。

次はbuild-only public workflowへの統合である。Pages設定、artifact upload、production deployへはこの手順だけでは進まない。
