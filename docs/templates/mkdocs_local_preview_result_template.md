# MkDocs Local Preview Check Result（合成テンプレート）

このテンプレートは`docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`の目視確認結果を
記録するための見本である。**このファイル自体は合成の空欄テンプレートであり、
実施結果の記入・commitはしないこと。** 実施結果は各自のローカル・社内共有ドライブ等、
commit対象外の場所へ記録する。

記入時の注意（`docs/runbooks/MkDocs_Local_Preview_Dry_Run.md` §11参照）:

- 記録してよいもの: build成否、目視確認したページ種別、見つかった改善点（抽象化した説明）、follow-up候補
- 記録してはいけないもの: 生成Markdown全文、実セリフ・実ストーリー本文、実イベント名・実キャラ名の羅列、ローカル絶対パス、実データ由来merged collection/Normalized Story JSON自体

---

## Run Info

- Date:
- Branch:
- Input type: synthetic / local real sample
- Source stories: (件数のみ。実イベント名は書かない、例: "EVENTカテゴリ1件・episode2件")
- Render output path: (例: `workspace/wiki_preview/<RUN_ID>`。パスそのものはローカル専用の記録に留める)
- MkDocs config: (例: `workspace/wiki_preview/mkdocs.local.yml`)
- Browser:
- Commit generated output: No

## Build Checks

- render_wiki.py result: (exit code、生成ページ数)
- mkdocs build --strict result: (成功/警告件数)
- mkdocs serve result: (起動できたか)

## Visual Checks

- Top page:
- Story index:
- Episode page:
- Character page:
- Basic Profile section:
- Related Characters links:
- Unresolved report:
- Navigation/sidebar:
- Mobile/narrow width:
- Japanese text rendering:
- Table readability:
- Long text handling:
- Missing title/subtitle fallback:

## Source Safety Checks

- No full dialogue text exposed:
- No raw DEC text exposed:
- No local absolute paths:
- No raw HTML/candidate files:
- No generated real Markdown committed:

## Findings

- Issues found:
- Suggested follow-up tasks:
- Blockers:
- Non-blockers:
