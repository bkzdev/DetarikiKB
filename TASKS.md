# TASKS

作業TODO管理用ファイル。`AI_CONTEXT.md`はプロジェクトの設計思想・仕様・引き継ぎ情報を扱い、こちらは「今何をしていて、次に何をするか」の作業状態を扱う。

完了済みPRの詳細な作業ログ・テスト件数・diff statは `docs/project_history/Completed_PRs_2026-07.md` に移した。ここには重複記載しない。作業を開始・完了・変更するたびに、該当する章を更新すること。

---

## Current Focus

- `feature/evidence-index-generation-dry-run`: Normalized Story JSON/Extraction ResultからPublic Evidence Index候補を生成するdry-run手順と最小scriptを検証した。`scripts/build_evidence_index_candidates.py`を追加し、Block単位（`dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`、既存Block IDがあるもののみ）でEvidence entryを生成、`text`/`rawText`/`raw`/`rawCommand`/`args`等の本文系フィールドは値を一切読み取らない（存在検知でreportにカウントのみ）。speakerは`isResolved: true`かつ`speakerId`がある場合のみ（`displayName`は常に`null`）、`--extractions`指定時のみExtraction Resultから`referencedBy.candidates`を補完する。生成candidateは内部で必ずschema検証+raw text禁止文字列検証を通し、失敗したstoryは書き出さない。出力先は`workspace/evidence_index_dry_runs/`（`.gitignore`へ追加）。実データ小規模サンプル（EVENTカテゴリ1story・episode2件、既存の匿名化サンプル`workspace/dry_runs/story_page_manual_review/`を再利用）で生成→`validate_evidence_index.py`→`render_wiki.py --evidence-index`まで確認し、生成YAML/report/Evidence pageいずれも非ASCII文字が「未登録」等の定型プレースホルダーのみであることを確認した（実データ本文・raw command・local pathの混入なし）。`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`を新設した。**Scene/Episode/Story単位の粗い粒度のEvidence entry・`speaker_label`のevidenceType対応・Story Summaryとの`referencedBy.summaries`連携・Internal Review Evidence Packet生成・`knowledge/evidence/stories/`への自動昇格は行っていない**（次候補`evidence-index-generation-review`/`internal-review-evidence-packet-design`）。合成fixture（`tests/fixtures/normalized_story/build_evidence_index_candidates/`・`tests/fixtures/extraction/build_evidence_index_candidates/`）とテスト21件を追加、実データ生成物は未commit。
- `feature/evidence-index-renderer-integration`: PR #83で実装したEvidence Index loader/schemaをWiki rendererに統合した。`scripts/render_wiki.py`に`--evidence-index <path>`（file/directory対応）を追加し、Evidence Index検証（schema + raw text禁止文字列 + `rawTextIncluded`）は`--validate`フラグの有無に関わらず常に実行する（安全性優先の設計判断）。`agents/wiki_generator/paths.py`に`evidence_page_path`（`evidence/{publicStoryId or storyId}.md`、Story別1ページ）、`agents/wiki_generator/evidence_index.py`に`EvidenceIndexLookup`/`build_evidence_index_lookup`/`resolve_group_public_story_id`を追加した。`render_evidence_page`でStory別Evidence pageを生成し、表示項目はType/Episode ID/Public Episode ID/Scene ID/Block ID/Speaker/Related Entities/Referenced byのみ（raw text/raw DEC command/raw path/generatedFrom詳細/inputRefs詳細/extraction JSON dump/normalized block dump/prompt/LLM生出力/workspace pathはいずれも非表示）。Story pageの「Review Links」sectionに該当storyのEvidence Indexが存在する場合のみEvidence pageへのリンクを追加し（存在しなければUnresolved report導線のみ従来通り）、Story Summary/Episode Summaryの`evidenceRefs`は該当`evidenceId`がEvidence Indexに存在すればEvidence pageの該当anchorへのMarkdownリンクへ、存在しなければ従来通りID表示のまま（非エラー）とした。**Evidence top page（`evidence/index.md`）・Evidence Index自動生成（Normalized Story JSON/Extraction Resultから）・Internal Review Evidence Packet生成・Episode pageへの変更は行っていない**（次候補`evidence-index-generation-dry-run`/`internal-review-evidence-packet-design`）。既存fixtureとクロス参照する新規fixture（`tests/fixtures/evidence_index/renderer_integration/`）を追加、実データ未投入。
- `feature/evidence-index-schema-implementation`: `docs/architecture/06_AI/Evidence_Index_Design.md`（PR #82）の設計を実装した。`schemas/evidence_index.schema.json`（`evidenceIndexVersion`/`entries`必須、entry側は`evidenceId`/`evidenceType`/`storyId`/`episodeId`/`visibility`必須、`visibility.rawTextIncluded`は`const: false`固定）、`agents/wiki_generator/evidence_index.py`（load/build_evidence_id_index/group_entries_by_story/group_entries_by_public_story/group_entries_by_episode/group_entries_by_public_episode等のloader、raw text禁止文字列検出・duplicate evidenceId検出を含むvalidation）、`scripts/validate_evidence_index.py`（schema検証・整合性検証CLI）、`docs/templates/evidence_index_template.yaml`、`tests/fixtures/evidence_index/`（合成fixture、無効例は`invalid_examples/`配下で非再帰的走査から除外）を追加した。保存場所は`knowledge/evidence/stories/{storyId}.yaml`を採用、`.gitkeep`のみで実データ未投入。**Evidence page renderer実装・Story Summary/Episode SummaryのevidenceRefsリンク化・Normalized Story JSON/Extraction Resultからの自動生成は行っていない**（次PR`evidence-index-renderer-integration`/`evidence-index-generation-dry-run`）。
- `feature/story-summary-evidence-index-design`: `evidenceRefs`（PR #81）の将来リンク先となるEvidence indexの設計を`docs/architecture/06_AI/Evidence_Index_Design.md`にまとめた。Public Evidence Index（raw textを含まない公開用索引）とInternal Review Evidence Packet（内部review用、`workspace/review_packets/evidence/`・commit禁止）を分離。raw dialogue text/raw DEC command/local pathは非表示方針。source of truthはDedicated Evidence Index file（Normalized Story JSON/Extraction Resultから安全な情報のみ抽出）を採用、Merged CollectionやSummaryはEvidence indexを参照する側と位置づけた。evidenceType（dialogue/monologue/narration/choice/stage_direction/speaker_label/scene/episode/story/unknown、10種で固定）・data model草案・Evidence ID link方針（初期推奨: Story別Evidence page `evidence/{publicStoryId or storyId}.md`）・Story page/Episode page/Summary/Unresolved reportとの関係・AI Analysis/Speculationとの分離方針を設計した。実装フェーズ案（Phase 1設計のみ〜Phase 5 internal review packets）を整理。**本PRではschema実装・renderer実装・Evidence page生成・リンク化は行っていない**（設計docsのみ、次PR`evidence-index-schema-implementation`）。
- `feature/story-summary-evidence-display`: Story page上の表示可能なStory Summary/Episode Summary本文の下に、対応する`evidenceRefs`をIDのみ短く表示するようにした（`agents/wiki_generator/renderer.py`の`_render_evidence_refs_line`、`Evidence refs: `ID1`, `ID2``形式）。表示対象条件はPR #80と同じ（`review.status`がreviewed/approved かつ `generationStatus`がgenerated）で、非表示Summaryは本文同様evidenceRefsも表示しない。evidenceRefsが空の場合は何も表示しない（案A、Summary本文の邪魔にならないことを優先）。renderer側でも非list値・非文字列・空文字列・重複を安全に処理する。**Episode pageへの表示・Evidence indexへのリンク化・Evidence index本体の実装は行っていない**（次候補`story-summary-evidence-index-design`）。既存fixture（`tests/fixtures/story_summaries/renderer_integration/`）にevidenceRefsを追加し、テスト18件（renderer）+1件（CLI）を追加、実データ未投入。
- `feature/story-summary-renderer-integration`: `docs/architecture/06_AI/Story_Summary_Design.md`（PR #78/#79）の設計・実装を踏まえ、Story Summary/Episode SummaryをWiki rendererへ統合した。`scripts/render_wiki.py`に`--story-summaries <path>`（file/directory対応、`--validate`/`--character-profiles`と併用可）を追加し、`agents/wiki_generator/story_summaries.py`に`StorySummaryLookup`/`resolve_story_summary`/`resolve_episode_summary`/`get_displayable_story_summary`/`get_displayable_episode_summary`/`is_document_displayable`を追加した。`is_displayable_summary`を`generationStatus`（`generated`のみ表示）も判定できるよう拡張（既存呼び出しとの後方互換は維持）。`storyId`優先→`publicStoryId`、`episodeId`優先→`publicEpisodeId`で照合し、矛盾時は非表示（安全側）。`review.status`が`reviewed`/`approved`かつ`generationStatus`が`generated`のSummaryのみStory pageの`## Story Summary`/`## Episode Summaries` placeholderを実本文へ差し替え、それ以外（unreviewed/rejected/needs_revision/draft/deprecated/未登録）は従来通り「未生成」。**Episode page/Character page/Characters index/Unresolved reportは変更していない**。evidenceRefs表示・AI要約生成は行っていない（次候補`story-summary-evidence-display`）。合成fixture（`tests/fixtures/story_summaries/renderer_integration/`）とテスト（renderer 29件・loader追加24件・CLI 8件）で確認、実データsummary未投入。
- `feature/story-summary-schema-implementation`: `docs/architecture/06_AI/Story_Summary_Design.md`（PR #78）の設計を実装した。`schemas/story_summary.schema.json`（1 story 1 file、`storyId`/`language`/`generationStatus`/`episodeSummaries`/`source`/`review`必須）、`agents/wiki_generator/story_summaries.py`（load/index/find/`is_displayable_summary`等のloader）、`scripts/validate_story_summaries.py`（schema検証・duplicate storyId/publicStoryId/episodeId/publicEpisodeId検出・raw/source text禁止文字列検出・`--require-reviewed`）、`docs/templates/story_summary_template.yaml`、`tests/fixtures/story_summaries/`（合成fixture、無効例は`invalid_examples/`配下で非再帰的走査から除外）を追加した。`knowledge/summaries/stories/`は`.gitkeep`のみで実データsummaryは未投入。`.gitignore`に`workspace/summary_drafts/`を追加した。**renderer統合（`render_wiki.py --story-summaries`等）・Story page rendererの変更・AI要約生成は行っていない**（次PR`story-summary-renderer-integration`）。
- `feature/story-summary-schema-design`: Story page（PR #76）のStory Summary/Episode Summary「未生成」placeholderを実データで置き換えるための設計を`docs/architecture/06_AI/Story_Summary_Design.md`にまとめた。Summaryは(A) Story Summary/(B) Episode Summary/(C) AI Analysis・Speculationを区別し、(C)はSummary schemaに混ぜない方針。保存場所は`knowledge/summaries/stories/{storyId}.yaml`（1 story 1 file）を採用、draftは`workspace/summary_drafts/`側でreviewしてから昇格する運用とした。生成ステータス（`missing`/`draft`/`generated`/`deprecated`）とレビューステータス（`unreviewed`/`reviewed`/`approved`/`rejected`/`needs_revision`）を分離し、`review.status`が`reviewed`/`approved`のもののみcommit・Wiki表示対象とする。`evidenceRefs`は任意保持可（Episode単位のevidenceId体系のまま、rawテキストは含めない）。**本PRではschema実装・renderer統合・AI要約生成は行っていない**（設計docsのみ）。
- `feature/story-page-manual-review`: `feature/wiki-story-page-renderer`（PR #76）で実装したStory page中心の導線を、実データ小規模サンプル（EVENTカテゴリ1件・episode2件、匿名化）でStory index→Story page→Episode pageまで`mkdocs serve`（`http://127.0.0.1:8127/`）で目視確認できる状態にした。episode1に合成`publicStoryId`/`publicEpisodeId`・合成title/subtitleを付与、episode2は`publicEpisodeId`未設定のままfallback確認用に残した。Story page Overview/Story Summary placeholder/Episode Summaries placeholder/Episode list/Related Characters集約/Review Links、Characters index/Character page/Unresolved report/Special Speaker Labelsいずれも表示・リンクとも問題なし。`workspace/wiki_preview/story_page_manual_review/`・`_site/`へ保持（**commit対象外**）。source text exposure check問題なし（`episodeId`にsourceKey由来語が残る既知課題のみ、本PRのscope外）。実装変更なし。ユーザーの実ブラウザ目視確認待ち。
- `feature/wiki-story-page-renderer`: `Story_Page_Design.md`の設計を踏まえ、Story pageを`agents/wiki_generator/renderer.py`に実装した（`render_story_page`、`story_page_path`/`resolve_story_path_id`）。`sourceDocuments`を`storyId`でグルーピングし、Story index（`| Story | Episodes | Status | Category |`、リンクtextは`storyTitle > publicStoryId > storyId`）→Story page（Overview・Story Summary placeholder「未生成」・EpisodeごとのEpisode Summary placeholder・Episode一覧・Related Characters集約・Unresolved report導線）→Episode pageという導線を実装した。`publicStoryId`があればStory page filenameに使い、無ければ`storyId`へfallback（短期URL構造は候補A、flat維持）。**Episode pageは変更していない**（`episode_page_path`・`publicEpisodeId`fallback方針はPR #73のまま）。AI要約生成・Story summary schemaはまだ実装していない。

## Next

直近5件程度。着手前にユーザーへ確認する。

1. **evidence-index-generation-review**: dry-run生成したEvidence Index候補の妥当性レビュー運用（speaker解決の正確性・relatedEntities過不足の確認手順等）を検討する
2. **internal-review-evidence-packet-design**: raw textを含みうるInternal Review Evidence Packetの詳細設計を検討する
3. **story-summary-generation-planning**: AI要約生成パイプライン（LLM provider/prompt設計）の着手時期・方式を検討する
4. **public-publishing-platform-evaluation**: public publishing workflow着手前に、MkDocs Material継続/MkDocs標準テーマ・別テーマ/Docusaurus/VitePress・Astro/独自HTML rendererを再評価する
5. **evidence-index-promotion-policy**: dry-run候補を`knowledge/evidence/stories/`へ昇格させる正式な運用（誰が・どの基準で承認するか）を検討する

---

## Backlog

### Parser / Story Manifest

- イベント番号の正式な採番ルール
- `displayOrder`の正式計算式、`canonicalOrder`の扱い
- **story manifest candidate builder**: `scripts/build_story_manifest_candidates.py`を実際のローカルraw DEC配置に対して実行し、生成候補を人間が確認する
- **story-manifest-public-id-nested-path**: Story/EpisodeのURLを現行フラット構成`stories/{episodeId}.md`からネスト構成`stories/{storyId}/{episodeId}.md`へ移行するかの検討（`publicStoryId`のWiki出力への活用含む、`Story_Page_Design.md` §10 候補C・Wiki_Output_Design.md §14）
- **public-id-manifest-assignment-policy**: `publicStoryId`/`publicEpisodeId`の採番・割当運用（人間手動 vs 半自動）を正式に決める
- story-summary-schema-design（Next参照）
- **story-title-subtitle-candidate-builder-real-trial**: `scripts/build_story_title_subtitle_candidates.py`を実際のWiki/CSV入力に対して実行し、生成候補を人間が確認する
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
- **evidence-index-generation-review**（Next参照）
- **evidence-index-promotion-policy**（Next参照）
- **internal-review-evidence-packet-design**（Next参照）
- **episode-page-evidence-linking-review**: Episode pageへのEvidence/Summary導線追加可否をレビューする（`evidence-index-renderer-integration`/`evidence-index-generation-dry-run`いずれもEpisode pageは無変更のまま）
- **mkdocs-manual-visual-review-002**: ユーザーによる`uv run mkdocs serve -f workspace/wiki_preview/manual_review_002/mkdocs_manual_review.yml -a 127.0.0.1:8125`起動後、`http://127.0.0.1:8125/`でのブラウザ目視確認
- **wiki-story-index-link-text-real-sample-review**: 実データ小規模サンプルでEpisode link text優先順位・metadataStatus表示を確認する
- **speaker-label-normalization-real-sample-review**: 実データ小規模サンプルでspeaker group/generic speaker検出の網羅性・誤検出を確認する（合成fixtureのみのため後続作業）
- Wiki Page Template
- relationship section renderer、Location/Organization/Item/Lore/Event page等のPhase 2実装

### Character Dictionary / Profiles

- **character profile import batch 002**: unmatched 200件のうち、displayName表記ゆれ解消やconfirmed化が進んだ分の人間確認済みcandidateを再照合し追加投入する
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

- **evidence index generation dry-run**: `scripts/build_evidence_index_candidates.py`を追加し、Normalized Story JSON（任意でExtraction Resultも）からPublic Evidence Index候補YAMLをdry-run生成できるようにした。Block単位（既存Block IDがあるもののみ）でEvidence entryを生成し、本文系フィールドは値を一切読み取らない。生成candidateは内部で必ずschema+raw text禁止文字列検証を通し、失敗したstoryは書き出さない。実データ小規模サンプルで生成→validate→render確認まで実施し、非ASCII文字の混入が定型プレースホルダーのみであることを確認した。`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`新設。**Scene/Episode/Story単位の粗い粒度のEvidence entry・Internal Review Evidence Packet・`knowledge/evidence/stories/`への自動昇格は行っていない**（次候補`evidence-index-generation-review`/`evidence-index-promotion-policy`）。テスト21件追加、実データ生成物は未commit（`workspace/evidence_index_dry_runs/`を`.gitignore`へ追加）。
- **evidence index renderer integration**: PR #83のEvidence Index loader/schemaをWiki rendererに統合した。`render_wiki.py --evidence-index <path>`（常時schema検証+raw text/rawTextIncluded検証）、`evidence_page_path`、`render_evidence_page`でStory別Evidence page生成（安全な項目のみ表示）、Story page Review LinksへのEvidence導線、Story/Episode Summary `evidenceRefs`のEvidence pageへのリンク化（未解決は従来通りID表示）を実装した。**Evidence top page・自動生成・Internal Review Evidence Packet・Episode page変更は行っていない**（次候補`evidence-index-generation-dry-run`/`internal-review-evidence-packet-design`）。テスト追加（renderer/CLI/path/lookup）、実データ未投入。
- **evidence index schema implementation**: `Evidence_Index_Design.md`（PR #82）を実装した。`schemas/evidence_index.schema.json`・`agents/wiki_generator/evidence_index.py`（loader/validator、storyId/publicStoryId/episodeId/publicEpisodeId別groupingヘルパー含む）・`scripts/validate_evidence_index.py`（CLI）・`docs/templates/evidence_index_template.yaml`・合成fixture（`tests/fixtures/evidence_index/`）を追加した。`evidenceType`10種enum・`visibility.rawTextIncluded`の`const: false`固定・raw text禁止文字列検出（`.dec`/`@ChTalk`等）・duplicate evidenceId検出を実装。保存場所は`knowledge/evidence/stories/{storyId}.yaml`を採用、`.gitkeep`のみで実データ未投入。**Evidence page renderer実装・evidenceRefsリンク化・Normalized Story JSON/Extraction Resultからの自動生成は行っていない**（次PR`evidence-index-renderer-integration`/`evidence-index-generation-dry-run`）。テスト96件追加（schema44・loader/validator42・CLI10）。
- **story summary evidence index design**: `evidenceRefs`の将来リンク先となるEvidence indexの設計を`docs/architecture/06_AI/Evidence_Index_Design.md`にまとめた。Public Evidence Index（raw text非公開の索引）とInternal Review Evidence Packet（`workspace/review_packets/evidence/`・commit禁止）を分離し、raw dialogue text/raw DEC command/local pathを表示しない方針を明記。source of truthはDedicated Evidence Index file（Normalized Story JSON/Extraction Resultから安全な情報のみ抽出）を採用。evidenceType 10種固定・data model草案・Evidence ID link方針（初期推奨: Story別Evidence page）・Story page/Episode page/Summary/Unresolved reportとの関係・AI Analysis/Speculationとの分離方針を整理し、Phase 1〜5の実装フェーズ案を示した。**本PRではschema実装・renderer実装・Evidence page生成・リンク化は行っていない**（設計docsのみ、次PR`evidence-index-schema-implementation`）。
- **story summary evidence display**: Story pageの表示可能なStory Summary/Episode Summary本文の下に、対応する`evidenceRefs`をIDのみ短く表示するようにした（`_render_evidence_refs_line`、`Evidence refs: `ID1`, `ID2``形式）。表示対象はPR #80と同じ条件、evidenceRefsが空の場合は何も表示しない方針（案A）を採用。**Episode pageへの表示・Evidence indexへのリンク化・Evidence index本体は未実装**（次候補`story-summary-evidence-index-design`）。既存fixtureにevidenceRefsを追加、テスト19件追加、実データ未投入。
- **story summary renderer integration**: Story Summary/Episode SummaryをWiki rendererへ統合した。`render_wiki.py --story-summaries <path>`を追加し、`agents/wiki_generator/story_summaries.py`にresolve/get系helper（`StorySummaryLookup`/`resolve_story_summary`/`resolve_episode_summary`/`get_displayable_story_summary`/`get_displayable_episode_summary`/`is_document_displayable`）を追加。`is_displayable_summary`を`generationStatus`判定込みに拡張（後方互換維持）。`review.status`がreviewed/approvedかつ`generationStatus`がgeneratedのSummaryのみStory pageへ表示、storyId/episodeId優先→publicStoryId/publicEpisodeIdで照合し矛盾時は非表示。**Episode page/Character page/Characters index/Unresolved reportは無変更**、evidenceRefs表示・AI要約生成は未実装。合成fixtureとテスト61件追加で確認、実データ未投入。
- **story summary schema implementation**: `Story_Summary_Design.md`（PR #78）を実装した。`schemas/story_summary.schema.json`・`agents/wiki_generator/story_summaries.py`（loader/validator）・`scripts/validate_story_summaries.py`（CLI、`--require-reviewed`でreviewed/approved以外をエラーにできる）・`docs/templates/story_summary_template.yaml`・合成fixture（`tests/fixtures/story_summaries/`）を追加した。生成ステータスフィールドは`review.status`との混同を避けるため`generationStatus`に改名。`knowledge/summaries/stories/`は`.gitkeep`のみで実データ未投入、`workspace/summary_drafts/`を`.gitignore`に追加した。**renderer統合・Story page renderer変更・AI要約生成は行っていない**（次PR`story-summary-renderer-integration`）。
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
