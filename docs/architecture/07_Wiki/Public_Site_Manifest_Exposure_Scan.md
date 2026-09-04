# Public Site Manifest / Exposure Scan

Version: 0.1
Status: Implemented
Updated: 2026-09-04

---

# 1. 目的

commit済みpublic-safe入力から生成したstatic siteをdeploy候補に渡す前に、site treeの完全なfile inventoryとdigestを固定し、rendered HTML / public data assetの内部情報露出が0であることをfail-closedに検査する。

本契約の`verified_build_candidate`はbuild gate通過だけを示す。manifestは`deploymentAuthorized: false`を固定し、`publish-ready`、production deploy承認、公開済み状態を表さない。

---

# 2. 構成

- schema: `schemas/public_site_manifest.schema.json`
- pure builder / validator: `agents/wiki_generator/public_site_manifest.py`
- CLI: `scripts/check_public_site_manifest.py`
- scan policy version: `0.1`
- manifest: site treeへ含めないdetached JSON

manifestには次を保持する。

- Gitの完全な40桁source revision（algorithmを`sha1`として明示）
- `uv.lock`、public input raw bytes、generator configのSHA-256
- generator name / version（versionは英数字開始の英数字・`.`・`+`・`_`・`-`だけ）
- public input / site tree / rendered exposureの固定`clean` gate
- bytewise path順の全file inventory、file SHA-256、size、media type、scan profile
- HTML route一覧、file / HTML / scan対象件数、総bytes
- canonical file inventoryのSHA-256である`treeSha256`

manifest自身はtree digestへ含めず、循環参照を避ける。reviewer、private mapping、internal input digest、local path、検出値、HTML断片は保持しない。

---

# 3. Site tree gate

scan対象rootは通常directoryでなければならない。再帰走査ではsymlink、reparse相当entry、FIFO / device等の非regular file、未知拡張子、case-fold path衝突、読込中のidentity / size / mtime変化をblockingにする。

全fileはraw bytesでdigest化する。`index.html`とroute `/`を必須とし、総bytesはGitHub Pagesの1 GB境界を超えてはならない。許可する初期file種別はHTML、CSS、JS、JSON、XML、source map、font、PNG / SVG / icon、gzip、Sphinx inventory、text、web manifestである。新しい生成形式は暗黙許可せずpolicy更新で追加する。

file pathはsite root相対のPOSIX表記へ正規化し、UTF-8 byte順で固定する。MkDocs / MaterialとZensicalはtheme assetが異なるため、両manifestの`treeSha256`完全一致は要求しない。共通HTML route、scan clean、public input / lock digestの一致を比較対象とする。

---

# 4. Rendered exposure gate

scan profileは次の3種である。

| profile | 対象 | 処理 |
|---|---|---|
| `html` | 全`.html` | raw source、可視text、comment、属性値、タグ間を連結したtextをscan |
| `public-data` | JSON / source map、SVG、text、XML、web manifest（`search/search_index.json` / sitemapを含む） | UTF-8全文をscan |
| `binary-asset` | theme JS / CSS、font、画像、gzip等 | bytes / path / typeをmanifest化し、固定marker全文scanはしない |

文字列はHTML entityとURL encodingを2回decodeし、Unicode NFKC、slash、lowercaseを正規化し、Unicode format characterを除く。これによりentity、percent encode、全角化、ゼロ幅文字、`sto<span>ryId</span>`のようなnode分割による単純な回避を拒否する。

JSON / source map / web manifestはraw UTF-8に加えてJSON parse後のkey / valueもscanし、`\uXXXX` escapeによる回避を拒否する。不正JSONは`public-data-json-invalid`でblockingにする。全site相対file pathも同じmarker ruleでscanするため、内部field名やlocal pathをfile path / HTML routeへ移してmanifestに露出させることはできない。

初期blocking rule:

- internal field marker: `storyId`、`episodeId`、`documentId`、`blockId`、`sceneId`、`candidateId`、`evidenceId(s)`、`humanDecision`、`sourceFile`、`sourceKey`、`rawText`、`extractionRun`
- private marker: `local_internal`、`internal_only`、`commitAllowed`、`preflightInputDigests`、`internalDocument`、`reviewerName`
- raw script marker: `.dec` file、`@ChTalk*`、`@ScenarioCos*`、`$numN`
- local path marker: `file://`、drive absolute path、`/home/`、`/Users/`、`/workspace/`、`/tmp/`、`data/raw/`
- 64桁hex digest marker

field markerはidentifier境界を要求するため、許可済みの`publicStoryId` / `publicEpisodeId`を部分一致でblockingにしない。`<script>`要素自体もgeneratorの正常出力なので禁止しない。vendor JS / CSSを固定markerで全文scanせず、検索可能・閲覧可能なHTML / search dataを必須scanする。

finding時はmanifestを成功成果物として生成せず、CLIは`status=blocked code=<anonymous-code>`だけを出す。検出値、file path、HTML断片はlogへ出さない。

---

# 5. CLI

既定はdry-runで、siteやmanifestを書き換えない。

```powershell
uv run python scripts/check_public_site_manifest.py `
  --site-dir <generated-site-dir> `
  --public-input knowledge/public/timelines/canonical_timeline_public_input.json `
  --source-sha <40-lowercase-hex> `
  --lock-file uv.lock `
  --generator-name zensical `
  --generator-version 0.0.57 `
  --config zensical.yml
```

detached manifestをCIの一時directoryへ新規作成する場合だけ、`--manifest-output <outside-site-path> --write-manifest`を同時指定する。既存fileは上書きせず、site root内へのmanifest作成を拒否する。親directoryをdirectory descriptorで固定し、相対`open` / `stat` / `unlink`を安全に実行できないplatformでは、明示出力を`manifest-output-secure-write-unavailable`でfail-closedに拒否する（dry-runは利用可能）。

---

# 6. 公開境界とNon-goals

このPRは合成site treeだけで契約を実装する。`site/`、`site_zensical/`、実HTML、実manifest、実public inputをcommit / uploadしない。

対象外:

- build-only GitHub Actions workflowへの統合
- Pages artifact upload、environment、permission、production deploy
- rollback rehearsal、既知正常SHA再配備
- 実public input昇格、`publish-ready`化、公開URL作成
- MkDocs / Zensicalのtheme asset / HTML bytes完全一致
- internal artifact、private mapping、local preflightをhosted buildへ渡すこと

次は本契約をcommit済み合成input / siteだけを扱うbuild-only workflowへ統合する。
