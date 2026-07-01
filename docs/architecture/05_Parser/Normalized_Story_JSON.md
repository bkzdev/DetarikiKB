# Normalized Story JSON（正規化済みストーリーJSON仕様）

Version: 0.2 Draft  
Project: Detariki Knowledge Base (DKB)  
Path: `docs/architecture/05_Parser/Normalized_Story_JSON.md`

---

# 1. 目的

この文書は、Detariki Knowledge Base（DKB）のParserが出力する **正規化済みストーリーJSON** の形式を定義する。

DKBでは、ゲームスクリプトをそのままLLMやKnowledge Graphへ渡さない。

必ず以下の流れを通す。

```text
Raw Script
  ↓
Story Parser
  ↓
Normalized Story JSON
  ↓
AI Extraction
  ↓
Knowledge Graph
  ↓
Wiki Generator
```

この `Normalized Story JSON` は、以下すべての共通入力となる。

- Character Extractor
- Organization Extractor
- Location Extractor
- Item Extractor
- Relationship Extractor
- Timeline Builder
- Knowledge Graph Builder
- Wiki Generator
- Evidence Viewer
- 将来の全文検索・AI検索

---

# 2. 関連設計書

本仕様は以下の設計書を前提とする。

| 文書 | 役割 |
|---|---|
| `Identifier_Specification.md` | ID体系を定義 |
| `Story_Metadata.md` | タイトル・公開順・表示順などのメタデータを定義 |
| `Script_Compatibility_Check.md` | 新旧スクリプト差分・未知コマンド検知を定義 |
| `Parser.md` | Parser全体の責務を定義 |
| `Story_Format.md` | 元スクリプト形式の特徴を定義 |
| `JSON_Output.md` | 実装後のJSON出力詳細を定義予定 |

---

# 3. 基本方針

## 3.1 Raw Scriptを直接AIへ渡さない

ゲームスクリプトには以下が混在している。

- セリフ
- モノローグ
- ナレーション
- 選択肢
- 背景指定
- 立ち絵指定
- BGM / SE
- キャラクター番号割り当て
- 変数
- フラグ
- 分岐
- 演出命令

AIが直接読むにはノイズが多いため、Parserで正規化する。

---

## 3.2 本文と演出命令を分離する

セリフ本文と演出命令は別のデータとして扱う。

例:

```json
{
  "type": "dialogue",
  "speakerName": "レイン",
  "text": "まずは、これまで起きた現状と今後の対策を説明したいと思います"
}
```

```json
{
  "type": "stage_direction",
  "directionType": "background",
  "raw": "bg 1 1002"
}
```

---

## 3.3 Evidenceを必ず保持する

各ブロックは可能な限り元ファイルの位置情報を持つ。

これにより、AIが生成した知識から元ストーリーへ戻れる。

---

## 3.4 不明情報を破棄しない

Parserが話者・場所・演出の意味を解決できない場合でも、情報は破棄しない。

不明情報は `unknown` として保持する。

---

## 3.5 AI処理前の中間形式とする

このJSONは「完成したWiki用データ」ではない。

あくまでAI抽出前の、構造化された中間データである。

---

# 4. 全体構造

Normalized Story JSONは以下の階層を持つ。

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

---

# 5. StoryDocument

## 5.1 基本構造

```json
{
  "schemaVersion": "0.2",
  "documentType": "normalized_story",
  "storyId": "MAIN_S01_C02",
  "storyCategory": "MAIN",
  "metadata": {},
  "parser": {},
  "source": {},
  "compatibilityReport": {},
  "episodes": []
}
```

---

## 5.2 フィールド定義

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `schemaVersion` | Yes | string | Normalized Story JSONのスキーマバージョン |
| `documentType` | Yes | string | 固定値 `normalized_story` |
| `storyId` | Yes | string | Story ID |
| `storyCategory` | Yes | string | `MAIN`, `EVT`, `RAID`, `OTHER`, `CHAR_MAIN`, `CHAR_EXTRA`, `CHAR_DATE` |
| `metadata` | Yes | object | `Story_Metadata.md` に準拠するメタデータ |
| `parser` | Yes | object | Parser情報 |
| `source` | Yes | object | 元ファイル情報 |
| `compatibilityReport` | No | object | 互換性チェック結果 |
| `episodes` | Yes | array | Episodeの配列 |

---

# 6. metadata

`metadata` は `Story_Metadata.md` の内容を格納する。

例:

```json
{
  "metadata": {
    "storyTitle": "異形生物対策班、始動！",
    "displayTitle": "第1期 第2章「異形生物対策班、始動！」",
    "season": 1,
    "chapter": 2,
    "displayOrder": 10200,
    "releaseOrder": null,
    "canonicalOrder": null
  }
}
```

Parserが自動取得できない値は `null` とする。

---

# 7. parser

Parser自身の情報を記録する。

```json
{
  "parser": {
    "parserName": "DKB Story Parser",
    "parserVersion": "0.2.0",
    "parserMode": "game_script",
    "preserveStageDirections": true,
    "createdAt": "2026-07-01T00:00:00+09:00"
  }
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `parserName` | Yes | Parser名 |
| `parserVersion` | Yes | Parserバージョン |
| `parserMode` | Yes | `game_script`, `merged_text`, `manual` など |
| `preserveStageDirections` | Yes | 演出命令を保存したか |
| `createdAt` | No | 変換日時 |

---

# 8. source

元ファイル情報を記録する。

```json
{
  "source": {
    "sourceFile": "main1-02-1",
    "sourcePath": "data/raw/main/season1/chapter02/episode01.txt",
    "sourceFormat": "game_script",
    "encoding": "utf-8",
    "lineCount": 320
  }
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `sourceFile` | Yes | 元ファイル名 |
| `sourcePath` | No | 元ファイルパス |
| `sourceFormat` | Yes | `game_script`, `merged_text`, `manual` |
| `encoding` | No | 文字コード |
| `lineCount` | No | 元ファイルの行数 |

---

# 9. compatibilityReport

互換性チェック結果を任意で格納する。

詳細は `Script_Compatibility_Check.md` で定義する。

```json
{
  "compatibilityReport": {
    "parserCompatibility": "compatible",
    "unknownCommands": [],
    "newSpeechCommands": [],
    "unknownCharacterIds": [],
    "controlCharsRemoved": 0
  }
}
```

---

# 10. Episode

Episodeは1つのストーリー内の個別エピソードを表す。

## 10.1 基本構造

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "episodeNumber": 1,
  "metadata": {},
  "speakerAssignments": [],
  "scenes": []
}
```

---

## 10.2 フィールド定義

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `episodeId` | Yes | string | Episode ID |
| `episodeNumber` | Yes | number | Story内でのエピソード番号 |
| `metadata` | Yes | object | エピソードタイトルなど |
| `speakerAssignments` | No | array | スクリプト中の話者割り当て記録 |
| `scenes` | Yes | array | Sceneの配列 |

---

## 10.3 metadata

```json
{
  "metadata": {
    "episodeTitle": null,
    "episodeSubtitle": null,
    "displayTitle": "第1期 第2章 エピソード1",
    "sortKey": "MAIN_S01_C02_E01"
  }
}
```

エピソードタイトルが判明している場合:

```json
{
  "metadata": {
    "episodeTitle": "作戦参謀レイン",
    "displayTitle": "第1期 第2章 エピソード1「作戦参謀レイン」"
  }
}
```

---

# 11. Speaker Assignment

Raw Scriptでは、キャラクター番号やスロットを経由して話者が指定される。

DKBでは、その解決過程も必要に応じて保持する。

## 11.1 例

```json
{
  "speakerAssignments": [
    {
      "slot": "0",
      "sourceCharacterId": "26",
      "speakerId": "CHAR_RAIN",
      "speakerName": "レイン",
      "source": {
        "lineStart": 12,
        "lineEnd": 12,
        "raw": "@ScenarioCos 0 26"
      }
    }
  ]
}
```

---

## 11.2 対象となる構文

既存パーサーから引き継ぐ対象:

| Raw Script | 意味 |
|---|---|
| `$numX = character_id` | キャラクター番号の変数割り当て |
| `$valueX = character_id` | 追加キャラクター番号の変数割り当て |
| `@ScenarioCos slot character_id` | スロットへの直接キャラクター割り当て |
| `@ScenarioCosLoad slot variable` | 変数経由でスロットへ割り当て |
| `name ...` | 強制話者名 |
| `@ChTalk slot` | セリフ |
| `@ChTalkMono slot` | モノローグ |
| `@ChTalkSoundOff slot` | 音声なしセリフ |
| `@ChTalkSoundOffMono slot` | 音声なしモノローグ |
| `@ChTalkName slot name path` | コマンド内に話者名を持つセリフ |

---

# 12. Scene

Sceneは、場所・場面・状況が一定のまとまりを表す。

## 12.1 基本構造

```json
{
  "sceneId": "MAIN_S01_C02_E01_SC001",
  "sceneNumber": 1,
  "location": {
    "locationId": null,
    "locationName": "異形生物対策班　本部"
  },
  "blocks": []
}
```

---

## 12.2 フィールド定義

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `sceneId` | Yes | string | Scene ID |
| `sceneNumber` | Yes | number | Episode内のScene番号 |
| `location` | No | object | 場所情報 |
| `blocks` | Yes | array | Dialogueなどのブロック配列 |

---

## 12.3 Scene分割ルール

Phase 1では、以下をScene分割の候補とする。

- `【-】` の直後に場所名らしき行がある場合
- 背景変更コマンドが検出された場合
- エピソード区切りがある場合
- 手動で場所ラベルが与えられている場合

Scene分割が不確実な場合は、無理に分割せず同一Sceneとして扱ってよい。

---

# 13. Block共通仕様

`blocks` に入る各要素は、共通フィールドを持つ。

```json
{
  "id": "MAIN_S01_C02_E01_DLG0001",
  "type": "dialogue",
  "text": "...",
  "source": {}
}
```

---

## 13.1 共通フィールド

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `id` | Yes | string | Block ID |
| `type` | Yes | string | Block種別 |
| `text` | No | string | 正規化済み本文 |
| `rawText` | No | string | 元テキスト |
| `source` | Yes | object | Evidence用の元ファイル情報 |
| `notes` | No | array | Parserメモ |

---

## 13.2 Block種別

| type | 説明 |
|---|---|
| `dialogue` | 通常セリフ |
| `monologue` | 心の声・独白 |
| `narration` | ナレーション・地の文 |
| `choice` | 選択肢分岐 |
| `stage_direction` | 演出命令 |
| `unknown` | 分類不能な行 |

---

# 14. Dialogue Block

通常セリフを表す。

```json
{
  "id": "MAIN_S01_C02_E01_DLG0001",
  "type": "dialogue",
  "speaker": {
    "speakerId": "CHAR_RAIN",
    "speakerName": "レイン",
    "sourceCharacterId": "26",
    "slot": "0",
    "isResolved": true
  },
  "voice": {
    "hasVoice": true
  },
  "text": "というわけで、本日付けで異形生物対策班作戦参謀に任命されましたレインです",
  "rawText": "というわけで、本日付けで異形生物対策班\\n作戦参謀に任命されましたレインです",
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 24,
    "lineEnd": 25,
    "raw": "@ChTalk 0",
    "parserRule": "ch_talk_dialogue",
    "confidence": 1.0
  }
}
```

---

## 14.1 speaker

| Field | 必須 | 説明 |
|---|---:|---|
| `speakerId` | No | 解決済みCharacter ID |
| `speakerName` | Yes | 表示用話者名 |
| `sourceCharacterId` | No | 元スクリプト上のキャラクター番号 |
| `slot` | No | スクリプト上の話者スロット |
| `isResolved` | Yes | 正規キャラクターへ解決できたか |

不明人物の場合:

```json
{
  "speakerId": null,
  "speakerName": "不明人物(ID:234)",
  "sourceCharacterId": "234",
  "slot": "3",
  "isResolved": false
}
```

---

## 14.2 voice

音声有無を保持する。

```json
{
  "voice": {
    "hasVoice": false
  }
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `hasVoice` | No | 音声付きセリフかどうか |

対応例:

| Raw Command | type | `voice.hasVoice` |
|---|---|---:|
| `@ChTalk` | `dialogue` | true |
| `@ChTalkSoundOff` | `dialogue` | false |
| `@ChTalkName` | `dialogue` | unknown / null |

---

# 15. Monologue Block

モノローグ・心の声を表す。

Raw Script上では `@ChTalkMono`、`@ChTalkSoundOffMono`、または括弧付きセリフなどから生成される。

```json
{
  "id": "MAIN_S01_C02_E01_MONO0001",
  "type": "monologue",
  "speaker": {
    "speakerId": "CHAR_AKAGI_HINA",
    "speakerName": "赤城陽菜",
    "sourceCharacterId": "1",
    "slot": "0",
    "isResolved": true
  },
  "voice": {
    "hasVoice": false
  },
  "text": "なんか、滋養強壮剤的というか栄養ドリンクみたいな名前……",
  "rawText": "（なんか、滋養強壮剤的というか栄養ドリンクみたいな名前……）",
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 80,
    "lineEnd": 80,
    "parserRule": "ch_talk_sound_off_mono"
  }
}
```

---

# 16. ChTalkSoundOff

`@ChTalkSoundOff` は音声なしセリフとして扱う。

例:

```text
@ChTalkSoundOff 6
レイヴェル、今回のジャマーの特徴を皆に説明してやってくれ
```

変換例:

```json
{
  "id": "EVT_260624_E01_DLG0001",
  "type": "dialogue",
  "speaker": {
    "speakerId": null,
    "speakerName": "不明人物(ID:slot6)",
    "sourceCharacterId": null,
    "slot": "6",
    "isResolved": false
  },
  "voice": {
    "hasVoice": false
  },
  "text": "レイヴェル、今回のジャマーの特徴を皆に説明してやってくれ",
  "source": {
    "raw": "@ChTalkSoundOff 6",
    "parserRule": "ch_talk_sound_off_dialogue"
  }
}
```

---

# 17. ChTalkSoundOffMono

`@ChTalkSoundOffMono` は音声なしモノローグとして扱う。

例:

```text
@ChTalkSoundOffMono 1
（朝から班長殿にお会いできるなんて、
今日はきっといい一日になるはず！）
```

変換例:

```json
{
  "id": "CHAR_MAIN_CHARACTER234_E01_MONO0001",
  "type": "monologue",
  "speaker": {
    "slot": "1",
    "isResolved": false
  },
  "voice": {
    "hasVoice": false
  },
  "text": "朝から班長殿にお会いできるなんて、今日はきっといい一日になるはず！",
  "source": {
    "raw": "@ChTalkSoundOffMono 1",
    "parserRule": "ch_talk_sound_off_mono"
  }
}
```

---

# 18. ChTalkName

`@ChTalkName` はコマンド内に表示話者名を持つセリフとして扱う。

例:

```text
@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
ジャマー召喚！
```

変換例:

```json
{
  "id": "MAIN_S03_C68_E01_DLG0001",
  "type": "dialogue",
  "speaker": {
    "speakerId": null,
    "speakerName": "美海＆恵茉",
    "sourceCharacterId": null,
    "slot": "0",
    "isResolved": false
  },
  "text": "ジャマー召喚！",
  "source": {
    "raw": "@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186",
    "parserRule": "ch_talk_name_dialogue"
  }
}
```

`@ChTalkName` の後続に `name` 行が存在する場合もある。

ただし、`name` 行が常に存在するとは限らないため、`@ChTalkName` 自体を会話マーカーとして扱う。

---

# 19. Narration Block

ナレーション・地の文・場所表示・システム文などを表す。

```json
{
  "id": "MAIN_S01_C02_E01_NAR0001",
  "type": "narration",
  "text": "異形生物対策班　本部",
  "narrationType": "location_label",
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 20,
    "lineEnd": 20
  }
}
```

---

## 19.1 narrationType

| narrationType | 説明 |
|---|---|
| `location_label` | 場所表示 |
| `system` | システム文 |
| `mission_result` | 任務完了など |
| `ellipsis` | `・・・` などの間 |
| `plain` | 通常の地の文 |
| `unknown` | 不明 |

---

# 20. Choice Block

選択肢と分岐を表す。

既存スクリプトでは、以下のような構文が該当する。

```text
branch 大丈夫、必ずできるよ！ 仕事だから、頑張ろう
#if $branch
...
#elseif $branch
...
#endif
```

---

## 20.1 基本構造

```json
{
  "id": "MAIN_S01_C02_E01_CHOICE001",
  "type": "choice",
  "choiceText": null,
  "options": [
    {
      "optionId": "MAIN_S01_C02_E01_CHOICE001_OPT01",
      "optionText": "大丈夫、必ずできるよ！",
      "blocks": []
    },
    {
      "optionId": "MAIN_S01_C02_E01_CHOICE001_OPT02",
      "optionText": "仕事だから、頑張ろう",
      "blocks": []
    }
  ],
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 130,
    "lineEnd": 145
  }
}
```

---

## 20.2 option内のblocks

選択肢分岐内にも通常のBlockを入れる。

```json
{
  "optionId": "MAIN_S01_C02_E01_CHOICE001_OPT01",
  "optionText": "大丈夫、必ずできるよ！",
  "blocks": [
    {
      "id": "MAIN_S01_C02_E01_DLG0012",
      "type": "dialogue",
      "speaker": {
        "speakerId": "CHAR_AKAGI_HINA",
        "speakerName": "赤城陽菜",
        "isResolved": true
      },
      "text": "は、班長がそういうなら……頑張ります！",
      "source": {}
    }
  ]
}
```

---

# 21. Stage Direction Block

演出命令を表す。

Phase 1ではすべてを意味解析する必要はない。

ただし、必要に応じて保持できる構造にする。

```json
{
  "id": "MAIN_S01_C02_E01_STAGE0001",
  "type": "stage_direction",
  "directionType": "background",
  "command": "bg",
  "rawCommand": "bg",
  "normalizedCommand": "bg",
  "args": ["1", "1002"],
  "raw": "bg 1 1002",
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 10,
    "lineEnd": 10
  }
}
```

---

## 21.1 directionType

| directionType | 説明 |
|---|---|
| `background` | 背景 |
| `sound` | SE / BGM |
| `character_display` | 立ち絵表示 |
| `motion` | モーション |
| `effect` | 演出効果 |
| `camera` | カメラ |
| `ui` | 会話UI・スマホ画面など |
| `video` | 動画再生 |
| `system` | システム制御 |
| `unknown` | 不明 |

---

## 21.2 最近のスクリプトで確認されたStage Direction候補

以下は `stage_direction` として保持する候補である。

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

---

## 21.3 大文字・小文字ゆれ

Raw Scriptには以下のような表記ゆれが存在する。

```text
@Visibleoff
@VisibleOff
```

```text
@ChCameraoff
@ChCameraOff
```

Parserは以下を保持する。

```json
{
  "rawCommand": "@Visibleoff",
  "normalizedCommand": "@VisibleOff"
}
```

---

# 22. Unknown Block

Parserが分類できなかった行を保持する。

```json
{
  "id": "MAIN_S01_C02_E01_UNKNOWN0001",
  "type": "unknown",
  "rawText": "未分類の行",
  "source": {
    "sourceFile": "main1-02-1",
    "lineStart": 999,
    "lineEnd": 999
  },
  "notes": [
    "Parser could not classify this line."
  ]
}
```

不明行を捨てないことで、Parser改善時に再検証できる。

---

# 23. source / Evidence情報

すべてのBlockは `source` を持つ。

```json
{
  "source": {
    "sourceFile": "main1-02-1",
    "sourcePath": "data/raw/main/season1/chapter02/episode01.txt",
    "lineStart": 24,
    "lineEnd": 25,
    "raw": "@ChTalk 0",
    "parserRule": "ch_talk_dialogue",
    "confidence": 1.0
  }
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `sourceFile` | Yes | 元ファイル名 |
| `sourcePath` | No | 元ファイルパス |
| `lineStart` | No | 開始行 |
| `lineEnd` | No | 終了行 |
| `raw` | No | 元の命令行または本文 |
| `parserRule` | No | 適用したParserルール |
| `confidence` | No | Parser判断の信頼度 |

---

# 24. 完全例

以下は構造の例であり、全文ではない。

```json
{
  "schemaVersion": "0.2",
  "documentType": "normalized_story",
  "storyId": "MAIN_S01_C02",
  "storyCategory": "MAIN",
  "metadata": {
    "storyTitle": "異形生物対策班、始動！",
    "displayTitle": "第1期 第2章「異形生物対策班、始動！」",
    "season": 1,
    "chapter": 2
  },
  "parser": {
    "parserName": "DKB Story Parser",
    "parserVersion": "0.2.0",
    "parserMode": "game_script",
    "preserveStageDirections": true,
    "createdAt": null
  },
  "source": {
    "sourceFile": "main1-02-1",
    "sourcePath": "data/raw/main/season1/chapter02/episode01.txt",
    "sourceFormat": "game_script",
    "encoding": "utf-8"
  },
  "compatibilityReport": {
    "parserCompatibility": "compatible",
    "unknownCommands": [],
    "newSpeechCommands": [],
    "unknownCharacterIds": [],
    "controlCharsRemoved": 0
  },
  "episodes": [
    {
      "episodeId": "MAIN_S01_C02_E01",
      "episodeNumber": 1,
      "metadata": {
        "episodeTitle": null,
        "displayTitle": "第1期 第2章 エピソード1"
      },
      "speakerAssignments": [
        {
          "slot": "0",
          "sourceCharacterId": "26",
          "speakerId": "CHAR_RAIN",
          "speakerName": "レイン",
          "source": {
            "lineStart": 12,
            "lineEnd": 12,
            "raw": "@ScenarioCos 0 26"
          }
        }
      ],
      "scenes": [
        {
          "sceneId": "MAIN_S01_C02_E01_SC001",
          "sceneNumber": 1,
          "location": {
            "locationId": null,
            "locationName": "異形生物対策班　本部"
          },
          "blocks": [
            {
              "id": "MAIN_S01_C02_E01_DLG0001",
              "type": "dialogue",
              "speaker": {
                "speakerId": "CHAR_RAIN",
                "speakerName": "レイン",
                "sourceCharacterId": "26",
                "slot": "0",
                "isResolved": true
              },
              "voice": {
                "hasVoice": true
              },
              "text": "というわけで、本日付けで異形生物対策班作戦参謀に任命されましたレインです",
              "rawText": "というわけで、本日付けで異形生物対策班\\n作戦参謀に任命されましたレインです",
              "source": {
                "sourceFile": "main1-02-1",
                "lineStart": 24,
                "lineEnd": 25,
                "parserRule": "ch_talk_dialogue",
                "confidence": 1.0
              }
            }
          ]
        }
      ]
    }
  ]
}
```

---

# 25. Parser実装への要求

Parserは最低限、以下を実装する。

## Phase 1 Must

- `@ChTalk` を `dialogue` に変換する
- `@ChTalkMono` を `monologue` に変換する
- `@ChTalkSoundOff` を `dialogue` に変換する
- `@ChTalkSoundOffMono` を `monologue` に変換する
- `@ChTalkName` を `speakerName` 付き `dialogue` に変換する
- `msg` を `narration` に変換する
- `name` を強制話者名として扱う
- `$numX` / `$valueX` をキャラクター割り当てとして解決する
- `@ScenarioCos` / `@ScenarioCosLoad` を話者解決に使用する
- `branch` / `#if` / `#elseif` / `#else` / `#endif` を `choice` に変換する
- 不明話者を破棄しない
- 不明行を破棄しない
- 未知コマンドを検知する
- 未登録キャラクターIDを検知する
- 各BlockにEvidence用 `source` を付ける

---

## Phase 1 Should

- 場所ラベルからSceneを分割する
- `【-】` に相当するナレーションを `location_label` として扱う
- 演出命令を `stage_direction` として保持できるようにする
- Parserルール名を `source.parserRule` に保存する
- コマンド名の大文字・小文字ゆれを正規化する
- 制御文字除去件数を記録する

---

## Phase 1 Could

- 背景コマンドからLocationを推定する
- BGM / SE を保持する
- 表情・モーションをStage Directionとして保持する
- 文字列の正規化ルールを設定ファイル化する
- `@VideoLoad` / `@VideoPlay` を動画演出として分類する
- `@Smartphone` 系をUI演出として分類する

---

# 26. 今後のJSON Schema化

この設計書をもとに、次に以下を作成する。

```text
schemas/story.schema.json
```

その後、Parserは必ずこのJSON Schemaで出力を検証する。

---

# 27. 採用方針

- Raw Scriptは直接AIへ渡さない
- ParserはNormalized Story JSONを出力する
- IDは `Identifier_Specification.md` に従う
- タイトル・表示順・公開順は `Story_Metadata.md` に従う
- 新旧スクリプト互換性は `Script_Compatibility_Check.md` に従う
- 全BlockにEvidenceを付ける
- 不明情報は破棄せず保持する
- Phase 1では完全な演出解釈より、本文・話者・選択肢・Evidenceを優先する
