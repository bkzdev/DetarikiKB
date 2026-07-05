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
raw DEC配置とDKB正規ID体系（storyId/episodeId）は`story_manifest.yaml`で分離管理する。title/subtitleは**DEC本文からは自動推測しない**（null許容）。AI生成タイトルは公式title/subtitleと分離し、`story_manifest.yaml`には保持しない。import candidate→人間レビュー→manifest反映という流れを経て`confirmed`になる。詳細: `docs/architecture/05_Parser/Story_Manifest_Design.md`, `docs/runbooks/Story_Title_Subtitle_Import.md`。

### 3.9 MkDocs preview方針（要約）
`agents/wiki_generator/`のrendererが生成したMarkdownは、一時ローカルMkDocs設定（commitしない）を使ってローカルでのみpreviewする。実データ由来の生成物（Normalized Story JSON・extraction/merge結果・Wiki Markdown・raw HTML・candidate YAML/CSV・workspace出力）は一切commitしない。実データでの確認結果は匿名化して記録する。詳細: `docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`。

### 3.10 実データ・生成物をcommitしない（横断ルール）
以下はどのPRでも一貫してcommit対象外: 実`.dec`、実データ由来`story_manifest.yaml`、実Normalized Story JSON、実extraction/merged collection、実Wiki Markdown、raw HTML、実candidate YAML/CSV、`workspace/`配下の生成物、`.env`、APIキー。`.gitignore`で網羅済み。

## 4. やってはいけないこと

- `reference/parser/story_parse_reference.py` / `characters_reference.json` を直接改造しない（読み取り専用の参照資料。DKB Parserは`agents/parser/`に新規実装する）
- Raw Scriptを直接LLMに渡してKnowledge化しない
- 不明情報を破棄する
- IDにタイトルを含める
- APIキーをリポジトリに書く
- `agents/extractor/`のLLM呼び出し本体・provider連携実装は、ユーザーの明示的な指示があるまで着手しない
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

Wiki:
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`

Runbooks:
- `docs/runbooks/Real_Data_Dry_Run.md`
- `docs/runbooks/MkDocs_Local_Preview_Dry_Run.md`
- `docs/runbooks/Story_Title_Subtitle_Import.md`
- `docs/runbooks/Character_Dictionary_Review.md`

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

## 9. 未確定事項

- イベント番号の正式な採番ルール、`displayOrder`/`canonicalOrder`の正式計算式
- `relationshipType`の語彙本確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`、現在プレースホルダー）
- Neo4j Graph Model、Wiki Page Template
- Stage Directionをどこまで詳細に意味解析するか
- `agents/parser/parser.py::_parse_tokens`のparse state dataclassリファクタ（既知のC901複雑度課題、`TASKS.md` Known Issues参照）

詳細な未着手項目・優先順位は`TASKS.md`のBacklog/Known Issuesを参照。
