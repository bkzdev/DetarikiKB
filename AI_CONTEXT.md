# AI_CONTEXT

Project: Detariki Knowledge Base (DK)  
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

現在のフェーズは、Parser Phase 1の準備である。

目標:

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

今はまだ本格的なAI抽出やWiki生成には進まない。

現在やるべきことは以下。

1. 設計書を読む
2. `schemas/story.schema.json` を作る
3. Script Compatibility Checkerを作る
4. Parserの初期実装を作る
5. サンプル `.dec` ファイルで検証する
6. Unknown command / unknown character をレポートする

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

OpenAI APIは必要な補助用途のみ。

---

# 5. 作成済み・配置済みの重要設計書

以下の設計書がある前提で作業する。

```text
docs/architecture/05_Parser/Identifier_Specification.md
docs/architecture/05_Parser/Story_Metadata.md
docs/architecture/05_Parser/Normalized_Story_JSON.md
docs/architecture/05_Parser/Script_Compatibility_Check.md
```

必要に応じて以下も参照する。

```text
docs/architecture/01_Project/00_Project_Overview.md
docs/architecture/01_Project/00A_Architecture_Decisions.md
docs/architecture/05_Parser/Parser.md
docs/architecture/05_Parser/Story_Format.md
```

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

次に実装する順番は `Parser_Implementation_Plan.md` に従う。

推奨開始順:

1. `schemas/story.schema.json`
2. `config/script_commands.yaml`
3. `scripts/check_script_compatibility.py`
4. `agents/parser/tokenizer.py`
5. `agents/parser/resolver.py`
6. `agents/parser/parser.py`
7. `agents/parser/normalizer.py`
8. `agents/parser/exporter.py`
9. `scripts/normalize_story.py`
10. `tests/parser/`

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

---

# 17. 現在の推奨判断

次は実装へ進んでよい。

ただし、最初に作るべきはParser本体ではなく、以下である。

```text
schemas/story.schema.json
config/script_commands.yaml
scripts/check_script_compatibility.py
```

理由:

- JSON出力の検証基準を先に作る
- 新旧スクリプト差分を検知できるようにする
- Parser実装時の破損を早期検出できる
