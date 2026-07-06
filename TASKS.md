# TASKS

作業TODO管理用ファイル。`AI_CONTEXT.md`はプロジェクトの設計思想・仕様・引き継ぎ情報を扱い、こちらは「今何をしていて、次に何をするか」の作業状態を扱う。

完了済みPRの詳細な作業ログ・テスト件数・diff statは `docs/project_history/Completed_PRs_2026-07.md` に移した。ここには重複記載しない。作業を開始・完了・変更するたびに、該当する章を更新すること。

---

## Current Focus

- `feature/wiki-character-index-page`: `characters/index.md`を追加しTop page→Characters index→Character pageの導線を作った（実装完了、実データ投入・生成物commitは無し、合成fixtureのみ）

## Next

直近5件程度。着手前にユーザーへ確認する。

1. **wiki-character-profile-display-refinement**: Character pageの基本プロフィール表に「特記事項」行を追加し、`profileHighlight.label/value`を`【label】value`形式（例: `【好きなこと】食べ歩き`）で表示する。既存の独立したprofileHighlight表示は基本プロフィール内へ統合し、profile source表示はCharacter page上で非表示にする（`character_profiles.yaml`側のsource情報自体は削除しない）
2. **wiki-renderer-readability-improvements**: Story index/Episode summary/Character details/Unresolved report等でMarkdown tableの横スクロールを解消する（列数削減、definition list風表示への移行、長いID/source候補の折りたたみ相当表示、モバイル/狭幅表示考慮）
3. **wiki-story-index-link-text-improvement**: Story indexのリンクテキストを`episodeId`から`displayTitle > episodeSubtitle > storyTitle+第N話 > episodeId`優先で表示する（title/subtitleデータが少ない現段階では急がない）
4. **story-id-policy-real-sample-review**: EVENT storyId/episodeIdがsourceKey由来の長い意味語を含みうる点を、追加の実データサンプル投入後に再検討する

---

## Backlog

### Parser / Story Manifest

- イベント番号の正式な採番ルール
- `displayOrder`の正式計算式、`canonicalOrder`の扱い
- **story manifest candidate builder**: `scripts/build_story_manifest_candidates.py`を実際のローカルraw DEC配置に対して実行し、生成候補を人間が確認する
- story-id-policy-real-sample-review（Next参照。候補: `EVT_YYYYMMDD_連番`等）
- **story-manifest-confirmed-metadata-batch-001**: 人間確認済みの公式タイトル・サブタイトル情報を`story_manifest.yaml`へ投入する（`metadataStatus: pending` → `confirmed`）
- **story-title-subtitle-candidate-builder-real-trial**: `scripts/build_story_title_subtitle_candidates.py`を実際のWiki/CSV入力に対して実行し、生成候補（`workspace/story_manifest/`配下、commitしない）を人間が確認する
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

- wiki-character-profile-display-refinement（Next参照）
- wiki-renderer-readability-improvements（Next参照）
- wiki-story-index-link-text-improvement（Next参照）
- Wiki Page Template
- relationship section renderer、Location/Organization/Item/Lore/Event page等のPhase 2実装

### Character Dictionary / Profiles

- character profile import batch 002: unmatched 200件のうち、displayName表記ゆれ解消やconfirmed化が進んだ分の人間確認済みcandidateを再照合し追加投入する
- character dictionary confirmed batch 004: 残る未確認10件（234/225/230/222/232/83/258/86/85/257）について、人間確認済みmappingが提供され次第confirmed化する
- キャラクターIDの完全辞書化・主要キャラクターのcanonical ID確定（loader/validation/coverage report/レビュー運用は実装済み。実データ頻出の未確認IDを人間がローマ字確認しconfirmed化する作業自体が残っている）

### Publishing

- **public publishing workflow**: GitHub Pages / Cloudflare Pages等への公開ワークフローを設計・実装する（`Wiki_Output_Design.md` §16 Non-goals）
- **public-publishing-platform-evaluation**: public publishing workflow着手前に、MkDocs Material継続/MkDocs標準テーマ・別テーマ/Docusaurus/VitePress・Astro/独自HTML rendererを再評価する。現時点ではMkDocs Materialから移行しない（Known Issues参照）

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
- **title/subtitleは実質未投入**: Wiki側の表示（Episode page/Story index）は`feature/wiki-episode-title-display-integration`で実装済みだが、`story_manifest.yaml`への人間確認済み実データの投入（confirmed化、`story-manifest-confirmed-metadata-batch-001`）はまだ行われていない。
- **Story indexが依然としてepisodeIdをリンクテキストとして露出**: title/displayTitle/episodeSubtitle優先表示への変更は、title/subtitleデータが少ない現段階では見送り、追加データ投入後に判断する（`wiki-story-index-link-text-improvement`）。
- **EVENT storyId/episodeId形式の再検討余地**: sourceKey由来の長い意味語（イベント固有名詞等）がpublic URL/IDに含まれうる。影響範囲が大きいため今は変更せず、追加の実データサンプル投入後に判断する（`story-id-policy-real-sample-review`）。
- **Wiki tableがMkDocs preview上で横長すぎる**: Story index/Episode summary/Character details/Unresolved report等で横スクロールが発生しており、可読性・モバイル対応の改善が必要（`wiki-renderer-readability-improvements`）。
- **MkDocs Materialは長期公開基盤として未確定**: local preview / early static publishing candidateとしては当面利用してよいが、長期的な新機能追加の不透明さから公開基盤として確定はしない。生成Markdownは特定theme/plugin機能に深く依存しないportableな状態を維持する。public publishing workflow着手前にMkDocs Material継続/別テーマ/Docusaurus/VitePress・Astro/独自rendererを再評価する（`public-publishing-platform-evaluation`）。目視確認は引き続き`mkdocs serve`前提とし、`file://`直開きは正式確認手順にしない。

---

## Recently Completed

直近のみ短く記録。詳細は`docs/project_history/Completed_PRs_2026-07.md`参照。

- **wiki character index page**: `characters/index.md`を新設し、Top page→Characters index→Character pageの導線を追加した。`is_page_eligible`なcharacterのみ一覧表示（unresolved/canonicalIdなし/status不一致は載せない）、Overview（Character pages/プロフィール登録あり・なし件数）とCharacter名・Profile Status・IDの3列のみの表（横長table問題を踏まえ列数を最小限に抑制）。profile表示の細部修正・Story indexリンクテキスト改善は別PRへ持ち越し。合成fixtureのみで検証、実データ未投入。
- **mkdocs manual visual review 001**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、うち1件にPR #62表示確認用のtitle/subtitle/metadataStatus=confirmedを設定、もう1件はpending/未設定のまま）からWiki Markdown・MkDocs HTMLを生成し`workspace/wiki_preview/manual_review_001/`・`manual_review_001_site/`へ保持（**commit対象外**）。Story Title/Episode Subtitle/Display Title/Metadata Status表示・Story indexのDisplay Title列・Basic Profile section（登録あり/なし）・Related Charactersリンクをいずれも`mkdocs serve`経由で確認。source text exposure check問題なし。実装変更なし。**Manual visual reviewは`mkdocs serve`（`http://127.0.0.1:8124/`）を使うこと。`file://`で`index.html`を直接開くと、directory-style URL（`use_directory_urls: true`、既定）のリンクがディレクトリ一覧表示になる（実際にユーザー環境で発生・確認済み）。file直接閲覧が必要な場合は、専用設定で`use_directory_urls: false`を検討すること。** ユーザーによる実ブラウザ目視確認の結果、5件の改善候補（character index page欠如・Story indexのepisodeId露出・storyId/episodeId形式・table可読性・character profile表示統合）とMkDocs Material長期利用方針の検討事項が見つかった（実装はまだ行っていない、詳細はNext/Backlog/Known Issues参照）。
- **wiki episode title display integration**: storyTitle/episodeSubtitle/displayTitle/metadataStatusをExtractor→Merger→Wiki rendererまで伝播し、Episode page（Summary table 4行追加）・Story index（Display Title列追加）へ表示。未設定時はepisodeIdへfallback、AI-generated titleとは分離。合成fixtureのみ、実タイトルは未投入。
- **project context compaction**（PR #61）: 肥大化した`AI_CONTEXT.md`/`TASKS.md`を圧縮し、完了済みPR履歴を`docs/project_history/`へ分離。
- **mkdocs local preview real sample trial**（PR #60）: 実データ小規模サンプルでmanifest候補生成→normalize→extract→merge→render→`mkdocs build --strict`まで警告0件で完走。source text exposure check問題なし。実ブラウザでの目視確認は未実施のまま持ち越し。
- **mkdocs local preview dry-run**（PR #59）: render→MkDocs preview運用手順・目視確認チェックリスト・結果テンプレートを整備。Episode pageのローカル絶対パス露出バグを修正。
- **story title/subtitle import design**（PR #58）: `story_manifest.yaml`のtitle/subtitle取り込み方針を設計。source種別7種定義、schema拡張。
- **normalize_story manifest integration**（PR #57）: `normalize_story.py`に`--manifest`/`--raw-root`/`--manifest-strict`を追加。既存挙動は完全維持。
- **story manifest design**（PR #56）: raw DEC配置とDKB正規ID体系を分離する`story_manifest.yaml`/schemaを設計。

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
