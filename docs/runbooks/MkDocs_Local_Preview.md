# MkDocs Local Preview Procedure（MkDocsローカルpreview手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/MkDocs_Local_Preview.md`

---

# 1. 目的

`agents/wiki_generator/`（Wiki renderer、`scripts/render_wiki.py`）が生成したMarkdownを、MkDocs Materialでローカルにプレビューする手順を定義する。

**本手順書はローカルpreview専用である。** GitHub Pages / Cloudflare Pages等への公開設定・deploy workflowは`docs/architecture/07_Wiki/Wiki_Output_Design.md` §16 Non-goalsの通りスコープ外であり、別PR（`public publishing workflow`、同§15項目7）で扱う。

---

# 2. 前提

- `uv sync` 済みであること（`mkdocs-material`は`pyproject.toml`の`dev` dependency groupに含まれており、追加のインストール作業は不要）
- 以下を把握していること
  - `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計、出力ディレクトリ案 §11）
  - `scripts/render_wiki.py`（CLIエントリポイント、`--character-profiles`/`--validate`/`--clean`オプション）
  - `docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`（実データでのWiki render dry-run手順、本手順書はその後段＝MkDocsでの見た目確認のみを扱う）

---

# 3. リポジトリに含まれるもの

- `mkdocs.yml`（リポジトリ直下）: `docs_dir: docs/site_preview`を指す最小設定。`theme.name: material`。
- `docs/site_preview/index.md`: このsite previewの目的・方針を説明する**合成説明ページのみ**。実キャラ名・実プロフィール値・実ストーリー本文・実データ由来の生成Markdownは一切含まない。

`docs/site_preview/`配下は、`docs/examples/wiki_output/`（設計サンプル置き場）と同様、**手書きの合成説明ページ専用**の場所である。`render_wiki.py`の実行結果（合成fixture由来・実データ由来いずれも）をここへコピー・commitしてはならない。

---

# 4. 合成fixtureでrenderして確認する

実際の`render_wiki.py`出力を見たい場合は、まず合成fixtureでローカルに生成する。

```bash
uv run python scripts/render_wiki.py \
    --input tests/fixtures/wiki/synthetic_merged_collection.json \
    --output workspace/wiki_preview/synthetic_mkdocs \
    --character-profiles tests/fixtures/character_profiles/synthetic_character_profiles.yaml \
    --validate \
    --clean
```

生成先`workspace/wiki_preview/synthetic_mkdocs/`は`.gitignore`対象（`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` §7で追加済み）。

---

# 5. 実データでrenderして確認する場合

実データ由来のmerged knowledge collectionがローカルにある場合は、`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`の手順で`workspace/wiki_preview/<RUN_ID>/`へ生成する。本手順書はその出力をMkDocsで見る方法のみを追加する（実データの取り扱いルール自体は同ドキュメント§6・§13にすべて従うこと）。

---

# 6. MkDocsでrenderer出力をpreviewする

**重要**: `mkdocs.yml`の`docs_dir`は`docs/site_preview`固定であり、CLIオプションで`docs_dir`だけを一時的に上書きする機能はMkDocsに無い（`-f/--config-file`で別の設定ファイルを指定するしかない）。そのため、`render_wiki.py`の出力（`workspace/wiki_preview/`配下）を見るには、その出力を指す**一時的な設定ファイル**をローカルに作る。

```bash
# 一時設定ファイルをworkspace配下に作る (commitしない、workspace/wiki_preview/配下はignore対象)
cat > workspace/wiki_preview/mkdocs.local.yml <<'YAML'
site_name: Detariki Knowledge Base (local preview)
docs_dir: synthetic_mkdocs
theme:
  name: material
YAML

# workspace/wiki_preview/mkdocs.local.yml から見て
# docs_dir: synthetic_mkdocs は workspace/wiki_preview/synthetic_mkdocs/ を指す
uv run mkdocs serve -f workspace/wiki_preview/mkdocs.local.yml
```

`docs_dir`はこの一時設定ファイル自身からの相対パスとして解決される。実データ出力（`workspace/wiki_preview/<RUN_ID>/`）を見る場合は`docs_dir: <RUN_ID>`に置き換える。

`mkdocs serve`はブラウザで`http://127.0.0.1:8000/`を開けばよい（`-a`でアドレス変更可）。終了は`Ctrl+C`。

commit対象の`mkdocs.yml`（`docs/site_preview/`向け）を確認したいだけの場合は、設定ファイルを省略してよい。

```bash
uv run mkdocs serve
```

---

# 7. commit禁止対象（最重要）

`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` §6の既存ルールに加え、本手順書固有のものを以下に列挙する。

- `workspace/wiki_preview/`配下の生成Markdown全般（合成fixture由来・実データ由来いずれも）
- `workspace/wiki_preview/mkdocs.local.yml`等、一時的に作ったローカル専用MkDocs設定ファイル
- `mkdocs build`のデフォルト出力先`site/`（本PRで`.gitignore`に追加済み）
- `docs/site_preview/`配下への、実データ由来・render_wiki.py出力由来のファイル追加
- GitHub Pages / Cloudflare Pages向けのdeploy workflow設定（本PRでは未実装）

---

# 8. よくある失敗

| 症状 | 想定される原因 | 対応 |
|---|---|---|
| `mkdocs serve`が`docs/site_preview/index.md`しか表示しない | `-f`で一時設定ファイルを指定し忘れている | §6の手順通り`-f workspace/wiki_preview/mkdocs.local.yml`を指定する |
| `Config value 'docs_dir'... does not exist` | 一時設定ファイルの`docs_dir`パスが、その設定ファイル自身からの相対パスになっていない | 一時設定ファイルを`workspace/wiki_preview/`直下に置き、`docs_dir`は`<RUN_ID>`のような同階層の相対名にする |
| `mkdocs build --strict`が警告で失敗する | Markdown内の壊れたリンク（存在しないファイルへの相対リンク等） | エラーメッセージのファイル名を確認し、renderer側のリンク生成ロジック（`agents/wiki_generator/renderer.py`）かfixtureを確認する |
| ブラウザで文字化けする | ブラウザの文字コード判定の問題（MkDocsは既定でUTF-8出力） | ブラウザの文字コード設定を確認する。`render_wiki.py`側の出力はすべてUTF-8固定 |

---

# 9. 次にやること

- `real data local render dry-run`（`Wiki_Output_Design.md` §15項目6）: 実データ由来merged knowledge collectionから実際にレンダリングし、本手順書でpreviewする
- `public publishing workflow`（同§15項目7）: GitHub Pages / Cloudflare Pages等への公開ワークフロー設計・実装（本PRでは未着手）
- Location/Organization/Item/Lore/Event page・Relationship section・Timeline page等Phase 2以降のページ種別が実装された場合、`docs/site_preview/index.md`の関連ドキュメント一覧を更新する

---

# 10. 関連ドキュメント

- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計、§11出力ディレクトリ案・§15実装PR案項目5）
- `docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`（実データでのWiki render dry-run手順、本手順書の前段）
- `docs/site_preview/index.md`（本PRで追加したsite previewのトップページ）
