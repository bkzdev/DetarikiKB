# MkDocs Local Preview Check Result — Real Sample Trial 001

`docs/templates/mkdocs_local_preview_result_template.md` を元にした、実データ小規模サンプルでの
目視確認結果の匿名化サマリーである。実イベント名・実ファイル名・実タイトル・実サブタイトル・
実セリフ・rawPath実一覧・ローカル絶対パス・実source URL・実HTML断片は一切含めていない。

## Run Info

- Date: 2026-07-05
- Branch: `feature/mkdocs-local-preview-real-sample-trial`
- Input type: local real sample
- Source stories: EVENTカテゴリ 1件（"EVENT sample A"）・episode 2件
- Render output path: `workspace/wiki_preview/real_sample_trial`（commit対象外）
- MkDocs config: 一時ローカル設定ファイル（commit対象外）
- Browser: 未実施（本セッションにブラウザ/スクリーンショットツールが無いため、生成Markdown本文とmkdocs build生成HTMLを直接読む方式で代替確認した。実際のブラウザでの見た目確認は次回以降の課題として残る）
- Commit generated output: No

## Build Checks

- `scripts/build_story_manifest_candidates.py` result: exit code 0、ストーリー1件・episode2件の候補を検出
- `scripts/normalize_story.py --manifest --manifest-strict` result: 2 episodeとも exit code 0、JSON Schema検証成功、manifest一致（matched_by: raw_path）
- `scripts/extract_story.py --validate` result: 2 episodeとも exit code 0
- `scripts/merge_extractions.py` result: exit code 0（`--report`相当の別引数は現行CLIに無く、`report`はcollection内に埋め込まれる仕様だった）
- `scripts/render_wiki.py --character-profiles --validate --clean` result: exit code 0、Markdown 7件生成（Top page 1・Story index 1・Episode page 2・Character page 2・Unresolved report 1）
- `mkdocs build --strict` result: 成功、警告0件（表示された警告はMkDocs Material側のバージョン告知のみで生成Markdownとは無関係）
- `mkdocs serve` result: 起動成功を確認（バックグラウンドプロセスのライフサイクル制約により起動確認後は停止）

## Visual Checks

（ブラウザでの目視確認は未実施。生成Markdown本文＋`mkdocs build`が生成した静的HTMLの直接確認による代替結果）

- Top page: OK（サマリー表・リンクとも正常生成）
- Story index: OK（storyId/episodeId/candidate合計/status/category列、Episode pageへの相対リンク正常）
- Episode page: OK（Summary/Candidate Counts/Related Characters/Validationセクションとも正常生成）
- Character page: OK（プロフィールあり1件・プロフィール未登録1件の両方を確認）
- Basic Profile section: OK（プロフィール登録済みキャラでは表項目・キャラ別特記事項が表示され、未登録キャラでは「プロフィール未登録」と表示された）
- Related Characters links: OK（resolved characterへの相対リンクが正しいページに解決することをビルド後HTMLで確認。unresolvedキャラは内部IDとunresolved表記のみ）
- Unresolved report: OK（Overview/Conflict Summary/Warning Summary/Canonical ID Summary/Relationship Type Summaryとも表示、unresolved character・locationの一覧表も正常）
- Navigation/sidebar: MkDocs Material標準ナビゲーションで生成、build時のリンク切れ警告なし
- Mobile/narrow width: 未確認（ブラウザ未使用のため。`viewport` metaタグの存在のみ静的HTMLで確認）
- Japanese text rendering: Markdown/HTMLレベルでは文字化けなし（実際のフォント描画はブラウザ確認が必要、未実施）
- Table readability: OK（各ページのMarkdown表がHTML `<table>`へ正しく変換されていることをビルド後HTMLで確認）
- Long text handling: 今回のサンプルでは該当する長文フィールド（自己紹介文等）が無かったため未確認
- Missing title/subtitle fallback: OK（`story_manifest.yaml`側でtitle/subtitle未設定のepisodeについて、Episode pageのtitle/見出しがepisodeIdでfallback表示されることを確認。既知の設計通り「第N話」形式のfallbackはまだ未実装）

## Source Safety Checks

- No full dialogue text exposed: 問題なし（evidenceId/candidateId等の参照情報のみで本文セリフは一切出力されないことを確認）
- No raw DEC text exposed: 問題なし（`@ChTalk`等のDECコマンド文字列・`$numX`変数はgrepで非検出）
- No local absolute paths: 問題なし（`C:\Users\...`・`D:\Dev\...`いずれもgrepで非検出。Episode pageのSource Pathはworkspace配下の相対パスのみ表示）
- No raw HTML/candidate files: 問題なし（生成物はMarkdown/ビルド後HTMLのみで、raw HTML・candidate YAML/CSVは参照・出力していない）
- No generated real Markdown committed: 遵守（本ファイル・commit差分に実データ由来Markdownを含めていない）
- 実rawディレクトリ名・raw root名の露出: 問題なし（grepで非検出）

## Findings

- Issues found: 今回のトライアルでrenderer側の不具合は見つからなかった
- Suggested follow-up tasks:
  - 実際のブラウザでの目視確認（本セッションではツール制約により未実施、次回のtrialで実施）
  - Episode pageのtitle/subtitle fallbackを「第N話」形式にする本格実装（`wiki episode title display integration`）
  - モバイル幅・長文自己紹介文でのレイアウト確認（該当データが無かったため未確認のまま）
- Blockers: なし
- Non-blockers: ブラウザ目視確認の未実施は次trialへ持ち越し
