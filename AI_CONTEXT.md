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

**Stage A candidate extractionは完了。Stage B（Merged Knowledge）は設計書・schema（entity単位・collection単位）・merge engine（単一/複数入力）・全8種Candidateの最小merge・manual override loader完了→現在merge report強化実装中**。`Merged_Knowledge_Design.md`（設計書）・`schemas/merged_knowledge.schema.json`（8種のmerged entityをoneOf判別）・`schemas/manual_overrides.schema.json`（手動補正ファイル）・`schemas/merged_knowledge_collection.schema.json`（merge engineのcollection wrapper用）・`agents/merger/`（`MergeEngine`・`entity_base.py`共通処理・`character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`/`relationship.py`/`timeline.py`）・`agents/merger/overrides.py`（manual override loader。displayName/status/canonicalIdの上書き、aliasesの追加・削除、fieldValues経由のnotes追加。対象entityの特定は保守的で名前一致は使わない）はmainへマージ済み。`feature/merge-report-enhancements`で、`report`にtype別・入力別の内訳（`unresolvedEntityCounts`/`conflictCounts`/`warningCounts`/`entityTypeSummaries`/`inputSummaries`）を追加中。既存の`conflictsCount`/`unresolvedCount`（全体合算値）はそのまま維持し、内訳を別フィールドとして追加する形（後方互換優先）。`schemas/merged_knowledge_collection.schema.json`のMergeReportに5フィールドを新規必須として追加、`manualOverrides`は引き続き任意プロパティ。`warningCounts.skippedOverrides`は`manualOverrides.skippedCount`をCLI層で反映する（`agents/merger/engine.py`自体はoverrideの存在を知らない）。canonical ID本格割り当て・高度なconflict解決・timeline contradiction detection・relationshipType taxonomy確定はまだ未着手。`entities`配下の`merged_knowledge.schema.json`への`$ref`接続は引き続き見送り中（PR #18のTODO）。`schemas/canonical_knowledge.schema.json`はStage C用の予約placeholder。重要ルール: **Stage A candidateのevidence（sourceType/confidence/evidenceIds/candidate ID/extractionRun）はマージ後も失わない**（schemaでevidenceRefs・sourceCandidatesを最低1件必須にして担保。manual override適用後も保持されることをテストで確認済み）。LLM呼び出し本体・provider連携・prompt設計は、CLAUDE.mdの方針により明示的な指示があるまで着手しない。

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

---

# 17. 現在の推奨判断

Parser本体（`agents/parser/`）、`schemas/extraction.schema.json` 系、`agents/extractor/` の最小skeleton・semantic validation・`CharacterCandidate`/`LocationCandidate`/`OrganizationCandidate`/`ItemCandidate`/`LoreCandidate`/`EventCandidate`/`RelationshipCandidate`/`TimelineCandidate`最小抽出、Extractor内部のファイル分割への再着手は不要（完了済み、§3.1）。

次の自然な一歩は `TASKS.md` の Next Actions（`feature/merge-report-enhancements`のPR以降、`Merged_Knowledge_Design.md` §13のPR分割案に従い、relationshipType taxonomy整理 → timeline contradiction detection → canonical ID方針整理 → real data dry-run procedure → Wiki出力設計）に従う。着手前に以下を守る。

- `agents/extractor/` のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（CLAUDE.mdの方針）
- Stage B実装では、Stage A candidateのevidence・provenance（sourceType/confidence/evidenceIds/candidate ID/extractionRun）を失わない（`Merged_Knowledge_Design.md` §4.1 / §10）

Parser Phase 1と同じ考え方（検証基準となるschemaを実体より先に作る）を踏襲する。
