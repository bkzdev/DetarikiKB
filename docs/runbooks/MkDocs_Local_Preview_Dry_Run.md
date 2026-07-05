# MkDocs Local Preview Dry-Run Procedure（生成Wiki目視確認dry-run手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`

---

# 1. 目的

`scripts/render_wiki.py` → MkDocs Materialでの表示までを実際に手元で通し、**目視で見た目を確認する**ための手順・チェックリスト・結果記録テンプレートを定義する。

`docs/runbooks/MkDocs_Local_Preview.md`が「MkDocsで見る方法」（設定ファイルの作り方等）を扱うのに対し、本手順書は**「実際に何をどう見て、何を確認するか」**（目視確認の中身）を扱う。

**`mkdocs build --strict`が成功することと、実際に見た目が正しいことは別問題である。** リンク切れ・schema違反はbuildエラーで検出できるが、テーブルの見づらさ・長文のはみ出し・fallback表示の不自然さ・日本語表示崩れ等は目視でしか分からない。本手順書はその目視確認を運用として定着させる。

**実データ由来の生成物（Normalized Story JSON・extraction result・merged collection・Wiki Markdown）は一切commitしない。** 合成fixtureでの確認・実データでのローカル確認いずれの場合も、生成物は`workspace/`配下（`.gitignore`対象）に留める。

---

# 2. 前提

- `docs/runbooks/MkDocs_Local_Preview.md`（MkDocsでのpreview手順、一時設定ファイルの作り方）
- `docs/runbooks/Real_Data_Dry_Run.md`・`docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`（実データでのParser→Extractor→Merger dry-run手順、本手順書はその後段）
- `docs/runbooks/Story_Title_Subtitle_Import.md`（title/subtitleがまだ`pending`のままでも問題ない前提。fallback表示の確認観点は§6参照）
- `scripts/render_wiki.py`の`--character-profiles`オプション
- `knowledge/dictionaries/character_profiles.yaml`（confirmed済みprofileを持つキャラがいれば、Basic Profile sectionの表示確認に使える）

---

# 3. 推奨ローカルサンプル

実データで確認する場合、以下のような小規模サンプルを推奨する（必須ではない。合成fixtureのみでも本手順書の目視確認は一通り実施できる）。

- EVENT系カテゴリのストーリー1〜2件
- 各ストーリーにつきepisode 1〜3件程度
- `knowledge/dictionaries/character_profiles.yaml`に登録済みのconfirmed profileを持つキャラクターが1人以上出るもの（Basic Profile sectionの表示確認のため）
- unresolved character（`characters.yaml`未登録のキャラクター）が少し含まれるもの（Unresolved report・Related Charactersのfallback表示確認のため）
- `story_manifest.yaml`がある場合は使ってよい。**title/subtitleが未設定（`null`）のままでも問題ない**（fallback表示の確認観点そのものになる）

**サンプル規模は意図的に小さく保つこと。** 大量データでの確認は目視の負担が大きく、本手順書の目的（運用手順の確立）とは別軸である。

---

# 4. 合成fixtureでの確認手順

まず合成fixtureで一通り確認する（実データが無くてもこのステップだけで手順の妥当性を確認できる）。

```bash
uv run python scripts/render_wiki.py \
    --input tests/fixtures/wiki/synthetic_merged_collection.json \
    --output workspace/wiki_preview/synthetic_mkdocs_preview \
    --character-profiles tests/fixtures/character_profiles/synthetic_character_profiles.yaml \
    --validate \
    --clean
```

`docs/runbooks/MkDocs_Local_Preview.md` §6の手順で一時ローカル設定を作り、`mkdocs serve`でpreviewする。

```bash
cat > workspace/wiki_preview/mkdocs.local.yml <<'YAML'
site_name: Detariki Knowledge Base (local preview)
docs_dir: synthetic_mkdocs_preview
theme:
  name: material
YAML

uv run mkdocs serve -f workspace/wiki_preview/mkdocs.local.yml
```

---

# 5. 実データ小規模サンプルでの確認手順

実データでのローカル確認は任意（本PRのスコープでは必須ではない。実施できない場合は§11の通り記録する）。

```bash
# 1. (任意) raw DEC配置からmanifest候補を生成
uv run python scripts/build_story_manifest_candidates.py \
    --raw-root <ローカルraw root> \
    --output workspace/story_manifest/story_manifest_candidates.yaml

# 2. (任意) title/subtitle候補を人間確認込みで生成する場合
uv run python scripts/build_story_title_subtitle_candidates.py \
    --input-csv <ローカルCSV> \
    --manifest workspace/story_manifest/story_manifest_candidates.yaml \
    --source-type manual \
    --output workspace/story_manifest/title_subtitle_candidates.yaml

# 3. Normalized Story JSON生成 (--manifestは任意、無くても--story-id/--categoryの
#    手動指定で従来通り動く。docs/runbooks/Real_Data_Dry_Run.md参照)
uv run python scripts/normalize_story.py \
    --input <ローカルraw root>/EVENT/.../CAB-....dec \
    --output workspace/dry_runs/<RUN_ID>/normalized/ \
    --manifest workspace/story_manifest/story_manifest_candidates.yaml \
    --raw-root <ローカルraw root> \
    --validate

# 4. Extractor
uv run python scripts/extract_story.py \
    --input workspace/dry_runs/<RUN_ID>/normalized/<episodeId>.json \
    --output workspace/dry_runs/<RUN_ID>/extracted/

# 5. Merger (--outputはディレクトリを指定する。merged_knowledge_collection.json
#    という固定ファイル名で出力される)
uv run python scripts/merge_extractions.py \
    --input workspace/dry_runs/<RUN_ID>/extracted/ \
    --output workspace/dry_runs/<RUN_ID>/

# 6. Wiki render (character_profiles.yamlを渡すと、confirmed済みprofileが
#    Basic Profile sectionへ反映される)
uv run python scripts/render_wiki.py \
    --input workspace/dry_runs/<RUN_ID>/merged_knowledge_collection.json \
    --output workspace/wiki_preview/<RUN_ID> \
    --character-profiles knowledge/dictionaries/character_profiles.yaml \
    --validate --clean

# 7. MkDocs preview
cat > workspace/wiki_preview/mkdocs.local.yml <<'YAML'
site_name: Detariki Knowledge Base (local preview)
docs_dir: <RUN_ID>
theme:
  name: material
YAML
uv run mkdocs serve -f workspace/wiki_preview/mkdocs.local.yml
```

`docs/runbooks/Real_Data_Dry_Run.md`・`docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`の既存commit禁止ルール（実DEC・実Normalized Story JSON・実extraction result・実merged collectionはcommitしない）にすべて従うこと。

---

# 6. 目視確認ポイント

ブラウザで`http://127.0.0.1:8000/`を開き、以下を確認する（詳細チェックリストは`docs/templates/mkdocs_local_preview_result_template.md`参照）。

- **Top page**: サマリー表・リンクが正しく表示される
- **Story index**: episode一覧・リンクが機能する
- **Episode page**: Candidate Counts表・Related Characters（リンク付き）・Validationセクションが表示される。**Source Path行にローカル絶対パスがそのまま出ていないこと**（§7参照）
- **Character page / Basic Profile section**: `character_profiles.yaml`にconfirmed profileがあるキャラは項目（ふりがな・所属・身長等）が表示され、無いキャラは「プロフィール未登録」と表示される
- **Related Characters links**: Character pageへのリンクが実際にクリックで遷移する
- **Unresolved report**: unresolved character/relationship/timeline等が一覧表示される
- **Navigation/sidebar**: MkDocsのサイドバー（`mkdocs.yml`に明示`nav`が無い場合は自動生成される）で各ページへ到達できる
- **モバイル/狭幅表示**: ブラウザ幅を狭めて表（Summary表等）が横スクロールするか崩れるか確認する
- **日本語表示**: 文字化けが無いこと
- **表の可読性**: 列幅・改行のバランス
- **長文の扱い**: `notes`等の自由記述フィールドが極端に長い場合の折り返し
- **title/subtitle未設定時のfallback表示**: `story_manifest.yaml`でtitle/subtitleが`null`（`pending`）のままのepisodeで、`episodeId`表記のfallbackが不自然でないか（title/subtitle表示自体のrenderer統合はまだ未実装、`Wiki_Output_Design.md` §9.3参照。現時点ではEpisode pageのタイトルは`episodeId`のまま）

---

# 7. source text exposure check（最重要）

生成されたMarkdownを確認する際、以下を必ず確認する。

- [ ] 元セリフ全文（dialogue本文）がWiki Markdownに出ていない
- [ ] raw DECコマンド（`@ChTalk`等）が出ていない
- [ ] **ローカル絶対パスが出ていない**（`C:\Users\...`等）。Episode pageの`Source Path`行は、`agents/wiki_generator/renderer.py`の`_sanitize_source_path()`により、絶対パスの場合はファイル名のみへ縮約表示される（本PRで追加、§9参照）。相対パスはそのまま表示される
- [ ] `rawPath`（`story_manifest.yaml`由来、まだWiki表示には使われていない）の扱いが安全である
- [ ] evidence ID（`evidenceId`/`episodeId`/`sceneId`/`blockId`）は参照情報として表示されてよい
- [ ] `sourceFileName`は必要最小限の表示に留め、大量表示・公開前は方針を再確認する
- [ ] 生成したMarkdown・merged collection・Normalized Story JSON・raw DECをcommitしない

---

# 8. commit禁止対象

- 実データ由来の生成Wiki Markdown（`workspace/wiki_preview/`配下すべて）
- 実DEC・実`story_manifest.yaml`・実Normalized Story JSON・実extraction result・実merged collection
- raw HTML・実candidate YAML/CSV
- ローカル絶対パスを含む結果ファイル
- 一時MkDocs設定ファイル（`workspace/wiki_preview/mkdocs.local.yml`等）
- `docs/templates/mkdocs_local_preview_result_template.md`への実施結果記録（合成テンプレートのみcommitし、実施結果自体はローカルまたは別途共有経路で管理する）

---

# 9. renderer小修正（本PRで実施したもの）

`mkdocs build --strict`自体は合成fixtureに対して警告0件で成功したが、目視確認の過程でSource Path行のローカル絶対パス露出リスクに気づいたため、以下の軽微な修正のみ行った。

- `agents/wiki_generator/renderer.py`に`_sanitize_source_path()`を追加し、`render_episode_page`の`Source Path`行がWindows絶対パス（`C:/...`）・POSIX絶対パス（`/...`）の場合はファイル名のみへ縮約表示するようにした（相対パスは従来通りそのまま表示）
- テンプレートエンジン導入・Wiki page構造の全面改修・relationship/timeline page本格実装等の大規模変更は行っていない

---

# 10. よくある失敗

`docs/runbooks/MkDocs_Local_Preview.md` §8の既存表に加え、以下を確認する。

| 症状 | 想定される原因 | 対応 |
|---|---|---|
| Character pageにBasic Profile sectionが出ない | `render_wiki.py`に`--character-profiles`を指定していない | `--character-profiles knowledge/dictionaries/character_profiles.yaml`（または合成fixture）を追加する |
| Episode pageのタイトルが`episodeId`のまま | title/subtitle表示のrenderer統合が未実装（設計のみ、`Wiki_Output_Design.md` §9.3） | 想定通りの挙動。将来PR（`wiki episode title display integration`）で対応予定 |
| Source Path行にローカルパスがそのまま出る | 本PR以前のrenderer、または`_sanitize_source_path`のパターンに一致しない特殊な絶対パス形式 | パターン（`_WINDOWS_DRIVE_PATTERN`等）を確認し、必要ならissueとして記録する |

---

# 11. 結果の記録方法

`docs/templates/mkdocs_local_preview_result_template.md`をコピーして記録する。**記録先（ローカルのコピー、社内共有ドライブ等）はcommit対象外とすること。**

**記録してよいもの**: build成否、目視確認したページ種別、見つかった改善点（抽象化した説明）、follow-up候補。

**記録してはいけないもの**: 生成Markdown全文、実セリフ・実ストーリー本文、実イベント名・実キャラ名の羅列、ローカル絶対パス、実データ由来merged collection/Normalized Story JSON自体。

---

# 12. 次にやること

- `mkdocs local preview real sample trial`: 実際のローカル実データサンプルで本手順書を一通り実施し、結果を記録する（本PR時点では未実施、§13参照）
- `wiki episode title display integration`: Episode pageのtitle/subtitle表示renderer実装（`Wiki_Output_Design.md` §9.3）
- `story title/subtitle candidate builder`: 実際のWiki/CSV入力での動作確認
- `public publishing workflow`: GitHub Pages / Cloudflare Pages等への公開ワークフロー設計

---

# 13. 実データ目視確認の実施状況

**本PR（`feature/mkdocs-local-preview-dry-run`）では、実データ目視確認は未実施である。** 合成fixture（`tests/fixtures/wiki/synthetic_merged_collection.json`・`tests/fixtures/character_profiles/synthetic_character_profiles.yaml`）での確認のみ実施した（`mkdocs build --strict`警告0件、目視確認は§6のポイントに沿って実施済み）。実データでの目視確認は次回実施とする。

---

# 14. 関連ドキュメント

- `docs/runbooks/MkDocs_Local_Preview.md`（MkDocsでのpreview手順そのもの、一時設定ファイルの作り方）
- `docs/runbooks/Real_Data_Dry_Run.md`・`docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`・`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`（前段のdry-run手順）
- `docs/runbooks/Story_Title_Subtitle_Import.md`（title/subtitleが`pending`のまま表示される前提）
- `docs/templates/mkdocs_local_preview_result_template.md`（結果記録テンプレート）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計）
