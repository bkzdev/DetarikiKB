# AI_CONTEXT

Project: Detariki Knowledge Base (DKB)
Audience: Antigravity / Claude Code / GPT-OSS120B / future AI coding agents
Language policy: ドキュメントは日本語、コード/データキーは英語

このファイルはAIエージェントが作業開始前に必ず読む「短い前提情報」である。詳細な設計・手順・完了済み履歴はここに書かず、各詳細docsへリンクする。作業状態・優先順位は`TASKS.md`を正とする。

---

## 1. プロジェクト概要

DKBは、ゲーム「デタリキZ」のストーリー全文を解析し、キャラクター・関係・場所・用語集・時系列・矛盾点・AI考察・Wiki・Knowledge Graphを自動生成・管理するKnowledge Baseである。

**設計思想**: Wikiを直接作るのではなく、Knowledge Baseを作り、Wikiはその成果物として生成する。Knowledge Baseを唯一のSource of Truthとする。Wiki Markdownは手書きせず、生成物として扱う。

## 2. パイプライン

```text
Raw Script (.dec)
  → Story Parser (agents/parser/)
  → Normalized Story JSON (schemas/story.schema.json)
  → Extraction (agents/extractor/, Stage A candidate)
  → Merge (agents/merger/, Stage B merged knowledge)
  → Wiki Generation (agents/wiki_generator/) / Knowledge Graph
```

現在の状態: Parser Phase 1・Extraction Stage A・Merge Stage B（8種entity最小merge）・Wiki renderer Phase 1・MkDocs local previewまで実装済み。詳細な完了履歴は `docs/project_history/Completed_PRs_2026-07.md` を参照。直近の作業内容は `TASKS.md` を参照。

## 3. 最重要方針

### 3.1 Raw Scriptを直接AIに渡さない
ゲームスクリプトは命令・演出・変数・本文が混在するため、必ずParserで正規化してからAI処理に渡す（`docs/architecture/05_Parser/`）。

### 3.2 不明情報を破棄しない
未知コマンド・未登録キャラID・分類不能行は捨てず、`compatibilityReport`または`type: "unknown"`ブロックとして保持する。

### 3.3 IDにタイトルを含めない
`storyId`/`episodeId`等は安定性が命。タイトル・表示名・公開順はmetadata側に置く（`docs/architecture/05_Parser/Identifier_Specification.md`, `Story_Metadata.md`）。

### 3.4 Official / AI Extraction / AI Speculationを分離する
公式情報・機械的抽出・AI考察を混ぜない。AI考察は独立ページまたは明示的なAIセクションに分離する。

### 3.5 canonical ID方針（要約）
`id`（処理内部の不安定な値）と`canonicalId`（Wiki上で安定参照する人間確認済みID）を区別する。canonicalIdは人間管理の構造化辞書由来のもの以外は自動付与しない。名前一致・単一episode観測・低confidence・LLM推測からの自動生成は禁止。詳細: `docs/architecture/06_AI/Canonical_ID_Policy.md`。

### 3.6 character dictionary方針（要約）
`knowledge/dictionaries/characters.yaml`はID解決専用辞書。`status: confirmed`（`characterId`確定）と`status: name_only`（`characterId: null`）を区別し、**name_onlyはresolved扱いにしない**。confirmed化は人間がローマ字表記を確認した上で個別に行い、AI推測での一括confirmed化は禁止。詳細: `docs/runbooks/Character_Dictionary_Review.md`。

### 3.7 character profile方針（要約）
公式プロフィール（読み仮名/所属/身長/誕生日/CV/自己紹介文等）は`knowledge/dictionaries/character_profiles.yaml`に分離管理し、**confirmed済みcharacterIdにのみ**紐づける。characters.yamlとは役割が異なる。詳細: `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`。

### 3.8 story_manifest / title・subtitle方針（要約）
raw DEC配置とDKB正規ID体系（storyId/episodeId）は`story_manifest.yaml`で分離管理する。title/subtitleは**DEC本文からは自動推測しない**（null許容）。AI生成タイトルは公式title/subtitleと分離し、`story_manifest.yaml`には保持しない。import candidate→人間レビュー→manifest反映という流れを経て`confirmed`になる。storyTitle/episodeSubtitle/displayTitle/metadataStatusは、Normalized Story JSON→Extractor→Merger→Wiki rendererまで伝播し、Episode page/Story indexに表示される（未設定時はepisodeIdへfallback、実タイトルの投入自体は別タスク）。Story indexのEpisodeリンクテキストも同じ`displayTitle > episodeSubtitle > storyTitle > episodeId`優先順位で人間向け表示にする（URL/ファイル名はepisodeIdベースのまま変更しない）。詳細: `docs/architecture/05_Parser/Story_Manifest_Design.md`, `docs/runbooks/Story_Title_Subtitle_Import.md`。

### 3.9 MkDocs preview方針（要約）
`agents/wiki_generator/`のrendererが生成したMarkdownは、一時ローカルMkDocs設定（commitしない）を使ってローカルでのみpreviewする。実データ由来の生成物（Normalized Story JSON・extraction/merge結果・Wiki Markdown・raw HTML・candidate YAML/CSV・workspace出力）は一切commitしない。実データでの確認結果は匿名化して記録する。目視確認は`mkdocs serve`を使う（`file://`直開きはdirectory-style URLがディレクトリ一覧表示になるため補助的確認に留める）。MkDocs Materialは当面のpreview用途では利用してよいが、長期公開基盤としては未確定（`TASKS.md` Known Issues参照）。詳細: `docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`。

### 3.10 speaker label方針（要約）
`name`コマンド/`@ChTalkName`由来のspeaker label（キャラクターID経由ではない表示名）は、通常のunresolved characterとは区別して構造化する（speaker_group/speaker_with_modifier/generic_speaker等、`agents/parser/speaker_labels.py`）。**自動でconfirmed character解決はしない**（resolutionStatusは`inferred`/`needs_review`のみ自動付与、`confirmed`は人間レビュー結果取り込み用に予約）。通常のCharacterCandidate/Character merged entityとは別枠（`specialSpeakerLabelCandidates`/`entities.specialSpeakerLabels`）で扱い、Unresolved reportでも別sectionに表示する。詳細: `docs/architecture/06_AI/Extraction_Result_Schema.md` §13.5, `Merged_Knowledge_Design.md` §7.5。

### 3.11 実データ・生成物をcommitしない（横断ルール）
以下はどのPRでも一貫してcommit対象外: 実`.dec`、実データ由来`story_manifest.yaml`、実Normalized Story JSON、実extraction/merged collection、実Wiki Markdown、raw HTML、実candidate YAML/CSV、`workspace/`配下の生成物、`.env`、APIキー。`.gitignore`で網羅済み。

## 4. やってはいけないこと

- `reference/parser/story_parse_reference.py` / `characters_reference.json` を直接改造しない（読み取り専用の参照資料。DKB Parserは`agents/parser/`に新規実装する）
- Raw Scriptを直接LLMに渡してKnowledge化しない
- 不明情報を破棄する
- IDにタイトルを含める
- APIキーをリポジトリに書く
- `agents/extractor/`のLLM呼び出し本体・provider連携実装は、ユーザーの明示的な指示があるまで着手しない（**`agents/summarizer/`系のLLM provider実装は、ユーザーが2026-07-13に明示的に解禁済み**。`agents/summarizer/provider.py`のOllama provider実装（`summary-generation-provider-implementation`）参照。`agents/extractor/`は引き続き未解禁のまま）
- 名前一致だけでcharacterId/canonicalIdを自動確定する
- DEC本文からtitle/subtitleを推測して埋める

## 5. 既存資産（参照専用）

```text
reference/parser/story_parse_reference.py
reference/parser/characters_reference.json
```

TTS/COEIROINK向け旧Parserの資産。キャラクターID解決・`$numX`/`@ScenarioCos`/`@ChTalk`/`msg`/`branch`等の仕様確認用としてのみ参照し、直接改造しない。

## 6. 重要な設計書リンク

Parser:
- `docs/architecture/05_Parser/Identifier_Specification.md`
- `docs/architecture/05_Parser/Story_Metadata.md`
- `docs/architecture/05_Parser/Normalized_Story_JSON.md`
- `docs/architecture/05_Parser/Script_Compatibility_Check.md`
- `docs/architecture/05_Parser/Story_Manifest_Design.md`

Extraction / Merge:
- `docs/architecture/06_AI/Extraction_Pipeline.md`
- `docs/architecture/06_AI/Extraction_Result_Schema.md`
- `docs/architecture/06_AI/Merged_Knowledge_Design.md`
- `docs/architecture/06_AI/Canonical_ID_Policy.md`
- `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`
- `docs/architecture/06_AI/Story_Summary_Design.md`（Story/Episode Summaryのデータ構造・保存場所（`knowledge/summaries/stories/{storyId}.yaml`）・status/review workflow設計。schema/loader/validator・Story page renderer統合（`--story-summaries`）・evidenceRefsのEvidence indexへのリンク化まで実装済み。AI要約生成・Episode pageへの表示はまだ未着手。AI要約生成パイプラインの実装計画は`docs/architecture/06_AI/Story_Summary_Generation_Plan.md`として確定済み（`story-summary-generation-planning`、Summary fileの公開ID問題へのEvidence Index方式踏襲方針・パイプライン段階設計・実装フェーズ分割を含む、設計のみ・実装未着手）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（evidenceRefsのリンク先となるEvidence indexの設計。Public Evidence Index/Internal Review Evidence Packetの分離、初期推奨はStory別Evidence page。schema/loader/validator・renderer統合（`render_wiki.py --evidence-index`）に加え、`scripts/build_evidence_index_candidates.py`によるNormalized Story JSON/Extraction Resultからの候補生成dry-run（`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`）まで実装済み。実データdry-run結果のレビューを踏まえたPublic promotion方針は`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（`stage_direction`除外方針・promotion/exclusion criteria）を参照。`build_evidence_index_candidates.py`は`--public-profile default|full|review`（**デフォルトはstage_directionを除外するdefault**）・`--include-types`/`--exclude-types`によるentry type filteringに対応済み。`scripts/check_evidence_index_promotion.py`（`docs/runbooks/Evidence_Index_Promotion_Check.md`）でPublic Evidence Index候補が昇格可能かをcheck-onlyで判定できる（`--policy public-default`、実際のcopy・commit・自動昇格はまだ未実装）。実データfiltered outputでのdry-run運用確認済み（187 entries、PASS）。`scripts/promote_evidence_index.py`（`docs/runbooks/Evidence_Index_Promotion_Copy.md`）でPASSした候補を`knowledge/evidence/stories/`へcopyできる（**デフォルトは常にdry-run、`--execute`必須**、promotion check・review note承認・上書き禁止等をすべて満たさない限りcopyしない）。実データでの`--execute`実行・commitはまだ未実施。初回実データ昇格試行（`evidence-index-promotion-first-reviewed-sample`）では、`knowledge/evidence/stories/{storyId}.yaml`のファイル名・Evidence Index内主キーがsourceKey由来の`storyId`をそのまま使う設計であることが判明し、Git履歴への永続混入リスクを理由に安全側で見送った。`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`で、内部trace ID（`storyId`/`evidenceId`等）と公開ID（`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`）を分離し、Public Evidence Indexは公開ID中心のprojectionとして保存する方針（案C）を決定した。`publicEvidenceId`の形式（`{publicEpisodeId}_{PREFIX}{sequence:04d}`）とschema（`schemas/evidence_index.schema.json`へのoptional追加）は実装済み（`evidence-index-public-id-schema-design`）。`scripts/project_evidence_index_public_ids.py`（`evidence-index-public-id-projection`）で、許可されたevidenceTypeのentryに`publicEvidenceId`を実際に生成・付与するCompatible projection（案A、既存の内部IDは削除しない）に加え、`--projection-mode public-safe`（`evidence-index-public-id-public-safe-projection`）で内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）を公開ID中心へ置換・除去するPublic-safe projection（案B）まで実装済み。実データでは`publicEpisodeId`未確定のepisodeがPublic-safe projectionをblockingにする問題が判明し、`docs/architecture/06_AI/Public_ID_Registry_Design.md`（`evidence-index-public-episode-id-assignment`）で採番方針（`{publicStoryId}_E{episodeOrder:02d}`）・永続化場所（長期方針としてPublic ID Registry、`schemas/public_id_registry.schema.json`）を設計し、`scripts/check_public_episode_ids.py`で欠落episodeの検出・割当候補提案（常に人間review必須）を実装した後、`project_evidence_index_public_ids.py`に`--registry`を追加してRegistryから実際に`publicEpisodeId`を補完できるようにした（`evidence-index-public-id-registry-integration`、匿名化実データサンプルで187 entries全件のPublic-safe projection通過を確認済み）。Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替えるrenderer switchも実装済み（`evidence-index-public-id-renderer-switch`、`agents/wiki_generator/evidence_index.py`の`display_evidence_id`/`resolve_evidence_entry`/`resolve_story_evidence_entries`）。**`evidence-index-promotion-first-reviewed-sample-retry`で、`knowledge/public_ids/story_public_ids.yaml`への実Public ID Registry entry追加（1 story分）と、`knowledge/evidence/stories/`への初回実データEvidence Index昇格（1 story・187 entries）を実施した**（`promote_evidence_index.py --execute`、複数story batch promotionは未着手）。`evidence-index-promotion-first-sample-visual-review`で、この昇格済み1 storyのWiki表示・Story page導線・内部ID非露出を実装変更なしで最終確認した。複数storyへ広げる際の運用方針は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（`evidence-index-promotion-batch-policy`）で設計済み（batch size段階・Registry review条件・promotion前後チェックリスト・visual review/failed story/rollback方針）。`evidence-index-promotion-first-batch-dry-run`で、2 storyを対象にworkspace限定でbatch dry-run（Registry候補・Public-safe projection・validation/promotion check/render/exposure check・visual review）を実施し、**tooling自体には問題が無いことを実証した**が、選定storyの品質（parser互換性由来のunknown比率過多）とStory page導線の前提条件（`story_manifest.yaml`のpublicStoryId未割当だと導線が機能しない）という2つの課題を新たに発見し、この2 storyでのreal batch promotionは見送った（実データcommitなし）。この品質問題を受け、promotion候補storyの機械的選定基準（unknown比率10%/30%閾値等、`promotion-candidate`/`parser-improvement-wait`/`excluded`の3分類）を`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3に確定した（`evidence-index-batch-candidate-selection-policy`）。`script-command-dictionary-expansion-batch-001`で対象2 storyのunknownコマンドを調査したところ、§4.2時点の約90%という数値は既にmainへmerge済みだった演出コマンド辞書拡張を反映する前のstaleなローカル生成物由来であることが判明し、本PR着手前のmain時点で再normalizeし直すと約1%まで下がっていた。残っていた未登録コマンド1種を`config/script_commands.yaml`・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`双方に追加し、対象2 storyのunknown比率を0%まで低減した（`Evidence_Index_Batch_Promotion_Policy.md` §4.4）。`story-manifest-public-story-id-real-data-assignment`で、この2 storyにローカルworkspace限定のstory_manifest経由で人間確定済み`publicStoryId`/`publicEpisodeId`を割り当てて再normalize/merge/renderし、**Story pageの「Review Links → Evidence index」導線が実データで機能することを実証した**（`Evidence_Index_Batch_Promotion_Policy.md` §4.5、tooling・伝播チェーンとも問題なし、`evidence-index-promotion-first-real-batch`へ進める状態と判定）。`evidence-index-promotion-first-real-batch`で、ユーザー事前承認のもと`knowledge/public_ids/story_public_ids.yaml`に2 story分のPublic ID Registry entryを追加し、初回実batch promotion（Phase 3）として`knowledge/evidence/stories/`へ2 story分の実Evidence Index（205 entries）を昇格した（既存の昇格済み1 storyには無変更。copy後、既存分を含む全3ファイル・392 entriesの再検証・再render・exposure checkもすべてPASS、詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.6）。`knowledge/evidence/stories/`への自動昇格・batch promotion scriptの実装・Internal Review Evidence Packetはまだ未着手）

Wiki:
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`
- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page中心構造への設計方針。`render_story_page`/`story_page_path`で実装済み、Episode pageは維持。Story/Episode SummaryはAI要約生成パイプライン実装まで「未生成」placeholder）

Runbooks:
- `docs/runbooks/Real_Data_Dry_Run.md`
- `docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`
- `docs/runbooks/Story_Title_Subtitle_Import.md`
- `docs/runbooks/Character_Dictionary_Review.md`
- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（`scripts/build_evidence_index_candidates.py`によるEvidence Index候補生成dry-run手順）

履歴・作業管理:
- `docs/project_history/Completed_PRs_2026-07.md`（完了済みPRの要約履歴）
- `TASKS.md`（現在の作業状態・Next/Backlog/Known Issues）

## 7. 現在の直近優先タスク

`TASKS.md`の`Current Focus`/`Next`を正とする。ここには重複記載しない。

## 8. 作業開始時の指示文（例）

```text
まず AI_CONTEXT.md を読んでください。
次に TASKS.md の Current Focus / Next を確認してください。
関連する docs/architecture/ の設計書（上記リンク参照）を確認してください。
既存の reference/parser/story_parse_reference.py は直接改造せず、仕様確認用として参照してください。
実装後は tests/ に pytest を追加し、合成fixtureで検証してください（実データはcommitしない）。
```

PRワークフロー・commit禁止リスト・標準検証コマンド・恒常Non-goals・最終報告様式は`docs/runbooks/AI_PR_Playbook.md`に集約されている。個別PRの指示プロンプトはこのPlaybookを前提とし、そのPR固有の情報（目的・参照docs・作業内容・固有のNon-goals追加分）のみを記載すればよい。

## 9. 未確定事項

- イベント番号の正式な採番ルール、`displayOrder`/`canonicalOrder`の正式計算式（Story ID/URL方針の比較・採用方針決定は`docs/architecture/05_Parser/Story_ID_Policy_Review.md`/`Story_ID_Policy_Decision.md`参照。既存storyId/episodeIdは当面維持、公開URL用`publicStoryId`/`publicEpisodeId`は`story_manifest.yaml`の任意フィールドとして実装済みで、renderer/paths.pyもEpisode page filename/URL/Story indexリンク先に反映済み（`Story_Manifest_Design.md` §13.2、14）。ID生成ロジック・Character page pathはまだ変更していない）
- `relationshipType`の語彙本確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`、現在プレースホルダー）
- Neo4j Graph Model、Wiki Page Template
- Stage Directionをどこまで詳細に意味解析するか
- `agents/parser/parser.py::_parse_tokens`のparse state dataclassリファクタ（既知のC901複雑度課題、`TASKS.md` Known Issues参照）

詳細な未着手項目・優先順位は`TASKS.md`のBacklog/Known Issuesを参照。
