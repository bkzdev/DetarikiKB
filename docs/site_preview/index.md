# Detariki Knowledge Base — Wiki Site Preview

このsite previewは、`agents/wiki_generator/`（Wiki renderer）が生成したMarkdownを
MkDocs Materialでローカル確認するための最小構成です。

## これは何か

- **Source of Truthはmerged knowledge collection**（`schemas/merged_knowledge_collection.schema.json`）であり、Wikiページはそこから`scripts/render_wiki.py`が生成する派生物です。
- この`docs/site_preview/`配下は、合成fixture（`tests/fixtures/wiki/synthetic_merged_collection.json`等）由来の説明ページのみを置く場所です。
- **実データ由来のgenerated pagesはこのディレクトリにcommitしません。** 実データ・合成データいずれの`render_wiki.py`出力も、ローカルpreview先は常に`workspace/wiki_preview/`配下（`.gitignore`対象）です。
- GitHub Pages / Cloudflare Pages等の公開設定は、このPRではまだ実装していません（`docs/architecture/07_Wiki/Wiki_Output_Design.md` §16 Non-goals）。

## ローカルでrenderer出力をpreviewする

実際に生成したWiki Markdown（合成fixture由来・実データ由来いずれも）をMkDocsで
プレビューする手順は `docs/runbooks/MkDocs_Local_Preview.md` を参照してください。

## 関連ドキュメント

- `docs/architecture/07_Wiki/Wiki_Output_Design.md` — Wiki出力設計
- `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md` — 公式プロフィール辞書の設計
- `docs/runbooks/MkDocs_Local_Preview.md` — MkDocsローカルpreview手順
- `docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` — 実データでのWiki render dry-run手順
