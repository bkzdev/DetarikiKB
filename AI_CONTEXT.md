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

**Stage A candidate extractionは完了。Stage B（Merged Knowledge）は設計書・schema（entity単位・collection単位）・merge engine（単一/複数入力）・全8種Candidateの最小merge・manual override loader・merge report強化・relationshipType taxonomy・canonical ID policy・real data dry-run procedure・no invisible unicode check・real data dry-run trial・script command coverage improvement・character dictionary coverage improvement・compatibility check consistency・branch / choice included dry-run・ruff known issues cleanup・script command coverage followup完了→次は実データ頻出未確認キャラクターIDのconfirmed化・GitHub Actions CI導入待ち**。script command coverage followupでは、branch / choice included dry-run（PR #33）で見つかった未登録コマンド7種（`costume`/`fa`/`@TalkPosR`/`@TalkPosL`/`@ChEyeOff`/`@VisibleS`/`@FadeOutBlack`）を、意味推定しすぎず既存のstage_directionカテゴリへ機械的に分類した（`costume`/`fa`/`@ChEyeOff`/`@VisibleS`→`character_display`、`@TalkPosR`/`@TalkPosL`→`ui`、`@FadeOutBlack`→`screen`。すべて既存カテゴリで表現でき新カテゴリ追加は不要だった）。合成fixtureで検証（実データはこのリポジトリのworktree環境に存在しないため実dry-run再測定は未実施）。ruff known issues cleanupでは、`uv run ruff check scripts agents tests`で検出されていたC901複雑度6件・E501/F841/E402を、挙動を変えずに解消した（`scripts/check_script_compatibility.py`の`main`/`build_markdown_report`/`check_file`、`scripts/normalize_story.py`の`main`、`agents/parser/tokenizer.py`の`_tokenize_line`はいずれも小さな`_classify_*`/`_build_*_section`/`_check_*`/フェーズ単位ヘルパーへ分割してクリア）。唯一`agents/parser/parser.py`の`_parse_tokens`（複雑度43>10）だけは意図的に未対応のまま残した。12個以上の`nonlocal`状態変数が`flush_text()`クロージャと全トークン種別ハンドラ間で密結合しており、安全に分割するには状態を`dataclass`へ切り出す規模のリファクタが必要で、実データ生成の中核ロジックであるためこのPRの目的（挙動不変のruff cleanup）を超えるリスクがあると判断した（詳細はTASKS.md §4 Known Issues参照）。branch / choice included dry-runでは、ユーザーに配置してもらった選択肢入り実データ（branch/#if/#else/#endif構成）を使い、`agents/parser/parser.py`の分岐処理に重大なブロック配置バグ3件を発見・修正した: (1) `#endif`後に`current_choice`がトップレベルの`None`へ戻らず、対応する`#endif`以降のシーン全体（実データで500行超・315ブロック相当）が最後のoptionへ丸ごと閉じ込められる不具合（`branch_stack`へのpush/popタイミングを`branch`呼び出し時点に変更して解消）、(2) ネストしたbranchの新choiceが常にシーン直下へ追加される不具合（`_add_block`経由の配置に変更）、(3) ネストしたbranch終了後に`current_option_idx`が復元されない不具合（`branch_stack`の要素を`(current_choice, current_option_idx)`のタプルに変更）。さらに`agents/parser/tokenizer.py`の`JAPANESE_PATTERN`が省略記号「……」（U+2026、General Punctuationブロック）を含まないため、句読点のみの本文行がUNKNOWN扱いになり本文（モノローグ等）が欠落する不具合も発見・修正した（TEXT判定条件に`or not line.isascii()`を追加）。修正後、実データのdialogue/monologue件数が生スクリプトの`@ChTalk`/`@ChTalkMono`出現数と完全一致することを確認済み。choice内話者がCharacterCandidate抽出の対象外という既存設計（PR #7）は実データでも正しく機能することを確認した。compatibility check consistencyでは、`scripts/check_script_compatibility.py`単体実行と`normalize_story.py --check-compat`経由のcompatibilityReportの判定が食い違っていた問題（根本原因: `agents/parser/normalizer.py`が`newSpeechCommands`を常に空配列でハードコードし、config/script_commands.yamlを一切参照していなかったこと）を、`agents/parser/compatibility.py`（判定ロジックのみを共有する新モジュール、大規模リファクタは避けた）を新設して解消した。`Normalizer`に`commands_config_path`引数を追加し、指定時は`config/script_commands.yaml`のヒントを使って実際に`newSpeechCommands`を判定・4値ステータス（compatible/warning/needs_update/blocked）を決定するようになった。実データ・合成データ双方で両経路の`unknownCommands`/`newSpeechCommands`/`parserCompatibility`が一致することを確認済み（`branch_issues`/`case_variants`検出はStoryParser側に追跡機構が無いためNormalizer側は常にFalse扱いという既知の非対称性が残る、TASKS.md参照）。real data dry-run trial（実データ2話でのParser→Extractor→Merger→Report確認、`docs/runbooks/Real_Data_Dry_Run_Result_Template.md`に数値サマリー記録）では、`scripts/normalize_story.py`/`scripts/check_script_compatibility.py`のコンソール絵文字printがWindows cp932コンソールでクラッシュするバグを発見・修正。加えて、実データでは演出コマンドの`config/script_commands.yaml`カバレッジ不足（ブロックの58〜69%が`unknown`）とキャラクター辞書（66件登録）の数値ID帯不足（merge後の全entityが`unresolved`のまま）という2つの既知の課題を確認した。前者は`script command coverage improvement`（`agents/parser/tokenizer.py`の`KEYWORD_TOKENS`・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`・`config/script_commands.yaml`へ37種の演出コマンドを追加）で対応済みで、実データ2話のunknownブロック率が68.8%/60.7%→0.1%/0%まで低下した（dialogue/monologue/narration件数は完全に不変）。後者（キャラクター辞書拡充）は`character dictionary coverage improvement`で対応済み: 根本原因は`reference/parser/characters_reference.json`（読み取り専用、66件、表示名のみのフラットJSON）が`existingCharacterId`相当の構造化IDを一切持てない形式だったことにあり、`knowledge/dictionaries/characters.yaml`（人手管理、`characterId`/`status`付き。設計上の正しい配置場所として既に`Merged_Knowledge_Design.md` §2.4に想定されていた）・`agents/parser/character_dictionary.py`（loader/validator/coverage report）・`agents/parser/resolver.py`の`CharacterDictionary.load`（拡張子自動判別）・`scripts/normalize_story.py`のデフォルト辞書切り替え・`scripts/check_character_dictionary_coverage.py`（新規coverage確認CLI）を実装。**Merger側のコード変更は一切不要**（既存の`existingCharacterId`→`status: merged`ロジックがそのまま機能することを確認）。CHAR_RAIN/CHAR_AKAGI_HINAの2件のみconfirmed化（既存テストスイート全体で既に確立済みの規約を辞書化）し、名前だけ判明している残り64件・実データで新たに見つかった未確認ID（234/225/230/222等）は`status: name_only`のまま、大量自動confirmed化はしていない（Canonical_ID_Policy.md §4-5の「名前一致だけでの自動確定禁止」に従う）。`check_script_compatibility.py`単体実行と`normalize_story.py --check-compat`経由の判定差異（根本原因は`agents/parser/normalizer.py`が`newSpeechCommands`を常にハードコードで空配列にしていることと特定済み、`feature/compatibility-check-consistency`で対応予定）は未対応（TASKS.md Next Actions参照）。`Merged_Knowledge_Design.md`（設計書）・`Canonical_ID_Policy.md`（canonicalId方針）・`docs/runbooks/Real_Data_Dry_Run.md`（実データを使ったParser→Extractor→Merger→Report確認の手順書）・`schemas/merged_knowledge.schema.json`（8種のmerged entityをoneOf判別）・`schemas/manual_overrides.schema.json`（手動補正ファイル）・`schemas/merged_knowledge_collection.schema.json`（merge engineのcollection wrapper用。`report`にtype別・入力別の内訳・`relationshipTypeSummary`・`canonicalIdSummary`を追加済み）・`agents/merger/`（`MergeEngine`・`entity_base.py`共通処理・`character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`/`relationship.py`/`timeline.py`）・`agents/merger/overrides.py`（manual override loader）・`agents/merger/relationship_taxonomy.py`（relationshipType暫定taxonomy）・`agents/merger/canonical_ids.py`（canonicalId helper/validation）・`scripts/check_dry_run_inputs.py`（dry-run状態確認補助スクリプト）はmainへマージ済み。`feature/no-invisible-unicode-check`で、`scripts/check_invisible_unicode.py`を新規追加中。GitHubの hidden/bidirectional Unicode warning自体は今後マージブロッカーにしない方針を明確化した上で、bidi override/control・zero-width系・BOM・soft hyphen等の明示的に危険なコードポイント、および`unicodedata.category(ch) == "Cf"`/bidi制御クラスに該当する文字だけを検出する。**日本語・全角記号・罫線・矢印・通常のUnicode引用符は「2バイト文字だからNG」として検出しない**（既存Markdown・JSON schema descriptionの日本語を削除する必要は無い）。real data dry-run trial（実データでの実際の試験運用）・timeline contradiction detection・Wiki出力設計・relationshipType taxonomy本確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`）・canonical ID辞書（`knowledge/dictionaries/*.yaml`）本体の実装はまだ未着手。`entities`配下の`merged_knowledge.schema.json`への`$ref`接続は引き続き見送り中（PR #18のTODO）。`schemas/canonical_knowledge.schema.json`はStage C用の予約placeholder。重要ルール: **Stage A candidateのevidence（sourceType/confidence/evidenceIds/candidate ID/extractionRun）はマージ後も失わない**（schemaでevidenceRefs・sourceCandidatesを最低1件必須にして担保。manual override適用後も保持されることをテストで確認済み）。LLM呼び出し本体・provider連携・prompt設計は、CLAUDE.mdの方針により明示的な指示があるまで着手しない。

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

次の自然な一歩は `TASKS.md` の Next Actions（real data dry-run trialで見つかった既知の課題対応のうち残り（実データ頻出の未確認キャラクターID(234/225/230/222等、`scripts/check_character_dictionary_coverage.py`で確認可能)を人間がローマ字確認して`knowledge/dictionaries/characters.yaml`へconfirmed化。演出コマンド辞書拡充は`script command coverage improvement`・`script command coverage followup`、キャラクター辞書のloader/validation/coverage report基盤は`character dictionary coverage improvement`、互換性チェック判定差異の解消は`compatibility check consistency`、選択肢を含む実データでのdry-runは`branch / choice included dry-run`、そこで見つかった未登録コマンドのscript command coverage追加は`script command coverage followup`で対応済み、ruff known issues cleanupも対応済み・残るのは`agents/parser/parser.py::_parse_tokens`のC901のみ・TASKS.md §4参照）→ `Merged_Knowledge_Design.md` §13のPR分割案に従い GitHub Actions CIへの`ruff check`/`ruff format --check`組み込み → timeline contradiction detection → Wiki出力設計 → relationshipType taxonomy本確定 → canonical ID辞書実装）に従う。着手前に以下を守る。

- `agents/extractor/` のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（CLAUDE.mdの方針）
- Stage B実装では、Stage A candidateのevidence・provenance（sourceType/confidence/evidenceIds/candidate ID/extractionRun）を失わない（`Merged_Knowledge_Design.md` §4.1 / §10）

Parser Phase 1と同じ考え方（検証基準となるschemaを実体より先に作る）を踏襲する。
