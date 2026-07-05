# TASKS

作業TODO管理用ファイル。`AI_CONTEXT.md`はプロジェクトの設計思想・仕様・引き継ぎ情報を扱い、こちらは「今何をしていて、次に何をするか」の作業状態を扱う。

完了済みPRの詳細な作業ログ・テスト件数・diff statは `docs/project_history/Completed_PRs_2026-07.md` に移した。ここには重複記載しない。作業を開始・完了・変更するたびに、該当する章を更新すること。

---

## Current Focus

- `feature/mkdocs-manual-visual-review-001`: 実データ小規模サンプルからWiki Markdown/MkDocs HTMLを生成し、`workspace/wiki_preview/manual_review_001/`・`manual_review_001_site/`にユーザー目視確認用として保持（**commitしない**、ユーザーのブラウザ確認待ち）。実装変更なし。source text exposure check問題なし

## Next

直近5件程度。着手前にユーザーへ確認する。

1. ユーザーによる`workspace/wiki_preview/manual_review_001_site/index.html`のブラウザ目視確認（Top page/Story index/Episode page/Character page/Basic Profile section/Related Characters/Unresolved report/モバイル幅/日本語表示/table可読性/title・subtitle・metadataStatus表示）
2. **renderer readability improvements**: 上記目視確認で見つかった改善点があれば反映する
3. **story-title-subtitle-candidate-builder-real-trial**: `scripts/build_story_title_subtitle_candidates.py`を実際のWiki/CSV入力に対して実行し、生成候補（`workspace/story_manifest/`配下、commitしない）を人間が確認する
4. **story-manifest-confirmed-metadata-batch-001**: 人間確認済みの公式タイトル・サブタイトル情報を`story_manifest.yaml`へ投入する（`metadataStatus: pending` → `confirmed`）
5. **character profile import batch 002**: unmatched 200件のうち、displayName表記ゆれ解消やconfirmed化が進んだ分の人間確認済みcandidateを再照合し追加投入する

---

## Backlog

### Parser / Story Manifest

- イベント番号の正式な採番ルール
- `displayOrder`の正式計算式、`canonicalOrder`の扱い
- **story manifest candidate builder**: `scripts/build_story_manifest_candidates.py`を実際のローカルraw DEC配置に対して実行し、生成候補を人間が確認する
- story-manifest-confirmed-metadata-batch-001（Next参照）
- `--check-compat`のレポート出力先をオプション化するか、既定動作として明示的にドキュメント化する
- `agents/parser/parser.py::_parse_tokens`のparse state dataclassリファクタ本体（Known Issues参照）

### Extraction / Merge

- timeline contradiction detection（順序整合性の本格検証）
- `relationshipType`のtaxonomy本確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`、現在プレースホルダー）
- canonical ID辞書（`knowledge/dictionaries/*.yaml`）本体の実装（現状はpolicy/helper/validationのみ）
- EventCandidateのparticipant/location解決
- `entities`配下の`schemas/merged_knowledge.schema.json`への`$ref`接続（cross-file $ref方針の決定待ち）
- merge report自体の生成物出力（`data/extracted/reports/merge_report.json`への書き出し）
- choice内話者・choice内location/organization/item/lore/event情報も含めた抽出への拡張
- semantic validationの拡充（FieldValue単位のevidenceIds検証、Relationship両端の実在確認、Timeline順序整合性チェック）
- Scene定義への拡張フィールド許容（scene metadataからのItem/Event/Timeline抽出に必要）
- Candidate ID暫定形式（`Extraction_Result_Schema.md` §4.2）の実運用検証
- extractor各moduleの重複ヘルパー集約（item.py/event.py/timeline.py/location.py、挙動維持を優先し据え置き中）

### Wiki / MkDocs

- Wiki Page Template
- relationship section renderer、Location/Organization/Item/Lore/Event page等のPhase 2実装
- renderer readability improvements（モバイル幅・長文レイアウト・実ブラウザ確認、Next参照）

### Character Dictionary / Profiles

- character profile import batch 002（Next参照）
- character dictionary confirmed batch 004（Next参照）
- キャラクターIDの完全辞書化・主要キャラクターのcanonical ID確定（loader/validation/coverage report/レビュー運用は実装済み。実データ頻出の未確認IDを人間がローマ字確認しconfirmed化する作業自体が残っている）

### Publishing

- **public publishing workflow**: GitHub Pages / Cloudflare Pages等への公開ワークフローを設計・実装する（`Wiki_Output_Design.md` §16 Non-goals）

### Quality / Refactor

- Neo4j Graph Model
- Stage Directionをどこまで詳細に意味解析するか
- 外部LLM Provider連携（opt-in、ローカルLLMがデフォルト）
- invalid direction（RelationshipCandidate）のwarning化

---

## Known Issues

- **`agents/parser/parser.py::_parse_tokens`のC901複雑度（43 > 10）が未解消**: CIでは`# noqa: C901`で暫定抑制のみ。12個以上の`nonlocal`状態変数が`flush_text()`クロージャと全トークン種別ハンドラ間で密結合しており、安全に分割するにはdataclassベースの状態オブジェクトへの大規模リファクタが必要（実データ生成の中核ロジックのため既存テストでの挙動不変確認を徹底した専用PRで対応すること）。
- **cp932コンソールでのconsole encodingテストがflakyになることがある**: `tests/scripts/test_console_output_encoding.py::test_normalize_story_cli_survives_cp932_console`がPython 3.14のsubprocess reader threadの非決定的挙動で稀に失敗することを確認済み（単体・複数回再実行では再現せず、環境要因と判断）。
- **semantic validationの範囲が限定的**: evidenceIds実在確認・duplicate candidate id・empty evidenceIndex等の基本チェックのみ実装済み。FieldValue単位のevidenceIds検証、Relationship両端のcandidate配列中の実在確認、Timeline順序整合性チェックは未実装。
- **character dictionaryの数値ID帯カバレッジ不足**: 演出コマンドカバレッジは実データで解消済み（unknown率68%台→0〜0.1%）だが、頻出未確認ID（234/225/230/222等）の人間によるローマ字確認・confirmed化が残作業（`docs/runbooks/Character_Dictionary_Review.md`）。
- **compatibility checkの既知の非対称性**: standalone実行と`normalize_story.py --check-compat`埋め込みの主要判定（`unknownCommands`/`newSpeechCommands`/`parserCompatibility`）は一致するが、`branch_issues`/`case_variants`をStoryParserが追跡しないため常にFalse扱い。裸単語コマンドの検出範囲も両経路で非対称（実データでは稀）。
- **Identifier_Specification.md §4.3のEVT形式との差分**: `story_manifest.yaml`のstoryId生成方針`EVT_{sourceKeyを大文字化}`（例: `EVT_250626_DANCER`）が、既存仕様書の`EVT_{eventNumber}`（数値管理番号）と異なる形式のまま未解消（`metadataStatus: pending`、人間レビュー時の判断待ち）。
- **実ブラウザでの目視確認が未実施**: mkdocs local preview系のPRはいずれもツール制約（本セッションにブラウザ/スクリーンショットツールが無い）により、生成Markdown本文とビルド後HTMLの直接確認で代替してきた。モバイル幅・日本語フォント描画等の実ブラウザ確認は持ち越し。
- **title/subtitleは実質未投入**: Wiki側の表示（Episode page/Story index）は`feature/wiki-episode-title-display-integration`で実装済みだが、`story_manifest.yaml`への人間確認済み実データの投入（confirmed化、`story-manifest-confirmed-metadata-batch-001`）はまだ行われていない。

---

## Recently Completed

直近のみ短く記録。詳細は`docs/project_history/Completed_PRs_2026-07.md`参照。

- **mkdocs manual visual review 001**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、うち1件にPR #62表示確認用のtitle/subtitle/metadataStatus=confirmedを設定、もう1件はpending/未設定のまま）からWiki Markdown・MkDocs HTMLを生成し`workspace/wiki_preview/manual_review_001/`・`manual_review_001_site/`へ保持（**commit対象外**）。Story Title/Episode Subtitle/Display Title/Metadata Status表示・Story indexのDisplay Title列・Basic Profile section（登録あり/なし）・Related Charactersリンクをいずれも実データで確認。source text exposure check問題なし。ユーザーのブラウザ目視確認待ち。実装変更なし。
- **wiki episode title display integration**: storyTitle/episodeSubtitle/displayTitle/metadataStatusをExtractor→Merger→Wiki rendererまで伝播し、Episode page（Summary table 4行追加）・Story index（Display Title列追加）へ表示。未設定時はepisodeIdへfallback、AI-generated titleとは分離。合成fixtureのみ、実タイトルは未投入。
- **project context compaction**（PR #61）: 肥大化した`AI_CONTEXT.md`/`TASKS.md`を圧縮し、完了済みPR履歴を`docs/project_history/`へ分離。
- **mkdocs local preview real sample trial**（PR #60）: 実データ小規模サンプルでmanifest候補生成→normalize→extract→merge→render→`mkdocs build --strict`まで警告0件で完走。source text exposure check問題なし。実ブラウザでの目視確認は未実施のまま持ち越し。
- **mkdocs local preview dry-run**（PR #59）: render→MkDocs preview運用手順・目視確認チェックリスト・結果テンプレートを整備。Episode pageのローカル絶対パス露出バグを修正。
- **story title/subtitle import design**（PR #58）: `story_manifest.yaml`のtitle/subtitle取り込み方針を設計。source種別7種定義、schema拡張。
- **normalize_story manifest integration**（PR #57）: `normalize_story.py`に`--manifest`/`--raw-root`/`--manifest-strict`を追加。既存挙動は完全維持。
- **story manifest design**（PR #56）: raw DEC配置とDKB正規ID体系を分離する`story_manifest.yaml`/schemaを設計。
- **MkDocs Material minimal site**（PR #55）: ローカルpreview専用の最小`mkdocs.yml`/`docs/site_preview/`を整備。story indexのリンク切れバグを修正。

---

## Archive

完了済みPR #1〜#60の詳細な作業履歴（各PRの実装内容・確認結果・あえて実装しなかったこと等）は `docs/project_history/Completed_PRs_2026-07.md` を参照。

---

## Rules

- 実スクリプト全文（`.dec`由来の生データ）をcommitしない
- `data/extracted/`配下の生成物をcommitしない
- APIキーをcommitしない（`.env`は`.gitignore`管理）
- 外部LLM Providerはopt-in、デフォルトはローカルLLM
- Raw Scriptを直接LLMに渡さない（必ずNormalized Story JSON経由）
- `agents/extractor/`のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（最小skeletonの実装は完了。CLAUDE.mdの方針）
- Stage B（Merged Knowledge）では、Stage A candidateのevidence・provenance（sourceType/confidence/evidenceIds/candidate ID/extractionRun）をマージ後も失わない（`Merged_Knowledge_Design.md` §4.1 / §10）
- unknown commandは破棄せず、Parser（`compatibilityReport.unknownCommands`・`type: "unknown"`ブロック）またはcompatibility check（`report.unknownCommands`）に必ず残す。実データ投入後は一覧を確認し、頻出かつ安全に分類できるものから`config/script_commands.yaml`・`agents/parser/parser.py`・`agents/parser/tokenizer.py`へ追加する。追加時のテストは実データ由来fixtureではなく合成fixtureで行う（継続的な運用手順は`docs/runbooks/Real_Data_Dry_Run.md` §18参照）
