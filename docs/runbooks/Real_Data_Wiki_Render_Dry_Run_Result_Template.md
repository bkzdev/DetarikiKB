# Real Data Wiki Render Dry-Run 結果記録テンプレート

Path: `docs/runbooks/Real_Data_Wiki_Render_Dry_Run_Result_Template.md`

このテンプレートは`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`の手順で実データWiki render dry-runを実施した際の結果を記録するためのものである。

**記録時の注意（`Real_Data_Wiki_Render_Dry_Run.md` §11参照）**: 生成Markdown全文・実セリフ・実ストーリー本文・実データmerged collection自体・ローカル絶対パス・大量のキャラクター名一覧は記録しない。数値は抽象化して記録する（例: `character pages generated: 2`）。

---

## Run 1

- **Run ID**: `<YYYYMMDD_HHMMSS>`
- **Input merged collection path**: `<ローカルディレクトリの種類のみ。絶対パスは書かない>`（例: `workspace/dry_runs/<RUN_ID>/merged_knowledge_collection.json`）
- **Output directory**: `<例: workspace/wiki_preview/<RUN_ID>/>`（commitしていないことを確認）
- **Renderer command**:
  ```bash
  uv run python scripts/render_wiki.py --input <...> --output <...> --validate --clean
  ```
- **Schema validation result**: `<OK / NG（NGの場合はエラーのJSON Pathのみ記録、内容は書かない）>`
- **Generated file counts**: `<合計件数>`
- **Generated page examples**: `<index.md / stories/index.md / reports/unresolved.md 等、ページ種別の一覧のみ。個別ファイル名（実データ由来のepisodeId等）は書かない>`
- **Character pages count**: `<件数>`
- **Episode pages count**: `<件数>`
- **Unresolved report presence**: `<生成された/されなかった>`
- **Unresolved counts summary**: `<例: characters 10+, locations 3, relationships 0 のような抽象化した件数>`
- **Conflict summary**: `<例: total 2 件>`
- **Warning summary**: `<例: total 1 件>`
- **Canonical ID summary**: `<例: totalAssigned 5, invalidCount 0（reportに存在しない場合は「report.canonicalIdSummaryなし」と記録）>`
- **Relationship type summary**: `<例: unknownTypes 2 種（reportに存在しない場合は「report.relationshipTypeSummaryなし」と記録）>`
- **Errors**: `<rendererが出したエラーの一般的な種別・関数名のみ。実データ内容は書かない>`
- **Warnings**: `<同上>`
- **Findings**: `<dry-runで見つかった一般的な問題点。例: 「sourceDocumentsが空の場合でもクラッシュしないことを確認」「長いwarningメッセージがtruncateされることを確認」>`
- **Follow-up tasks**: `<次に対応すべきこと>`
- **Confirmation that no generated output was committed**: `<git status --short で workspace/wiki_preview 等が出ていないことを確認済み / 確認方法>`

---

## 記録例（2026-07-04、実データmerged collectionがローカルに存在しなかったケース）

- **Run ID**: N/A（実データrender dry-run未実行）
- **Input merged collection path**: N/A
- **Output directory**: N/A
- **Renderer command**: N/A
- **Schema validation result**: N/A
- **Generated file counts**: N/A
- **Generated page examples**: N/A
- **Character pages count**: N/A
- **Episode pages count**: N/A
- **Unresolved report presence**: N/A
- **Unresolved counts summary**: N/A
- **Conflict summary**: N/A
- **Warning summary**: N/A
- **Canonical ID summary**: N/A
- **Relationship type summary**: N/A
- **Errors**: N/A
- **Warnings**: N/A
- **Findings**: 実データ由来のmerged knowledge collection（`merged_knowledge_collection.json`）がローカル環境に存在しなかったため、実データでのWiki render dry-runは実施しなかった（`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` §8「実データが無い場合の代替確認」に従う）。代わりに以下を実施した:
  - `tests/fixtures/wiki/synthetic_merged_collection.json`（既存の合成fixture）を入力に`scripts/render_wiki.py --validate --clean`を実行し、exit code 0・schema検証OK・`index.md`/`stories/index.md`/`stories/*.md`（2件）/`characters/*.md`（1件、`CHAR_TEST_RAIN`）/`reports/unresolved.md`が生成されることを確認した
  - `sourceDocuments`が空配列・`report.canonicalIdSummary`/`report.relationshipTypeSummary`が存在しない・entityの`displayName`等の任意フィールドが欠落した合成の縮退collection（一時ファイル、コミットせず）を作成し、rendererがクラッシュせずexit code 0で完了することを確認した
  - この縮退collectionの確認で、`report.warnings`の1件が長文（197文字）だった際に切り詰められず全文表示されることに気づき、`_truncate_message`（`agents/wiki_generator/renderer.py`、200文字超で末尾に`...(省略)`を付けて切り詰め）を追加した。他の項目（optional field欠落・None値・空配列・candidateCounts欠落・sourceDocuments空）はすべて既存実装で問題なく動作した
- **Follow-up tasks**: 実データ由来のmerged knowledge collectionが用意できた際に、本テンプレートで改めてRun記録を追加する
- **Confirmation that no generated output was committed**: `git status --short`で`workspace/wiki_preview/`配下の出力が一切追跡対象になっていないことを確認済み
