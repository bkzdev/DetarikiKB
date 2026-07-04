# Real Data Wiki Render Dry-Run Procedure（実データWikiレンダリングdry-run手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`

---

# 1. 目的

ローカルに存在する実データ由来のmerged knowledge collection（`schemas/merged_knowledge_collection.schema.json`準拠、`scripts/merge_extractions.py`の出力）を入力に、`agents/wiki_generator/`のrenderer（`scripts/render_wiki.py`）が壊れずにWiki Markdown一式を生成できるかをローカル環境だけで確認する手順を定義する。

`docs/runbooks/Real_Data_Dry_Run.md`が Parser → Extractor → Merger までのdry-runを扱うのに対し、本ドキュメントはその後段（Merger出力 → Wiki Markdown）のみを対象とする。

**実データ由来Wikiページ・生成Markdown・merged collection本体は一切Gitにcommitしない。** このdocumentはあくまで「ローカルのignored領域でどう試すか」の手順書である。

---

# 2. 前提

- `uv sync` 済みであること
- `docs/runbooks/Real_Data_Dry_Run.md`の手順で、ローカルに実データ由来のmerged knowledge collection（`merged_knowledge_collection.json`）が既に生成済みであること。**本手順書はmerged collectionの生成自体は扱わない**（Parser/Extractor/Merger dry-runは`Real_Data_Dry_Run.md`を参照）
- 以下を把握していること
  - `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計、ページ種別・front matter方針・evidenceRefs表示方針）
  - `agents/wiki_generator/`（`renderer.py`/`paths.py`/`models.py`）
  - `scripts/render_wiki.py`（CLIエントリポイント）

merged collectionがローカルに無い場合は、無理に生成しない。`tests/fixtures/wiki/synthetic_merged_collection.json`（合成fixture）でrendererの動作確認を代替する（§8参照）。

---

# 3. 入力ファイルの想定

- パス例: `workspace/dry_runs/<RUN_ID>/merged_knowledge_collection.json`（`Real_Data_Dry_Run.md` §10の出力そのまま）
- 形式: `schemas/merged_knowledge_collection.schema.json`準拠のJSON
- このファイル自体はGit管理対象外（`.gitignore`の`workspace/dry_runs/`で保護済み）

---

# 4. 出力先の想定

- パス例: `workspace/wiki_preview/<RUN_ID>/`
- `workspace/wiki_preview/`は本PRで`.gitignore`に追加した専用ignore対象ディレクトリ（§6参照）
- 出力先ディレクトリ名にRUN_IDを含めることで、複数回のdry-runを時系列で見分けられるようにする（`Real_Data_Dry_Run.md`の`workspace/dry_runs/<timestamp>/`と同じ命名方針、`YYYYMMDD_HHMMSS`推奨）

---

# 5. 実行コマンド例

```bash
# schema検証込みで生成（推奨）
uv run python scripts/render_wiki.py \
    --input workspace/dry_runs/<RUN_ID>/merged_knowledge_collection.json \
    --output workspace/wiki_preview/<RUN_ID> \
    --validate \
    --clean
```

実際のパスはローカル環境に合わせること（`<RUN_ID>`は`Real_Data_Dry_Run.md`で使ったdry-run実行のタイムスタンプに揃えると、どのmerge結果から生成したWikiかを追跡しやすい）。

生成後、目視確認は以下のように行う（本文をそのままターミナルに大量出力しないよう、ページ単位・grepで部分確認することを推奨）。

```bash
# 生成ファイル一覧
find workspace/wiki_preview/<RUN_ID> -type f

# 個別ページの確認 (ローカルのエディタ・catで直接読む。commitはしない)
cat workspace/wiki_preview/<RUN_ID>/index.md
cat workspace/wiki_preview/<RUN_ID>/reports/unresolved.md
```

---

# 6. commit禁止対象（最重要）

以下は`docs/runbooks/Real_Data_Dry_Run.md` §3・`TASKS.md` §5の既存ルールを、Wiki render dry-runの文脈で再掲する。

- 実データ由来Wikiページ・生成Markdown（`workspace/wiki_preview/`配下すべて）
- 実データ由来merged knowledge collection本体（`merged_knowledge_collection.json`）
- `data/raw/` `data/normalized/` `data/extracted/` `data/reports/` 配下の生成物
- `workspace/dry_runs/` 配下の出力
- `site_src/`（将来MkDocs導入時の想定ソースディレクトリ、本PR時点では未使用）
- `.env`・APIキー・ログファイル

本PRで`.gitignore`に`workspace/wiki_preview/`・`workspace/wiki_render/`・`site_src/`・`docs/wiki_generated/`・`generated/wiki/`を追加済み（§7参照。既にカバーされている場合は追加不要）。ただし`.gitignore`は「うっかりaddしてしまう」ことへの保険であり、`git add -f`等での意図的な追加までは防げないため、dry-run後は必ず§13のチェックリストで確認すること。

---

# 7. .gitignoreの確認

このPRで以下を`.gitignore`に追加・確認した。

| パターン | 対象 | 状態 |
|---|---|---|
| `workspace/wiki_preview/` | Wiki render dry-run出力一式 | **今回追加** |
| `workspace/wiki_render/` | 別名で出力した場合の予備パターン | **今回追加** |
| `site_src/` | 将来MkDocs導入時のソースディレクトリ（未使用だが先回りしてignore） | **今回追加** |
| `docs/wiki_generated/` | 将来docs配下に生成する場合の予備パターン | **今回追加** |
| `generated/wiki/` | 将来のWiki生成物専用ディレクトリの予備パターン | **今回追加** |

確認コマンド:

```bash
git check-ignore -v workspace/wiki_preview/20260704_000000/index.md
```

---

# 8. 実データが無い場合の代替確認

ローカルに実データ由来のmerged knowledge collectionが無い場合、無理に生成しない。代わりに以下で代替する。

```bash
uv run python scripts/render_wiki.py \
    --input tests/fixtures/wiki/synthetic_merged_collection.json \
    --output workspace/wiki_preview/synthetic_check \
    --validate \
    --clean
```

これは合成データのみを使うため出力自体は`tests/fixtures/`由来であり、commit可否の判断は不要（そもそも実データではない）。ただし出力先の`workspace/wiki_preview/synthetic_check/`自体はこの手順書のcommit禁止ルール（§6）に従いcommitしない（`.gitignore`で保護済み）。

---

# 9. 確認項目

生成後、以下を確認する。

- [ ] `scripts/render_wiki.py`がexit code `0`で完了する
- [ ] `--validate`指定時、schema検証が通る（`[wiki] schema検証: OK`）
- [ ] `index.md`が生成される
- [ ] `stories/index.md`が生成される
- [ ] `stories/{episodeId}.md`が入力の`sourceDocuments`件数分生成される
- [ ] `characters/{canonicalId}.md`が、canonicalIdが確定し`status: merged`のcharacterの件数分だけ生成される（canonicalIdなし・status不一致のcharacterは個別ページ化されていないこと）
- [ ] `reports/unresolved.md`が生成される
- [ ] 生成された各ページに元セリフ全文・実本文（`textExcerpt`相当）が出力されていない
- [ ] `stories/*.md`のfront matterに`source_path`（ローカルファイルパス）が含まれていない（本文Summary表のみに表示される設計、`Wiki_Output_Design.md` §9.3参照）
- [ ] `reports/unresolved.md`にOverview・entity種別別section・Conflict Summary・Warning Summaryが表示される
- [ ] `report.canonicalIdSummary`/`report.relationshipTypeSummary`が入力に存在する場合はCanonical ID Summary/Relationship Type Summaryセクションが表示され、存在しない場合はセクション自体が省略される

---

# 10. よくある失敗

| 症状 | 想定される原因 | 対応 |
|---|---|---|
| `[エラー] 入力ファイルが見つかりません` | `--input`のパスが誤っている、またはmerge dry-run（`Real_Data_Dry_Run.md` §10）が未実行 | パスを確認、必要なら先にmerge dry-runを実行 |
| `[エラー] JSONとして読み込めませんでした` | merge dry-runが途中で失敗し不完全なJSONが出力されている | `merge_extractions.py`の実行ログ・exit codeを確認 |
| `--validate`でschema検証エラー | merge engine出力が`merged_knowledge_collection.schema.json`と不一致（実装バグの可能性） | エラーメッセージのJSON Pathを確認し、`agents/merger/`側の該当entity typeを疑う |
| `characters/*.md`が想定より少ない/多い | `is_page_eligible`の判定基準（canonicalId確定 + `status: merged`）を誤解している | `reports/unresolved.md`で対象外になったcharacterの理由（Status/Canonical ID列）を確認する |
| Windowsコンソールで文字化け・`UnicodeEncodeError` | cp932コンソールでの絵文字/一部Unicode出力（`Real_Data_Dry_Run.md` §17参照） | `render_wiki.py`自体は絵文字を出力しないため通常発生しないが、発生した場合は出力をリダイレクトして確認する |
| `stories/*.md`が0件 | 入力の`sourceDocuments`が空配列 | merge dry-run側の入力（`data/extracted/`配下）が空でないか確認 |

---

# 11. 結果記録方法

実施結果は`docs/runbooks/Real_Data_Wiki_Render_Dry_Run_Result_Template.md`のテンプレートに沿って記録する。

**記録してよいもの**: 生成ファイル数、ページ種別ごとの件数、unresolved件数・conflict件数・warning件数などの集計値、rendererが落ちた場合の一般的な問題点（スタックトレースの関数名・原因種別）、follow-up task。

**記録してはいけないもの**: 生成Markdown全文、実セリフ・実ストーリー本文、実データmerged collection自体、ローカル絶対パス、大量のキャラクター名一覧、`data/raw`等の内容。数値は抽象化して記録する（例: `character pages generated: 2`のように件数のみ）。

---

# 12. 次にやること

- rendererがdry-runで見つけたバグを修正した場合は、必ず`tests/fixtures/wiki/`の合成fixtureで回帰テストを追加する（実データ由来fixtureは追加しない）
- Location/Organization/Item/Lore/Event page・Relationship section・Timeline pageなどPhase 2以降のページ種別は本手順書のスコープ外（`Wiki_Output_Design.md` §15参照）
- MkDocs Materialでの実際のビルド確認（`Wiki_Output_Design.md` §15項目5）は別PRで扱う

---

# 13. commit前チェックリスト

dry-run実施後、何かをcommitする前に必ず以下を確認する。

- [ ] `git status --short`に`workspace/wiki_preview/`配下の出力が出ていない
- [ ] `git status --short`に`workspace/dry_runs/`配下の出力が出ていない
- [ ] 実データ由来のmerged knowledge collection・episode_extraction・Normalized Story JSONがcommit対象に含まれていない
- [ ] 実データ由来Wikiページ・生成Markdownがcommit対象に含まれていない
- [ ] `docs/runbooks/`配下に追加した結果記録に、実データ本文・実セリフ・大量の固有名詞・ローカル絶対パスが含まれていない

`scripts/check_dry_run_inputs.py`（引数なし実行）で、commitしてはいけないファイルがgit tracked状態になっていないかを機械的に確認できる。

```bash
uv run python scripts/check_dry_run_inputs.py
```

---

# 14. 関連ドキュメント

- `docs/runbooks/Real_Data_Dry_Run.md`（Parser → Extractor → Merger dry-run手順、本手順書の前段）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計）
- `docs/runbooks/Real_Data_Wiki_Render_Dry_Run_Result_Template.md`（実施結果の数値サマリーテンプレート）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
