# TASKS

作業TODO管理用ファイル。`AI_CONTEXT.md`はプロジェクトの設計思想・仕様・引き継ぎ情報を扱い、こちらは「今何をしていて、次に何をするか」の作業状態を扱う。

完了済みPRの詳細な作業ログ・テスト件数・diff statは `docs/project_history/Completed_PRs_2026-07.md` に移した。ここには重複記載しない。作業を開始・完了・変更するたびに、該当する章を更新すること。

---

## Current Focus

- `feature/story-summary-schema-design`: Story page（PR #76）のStory Summary/Episode Summary「未生成」placeholderを実データで置き換えるための設計を`docs/architecture/06_AI/Story_Summary_Design.md`にまとめた。Summaryは(A) Story Summary/(B) Episode Summary/(C) AI Analysis・Speculationを区別し、(C)はSummary schemaに混ぜない方針。保存場所は`knowledge/summaries/stories/{storyId}.yaml`（1 story 1 file）を採用、draftは`workspace/summary_drafts/`側でreviewしてから昇格する運用とした。生成ステータス（`missing`/`draft`/`generated`/`deprecated`）とレビューステータス（`unreviewed`/`reviewed`/`approved`/`rejected`/`needs_revision`）を分離し、`review.status`が`reviewed`/`approved`のもののみcommit・Wiki表示対象とする。`evidenceRefs`は任意保持可（Episode単位のevidenceId体系のまま、rawテキストは含めない）。**本PRではschema実装・renderer統合・AI要約生成は行っていない**（設計docsのみ）。
- `feature/story-page-manual-review`: `feature/wiki-story-page-renderer`（PR #76）で実装したStory page中心の導線を、実データ小規模サンプル（EVENTカテゴリ1件・episode2件、匿名化）でStory index→Story page→Episode pageまで`mkdocs serve`（`http://127.0.0.1:8127/`）で目視確認できる状態にした。episode1に合成`publicStoryId`/`publicEpisodeId`・合成title/subtitleを付与、episode2は`publicEpisodeId`未設定のままfallback確認用に残した。Story page Overview/Story Summary placeholder/Episode Summaries placeholder/Episode list/Related Characters集約/Review Links、Characters index/Character page/Unresolved report/Special Speaker Labelsいずれも表示・リンクとも問題なし。`workspace/wiki_preview/story_page_manual_review/`・`_site/`へ保持（**commit対象外**）。source text exposure check問題なし（`episodeId`にsourceKey由来語が残る既知課題のみ、本PRのscope外）。実装変更なし。ユーザーの実ブラウザ目視確認待ち。
- `feature/wiki-story-page-renderer`: `Story_Page_Design.md`の設計を踏まえ、Story pageを`agents/wiki_generator/renderer.py`に実装した（`render_story_page`、`story_page_path`/`resolve_story_path_id`）。`sourceDocuments`を`storyId`でグルーピングし、Story index（`| Story | Episodes | Status | Category |`、リンクtextは`storyTitle > publicStoryId > storyId`）→Story page（Overview・Story Summary placeholder「未生成」・EpisodeごとのEpisode Summary placeholder・Episode一覧・Related Characters集約・Unresolved report導線）→Episode pageという導線を実装した。`publicStoryId`があればStory page filenameに使い、無ければ`storyId`へfallback（短期URL構造は候補A、flat維持）。**Episode pageは変更していない**（`episode_page_path`・`publicEpisodeId`fallback方針はPR #73のまま）。AI要約生成・Story summary schemaはまだ実装していない。

## Next

直近5件程度。着手前にユーザーへ確認する。

1. **story-summary-schema-implementation**: `docs/architecture/06_AI/Story_Summary_Design.md`を踏まえ、`schemas/story_summary.schema.json`とloader/validatorを実装する
2. **story-summary-renderer-integration**: `render_wiki.py --story-summaries`を追加し、Story page Summary placeholderを実際のSummaryデータへ差し替える
3. **story-title-subtitle-candidate-builder-real-trial**: `scripts/build_story_title_subtitle_candidates.py`を実際のWiki/CSV入力に対して実行し、生成候補を人間が確認する
4. **character profile import batch 002**: unmatched 200件のうち、displayName表記ゆれ解消やconfirmed化が進んだ分の人間確認済みcandidateを再照合し追加投入する
5. **public-publishing-platform-evaluation**: public publishing workflow着手前に、MkDocs Material継続/MkDocs標準テーマ・別テーマ/Docusaurus/VitePress・Astro/独自HTML rendererを再評価する

---

## Backlog

### Parser / Story Manifest

- イベント番号の正式な採番ルール
- `displayOrder`の正式計算式、`canonicalOrder`の扱い
- **story manifest candidate builder**: `scripts/build_story_manifest_candidates.py`を実際のローカルraw DEC配置に対して実行し、生成候補を人間が確認する
- **story-manifest-public-id-nested-path**: Story/EpisodeのURLを現行フラット構成`stories/{episodeId}.md`からネスト構成`stories/{storyId}/{episodeId}.md`へ移行するかの検討（`publicStoryId`のWiki出力への活用含む、`Story_Page_Design.md` §10 候補C・Wiki_Output_Design.md §14）
- **public-id-manifest-assignment-policy**: `publicStoryId`/`publicEpisodeId`の採番・割当運用（人間手動 vs 半自動）を正式に決める
- story-summary-schema-design（Next参照）
- story-title-subtitle-candidate-builder-real-trial（Next参照）
- **story-manifest-confirmed-metadata-batch-001**: 人間確認済みの公式タイトル・サブタイトル情報を`story_manifest.yaml`へ投入する（`metadataStatus: pending` → `confirmed`。story-title-subtitle-candidate-builder-real-trialの後続作業）
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

- **story-page-related-characters-refinement**: Story page Related Charactersの表示（順序・重複・unresolvedの扱い等）をさらに改善する
- **story-summary-schema-implementation** / **story-summary-renderer-integration**（Next参照）
- **mkdocs-manual-visual-review-002**: ユーザーによる`uv run mkdocs serve -f workspace/wiki_preview/manual_review_002/mkdocs_manual_review.yml -a 127.0.0.1:8125`起動後、`http://127.0.0.1:8125/`でのブラウザ目視確認
- **wiki-story-index-link-text-real-sample-review**: 実データ小規模サンプルでEpisode link text優先順位・metadataStatus表示を確認する
- **speaker-label-normalization-real-sample-review**: 実データ小規模サンプルでspeaker group/generic speaker検出の網羅性・誤検出を確認する（合成fixtureのみのため後続作業）
- Wiki Page Template
- relationship section renderer、Location/Organization/Item/Lore/Event page等のPhase 2実装

### Character Dictionary / Profiles

- **character profile import batch 002**（Next参照）
- character dictionary confirmed batch 004: 残る未確認10件（234/225/230/222/232/83/258/86/85/257）について、人間確認済みmappingが提供され次第confirmed化する
- キャラクターIDの完全辞書化・主要キャラクターのcanonical ID確定（loader/validation/coverage report/レビュー運用は実装済み。実データ頻出の未確認IDを人間がローマ字確認しconfirmed化する作業自体が残っている）

### Publishing

- **public publishing workflow**: GitHub Pages / Cloudflare Pages等への公開ワークフローを設計・実装する（`Wiki_Output_Design.md` §16 Non-goals）
- **public-publishing-platform-evaluation**（Next参照。現時点ではMkDocs Materialから移行しない、Known Issues参照）

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
- **EVENT storyId/episodeId形式の再検討余地**: sourceKey由来の長い意味語（イベント固有名詞等）がpublic URL/IDに含まれうる。実データサンプルレビュー・採用方針決定・`publicStoryId`/`publicEpisodeId`のfield設計実装・renderer/paths.py切替（`docs/architecture/05_Parser/Story_ID_Policy_Review.md` / `Story_ID_Policy_Decision.md` / `Story_Manifest_Design.md` §13.2）は完了済み。ネスト構成（`stories/{storyId}/{episodeId}.md`）への移行・`publicStoryId`のWiki出力への活用は`story-manifest-public-id-nested-path`で検討する（未着手）。
- **Wiki tableがMkDocs preview上で横長すぎる**: Story index/Episode summary/Character details/Unresolved report等で横スクロールが発生しており、可読性・モバイル対応の改善が必要（`wiki-renderer-readability-improvements`）。
- **MkDocs Materialは長期公開基盤として未確定**: local preview / early static publishing candidateとしては当面利用してよいが、長期的な新機能追加の不透明さから公開基盤として確定はしない。生成Markdownは特定theme/plugin機能に深く依存しないportableな状態を維持する。public publishing workflow着手前にMkDocs Material継続/別テーマ/Docusaurus/VitePress・Astro/独自rendererを再評価する（`public-publishing-platform-evaluation`）。目視確認は引き続き`mkdocs serve`前提とし、`file://`直開きは正式確認手順にしない。

---

## Recently Completed

直近のみ短く記録。詳細は`docs/project_history/Completed_PRs_2026-07.md`参照。

- **story summary schema design**: Story Summary/Episode Summaryのデータ構造設計を`docs/architecture/06_AI/Story_Summary_Design.md`にまとめた。(A) Story Summary/(B) Episode Summary/(C) AI Analysis・Speculationを区別しSummary schemaには(C)を含めない方針、保存場所は`knowledge/summaries/stories/{storyId}.yaml`採用（draftは`workspace/summary_drafts/`側でレビュー後に昇格）、生成ステータスとレビューステータスを分離、`evidenceRefs`は任意保持可でrawテキストは含めない方針を決定した。schema実装・renderer統合・AI要約生成は次PR（`story-summary-schema-implementation`/`story-summary-renderer-integration`）に持ち越し、本PRでは実装変更なし。
- **story page manual review**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、匿名化。うちepisode1に合成`publicStoryId`/`publicEpisodeId`/合成title・subtitleを付与、episode2は`publicEpisodeId`未設定のままfallback確認用）で、PR #76のStory page中心導線（Story index→Story page→Episode page）を`normalize→extract→merge→render→mkdocs build --strict`まで通し確認した。Story page Overview・Story/Episode Summary placeholder・Episode list（publicEpisodeIdあり/fallbackとも正しくリンク）・Related Characters集約・Unresolved report導線、Characters index/Character page（profile登録あり2件）/Unresolved report/Special Speaker Labelsいずれも問題なし。`workspace/wiki_preview/story_page_manual_review/`・`_site/`へ保持（**commit対象外**）。source text exposure check問題なし（`episodeId`にsourceKey由来語が残る既知課題を除く、`Story_ID_Policy_Review.md`参照）。`mkdocs serve`（`http://127.0.0.1:8127/`）経由でcurl確認（全ページ200）、実装変更なし。ユーザーの実ブラウザ目視確認待ち。
- **wiki story page renderer**: `Story_Page_Design.md`の設計を踏まえ、Story pageを実装した。`render_story_page`（`agents/wiki_generator/renderer.py`）・`story_page_path`/`resolve_story_path_id`（`agents/wiki_generator/paths.py`）を追加し、`sourceDocuments`を`storyId`でグルーピングしてStory index（Story/Episodes/Status/Category、`storyTitle > publicStoryId > storyId`優先のリンクtext）→Story page（Overview・Story Summary/Episode Summaries placeholder「未生成」・Episode一覧・Related Characters集約・Unresolved report導線）→Episode pageという導線を実装した。`publicStoryId`があればStory page filenameに使い、無ければ`storyId`へfallback（短期URL構造は候補A、flat維持）。**Episode page（`episode_page_path`・`publicEpisodeId`fallback方針）・Character page path・storyId/episodeId生成ロジックは変更していない**。合成fixtureに同一storyId複数episode・public ID有無のパターンを追加して検証、実データ未投入。
- **wiki story page design**: Episode page中心のWiki構造を、今後Story page中心へ寄せるための設計を`docs/architecture/07_Wiki/Story_Page_Design.md`にまとめた。Story pageを新規追加する方針・Episode pageは残す方針・`evidenceId`/`episodeId`/`blockId`管理はEpisode単位維持・Story/Episode Summary placeholder（「未生成」表示、AI要約生成は後続PR）・URL構造候補（短期=候補A flat、長期=候補C nestedを再評価）を決定した。**Story page renderer実装・URL変更・renderer/paths.py変更はしていない**（設計のみ）。次PRは`wiki-story-page-renderer`。
- **public id renderer manual review**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、匿名化）でPR #72/#73の`publicStoryId`/`publicEpisodeId`実装をmanifest手動付与→normalize→extract→merge→render→`mkdocs build --strict`まで通し確認した。publicEpisodeIdありのepisodeはEpisode page URL/filenameがpublic IDベースになりStory indexリンクも追従、publicEpisodeIdなしのepisodeは既存episodeIdへfallbackすることを確認。Characters index/Character page/Unresolved report/Special Speaker Labelsは壊れていない。`workspace/wiki_preview/public_id_manual_review/`・`public_id_manual_review_site/`へ保持（**commit対象外**）。source text exposure check問題なし。`mkdocs serve`（`http://127.0.0.1:8126/`）経由でcurl確認、実装変更なし。ユーザーの実ブラウザ目視確認待ち。
- **story manifest public id renderer switch**: `publicEpisodeId`/`publicStoryId`をExtractor（`episode_extraction`）→Merger（`sourceDocuments[]`）経由でWiki rendererまで伝播し、`agents/wiki_generator/paths.py`の`episode_page_path`が`publicEpisodeId`（空文字列・whitespaceのみは無視）を優先、無ければ既存`episodeId`へfallbackするようにした。Story indexのリンク先も自動的に追従（リンクtext優先順位は変更なし）。Episode page SummaryにPublic Episode ID/Public Story ID（未設定時「未登録」）を追加。schemas（story/extraction/merged_knowledge_collection）に`publicStoryId`/`publicEpisodeId`を追加。**storyId/episodeId生成ロジック・Story manifest candidate builder・Character page pathは変更していない**。合成fixtureのみで検証、実データ未投入。
- **story manifest public id fields design**: `Story_ID_Policy_Decision.md`（PR #71）で採用した`publicStoryId`（story-level）/`publicEpisodeId`（episode-level）を`schemas/story_manifest.schema.json`（任意フィールド、既存ID同様`^[A-Z][A-Z0-9_]*$`パターン、null許容）・`agents/parser/story_manifest.py`（`StoryManifestStory.public_story_id`/`StoryManifestEpisode.public_episode_id`）へ実装した。`scripts/normalize_story.py`は`source.manifest.publicStoryId`/`publicEpisodeId`としてtraceability目的でのみNormalized Story JSONへ転記する。category別合成例（MAIN/EVENT/RAID/OTHER/CHARACTER）を`Story_Manifest_Design.md` §13.2に記載。**storyId/episodeId生成ロジック・URL/file path・renderer/paths.pyは変更していない**（renderer切替は後続PR`story-manifest-public-id-renderer-paths-switch`）。
- **story id policy design decision**: `Story_ID_Policy_Review.md`（PR #70）の比較結果を踏まえ、DKBが採用するID方針を`docs/architecture/05_Parser/Story_ID_Policy_Decision.md`で正式決定した。既存`storyId`/`episodeId`は当面維持、将来の公開Wiki URL用IDを`publicStoryId`/`publicEpisodeId`として`story_manifest.yaml`側に分離する方針を採用（次PRで設計）。category別方針・採用しない案（title/subtitle由来URL含む）・migration方針（additive first）を確定した。**ID生成ロジック・schema・URL/file pathの実装変更はしていない**（設計決定のみ）。
- **story id policy real sample review**: 実データ小規模サンプル（EVENT 5件相当、匿名化）をもとに、Story ID/Episode ID/URL path方針をレビューし`docs/architecture/05_Parser/Story_ID_Policy_Review.md`を新設した。現行`EVT_{sourceKey}`方式・date+sequence案・manifest-assigned stable ID案・category-specific policy案の4案を評価軸付きで比較し、「今すぐ全面移行しない、raw traceability用IDと公開URL用IDを次PRで分離設計する」ことを推奨した。**ID生成ロジック・URL/file pathの実装変更はしていない**（設計レビューのみ）。
- **wiki story index link text improvement**: Story indexのEpisode列を、`episodeId`中心のリンクテキストから`displayTitle > episodeSubtitle > storyTitle > episodeId`優先の人間向けタイトルへのリンクへ変更した（`_episode_link_text`/`_get_episode_display_title`/`_first_non_blank`）。空文字列・whitespaceのみの値は未登録扱いとしてfallbackする。Episode link textと重複していた独立の「Display Title」列を廃止し、input validation status（valid/invalid）列はmetadataStatus表示へ置き換えた（Episode page側のValidation sectionで引き続き確認可能）。titleに`|`/`[`/`]`が含まれる場合の最小限のMarkdown escapeも追加した。episodeId/URL/ファイル名（`stories/{episodeId}.md`）は変更していない。合成fixtureのみで検証、実データ未投入。
- **speaker label normalization**: `name`コマンド/`@ChTalkName`由来のspeaker labelを`agents/parser/speaker_labels.py`で構造化（speaker_group/speaker_with_modifier/generic_speaker/ambiguous_speaker等）し、通常のCharacterCandidate/Character merged entityとは別枠（`specialSpeakerLabelCandidates`/`entities.specialSpeakerLabels`）で扱うようにした。confirmed character dictionaryとの参考照合（`inferredSpeakers`）はあるが自動でconfirmed昇格はしない（resolutionStatusは`inferred`/`needs_review`のみ自動付与）。Unresolved reportに「Special Speaker Labels」sectionを追加し、通常のUnresolved Charactersとは重複しない。`characters.yaml`は変更なし。合成fixtureのみで検証、実データ未投入。
- **mkdocs manual visual review 002**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、うち1件にPR #62表示確認用のtitle/subtitle/metadataStatus=confirmedを設定）でPR #64〜#66の改善（Characters index導線・特記事項`【label】value`表示・profile source非表示・Story index/Unresolved reportの列数削減・Episode Summary箇条書き化）をすべて実データで確認した。`workspace/wiki_preview/manual_review_002/`・`manual_review_002_site/`へ保持（**commit対象外**）。source text exposure check問題なし。`mkdocs serve`（`http://127.0.0.1:8125/`）経由でcurl確認、実装変更なし。ユーザーの実ブラウザ目視確認待ち。
- **wiki renderer readability improvements**: manual visual review 001の「表が横長すぎる」指摘を受け、Story index（7列→5列、documentId/candidate合計を削除）・Episode page（Summary tableを箇条書きへ変更、ID類はcode表示）・Unresolved report（entity種別別表を6列→5列、Evidence/Source CandidatesをRefs列へ統合）を改善した。既存情報は削除せず、Episode page側詳細セクション等で引き続き確認可能。Characters index・profileHighlight表示・profile source非表示（PR #64/#65）は変更していない。合成fixtureのみで検証。
- **wiki character profile display refinement**: Character pageの基本プロフィール表を整理した。`profileHighlight`は独立sectionを廃止し表内「特記事項」行として`【label】value`形式（例:`【好きなこと】食べ歩き`）で表示、label/valueいずれか欠落時も安全にfallbackする。profile source（出典）はCharacter page上から非表示にした（`character_profiles.yaml`側のsource情報自体は削除せず保持）。実プロフィールデータは変更していない、合成fixtureのみで検証。
- **wiki character index page**: `characters/index.md`を新設し、Top page→Characters index→Character pageの導線を追加した。`is_page_eligible`なcharacterのみ一覧表示（unresolved/canonicalIdなし/status不一致は載せない）、Overview（Character pages/プロフィール登録あり・なし件数）とCharacter名・Profile Status・IDの3列のみの表（横長table問題を踏まえ列数を最小限に抑制）。profile表示の細部修正・Story indexリンクテキスト改善は別PRへ持ち越し。合成fixtureのみで検証、実データ未投入。
- **mkdocs manual visual review 001**: 実データ小規模サンプル（EVENTカテゴリ1件・episode2件、うち1件にPR #62表示確認用のtitle/subtitle/metadataStatus=confirmedを設定、もう1件はpending/未設定のまま）からWiki Markdown・MkDocs HTMLを生成し`workspace/wiki_preview/manual_review_001/`・`manual_review_001_site/`へ保持（**commit対象外**）。Story Title/Episode Subtitle/Display Title/Metadata Status表示・Story indexのDisplay Title列・Basic Profile section（登録あり/なし）・Related Charactersリンクをいずれも`mkdocs serve`経由で確認。source text exposure check問題なし。実装変更なし。**Manual visual reviewは`mkdocs serve`（`http://127.0.0.1:8124/`）を使うこと。`file://`で`index.html`を直接開くと、directory-style URL（`use_directory_urls: true`、既定）のリンクがディレクトリ一覧表示になる（実際にユーザー環境で発生・確認済み）。file直接閲覧が必要な場合は、専用設定で`use_directory_urls: false`を検討すること。** ユーザーによる実ブラウザ目視確認の結果、5件の改善候補（character index page欠如・Story indexのepisodeId露出・storyId/episodeId形式・table可読性・character profile表示統合）とMkDocs Material長期利用方針の検討事項が見つかった（実装はまだ行っていない、詳細はNext/Backlog/Known Issues参照）。
- **project context compaction**（PR #61）: 肥大化した`AI_CONTEXT.md`/`TASKS.md`を圧縮し、完了済みPR履歴を`docs/project_history/`へ分離。

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
