# Parser Implementation Plan（Parser実装計画）

Version: 0.1 Draft  
Project: Detariki Knowledge Base (DKB)  
Recommended path: `docs/architecture/05_Parser/Parser_Implementation_Plan.md`

---

# 1. 目的

この文書は、DKB Parser Phase 1 の実装計画を定義する。

対象:

- `schemas/story.schema.json`
- `config/script_commands.yaml`
- `scripts/check_script_compatibility.py`
- `agents/parser/`
- `scripts/normalize_story.py`
- `tests/parser/`

この計画は、Antigravity / Claude Code / GPT-OSS120B などのAI開発エージェントが順番に実装できるように作成している。

---

# 2. 前提

作業開始前に以下を読むこと。

```text
AI_CONTEXT.md
docs/architecture/05_Parser/Identifier_Specification.md
docs/architecture/05_Parser/Story_Metadata.md
docs/architecture/05_Parser/Normalized_Story_JSON.md
docs/architecture/05_Parser/Script_Compatibility_Check.md
```

参考実装:

```text
reference/parser/story_parse_reference.py
reference/parser/characters_reference.json
```

注意:

`reference/parser/story_parse_reference.py` は直接改造しない。

---

# 3. 実装の全体像

```text
Phase 1: JSON Schema
Phase 2: Script Command Dictionary
Phase 3: Script Compatibility Checker
Phase 4: Tokenizer
Phase 5: Speaker Resolver
Phase 6: Parser Core
Phase 7: Normalizer
Phase 8: Exporter
Phase 9: CLI
Phase 10: Tests
Phase 11: Sample Validation
```

---

# 4. Phase 1: `schemas/story.schema.json`

## 4.1 目的

`Normalized_Story_JSON.md` に基づいて、正規化済みストーリーJSONのJSON Schemaを作成する。

## 4.2 作成ファイル

```text
schemas/story.schema.json
```

## 4.3 最低限含める構造

```text
StoryDocument
  ├─ schemaVersion
  ├─ documentType
  ├─ storyId
  ├─ storyCategory
  ├─ metadata
  ├─ parser
  ├─ source
  ├─ compatibilityReport
  └─ episodes
       └─ Episode
            ├─ episodeId
            ├─ episodeNumber
            ├─ metadata
            ├─ speakerAssignments
            └─ scenes
                 └─ Scene
                      ├─ sceneId
                      ├─ sceneNumber
                      ├─ location
                      └─ blocks
```

## 4.4 Block Types

必ず以下を許可する。

```text
dialogue
monologue
narration
choice
stage_direction
unknown
```

## 4.5 Acceptance Criteria

- `schemaVersion` は必須
- `documentType` は `normalized_story`
- `storyCategory` は以下のenum

```text
MAIN
EVT
RAID
OTHER
CHAR_MAIN
CHAR_EXTRA
CHAR_DATE
```

- `episodes` は配列
- `scenes` は配列
- `blocks` は配列
- Blockごとに `id`, `type`, `source` を持てる
- `dialogue` / `monologue` は `speaker` を持てる
- `voice.hasVoice` を許可する
- `choice.options[].blocks` を許可する
- `stage_direction.rawCommand` / `normalizedCommand` を許可する
- `compatibilityReport` を許可する

---

# 5. Phase 2: `config/script_commands.yaml`

## 5.1 目的

既知コマンドを辞書化し、Parserと互換性チェックで共通利用する。

## 5.2 作成ファイル

```text
config/script_commands.yaml
```

## 5.3 初期内容

```yaml
speech:
  - "@ChTalk"
  - "@ChTalkMono"
  - "@ChTalkSoundOff"
  - "@ChTalkSoundOffMono"
  - "@ChTalkName"

speaker_assignment:
  - "@ScenarioCos"
  - "@ScenarioCosLoad"
  - "name"

variable_assignment:
  - "$num"
  - "$value"

choice:
  - "branch"
  - "#if"
  - "#elseif"
  - "#else"
  - "#endif"

narration:
  - "msg"

stage_direction:
  - "bg"
  - "bgm"
  - "se"
  - "@FaceLow"
  - "@Visible"
  - "@VisibleOff"
  - "@Visibleoff"
  - "@ChCamera"
  - "@ChCameraOff"
  - "@ChCameraoff"
  - "@MotionReset"
  - "@TalkPos"
  - "@TalkPosLLL"
  - "@TalkPosRRR"
  - "@ChCharaEye"
  - "@ChCharaEyeOff"
  - "@ChCharaEyeoff"
  - "@Smartphone"
  - "@SmartphoneOff"
  - "@Smartphoneoff"
  - "@VideoLoad"
  - "@VideoPlay"
  - "segmentCorrection"
  - "visibleAccessory"

ignored:
  - ""
```

## 5.4 Acceptance Criteria

- YAMLとして読み込める
- ParserとCompatibility Checkerで共有できる
- 大文字・小文字ゆれを検知または正規化できる余地を残す

---

# 6. Phase 3: `scripts/check_script_compatibility.py`

## 6.1 目的

Raw Scriptを処理する前に、未知コマンド・新規会話コマンド・未登録キャラIDなどを検出する。

## 6.2 作成ファイル

```text
scripts/check_script_compatibility.py
```

## 6.3 入力

```bash
python scripts/check_script_compatibility.py data/raw/
```

または単一ファイル:

```bash
python scripts/check_script_compatibility.py data/raw/main/example.dec
```

## 6.4 出力

```text
data/reports/script_compatibility_report.json
data/reports/script_compatibility_report.md
```

## 6.5 検出項目

- unknownCommands
- newSpeechCommands
- changedCommandPatterns
- unknownCharacterIds
- branchIssues
- controlChars
- caseVariants
- hyphenOptionLines

## 6.6 Compatibility Status

```text
compatible
warning
needs_update
blocked
```

## 6.7 Acceptance Criteria

- 6本のサンプル `.dec` を読み込める
- `@ChTalkSoundOff`, `@ChTalkSoundOffMono`, `@ChTalkName` をspeechとして認識できる
- 未知コマンドを集計できる
- 未登録キャラクターIDを検出できる
- Markdownレポートを出せる
- JSONレポートを出せる
- 読み込み失敗時に安全にエラー表示する

---

# 7. Phase 4: `agents/parser/tokenizer.py`

## 7.1 目的

Raw Scriptを行単位・コマンド単位のTokenへ分解する。

## 7.2 作成ファイル

```text
agents/parser/tokenizer.py
```

## 7.3 想定クラス

```python
@dataclass
class ScriptToken:
    line_number: int
    raw: str
    command: str | None
    args: list[str]
    text: str | None
    token_type: str
```

## 7.4 token_type候補

```text
command
text
empty
control_char
hyphen_option
unknown
```

## 7.5 対応すべき例

```text
@ChTalk 0
@ChTalkSoundOff 6
@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
msg
name ジャマー
$num1 = 234
@ScenarioCos 1 234
branch A B
#if $branch
#else
#endif
```

## 7.6 Acceptance Criteria

- 行番号を保持する
- raw行を保持する
- commandとargsを分離する
- 制御文字を検出する
- ハイフン行を検出する
- 日本語本文を壊さない

---

# 8. Phase 5: `agents/parser/resolver.py`

## 8.1 目的

キャラクターID・話者スロット・強制話者名を解決する。

## 8.2 作成ファイル

```text
agents/parser/resolver.py
```

## 8.3 想定クラス

```python
@dataclass
class Speaker:
    speaker_id: str | None
    speaker_name: str
    source_character_id: str | None
    slot: str | None
    is_resolved: bool
```

```python
class SpeakerResolver:
    def assign_character(self, slot: str, source_character_id: str) -> None:
        ...

    def assign_variable(self, variable_name: str, source_character_id: str) -> None:
        ...

    def resolve_slot(self, slot: str) -> Speaker:
        ...

    def set_forced_name(self, name: str) -> None:
        ...
```

## 8.4 入力辞書

```text
reference/parser/characters_reference.json
```

将来的には:

```text
knowledge/dictionaries/characters.yaml
```

## 8.5 Acceptance Criteria

- `$numX = character_id` を保持できる
- `$valueX = character_id` を保持できる
- `@ScenarioCos slot character_id` を解決できる
- `@ScenarioCosLoad slot variable` を解決できる
- `name ...` を強制話者名として扱える
- `@ChTalkName` のコマンド内話者名を扱える
- 未登録キャラIDを破棄しない
- `speakerId: null` を許容する

---

# 9. Phase 6: `agents/parser/parser.py`

## 9.1 目的

Token列からNormalized Storyの中間構造を作る。

## 9.2 作成ファイル

```text
agents/parser/parser.py
```

## 9.3 対応するBlock

```text
dialogue
monologue
narration
choice
stage_direction
unknown
```

## 9.4 会話コマンド対応

```text
@ChTalk              → dialogue, voice.hasVoice = true
@ChTalkMono          → monologue, voice.hasVoice = true
@ChTalkSoundOff      → dialogue, voice.hasVoice = false
@ChTalkSoundOffMono  → monologue, voice.hasVoice = false
@ChTalkName          → dialogue, speakerName from command
```

## 9.5 Narration対応

```text
msg
```

## 9.6 Choice対応

```text
branch
#if
#elseif
#else
#endif
```

Phase 1では完全な分岐木でなくてもよいが、情報は破棄しない。

## 9.7 Stage Direction対応

既知stage directionコマンドは `stage_direction` として保持する。

未知コマンドも、必要に応じて `stage_direction` または `unknown` として保持する。

## 9.8 Acceptance Criteria

- 本文行を直前の会話コマンドへ紐づけられる
- 会話コマンド直後の複数行本文を1Blockにできる
- `@ChTalkSoundOff` を捨てない
- `@ChTalkSoundOffMono` を捨てない
- `@ChTalkName` を捨てない
- `name` 行の扱いを誤らない
- source lineStart / lineEnd を保持する
- unknown行を捨てない

---

# 10. Phase 7: `agents/parser/normalizer.py`

## 10.1 目的

Parser中間構造を `Normalized_Story_JSON.md` に準拠したJSONへ整形する。

## 10.2 作成ファイル

```text
agents/parser/normalizer.py
```

## 10.3 主な処理

- storyId付与
- episodeId付与
- sceneId付与
- block id付与
- metadata統合
- parser情報付与
- source情報付与
- compatibilityReport統合
- text整形
- rawText保持
- voice情報付与
- speaker情報整形

## 10.4 Acceptance Criteria

- `schemaVersion: "0.2"` を出力できる
- `documentType: "normalized_story"` を出力できる
- ID仕様に沿ったIDを生成できる
- `episodes[].scenes[].blocks[]` を生成できる
- 各Blockに `source` を付与できる
- JSON Schemaで検証できる

---

# 11. Phase 8: `agents/parser/exporter.py`

## 11.1 目的

Normalized Story JSONをファイルへ出力する。

## 11.2 作成ファイル

```text
agents/parser/exporter.py
```

## 11.3 出力先例

```text
data/normalized/main/MAIN_S03_C68_E01.json
data/normalized/event/EVT_260624_E01.json
data/normalized/character/CHAR_MAIN_CHARACTER234_E01.json
```

## 11.4 Acceptance Criteria

- UTF-8で出力する
- ensure_ascii=Falseで日本語を保持する
- pretty printする
- 出力ディレクトリを自動作成する
- 既存ファイル上書き時は安全に処理する

---

# 12. Phase 9: `scripts/normalize_story.py`

## 12.1 目的

CLIからRaw ScriptをNormalized Story JSONへ変換する入口を作る。

## 12.2 作成ファイル

```text
scripts/normalize_story.py
```

## 12.3 CLI例

```bash
python scripts/normalize_story.py \
  --input data/raw/main/CAB-csl_script_mainstory_chapter68-main1.dec \
  --story-id MAIN_S03_C68 \
  --episode-id MAIN_S03_C68_E01 \
  --category MAIN \
  --output data/normalized/main/
```

## 12.4 Acceptance Criteria

- 単一ファイルを変換できる
- storyId / episodeId / category を引数で受け取れる
- JSON Schema validationを任意で実行できる
- compatibility checkを任意で実行できる
- エラーを読みやすく表示する

---

# 13. Phase 10: Tests

## 13.1 作成ディレクトリ

```text
tests/parser/
```

## 13.2 作成テスト

```text
tests/parser/test_tokenizer.py
tests/parser/test_resolver.py
tests/parser/test_parser_basic.py
tests/parser/test_script_compatibility.py
tests/parser/test_normalized_story_schema.py
```

## 13.3 Fixtures

```text
tests/fixtures/parser/
```

サンプルは小さな抜粋を作る。

実データ全体をテストに入れすぎない。

## 13.4 必須テストケース

- `@ChTalk`
- `@ChTalkMono`
- `@ChTalkSoundOff`
- `@ChTalkSoundOffMono`
- `@ChTalkName`
- `name`
- `msg`
- `@ScenarioCos`
- `@ScenarioCosLoad`
- `$numX`
- `$valueX`
- 未登録キャラID
- 未知コマンド
- 制御文字
- `branch` / `#if` / `#else` / `#endif`

---

# 14. Phase 11: Sample Validation

## 14.1 対象サンプル

以下のようなサンプルで検証する。

```text
CAB-csl_script_charastory_character234-episode1.dec
CAB-csl_script_event_260504_childwb_event-episode1.dec
CAB-csl_script_event_260609_tukasahome-episode1.dec
CAB-csl_script_event_260624_cosplay_event-episode1.dec
CAB-csl_script_mainstory_chapter68-main1.dec
CAB-csl_script_surprise_character234Surprise_1.dec
```

## 14.2 確認項目

- compatibility reportが出る
- `@ChTalkSoundOff` がdialogueになる
- `@ChTalkSoundOffMono` がmonologueになる
- `@ChTalkName` がspeakerNameを保持する
- unknown character IDが破棄されない
- unknown commandsがレポートされる
- JSON Schema validationが通る
- 日本語本文が崩れない

---

# 15. 実装順序の推奨

AIエージェントは以下の順番で作業する。

```text
1. schemas/story.schema.json
2. config/script_commands.yaml
3. scripts/check_script_compatibility.py
4. tests/parser/test_script_compatibility.py
5. agents/parser/tokenizer.py
6. tests/parser/test_tokenizer.py
7. agents/parser/resolver.py
8. tests/parser/test_resolver.py
9. agents/parser/parser.py
10. tests/parser/test_parser_basic.py
11. agents/parser/normalizer.py
12. agents/parser/exporter.py
13. scripts/normalize_story.py
14. tests/parser/test_normalized_story_schema.py
```

理由:

- 先に検証基準を作る
- 互換性チェックでスクリプト差分を検知できるようにする
- Parser本体は小さく分割して作る
- 各段階でpytestを追加する

---

# 16. 完了条件

Parser Phase 1は以下を満たしたら完了とする。

```text
schemas/story.schema.json がある
config/script_commands.yaml がある
scripts/check_script_compatibility.py がある
agents/parser/ 一式がある
scripts/normalize_story.py がある
tests/parser/ がある
6種類のサンプルスクリプトで互換性チェックできる
1ファイル以上をNormalized Story JSONへ変換できる
出力JSONがstory.schema.jsonで検証できる
@ChTalkSoundOff / @ChTalkSoundOffMono / @ChTalkName に対応している
未知コマンド・未登録キャラIDを破棄せずレポートできる
```

---

# 17. 実装時の注意

## 17.1 完璧な演出解析を急がない

Phase 1では以下を優先する。

1. 本文
2. 話者
3. モノローグ
4. ナレーション
5. 選択肢
6. Evidence
7. unknown retention

演出は `stage_direction` として保持できればよい。

---

## 17.2 不明情報を捨てない

Parserがわからないものは、エラー停止よりも以下を優先する。

```text
unknown block
unknown command report
unknown character report
```

ただし、本文境界が壊れる場合は `needs_update` または `blocked` にする。

---

## 17.3 テストを小さくする

実スクリプト全文をテストに入れすぎない。

必要な構文だけの小さなfixtureを作る。

---

## 17.4 既存Parserを壊さない

`reference/parser/story_parse_reference.py` は直接変更しない。

---

# 18. AIエージェントへの実装指示テンプレート

```text
AI_CONTEXT.md と docs/architecture/05_Parser/ 配下の設計書を読んでください。

Parser_Implementation_Plan.md の Phase 1 から順番に実装してください。

まず schemas/story.schema.json を作成してください。
次に config/script_commands.yaml を作成してください。
次に scripts/check_script_compatibility.py を作成してください。

reference/parser/story_parse_reference.py は直接改造しないでください。
DKB Parserは agents/parser/ に新規実装してください。

実装ごとに pytest を追加してください。
不明コマンド、不明キャラクターID、不明行は破棄しないでください。
```

---

# 19. 次フェーズ候補

Parser Phase 1完了後に検討する。

```text
Phase 2: Character Extractor
Phase 3: Relationship Extractor
Phase 4: Location / Organization Extractor
Phase 5: Knowledge Graph Builder
Phase 6: Wiki Generator
Phase 7: AI Analysis Generator
```
