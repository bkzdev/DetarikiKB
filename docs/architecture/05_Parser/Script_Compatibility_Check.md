# Script Compatibility Check（スクリプト互換性チェック仕様）

Version: 0.1 Draft  
Project: Detariki Knowledge Base (DKB)  
Path: `docs/architecture/05_Parser/Script_Compatibility_Check.md`

---

# 1. 目的

この文書は、Detariki Knowledge Base（DKB）における **元スクリプトの互換性チェック** の仕様を定義する。

目的は、ゲーム側のスクリプト形式に新機能・新命令・新構文が追加された場合に、Parserの破損や抽出漏れを早期に検知することである。

---

# 2. 背景

DKBでは、ゲームスクリプトをParserで正規化してからAI抽出・Knowledge Graph化・Wiki生成を行う。

しかし、ゲーム運営の更新により、スクリプトには以下のような変化が発生する可能性がある。

- 新しい会話コマンドの追加
- 新しいモノローグコマンドの追加
- コマンド引数形式の変更
- 新しい演出命令の追加
- コマンド名の大文字・小文字ゆれ
- 新しいキャラクターIDの追加
- 新しい分岐形式の追加
- 制御文字や特殊行の追加
- ファイル命名規則の変化

そのため、Parser実装とは別に、スクリプト互換性チェック機能を持つ。

---

# 3. 対象ファイル

対象は `data/raw/` 以下に配置される `.dec` または `.txt` 形式のストーリースクリプトである。

例:

```text
data/raw/main/
data/raw/event/
data/raw/character/
data/raw/collaboration/
data/raw/other/
```

---

# 4. チェック対象

互換性チェックでは、主に以下を検出する。

| 種別 | 内容 |
|---|---|
| 未知コマンド | Parserが知らないコマンド |
| 新規会話コマンド | セリフ・モノローグに影響する未知コマンド |
| 既存コマンドの新形式 | 引数数や構文が変わった既存コマンド |
| 未登録キャラクターID | `characters.json` に存在しないID |
| 分岐構文 | `branch`, `#if`, `#elseif`, `#else`, `#endif` の異常 |
| 制御文字 | `\x02`, `\x07`, `\x08` など |
| 表記ゆれ | `@Visibleoff` / `@VisibleOff` など |
| 分類不能行 | Parserが扱えない行 |

---

# 5. チェック結果の分類

互換性チェック結果は以下の4段階で分類する。

| Status | 意味 |
|---|---|
| `compatible` | 既存Parserで問題なく処理可能 |
| `warning` | 処理可能だが未知コマンドや未登録IDがある |
| `needs_update` | 本文抽出に影響する新規構文がある |
| `blocked` | Parserが安全に処理できない |

---

# 6. 既知コマンド辞書

互換性チェックは、既知コマンド辞書をもとに行う。

推奨配置:

```text
knowledge/dictionaries/script_commands.yaml
```

または:

```text
config/script_commands.yaml
```

---

## 6.1 コマンド分類

```yaml
speech:
  - "@ChTalk"
  - "@ChTalkMono"
  - "@ChTalkSoundOff"
  - "@ChTalkSoundOffMono"
  - "@ChTalkName"

speaker_assignment:
  - "$num"
  - "$value"
  - "@ScenarioCos"
  - "@ScenarioCosLoad"
  - "name"

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
  - "@ChCamera"
  - "@ChCameraOff"
  - "@MotionReset"
  - "@TalkPos"
  - "@TalkPosLLL"
  - "@TalkPosRRR"
  - "@ChCharaEye"
  - "@ChCharaEyeOff"
  - "@Smartphone"
  - "@SmartphoneOff"
  - "@VideoLoad"
  - "@VideoPlay"
  - "segmentCorrection"

ignored:
  - ""
```

---

# 7. 重要コマンド

## 7.1 既存会話コマンド

Parser Phase 1で必ず対応する。

```text
@ChTalk
@ChTalkMono
```

---

## 7.2 追加対応が必要な会話コマンド

最近のサンプルで確認されたため、Parser Phase 1に含める。

```text
@ChTalkSoundOff
@ChTalkSoundOffMono
@ChTalkName
```

---

## 7.3 `@ChTalkSoundOff`

音声なしセリフ。

例:

```text
@ChTalkSoundOff 6
レイヴェル、今回のジャマーの特徴を皆に説明してやってくれ
```

変換方針:

```json
{
  "type": "dialogue",
  "voice": {
    "hasVoice": false
  }
}
```

---

## 7.4 `@ChTalkSoundOffMono`

音声なしモノローグ。

例:

```text
@ChTalkSoundOffMono 1
（朝から班長殿にお会いできるなんて、
今日はきっといい一日になるはず！）
```

変換方針:

```json
{
  "type": "monologue",
  "voice": {
    "hasVoice": false
  }
}
```

---

## 7.5 `@ChTalkName`

コマンド内に話者名を持つセリフ。

例:

```text
@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
ジャマー召喚！
```

変換方針:

```json
{
  "type": "dialogue",
  "speaker": {
    "speakerId": null,
    "speakerName": "美海＆恵茉",
    "isResolved": false
  }
}
```

注意:

`@ChTalkName` の後に `name` 行が続く場合もあるが、必ず存在するとは限らない。  
そのため `@ChTalkName` 自体を会話マーカーとして扱う。

---

# 8. 未知コマンド検知

## 8.1 判定方法

1行の先頭トークンを取得する。

例:

```text
@FaceLow 0 1
```

先頭トークン:

```text
@FaceLow
```

既知コマンド辞書に存在しない場合、未知コマンドとして記録する。

---

## 8.2 出力例

```json
{
  "unknownCommands": [
    {
      "command": "@NewCommand",
      "count": 12,
      "files": [
        "CAB-csl_script_event_xxx.dec"
      ],
      "sampleLines": [
        {
          "lineNumber": 120,
          "raw": "@NewCommand 1 2 3"
        }
      ]
    }
  ]
}
```

---

# 9. 新規会話コマンド検知

未知コマンドのうち、以下の条件を満たすものは新規会話コマンド候補とする。

- コマンド名に `Talk` が含まれる
- コマンド名に `Name` が含まれる
- 直後に日本語本文が続く
- 引数に話者スロットらしき数値が含まれる
- 既存の `@ChTalk` 系と似た構造を持つ

---

## 9.1 出力例

```json
{
  "newSpeechCommands": [
    {
      "command": "@ChTalkSoundOff",
      "reason": "Command name contains Talk and is followed by text lines.",
      "severity": "high",
      "suggestedType": "dialogue"
    }
  ]
}
```

---

# 10. 既存コマンドの新形式検知

同じコマンドでも、引数形式が変わる可能性がある。

例:

```text
@ChTalk 0
@ChTalk 0 emotion=smile
@ChTalk player 0
```

互換性チェックでは、コマンドごとに引数パターンを集計する。

---

## 10.1 出力例

```json
{
  "changedCommandPatterns": [
    {
      "command": "@ChTalk",
      "knownPatterns": [
        "@ChTalk {slot}"
      ],
      "observedPattern": "@ChTalk {slot} {option}",
      "sample": "@ChTalk 0 emotion=smile",
      "severity": "medium"
    }
  ]
}
```

---

# 11. 未登録キャラクターID検知

スクリプト内の以下を対象に、キャラクターIDを抽出する。

```text
$numX = character_id
$valueX = character_id
@ScenarioCos slot character_id
@ScenarioCosLoad slot variable
```

抽出された `sourceCharacterId` が `characters.json` に存在しない場合、未登録キャラクターIDとして記録する。

---

## 11.1 出力例

```json
{
  "unknownCharacterIds": [
    {
      "sourceCharacterId": "234",
      "files": [
        "CAB-csl_script_charastory_character234-episode1.dec",
        "CAB-csl_script_surprise_character234Surprise_1.dec"
      ],
      "sampleLines": [
        {
          "lineNumber": 18,
          "raw": "@ScenarioCos 1 234"
        }
      ]
    }
  ]
}
```

---

## 11.2 Parser側の扱い

未登録キャラクターIDは破棄しない。

```json
{
  "speaker": {
    "speakerId": null,
    "speakerName": "不明人物(ID:234)",
    "sourceCharacterId": "234",
    "isResolved": false
  }
}
```

---

# 12. 分岐構文チェック

以下の構文を対象にする。

```text
branch
#if
#elseif
#else
#endif
```

チェック内容:

- `branch` に選択肢テキストが存在するか
- `#if` と `#endif` が対応しているか
- `#elseif` / `#else` が不自然な位置にないか
- 分岐内に本文ブロックが存在するか

---

## 12.1 出力例

```json
{
  "branchIssues": [
    {
      "type": "missing_endif",
      "lineNumber": 140,
      "raw": "#if $branch",
      "severity": "high"
    }
  ]
}
```

---

# 13. 制御文字チェック

以下のような制御文字を検出する。

```text
\x02
\x07
\x08
```

Parserでは本文として扱わず除去する。

ただし、除去件数は記録する。

---

## 13.1 出力例

```json
{
  "controlChars": {
    "removedCount": 3,
    "chars": [
      "\\x02",
      "\\x07",
      "\\x08"
    ]
  }
}
```

---

# 14. 表記ゆれチェック

以下のような大文字・小文字ゆれを検出する。

```text
@Visibleoff
@VisibleOff
```

```text
@ChCameraoff
@ChCameraOff
```

対応方針:

- `rawCommand` には元表記を保存
- `normalizedCommand` には正規化後の表記を保存
- Parser内部では正規化後のコマンドで処理する

---

## 14.1 出力例

```json
{
  "caseVariants": [
    {
      "normalizedCommand": "@VisibleOff",
      "variants": [
        "@Visibleoff",
        "@VisibleOff"
      ],
      "count": 144
    }
  ]
}
```

---

# 15. ハイフン行チェック

以下のような行を検出する。

```text
- speed 0.1
- next idle
- range 0.03
```

これらは独立した本文ではなく、直前の演出命令に対する補助指定である可能性が高い。

Phase 1では `stage_direction` として保持する。

---

# 16. 互換性レポート形式

互換性チェックは以下のJSONを出力する。

```json
{
  "schemaVersion": "0.1",
  "documentType": "script_compatibility_report",
  "targetFiles": [],
  "summary": {},
  "files": []
}
```

---

## 16.1 summary

```json
{
  "summary": {
    "totalFiles": 6,
    "totalLines": 12000,
    "parserCompatibility": "needs_update",
    "unknownCommandCount": 38,
    "newSpeechCommandCount": 3,
    "unknownCharacterIdCount": 11,
    "controlCharsRemoved": 3
  }
}
```

---

## 16.2 file report

```json
{
  "file": "CAB-csl_script_event_260624_cosplay_event-episode1.dec",
  "storyCategory": "EVT",
  "parserCompatibility": "needs_update",
  "lineCount": 1800,
  "unknownCommands": [
    "@FaceLow",
    "segmentCorrection"
  ],
  "newSpeechCommands": [
    "@ChTalkSoundOff"
  ],
  "unknownCharacterIds": [
    "232"
  ],
  "controlCharsRemoved": 0,
  "branchIssues": [],
  "caseVariants": []
}
```

---

# 17. Severity

| Severity | 意味 |
|---|---|
| `low` | 無視しても本文抽出に大きな影響はない |
| `medium` | 一部情報が失われる可能性がある |
| `high` | 本文・話者・選択肢抽出に影響する |
| `critical` | Parserが安全に処理できない |

---

# 18. Compatibility Status 判定基準

## 18.1 compatible

条件:

- 未知の会話コマンドなし
- 分岐構文エラーなし
- 未知コマンドがすべて無視可能
- 未登録キャラクターIDなし、または安全にunknown speaker化可能

---

## 18.2 warning

条件:

- 未知演出コマンドがある
- 未登録キャラクターIDがある
- 制御文字が除去された
- ただし本文抽出には影響しない

---

## 18.3 needs_update

条件:

- 新規会話コマンドがある
- 既存会話コマンドの引数形式が変化している
- 新しい分岐構文がある
- 既存Parserでは本文や話者を取り逃がす可能性がある

---

## 18.4 blocked

条件:

- ファイルの読み込みに失敗
- エンコード不明
- 分岐構文が破綻している
- 会話本文の境界が判断できない
- Parserが安全なfallbackを作れない

---

# 19. CLI設計

将来的に以下のようなCLIを作成する。

```bash
python scripts/check_script_compatibility.py data/raw/event/
```

出力:

```text
data/reports/script_compatibility_report.json
data/reports/script_compatibility_report.md
```

---

# 20. CI連携

GitHub Actionsで、新しいRaw Scriptが追加されたときに互換性チェックを実行する。

```text
.github/workflows/script-compatibility.yml
```

実行タイミング:

- `data/raw/**` が変更されたPR
- Parser辞書が変更されたPR
- 手動実行

失敗条件:

- `parserCompatibility = blocked`
- `critical` severityが存在
- 新規会話コマンドがあるのに辞書未登録

---

# 21. Parserへの反映フロー

新しいスクリプトを追加したときの流れ:

```text
Raw Script追加
  ↓
Script Compatibility Check
  ↓
unknown command / new speech command を検出
  ↓
必要なら script_commands.yaml を更新
  ↓
Parserルールを追加
  ↓
Normalized Story JSONで検証
  ↓
story.schema.jsonで検証
```

---

# 22. 今回サンプルから反映する決定事項

最近のサンプル解析により、以下をParser Phase 1に含める。

## Must

- `@ChTalkSoundOff`
- `@ChTalkSoundOffMono`
- `@ChTalkName`
- 未登録キャラクターID検知
- 未知コマンド検知
- 制御文字除去件数記録

## Should

- 大文字・小文字ゆれ検知
- ハイフン行検知
- 演出コマンドを `stage_direction` として保持
- 互換性レポートJSON出力

## Could

- コマンド別出現頻度レポート
- Story Category別のコマンド差分レポート
- Parser対応率スコア
- Markdown版互換性レポート出力

---

# 23. 採用方針

- 新しいRaw Scriptを投入したら、まず互換性チェックを行う
- 未知コマンドを即エラーにせず、分類してレポートする
- 会話系の未知コマンドは高優先度で扱う
- 演出系の未知コマンドはPhase 1では `stage_direction` として保持する
- 未登録キャラクターIDは破棄せず `unknown speaker` として保持する
- 互換性チェックはParser改善の入口として扱う
