# AI_CONTEXT

Project: Detariki Knowledge Base (DKB)  
Recommended path: `AI_CONTEXT.md`  
Audience: Antigravity / Claude Code / GPT-OSS120B / future AI coding agents  
Language policy: Documentation in Japanese, code/data keys in English

---

# 1. このファイルの目的

このファイルは、Detariki Knowledge Base（DKB）プロジェクトを別AI・別チャット・別開発環境へ引き継ぐためのコンテキストファイルである。

このプロジェクトに参加するAIエージェントは、作業開始前に必ずこのファイルを読むこと。

---

# 2. プロジェクト概要

Detariki Knowledge Base（DKB）は、ゲーム「デタリキZ」のストーリー全文データを解析し、以下を自動生成・管理するためのKnowledge Baseである。

- 各話の概要
- 登場人物まとめ
- キャラクター情報
- 人物関係
- 組織情報
- 場所情報
- 用語集
- 時系列
- 伏線
- 矛盾点
- AI考察
- Wiki形式ページ
- Knowledge Graph
- 将来の検索・AI参照用データ

重要な設計思想:

```text
Wikiを直接作るのではなく、
Knowledge Baseを作り、
Wikiはその成果物として生成する。
```

Knowledge Baseを唯一のSource of Truthとする。

---

# 3. 現在の目的

目標のパイプライン全体:

```text
Raw Script
  ↓
Story Parser
  ↓
Normalized Story JSON
  ↓
JSON Schema Validation
  ↓
AI Extraction / Knowledge Graph / Wiki Generation
```

## 3.1 現在のフェーズ

**Parser Phase 1は完了した**（`agents/parser/` 一式・`schemas/story.schema.json`・compatibility checker・テスト、`.dec` サンプルでの検証まで実装済み。mainへマージ済み）。

現在は **Extraction Phase**。`Extraction_Pipeline.md`（パイプライン全体設計）・`Extraction_Result_Schema.md`（出力フィールド設計）・`schemas/extraction.schema.json` 系（validator・fixture・テスト）まで完了し、mainへマージ済み。

`agents/extractor/` は最小skeleton（Normalized Story JSONから`episode_extraction`の構造とevidenceIndexを生成、LLM呼び出しなし）、semantic validation（`agents/extractor/validator.py`: evidenceIds実在確認、duplicate candidate id検出、empty evidenceIndex検出、extractionRun整合性確認、relationship基本チェック、timeline基本チェック。`scripts/validate_extraction_json.py --semantic`から利用可能）、`CharacterCandidate`/`LocationCandidate`/`OrganizationCandidate`/`ItemCandidate`/`LoreCandidate`/`EventCandidate`/`RelationshipCandidate`のrule-based最小抽出（構造的な手がかりのみ、本文の自然文推定は行わない、LLM不使用）まで実装済み・mainへマージ済み。抽出ロジックはCandidate種別ごとに`agents/extractor/character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`/`relationship.py`/`timeline.py`へ分割済み（`base.py`が共通ヘルパー、`extractor.py`はオーケストレーションのみ）。`RelationshipCandidate`はBlock上の明示的な`relationshipType`+source/targetペア、および`speakerAssignments`の明示的な`organizationId`/`affiliation`（Character→OrganizationのMEMBER_OF/AFFILIATED_WITH）のみを対象とする。`TimelineCandidate`はepisode.metadataの明示的な`canonicalOrder`/`releaseOrder`/`displayOrder`、Block上の明示的な`timelineId`/`timelineLabel`/`timePosition`/`orderValue`、stage_direction等の明示的な`flashback`/`flashforward`/`dayChange`/`timeShift`/`sceneTime`構造フィールドのみを対象とする。Stage A（全8種Candidate）の設計・schema・実装・semantic validation・CLI・テストの整合性は横断レビュー済み（全8種共存の統合テスト追加・古いdocstring修正まで。不整合は無し、mainへマージ済み）。

**Stage A candidate extractionは完了。Stage B（Merged Knowledge）は設計書・schema（entity単位・collection単位）・merge engine（単一/複数入力）・全8種Candidateの最小merge・manual override loader・merge report強化・relationshipType taxonomy・canonical ID policy・real data dry-run procedure・no invisible unicode check・real data dry-run trial・script command coverage improvement・character dictionary coverage improvement・compatibility check consistency・branch / choice included dry-run・ruff known issues cleanup・script command coverage followup・GitHub Actions CI・character dictionary confirmed review workflow・character dictionary reference JSON import batch 001・wiki output design・wiki renderer skeleton・character page renderer expansion・episode page renderer expansion・unresolved report renderer refinement・real data wiki render dry-run・real data merged collection dry-run・character dictionary confirmed batch 002・character dictionary review packet・character dictionary confirmed batch 003・character profile schema design・character profile wiki import pipeline完了→次は正しいメンバー一覧テーブルURLの特定・character profile import batch 001（実プロフィール投入）・character profile renderer section（Wiki実装）・character dictionary confirmed batch 004（残る未確認10件）・relationship section renderer・Location/Organization/Item/Lore/Event page等のPhase 2実装・`agents/parser/parser.py::_parse_tokens`のparse state dataclassリファクタ待ち**。character profile wiki import pipelineでは、デタリキZ攻略Wikiのメンバー一覧テーブルから`character_profiles.yaml`へ投入可能な中間形式（import candidate）を取得・変換・照合する仕組みを追加した（**character_profiles.yamlへの実プロフィール投入は行っていない**）。`agents/parser/character_profile_wiki_import.py`（新規、標準ライブラリの`html.parser.HTMLParser`のみでHTMLテーブルを抽出、新規依存は追加せず）に、テーブル抽出・列見出し正規化（キャラ名/よみがな/所属/身長(cm)/誕生日/血液型/特記事項/CV、実装日等の対応項目が無い列は無視）・フィールドパーサー（heightCmは数字以外除去して整数化、birthdayは`month/day`形式を`{month,day,display}`に分解、profileHighlightは`【label】value`形式を分解しラベル無しは`label: "特記事項"`とする、selfIntroductionは一覧テーブルに存在しないため常にnull）・`match_candidates`（characters.yamlで**status: confirmed**のdisplayName完全一致のみを自動matchとし、name_only/未登録は`unmatched`として人間確認に回す、characterIdは自動生成しない）を実装した。CLI `scripts/import_character_profiles_from_wiki.py`（`--source-url`/`--input-html`排他・`--output`・`--format {yaml,csv,both}`・`--dry-run`）は、取得前に`urllib.robotparser`でrobots.txtを確認し（許可されない場合は安全側に倒して取得しない）、1ページのみ取得する（個別ページ巡回はしない）。`docs/runbooks/Character_Profile_Wiki_Import.md`（新規）に取得元・対応表・照合方針・自己紹介文を今回取得しない方針・人間確認後にimportする方針をまとめた。`.gitignore`に`workspace/profile_import/`等を追加した。実WIKI dry-runを1回実施したが、ユーザー提供の候補URLで取得したページはWikiのトップページ/目次相当であり、メンバー一覧テーブルを検出できなかった（個別ページ巡回・追加URL探索はせず、方針通り1回のみで留めた）。合成fixture（`tests/fixtures/character_profiles/synthetic_wiki_member_table.html`）では全機能を確認済み（confirmed一致のみmatch、name_only/未登録はunmatched、selfIntroduction常にnull、heightCm/birthday/profileHighlightの変換）。合成データのみで39件のテストを追加した。character profile schema designでは、`knowledge/dictionaries/characters.yaml`（ID解決用辞書）とは別に、公式プロフィール情報（読み仮名・所属・身長・誕生日・血液型・CV・キャラ別特記事項・自己紹介文）を管理する専用辞書`knowledge/dictionaries/character_profiles.yaml`の設計・schema・validator・helper・templateを整備した（**実キャラクターのプロフィールデータ投入は行っていない**、`profiles: []`の空辞書のみ）。`docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`（新規設計ドキュメント）に、characters.yamlとの役割分担・confirmed済みcharacterIdへの紐づけ方針（未confirmed・未登録characterIdへのプロフィール紐づけは検証エラー）・公式プロフィール/AI抽出/AI考察の分離方針・フィールドごとの扱いをまとめた。`schemas/character_profiles.schema.json`（characterId: `CHAR_[A-Z0-9_-]+`パターン必須、heightCmは整数、birthdayはmonth 1-12/day 1-31、profileHighlightはlabel/value必須でvalue maxLength 200、selfIntroductionはmaxLength 500）・`agents/parser/character_profiles.py`（`CharacterProfile`等のデータクラス、`load_character_profiles`/`validate_character_profiles`/`build_character_profile_index`/`get_character_profile`）・`scripts/validate_character_profiles.py`（CLI、schema検証→characters.yamlとの整合性検証の順）を実装した。`docs/templates/character_profiles_template.yaml`（合成データのみ、全フィールド埋まった例と最小例の2件）を追加し、実際の`characters.yaml`と照合すると架空IDのため意図的にエラーになることを確認した（クロスチェック機能が正しく動作する証拠）。`docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.4に「基本プロフィールsection」の表示方針を軽微追記したが、**Wiki renderer側の実装は行っていない**。合成fixtureのみで32件のテストを追加した（characters.yamlとの整合性チェック含む）。character dictionary confirmed batch 003では、`feature/character-dictionary-review-packet`で生成したreview packetを人間が確認し、`existingDictionaryStatus: name_only`だった12件（sourceCharacterId 5/8/24/29/35/70/203/207/208/209/216/217）について`knowledge/dictionaries/characters.yaml`をconfirmed化した（`characterId`はCHAR_{数値}_{ROMANIZED_NAME}形式、人間の希望により数値プレフィックスを採用。confirmed 2件→14件、name_only 64件→52件）。`existingDictionaryStatus: unknown`（displayName自体が「不明人物(ID:XXX)」で未判明）の10件はconfirmed化していない。`validate_character_dictionary`でVALIDATION: OK・`compare_character_dictionaries.py`でreference JSON差分0件を確認。実データ由来のraw `.dec`（6ファイル）を更新後の辞書で`normalize_story.py`から再normalize→`extract_story.py`→`merge_extractions.py`と再実行し、**`canonicalIdSummary.totalAssigned`が0件→12件に増加し、confirmed化した12件すべてがcanonicalId付きのmerged characterとして解決されることを確認**（conflict/warning/error 0件）。`render_wiki.py`も再実行し、12件全てのCharacter pageが新規生成されることを確認した（生成物はcommitせず）。`characters.yaml`のデータ変更のみでロジック変更が無いため新規回帰テストは追加していない。character dictionary review packetでは、batch 002で判明した「人間確認済みmapping入力が無いとconfirmed化できない」というボトルネックを解消するため、辞書のconfirmed化そのものは一切行わず、review packet生成の仕組みだけを整備した: `agents/parser/character_dictionary.py`に`build_character_review_packet`（merged knowledge collectionの`entities.characters`から、辞書でconfirmed済み（= entity自体もstatus: merged）のsourceCharacterIdを除外し、name_only・unknownのみを対象に、displayName/辞書の既存状態/observedCount（evidenceRefs件数）/appearedEpisodeCount/sourceDocumentCountと空のhumanReviewStatus: pending/humanConfirmedCharacterId: null/notes: ""プレースホルダーを組み立てる関数）を新規追加した。CLI `scripts/build_character_review_packet.py`（`--merged-collection`/`--dictionary`/`--output`/`--format {yaml,csv,both}`/`--batch-id`）を追加し、YAML/CSV両形式で書き出せるようにした。`docs/runbooks/Character_Dictionary_Review.md`に§12「review packet」を新設し、humanReviewStatusの4状態（pending/confirmed/rejected/needs_more_context）・confirmed-batchへの渡し方（`workspace/local_inputs/character_confirmed_batch_XXX.yaml`）を明文化した。`docs/templates/character_dictionary_review_packet_template.yaml`・`docs/templates/character_dictionary_confirmed_batch_input_template.yaml`（いずれも合成データのみ）を追加した。`.gitignore`に`workspace/review_packets/`・`workspace/local_inputs/`・`character_confirmed_batch_*.yaml`等を追加した際、テンプレートファイル名`character_confirmed_batch_input_template.yaml`が自分自身の追加した`character_confirmed_batch_*.yaml`パターンに誤って一致する不具合に気づき、`character_dictionary_confirmed_batch_input_template.yaml`へリネームして解消した。実データ（Normalized Story JSON 8ファイル）から`extract_story.py`→`merge_extractions.py`でmerged collectionを再生成し、`build_character_review_packet.py --format both`を実際に実行して22件のレビュー候補（YAML/CSV）が生成されることを確認した（生データ非混入をgrepで確認後、ローカルから削除・commitせず）。character dictionary confirmed batch 002では、**人間確認済みmapping（sourceCharacterId→characterId）が今回のセッションに提供されなかったため、`knowledge/dictionaries/characters.yaml`は一切変更していない**（AI推測・名前一致だけでのconfirmed化を禁止する`docs/runbooks/Character_Dictionary_Review.md` §9のルールに従う）。`scripts/check_character_dictionary_coverage.py`でローカルの実データ.decファイルに対するcoverageを再確認したところ、confirmed 2件/name_only 64件・unknownCount 11件・top unknown sourceCharacterId（234/225/230/222等、件数のみ）は前回セッション時点から不変であることを確認した。`--review-template-output`・`compare_character_dictionaries.py`（reference JSON差分0件）も動作確認のみ行い、生成物はローカルから削除・commitしていない。辞書に変更が無いため実データdry-runの再実行は行わず、既存の`feature/real-data-merged-collection-dry-run`（PR #45）の結果がそのまま現状を表す。既存の回帰テスト（`tests/parser/test_character_dictionary.py`・`tests/parser/test_character_dictionary_pipeline.py`）が本バッチで求められる検証パターン（duplicate ID検出、confirmed statusのcharacterId必須、confirmed mapping適用後のexistingCharacterId付与、unconfirmed mappingの非解決）をすべて既に網羅していることを確認し、新規テストは追加していない。real data merged collection dry-runでは、`docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`（Extractor実行手順・Merger実行手順・Wiki renderへ渡す手順をまとめた、`Real_Data_Dry_Run.md`と`Real_Data_Wiki_Render_Dry_Run.md`の橋渡し役の手順書）と`docs/runbooks/Real_Data_Merged_Collection_Dry_Run_Result_Template.md`（結果記録テンプレート）を新規追加した。ローカル環境に実データ由来のNormalized Story JSON（8ファイル、main/character/event/other/raidカテゴリ）が存在したため、`scripts/extract_story.py`（episodeごとに8回実行）→`scripts/merge_extractions.py`→`scripts/render_wiki.py`の一連のパイプラインを**実データで実行できた**。結果（抽象化した件数のみ）: extraction result合算characters 36/locations 6/他0件・extractionErrors 0件、merged entity counts characters 30/locations 6/他0件、conflict counts total 1件（field_value_conflict）、warning counts total 0件。**全キャラクター・場所がunresolvedのまま**（既知の課題＝キャラクター辞書の数値ID帯不足によるもの、本PRのスコープでは辞書拡充を行わない）で、relationships/timeline等は実データに構造化タグが無いため0件（既知の制約、TASKS.md参照）。Wiki render handoffも実施し、`render_wiki.py --validate --clean`がexit code 0・Markdown 11件生成（character page 0件は想定通り）。Extractor/Merger/Rendererいずれもエラー・クラッシュなく完走し、**今回新たに見つかった不具合は無かった**（PR #43/#44で追加した堅牢性がそのまま機能）ため、rendererへの追加修正・新規回帰テストとも不要だった。real data wiki render dry-runでは、`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`（Wiki render専用のdry-run手順書、`Real_Data_Dry_Run.md`のMerger以降を引き継ぐ）と`docs/runbooks/Real_Data_Wiki_Render_Dry_Run_Result_Template.md`（結果記録テンプレート）を新規追加し、`.gitignore`に`workspace/wiki_preview/`・`workspace/wiki_render/`・`site_src/`・`docs/wiki_generated/`・`generated/wiki/`を追加した。ローカル環境には実データ由来のNormalized Story JSONまでは存在したが、Extractor/Merger出力（`merged_knowledge_collection.json`）は生成されていなかったため、**実データでのWiki render dry-runは実施していない**（指示に従い、Extractor/Merger実行による新規merged collection作成で無理に用意することはしなかった）。代わりに既存の合成fixture（`tests/fixtures/wiki/synthetic_merged_collection.json`）での`render_wiki.py`実行確認に加え、`sourceDocuments`が空配列・`canonicalIdSummary`/`relationshipTypeSummary`が存在しない・entityの任意フィールドが欠落した縮退collection（新規`tests/fixtures/wiki/synthetic_minimal_collection.json`）で堅牢性を検証した。この検証で、`report.warnings`の長いメッセージ（200文字超）が切り詰められず全文表示される問題を発見し、`agents/wiki_generator/renderer.py`に`_truncate_message`/`_MAX_WARNING_MESSAGE_LENGTH`（200文字、超過分は末尾`...(省略)`）を追加して`_render_capped_list`から呼び出すようにした（`report.warnings`・`canonicalIdSummary.warnings`の両方に適用される）。他の縮退パターン（optional field欠落・None値・空配列・candidateCounts欠落・sourceDocuments空）はすべて既存実装のままクラッシュせず正しく動作することを確認した。回帰テストは`tests/wiki/test_wiki_renderer.py`に6件追加した。unresolved report renderer refinementでは、`render_unresolved_report`（`agents/wiki_generator/renderer.py`）に、Overview（unresolvedEntityCounts合計/conflictCounts.total/warningCounts.total/canonicalIdSummaryのinvalidCount・duplicateCount）・entity種別別表へのCanonical ID列・Source Candidates件数列追加・Conflict Summary（`conflictCounts.bySeverity`/`byType`/`byEntityType`）・Warning Summary（`warningCounts`と`warnings`先頭10件）・Canonical ID Summary（`canonicalIdSummary`、任意フィールドのため無ければ省略）・Relationship Type Summary（`relationshipTypeSummary`、`unknownTypes`を見出し付きで一覧表示するのみで自動修正はしない、任意フィールドのため無ければ省略）を追加した。既存の`is_page_eligible`をそのまま流用し、canonicalId確定+status:mergedのentityのみ個別ページ対象外（Unresolved report集約）とする判定は変更していない。合成fixtureに`REL_TEST_UNKNOWN`（unresolved relationship）・`TL_TEST_UNKNOWN`（unresolved timeline entry）・`CHAR_TEST_DEPRECATED`（canonicalId確定済みだがstatus: deprecatedで非page-eligibleとなるケースの検証用）を追加し、`relationshipTypeSummary.unknownTypes`・`canonicalIdSummary.warnings`にも値を追加した。§9.13〜9.15（Conflict/Relationship type/Canonical ID report page）は独立ページとして構想されていたが、今回はUnresolved report内のセクションとして統合実装した（独立ページ化は未確定）。evidence/sourceCandidatesは件数のみ表示し元セリフ全文・raw payloadは含めない方針を踏襲した。episode page renderer expansionでは、`render_episode_page`（`agents/wiki_generator/renderer.py`、シグネチャを`(source_document, collection)`に変更）にCandidate Counts表（8種ラベル付き）・Related Characters summary（`evidenceRefs.episodeId`/`sourceCandidates.episodeId`/`extractionRunRefs`のいずれかでepisodeIdに一致するcharacterを列挙、canonicalIdがあれば`` `CHAR_XXX` ``、unresolvedなら内部idと`unresolved`表記）・Validation（`report.inputResults`をsourceDocumentの`path`で突き合わせられた場合のみinput status/errors/warnings件数を表示）のセクションを追加した。front matterに`page_type: "episode"`（entity_typeとは区別）・`episode_id`/`story_id`/`document_id`を追加し、`source_path`は漏洩懸念からfront matterに含めずSummary表のみに表示する。`render_story_index_page`にもdocumentId・candidate合計・status列を追加した。合成fixture（`sourceDocuments`を`EP_TEST_001`/`EP_TEST_002`の2件に拡張、`EP_TEST_002`はwarnings付きinputResultで検証）のみで確認し、実データ由来Wikiページは生成・commitしていない。character page renderer expansionでは、`render_character_page`（`agents/wiki_generator/renderer.py`）にAliases（全件列挙、空なら「別名は登録されていません。」）・Source Candidates summary（candidateId/candidateType/episodeId/evidenceIds件数/sourceDocumentId、raw payloadは含めない）・Conflicts（`field`を追加表示）のセクションを追加し、front matterに`confidence`/`source_types`を任意フィールドとして追加した。conflictsが存在してもstatus: merged かつ canonicalIdありなら通常ページを生成する（conflictsの有無はページ生成可否に影響しない）ことをテストで明示的に確認した。合成fixture（`CHAR_TEST_RAIN`をaliases/evidenceRefs/sourceCandidates各2件に拡張、新規`CHAR_TEST_CONFLICT`でconflicts表示を検証）のみで確認し、実データ由来Wikiページは生成・commitしていない。関連Relationship表示・登場エピソード一覧・AI推定ラベル付けは未実装（Phase 2/3待ち）。wiki renderer skeletonでは、既存の空placeholder package `agents/wiki_generator/`に、merged knowledge collectionからWiki Markdownを生成する最小renderer（`paths.py`: canonicalId優先URL方針の実装、`models.py`: front matter組み立て、`renderer.py`: Top page/Story index/Episode page簡易版/Character page/Unresolved report pageの生成関数とページ組み立てオーケストレーション）と、`scripts/render_wiki.py`（CLI、`--validate`/`--clean`オプション付き）を実装した。canonicalIdが設定されておりstatus: mergedのentityのみ個別ページ（`characters/{canonicalId}.md`）を生成し、それ以外は`reports/unresolved.md`へ集約する（`Wiki_Output_Design.md` §5の判定基準通り）。evidenceRefsはevidenceId/episodeId/sceneId/blockIdの参照情報のみ表示し本文は出力しない。合成fixture（`tests/fixtures/wiki/synthetic_merged_collection.json`、`CHAR_TEST_RAIN`等の架空ID、schema検証済み）のみで検証し、実データ由来Wikiページは生成・commitしていない。Location/Organization/Item/Lore/Event page等のPhase 2以降は未実装。wiki output designでは、**Wiki生成パイプラインの実装は一切行わず**、merged knowledge collectionから将来生成するWikiページの設計のみを行った: `docs/architecture/07_Wiki/Wiki_Output_Design.md`（既存の空プレースホルダーディレクトリを使用）に、source of truthはmerged knowledge collectionでありWikiページは生成物として手編集しない方針、公式情報/AI要約/AI考察/manual overrideの分離方針（`AI_CONTEXT.md` §4.5の具体化）、evidenceRefsの扱い（元セリフ全文を転載せず参照情報のみ残す）、unresolved entity/canonicalIdなしentityの表示方針（`status: unresolved`は個別ページを生成せずUnresolved reportへ集約）、ページ種別のPhase分け（Phase 1: Top/Story index/Episode/Character/Unresolved report、Phase 2: Location/Organization/Item/Lore/Event/Relationship section/Timeline、Phase 3: AI analysis/Evidence index/Knowledge Graph view）、各ページの責務、front matter方針、出力ディレクトリ案（`site_src/`推奨、生成物は当面commitしない）、テンプレート方針（Jinja2導入可否は実装PRで判断、このPRでは確定しない）、merged collectionとの対応表、URL/slug方針（canonicalId優先、名前ベースslugは避ける）、将来の実装PR案7件をまとめた。既存の空プレースホルダー（`Character_Page.md`等）には設計書の該当セクションへのポインタのみ追記し、合成サンプル（`docs/examples/wiki_output/`、`CHAR_EXAMPLE`等の架空ID）を追加した。character dictionary reference JSON import batch 001では、`reference/parser/characters_reference.json`（唯一の入力元として確認済み）と`knowledge/dictionaries/characters.yaml`を比較した結果、**差分が0件**（66件全件一致・displayName不一致0・YAML/JSONそれぞれ片方のみのID 0件）であることを確認した。これは`feature/character-dictionary-coverage`で既に完全移行済みだったためで、辞書ファイル自体は変更していない。将来のbatchに備え、`scripts/compare_character_dictionaries.py`（既定dry-run、`--write`指定時のみYAML未登録IDを`status: name_only`・`characterId: null`固定で追記、confirmed化・characterId自動生成は一切行わない）を新規追加した。character dictionary confirmed review workflowでは、confirmed entryの追加自体は一切行わず（AIの推測によるconfirmed化を禁止する本PRの最重要制約）、安全にconfirmed化するための運用を整備した: `docs/runbooks/Character_Dictionary_Review.md`（confirmed/name_onlyの意味、confirmed化してよい条件・いけない条件、aliases/notesの扱い、実データ由来dumpをcommitしないルール等を明文化）・`docs/templates/character_dictionary_review_template.yaml`（合成データのみのレビュー用テンプレート見本）・`agents/parser/character_dictionary.py`の拡張（`build_character_dictionary_coverage_report`にconfirmed/name_only別のcoverage内訳を追加、未登録ID一覧を人間確認用に整形する`build_review_candidates`を新規追加、`validate_character_dictionary`にaliases重複検出を追加）・`scripts/check_character_dictionary_coverage.py`の`--review-template-output`オプション（未登録IDのレビュー用テンプレートをローカルignored領域へ書き出す、実データ内容は含まない）。現状確認: `knowledge/dictionaries/characters.yaml`は66件中confirmed 2件（CHAR_RAIN/CHAR_AKAGI_HINA）・name_only 64件のまま変更していない。GitHub Actions CIでは、`.github/workflows/ci.yml`を新規追加し、PR・main push時に`uv run pytest`・`scripts/check_invisible_unicode.py`・`scripts/check_dry_run_inputs.py`・`ruff format --check`・`ruff check`を自動実行するようにした（`ubuntu-latest`、`astral-sh/setup-uv`+`actions/setup-python`、Python 3.12。ユーザー指示は3.10だったが`pyproject.toml`の`requires-python>=3.12`と矛盾するため3.12を採用）。残っていた`agents/parser/parser.py::_parse_tokens`のC901（43>10）は、大規模リファクタを避けるため`# noqa: C901`（「parse state dataclass refactorまでの暫定抑制」とコメント明記）で暫定抑制し、CIでは`ruff check`がクリーンに通るようにした。複雑度そのものの解消（dataclassベースの状態オブジェクトへのリファクタ）は引き続き未着手（TASKS.md §4参照）。script command coverage followupでは、branch / choice included dry-run（PR #33）で見つかった未登録コマンド7種（`costume`/`fa`/`@TalkPosR`/`@TalkPosL`/`@ChEyeOff`/`@VisibleS`/`@FadeOutBlack`）を、意味推定しすぎず既存のstage_directionカテゴリへ機械的に分類した（`costume`/`fa`/`@ChEyeOff`/`@VisibleS`→`character_display`、`@TalkPosR`/`@TalkPosL`→`ui`、`@FadeOutBlack`→`screen`。すべて既存カテゴリで表現でき新カテゴリ追加は不要だった）。合成fixtureで検証（実データはこのリポジトリのworktree環境に存在しないため実dry-run再測定は未実施）。ruff known issues cleanupでは、`uv run ruff check scripts agents tests`で検出されていたC901複雑度6件・E501/F841/E402を、挙動を変えずに解消した（`scripts/check_script_compatibility.py`の`main`/`build_markdown_report`/`check_file`、`scripts/normalize_story.py`の`main`、`agents/parser/tokenizer.py`の`_tokenize_line`はいずれも小さな`_classify_*`/`_build_*_section`/`_check_*`/フェーズ単位ヘルパーへ分割してクリア）。唯一`agents/parser/parser.py`の`_parse_tokens`（複雑度43>10）だけは意図的に未対応のまま残した。12個以上の`nonlocal`状態変数が`flush_text()`クロージャと全トークン種別ハンドラ間で密結合しており、安全に分割するには状態を`dataclass`へ切り出す規模のリファクタが必要で、実データ生成の中核ロジックであるためこのPRの目的（挙動不変のruff cleanup）を超えるリスクがあると判断した（詳細はTASKS.md §4 Known Issues参照）。branch / choice included dry-runでは、ユーザーに配置してもらった選択肢入り実データ（branch/#if/#else/#endif構成）を使い、`agents/parser/parser.py`の分岐処理に重大なブロック配置バグ3件を発見・修正した: (1) `#endif`後に`current_choice`がトップレベルの`None`へ戻らず、対応する`#endif`以降のシーン全体（実データで500行超・315ブロック相当）が最後のoptionへ丸ごと閉じ込められる不具合（`branch_stack`へのpush/popタイミングを`branch`呼び出し時点に変更して解消）、(2) ネストしたbranchの新choiceが常にシーン直下へ追加される不具合（`_add_block`経由の配置に変更）、(3) ネストしたbranch終了後に`current_option_idx`が復元されない不具合（`branch_stack`の要素を`(current_choice, current_option_idx)`のタプルに変更）。さらに`agents/parser/tokenizer.py`の`JAPANESE_PATTERN`が省略記号「……」（U+2026、General Punctuationブロック）を含まないため、句読点のみの本文行がUNKNOWN扱いになり本文（モノローグ等）が欠落する不具合も発見・修正した（TEXT判定条件に`or not line.isascii()`を追加）。修正後、実データのdialogue/monologue件数が生スクリプトの`@ChTalk`/`@ChTalkMono`出現数と完全一致することを確認済み。choice内話者がCharacterCandidate抽出の対象外という既存設計（PR #7）は実データでも正しく機能することを確認した。compatibility check consistencyでは、`scripts/check_script_compatibility.py`単体実行と`normalize_story.py --check-compat`経由のcompatibilityReportの判定が食い違っていた問題（根本原因: `agents/parser/normalizer.py`が`newSpeechCommands`を常に空配列でハードコードし、config/script_commands.yamlを一切参照していなかったこと）を、`agents/parser/compatibility.py`（判定ロジックのみを共有する新モジュール、大規模リファクタは避けた）を新設して解消した。`Normalizer`に`commands_config_path`引数を追加し、指定時は`config/script_commands.yaml`のヒントを使って実際に`newSpeechCommands`を判定・4値ステータス（compatible/warning/needs_update/blocked）を決定するようになった。実データ・合成データ双方で両経路の`unknownCommands`/`newSpeechCommands`/`parserCompatibility`が一致することを確認済み（`branch_issues`/`case_variants`検出はStoryParser側に追跡機構が無いためNormalizer側は常にFalse扱いという既知の非対称性が残る、TASKS.md参照）。real data dry-run trial（実データ2話でのParser→Extractor→Merger→Report確認、`docs/runbooks/Real_Data_Dry_Run_Result_Template.md`に数値サマリー記録）では、`scripts/normalize_story.py`/`scripts/check_script_compatibility.py`のコンソール絵文字printがWindows cp932コンソールでクラッシュするバグを発見・修正。加えて、実データでは演出コマンドの`config/script_commands.yaml`カバレッジ不足（ブロックの58〜69%が`unknown`）とキャラクター辞書（66件登録）の数値ID帯不足（merge後の全entityが`unresolved`のまま）という2つの既知の課題を確認した。前者は`script command coverage improvement`（`agents/parser/tokenizer.py`の`KEYWORD_TOKENS`・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`・`config/script_commands.yaml`へ37種の演出コマンドを追加）で対応済みで、実データ2話のunknownブロック率が68.8%/60.7%→0.1%/0%まで低下した（dialogue/monologue/narration件数は完全に不変）。後者（キャラクター辞書拡充）は`character dictionary coverage improvement`で対応済み: 根本原因は`reference/parser/characters_reference.json`（読み取り専用、66件、表示名のみのフラットJSON）が`existingCharacterId`相当の構造化IDを一切持てない形式だったことにあり、`knowledge/dictionaries/characters.yaml`（人手管理、`characterId`/`status`付き。設計上の正しい配置場所として既に`Merged_Knowledge_Design.md` §2.4に想定されていた）・`agents/parser/character_dictionary.py`（loader/validator/coverage report）・`agents/parser/resolver.py`の`CharacterDictionary.load`（拡張子自動判別）・`scripts/normalize_story.py`のデフォルト辞書切り替え・`scripts/check_character_dictionary_coverage.py`（新規coverage確認CLI）を実装。**Merger側のコード変更は一切不要**（既存の`existingCharacterId`→`status: merged`ロジックがそのまま機能することを確認）。CHAR_RAIN/CHAR_AKAGI_HINAの2件のみconfirmed化（既存テストスイート全体で既に確立済みの規約を辞書化）し、名前だけ判明している残り64件・実データで新たに見つかった未確認ID（234/225/230/222等）は`status: name_only`のまま、大量自動confirmed化はしていない（Canonical_ID_Policy.md §4-5の「名前一致だけでの自動確定禁止」に従う）。`check_script_compatibility.py`単体実行と`normalize_story.py --check-compat`経由の判定差異（根本原因は`agents/parser/normalizer.py`が`newSpeechCommands`を常にハードコードで空配列にしていることと特定済み、`feature/compatibility-check-consistency`で対応予定）は未対応（TASKS.md Next Actions参照）。`Merged_Knowledge_Design.md`（設計書）・`Canonical_ID_Policy.md`（canonicalId方針）・`docs/runbooks/Real_Data_Dry_Run.md`（実データを使ったParser→Extractor→Merger→Report確認の手順書）・`schemas/merged_knowledge.schema.json`（8種のmerged entityをoneOf判別）・`schemas/manual_overrides.schema.json`（手動補正ファイル）・`schemas/merged_knowledge_collection.schema.json`（merge engineのcollection wrapper用。`report`にtype別・入力別の内訳・`relationshipTypeSummary`・`canonicalIdSummary`を追加済み）・`agents/merger/`（`MergeEngine`・`entity_base.py`共通処理・`character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`/`relationship.py`/`timeline.py`）・`agents/merger/overrides.py`（manual override loader）・`agents/merger/relationship_taxonomy.py`（relationshipType暫定taxonomy）・`agents/merger/canonical_ids.py`（canonicalId helper/validation）・`scripts/check_dry_run_inputs.py`（dry-run状態確認補助スクリプト）はmainへマージ済み。`feature/no-invisible-unicode-check`で、`scripts/check_invisible_unicode.py`を新規追加中。GitHubの hidden/bidirectional Unicode warning自体は今後マージブロッカーにしない方針を明確化した上で、bidi override/control・zero-width系・BOM・soft hyphen等の明示的に危険なコードポイント、および`unicodedata.category(ch) == "Cf"`/bidi制御クラスに該当する文字だけを検出する。**日本語・全角記号・罫線・矢印・通常のUnicode引用符は「2バイト文字だからNG」として検出しない**（既存Markdown・JSON schema descriptionの日本語を削除する必要は無い）。real data dry-run trial（実データでの実際の試験運用）・timeline contradiction detection・Wiki出力設計・relationshipType taxonomy本確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`）・canonical ID辞書（`knowledge/dictionaries/*.yaml`）本体の実装はまだ未着手。`entities`配下の`merged_knowledge.schema.json`への`$ref`接続は引き続き見送り中（PR #18のTODO）。`schemas/canonical_knowledge.schema.json`はStage C用の予約placeholder。重要ルール: **Stage A candidateのevidence（sourceType/confidence/evidenceIds/candidate ID/extractionRun）はマージ後も失わない**（schemaでevidenceRefs・sourceCandidatesを最低1件必須にして担保。manual override適用後も保持されることをテストで確認済み）。LLM呼び出し本体・provider連携・prompt設計は、CLAUDE.mdの方針により明示的な指示があるまで着手しない。

直近の作業状態・次のアクション・保留事項・既知の問題は `TASKS.md` を参照すること（このファイルには詳細TODOを追記しない）。

## 3.2 このセクションの更新ルール

このセクションはプロジェクトの現在地を示す唯一の場所である。Phaseが完了する、または新しい設計書ができるたびに、このセクション（と§5の設計書一覧）を更新すること。更新を怠ると、次に参加するAIエージェントが古い前提（例: 「Parser Phase 1はまだ準備段階」）で作業を始めてしまう。

---

# 4. 採用済み方針

## 4.1 Documentation Style

設計書本文は日本語で書く。

ただし、以下は英語を使う。

- JSON key
- Python variable / function / class
- Neo4j label / relationship type
- file name
- directory name
- ID
- CLI command
- schema field

例:

```json
{
  "storyId": "MAIN_S01_C02",
  "episodeId": "MAIN_S01_C02_E01",
  "speakerId": "CHAR_RAIN"
}
```

---

## 4.2 Source of Truth

Knowledge Baseを唯一のSource of Truthとする。

Wiki Markdownは手書きで管理するのではなく、Knowledge Baseから生成する成果物とする。

---

## 4.3 Raw Scriptは直接AIに渡さない

ゲームスクリプトは命令・演出・変数・本文が混在しているため、直接AIに読ませない。

必ずParserで正規化してからAI処理に渡す。

---

## 4.4 Evidence First

AIが生成した要約・関係・考察には、可能な限り根拠IDを持たせる。

根拠は以下のような単位を優先する。

1. Dialogue
2. Monologue
3. Narration
4. Choice Option
5. Scene
6. Episode
7. Story

---

## 4.5 Official / AI Summary / AI Analysisを分離する

公式情報とAI生成情報を混ぜない。

AI考察は独立ページまたは明示的なAIセクションに分離する。

---

## 4.6 Static Site First

公開は静的サイトを基本とする。

候補:

- GitHub Pages
- Cloudflare Pages
- MkDocs Material

ユーザー登録・コメント・投稿機能は現時点では不要。

---

## 4.7 Local First AI

ローカルLLM利用を前提にする。

理由:

- 大量ストーリー処理の従量課金を避ける
- 手元のGPUを活用する
- データ処理をローカルで完結しやすくする

外部LLM Providerは必要な補助用途のみ。
OpenAI / Anthropic / Gemini / OpenRouter などは外部Providerの一例であり、デフォルトはローカルLLMとする。

---

# 5. 作成済み・配置済みの重要設計書

Parser関連（Phase 1で実装済み、以下の設計書がある前提で作業する）。

```text
docs/architecture/05_Parser/Identifier_Specification.md
docs/architecture/05_Parser/Story_Metadata.md
docs/architecture/05_Parser/Normalized_Story_JSON.md
docs/architecture/05_Parser/Script_Compatibility_Check.md
```

Extraction Phase関連（Stage A設計・実装完了。`schemas/extraction.schema.json`・`agents/extractor/`の全8種Candidate最小抽出・semantic validation・Stage A統合レビュー・Stage B設計書`Merged_Knowledge_Design.md`・Stage B entity schema `schemas/merged_knowledge.schema.json`/`schemas/manual_overrides.schema.json`・collection schema `schemas/merged_knowledge_collection.schema.json`・merge engine（複数入力対応、`agents/merger/`）・全8種Candidateの最小merge実装はmainへマージ済み。manual override loader（`agents/merger/overrides.py`）は`feature/manual-override-loader`でPR準備中）。

```text
docs/architecture/06_AI/Extraction_Pipeline.md
docs/architecture/06_AI/Extraction_Result_Schema.md
docs/architecture/06_AI/Merged_Knowledge_Design.md
```

必要に応じて以下も参照する。

```text
docs/architecture/01_Project/00_Project_Overview.md
docs/architecture/01_Project/00A_Architecture_Decisions.md
docs/architecture/05_Parser/Parser.md
docs/architecture/05_Parser/Story_Format.md
```

`docs/architecture/06_AI/Agents.md`、`Models.md`、`Pipeline.md`、`Prompt_Design.md` は現時点で0バイトの空プレースホルダーであり、内容は存在しない。

---

# 6. ID仕様の要点

IDにはタイトルを含めない。

タイトル・表示名・公開順・開催期間は `Story_Metadata.md` で扱う。

主なStory Prefix:

| Prefix | 種別 |
|---|---|
| `MAIN` | メインストーリー |
| `EVT` | イベントストーリー |
| `RAID` | 共同戦線イベントストーリー |
| `OTHER` | その他ストーリー |
| `CHAR_MAIN` | キャラクターメインストーリー |
| `CHAR_EXTRA` | キャラクターエクストラストーリー |
| `CHAR_DATE` | キャラクターデートストーリー |

例:

```text
MAIN_S01_C02
MAIN_S01_C02_E01
MAIN_S01_C02_E01_SC001
MAIN_S01_C02_E01_DLG0001
CHAR_AKAGI_HINA
CHAR_MAIN_AKAGI_HINA_E01
```

---

# 7. Story Metadataの要点

タイトルや表示順はIDから分離する。

例:

```json
{
  "storyId": "MAIN_S01_C02",
  "storyTitle": "異形生物対策班、始動！",
  "displayTitle": "第1期 第2章「異形生物対策班、始動！」",
  "displayOrder": 10200,
  "releaseOrder": null,
  "canonicalOrder": null
}
```

エピソードタイトルがある場合:

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "episodeTitle": "作戦参謀レイン",
  "displayTitle": "第1期 第2章 エピソード1「作戦参謀レイン」"
}
```

---

# 8. Normalized Story JSONの要点

Parserは以下の構造を出力する。

```text
StoryDocument
  ├─ metadata
  ├─ parser
  ├─ source
  ├─ compatibilityReport
  └─ episodes
       └─ Episode
            ├─ speakerAssignments
            └─ scenes
                 └─ Scene
                      └─ blocks
                           ├─ dialogue
                           ├─ monologue
                           ├─ narration
                           ├─ choice
                           ├─ stage_direction
                           └─ unknown
```

最重要:

- 本文・話者・選択肢・Evidenceを優先する
- 演出命令は捨てずに `stage_direction` として保持可能にする
- 不明情報は破棄せず `unknown` として残す
- 全Blockに可能な限り `source` を付ける

---

# 9. Parser Phase 1 Must

Parser Phase 1では必ず以下に対応する。

## 会話

```text
@ChTalk
@ChTalkMono
@ChTalkSoundOff
@ChTalkSoundOffMono
@ChTalkName
```

変換方針:

| Raw Command | type | voice.hasVoice |
|---|---|---:|
| `@ChTalk` | `dialogue` | true |
| `@ChTalkMono` | `monologue` | true |
| `@ChTalkSoundOff` | `dialogue` | false |
| `@ChTalkSoundOffMono` | `monologue` | false |
| `@ChTalkName` | `dialogue` | null / unknown |

---

## 話者解決

```text
$numX = character_id
$valueX = character_id
@ScenarioCos slot character_id
@ScenarioCosLoad slot variable
name ...
```

---

## ナレーション

```text
msg
```

---

## 分岐

```text
branch
#if
#elseif
#else
#endif
```

---

## 互換性

- 未知コマンドを検知する
- 新規会話コマンド候補を検知する
- 未登録キャラクターIDを検知する
- 制御文字除去件数を記録する
- 不明行を破棄しない

---

# 10. 最近のスクリプト解析で判明した重要事項

最近のサンプル `.dec` により、以下の追加対応が必要と判明した。

```text
@ChTalkSoundOff
@ChTalkSoundOffMono
@ChTalkName
```

これらは単なる演出ではなく、本文・話者・モノローグ判定に影響する。

演出系・表示系コマンドとして以下も確認済み。

```text
@FaceLow
segmentCorrection
@Visible
@Visibleoff
@VisibleOff
@ChCamera
@ChCameraoff
@ChCameraOff
@MotionReset
@TalkPos
@TalkPosLLL
@TalkPosRRR
@ChCharaEye
@ChCharaEyeoff
@ChCharaEyeOff
@Smartphone
@SmartphoneOff
@Smartphoneoff
@VideoLoad
@VideoPlay
visibleAccessory
```

Phase 1では、これらを完全解釈せず `stage_direction` として保持できればよい。

---

# 11. 既存資産

既存の参考Parserがある。

```text
reference/parser/story_parse_reference.py
reference/parser/characters_reference.json
```

この既存Parserは直接改造しない。

理由:

- TTS / COEIROINK向け出力とDKB Parserの目的が違う
- 既存資産は仕様確認用・比較用として保持する
- DKB Parserは `agents/parser/` 以下に新規実装する

既存Parserから参考にする点:

- キャラクターID解決
- `$numX` / `$valueX`
- `@ScenarioCos`
- `@ScenarioCosLoad`
- `@ChTalk`
- `@ChTalkMono`
- `msg`
- `name`
- `branch` / `#if` / `#elseif` / `#else` / `#endif`
- command exclusion / ignored command handling

---

# 12. 推奨ディレクトリ

Parser関係:

```text
agents/parser/
  __init__.py
  tokenizer.py
  resolver.py
  parser.py
  normalizer.py
  exporter.py
```

Scripts:

```text
scripts/
  check_script_compatibility.py
  normalize_story.py
  validate_json.py
```

Schemas:

```text
schemas/
  story.schema.json
```

Tests:

```text
tests/parser/
  test_tokenizer.py
  test_resolver.py
  test_parser_basic.py
  test_script_compatibility.py
  fixtures/
```

Reports:

```text
data/reports/
```

Raw sample scripts:

```text
data/raw/
```

---

# 13. やってはいけないこと

## 13.1 既存Parserを直接改造しない

`reference/parser/story_parse_reference.py` は参照用である。

DKB Parserは `agents/parser/` に新規実装する。

---

## 13.2 Raw Scriptを直接LLMに投げてKnowledge化しない

必ずNormalized Story JSONを経由する。

---

## 13.3 不明情報を破棄しない

未知コマンド・未登録キャラID・分類不能行は捨てず、レポートまたは `unknown` として保持する。

---

## 13.4 タイトルをIDに含めない

IDは安定性が重要。

タイトル・表示名・短縮名・公開順はメタデータに置く。

---

## 13.5 APIキーをリポジトリへ書かない

OpenAI API keyなどは `.env` または環境変数で管理する。

`.env` は `.gitignore` に含める。

---

# 14. 次にやること

次の作業内容・優先順位は `TASKS.md`（Current Focus / Next Actions）を正とする。ここには重複記載しない。

`agents/extractor/` のLLM呼び出し本体・provider連携の実装着手は指示待ち（§3.1）。着手前に解決しておくべき未確定事項は§16および`TASKS.md`のBacklogを参照。

---

# 15. 作業開始時の指示文

AIエージェントへ渡す指示例:

```text
まず AI_CONTEXT.md を読んでください。
次に docs/architecture/05_Parser/ 配下の設計書を読んでください。
特に Identifier_Specification.md、Story_Metadata.md、Normalized_Story_JSON.md、Script_Compatibility_Check.md を重視してください。
そのうえで Parser_Implementation_Plan.md の Phase 1 から順番に実装してください。
既存の reference/parser/story_parse_reference.py は直接改造せず、仕様確認用として参照してください。
実装後は tests/parser/ にpytestを追加し、サンプル .dec で互換性チェックと正規化JSON出力を検証してください。
```

---

# 16. 未確定事項

以下は今後確認・決定が必要。

- キャラクターIDの完全辞書化
- 主要キャラクターのcanonical ID
- イベント番号の正式な採番ルール
- ローマ字表記ルール
- Stage Directionをどこまで詳細に意味解析するか
- `displayOrder` の正式計算式
- `canonicalOrder` の扱い
- JSON Schemaの厳密度
- Neo4j Graph Model
- Wiki Page Template
- `relationshipType` の語彙（`docs/architecture/04_Knowledge_Graph/Relationships.md`、現在空プレースホルダー。`Extraction_Result_Schema.md` §16.4も参照）
- Candidate ID暫定形式（`Extraction_Result_Schema.md` §4.2）の実運用検証
- **キャラクター公式プロフィール辞書の設計**（`TASKS.md` §3 Backlog「Character profile dictionary design」参照、未実装・未着手）: `knowledge/dictionaries/characters.yaml`はID解決用（`sourceCharacterId`/`characterId`/`displayName`/`aliases`/`status`/`notes`）に用途を限定し、読み仮名（kana/romaji）・所属・身長・誕生日・血液型・CV・自己紹介文・特記事項等の公式プロフィール情報は別ファイル（候補: `knowledge/dictionaries/character_profiles.yaml`）側で扱う方針。プロフィールは**confirmed済みcharacterId**にのみ紐づけ、AI抽出情報とは混ぜない。schema設計・Wiki Character page「基本プロフィール」section設計とも未着手

---

# 17. 現在の推奨判断

Parser本体（`agents/parser/`）、`schemas/extraction.schema.json` 系、`agents/extractor/` の最小skeleton・semantic validation・`CharacterCandidate`/`LocationCandidate`/`OrganizationCandidate`/`ItemCandidate`/`LoreCandidate`/`EventCandidate`/`RelationshipCandidate`/`TimelineCandidate`最小抽出、Extractor内部のファイル分割への再着手は不要（完了済み、§3.1）。

次の自然な一歩は `TASKS.md` の Next Actions（real data dry-run trialで見つかった既知の課題対応のうち残り（実データ頻出の未確認キャラクターID(234/225/230/222等、`scripts/check_character_dictionary_coverage.py`で確認可能)を、`docs/runbooks/Character_Dictionary_Review.md`の手順に沿って人間がローマ字確認し`knowledge/dictionaries/characters.yaml`へconfirmed化する作業自体は引き続き残作業。演出コマンド辞書拡充は`script command coverage improvement`・`script command coverage followup`、キャラクター辞書のloader/validation/coverage report基盤は`character dictionary coverage improvement`、confirmed化のレビュー運用整備は`character dictionary confirmed review workflow`、reference JSON（`characters_reference.json`）のbatch取り込み確認（差分ゼロ、既に完全移行済み）は`character dictionary reference JSON import batch 001`、互換性チェック判定差異の解消は`compatibility check consistency`、選択肢を含む実データでのdry-runは`branch / choice included dry-run`、GitHub Actions CIへの`ruff check`/`ruff format --check`等の組み込みは`feature/github-actions-ci`で対応済み、Wiki出力設計は`docs/architecture/07_Wiki/Wiki_Output_Design.md`（`wiki output design`）で対応済み、wiki renderer skeleton（Top/Story index/Episode簡易/Character/Unresolved reportページ生成、`agents/wiki_generator/`）は`feature/wiki-renderer-skeleton`で対応済み、Character page表示項目拡張（Aliases/Source Candidates summary/Conflicts field等）は`feature/character-page-renderer-expansion`、Episode page表示項目拡張（Candidate Counts表/Related Characters summary/Validationセクション等）は`feature/episode-page-renderer-expansion`、Unresolved report表示項目拡張（Overview/Conflict Summary/Warning Summary/Canonical ID Summary/Relationship Type Summary・entity種別別表へのCanonical ID・Source Candidates列追加）は`feature/unresolved-report-renderer-refinement`、real data wiki render dry-run（runbook・result template・`.gitignore`追加、実データmerged collection未存在のため実データdry-runは未実行、synthetic縮退collectionでの検証・警告メッセージtruncate修正）は`feature/real-data-wiki-render-dry-run`、real data merged collection dry-run（実データ8話でExtractor→Merger→Wiki render handoffまで完走確認、不具合なし）は`feature/real-data-merged-collection-dry-run`、character dictionary confirmed batch 002（人間確認済みmapping未提供のため辞書変更なし、coverage再確認のみ）は`feature/character-dictionary-confirmed-batch-002`、character dictionary review packet（`build_character_review_packet`/`scripts/build_character_review_packet.py`によるレビュー用packet生成の仕組み整備、辞書confirmed化自体は行わず）は`feature/character-dictionary-review-packet`、character dictionary confirmed batch 003（人間確認済み12件をconfirmed化、実データdry-runでcanonicalIdSummary.totalAssigned 0→12・Character page 12件生成を確認）は`feature/character-dictionary-confirmed-batch-003`、character profile schema design（`character_profiles.yaml`の設計・schema・validator・helper・template整備、実プロフィールデータ投入は未実施）は`feature/character-profile-schema-design`、character profile wiki import pipeline（WIKI取得・変換・照合の仕組み整備、実WIKI dry-runはページ検出失敗のため正しいURL特定が残作業）は`feature/character-profile-wiki-import-pipeline`で対応済み・残るのは`agents/parser/parser.py::_parse_tokens`のC901本体解消（CIでは`# noqa: C901`で暫定抑制済み）のみ・TASKS.md §4参照）→ `Merged_Knowledge_Design.md` §13のPR分割案に従い `_parse_tokens`のparse state dataclassリファクタ → timeline contradiction detection → 残る未確認10件（234/225/230/222/232/83/258/86/85/257）について人間が実データを確認しconfirmed化できた場合の次のconfirmed-batch（character dictionary confirmed batch 004） → 正しいメンバー一覧テーブルURLを特定して改めて実WIKI dry-runを実施 → 人間が確認した実プロフィールデータのcharacter_profiles.yamlへの投入（character profile import batch 001） → Wiki Character pageの基本プロフィールsection実装（character profile renderer section） → relationship section renderer・Location/Organization/Item/Lore/Event page等のwiki renderer Phase 2拡張（`Wiki_Output_Design.md` §15実装PR案、着手前に確認） → relationshipType taxonomy本確定 → canonical ID辞書実装）に従う。着手前に以下を守る。

- `agents/extractor/` のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（CLAUDE.mdの方針）
- Stage B実装では、Stage A candidateのevidence・provenance（sourceType/confidence/evidenceIds/candidate ID/extractionRun）を失わない（`Merged_Knowledge_Design.md` §4.1 / §10）

Parser Phase 1と同じ考え方（検証基準となるschemaを実体より先に作る）を踏襲する。
