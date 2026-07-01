# Script Compatibility Analysis（スクリプト互換性解析）

Version: 0.1 Draft  
Project: Detariki Knowledge Base (DKB)  
Date: 2026-07-01  
Input: Recent `.dec` script samples

---

# 1. 解析対象

| File | 種別 |
|---|---|
| `CAB-csl_script_charastory_character234-episode1.dec` | キャラクターメインストーリー |
| `CAB-csl_script_event_260504_childwb_event-episode1.dec` | 共同戦線イベントストーリー |
| `CAB-csl_script_event_260609_tukasahome-episode1.dec` | その他イベントストーリー |
| `CAB-csl_script_event_260624_cosplay_event-episode1.dec` | 通常イベントストーリー |
| `CAB-csl_script_mainstory_chapter68-main1.dec` | メインストーリー |
| `CAB-csl_script_surprise_character234Surprise_1.dec` | キャラクターデートストーリー |

---

# 2. 結論

最近のスクリプトには、既存Parserが想定していないコマンドが複数存在する。

特に重要なのは、以下の3種類である。

| Command | 重要度 | 理由 |
|---|---|---|
| `@ChTalkSoundOff` | High | 音声なしセリフ。既存Parserが無視すると話者割り当てが崩れる |
| `@ChTalkSoundOffMono` | High | 音声なしモノローグ。既存Parserが無視するとモノローグ判定できない |
| `@ChTalkName` | High | コマンド内に話者名を持つセリフ。既存Parserが無視すると話者名を取り逃がす |

これらは単なる演出命令ではなく、本文構造に関わるため、Parser Phase 1で対応すべきである。

---

# 3. 設計への反映

この解析結果は以下の設計書へ反映済み。

- `Normalized_Story_JSON.md`
- `Script_Compatibility_Check.md`

---

# 4. 追加対応すべき会話コマンド

## 4.1 `@ChTalkSoundOff`

音声なしセリフとして扱うべきである。

```text
@ChTalkSoundOff 6
レイヴェル、今回のジャマーの特徴を皆に説明してやってくれ
```

対応方針:

```json
{
  "type": "dialogue",
  "voice": {
    "hasVoice": false
  }
}
```

---

## 4.2 `@ChTalkSoundOffMono`

音声なしモノローグとして扱うべきである。

```text
@ChTalkSoundOffMono 1
（朝から班長殿にお会いできるなんて、
今日はきっといい一日になるはず！）
```

対応方針:

```json
{
  "type": "monologue",
  "voice": {
    "hasVoice": false
  }
}
```

---

## 4.3 `@ChTalkName`

コマンド内に話者名を持つセリフとして扱うべきである。

```text
@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
ジャマー召喚！
```

対応方針:

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

---

# 5. 主な未知コマンド

以下は既存Parserのコマンド辞書に追加検討すべきコマンドである。

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

Phase 1では、これらを `stage_direction` として保持できればよい。

---

# 6. キャラクター辞書更新候補

今回のサンプルでは、既存 `characters.json` に存在しない可能性があるキャラクターIDが確認された。

```text
83
85
86
222
225
228
230
232
234
257
258
```

対応方針:

- 未登録キャラクターIDは破棄しない
- `sourceCharacterId` として保持する
- `speakerId` は `null`
- `speakerName` は `不明人物(ID:xxx)` とする
- 後で辞書更新により解決できるようにする

---

# 7. 結論

Parser Phase 1では、本文抽出の正確性を優先し、以下を必須対応とする。

- `@ChTalk`
- `@ChTalkMono`
- `@ChTalkSoundOff`
- `@ChTalkSoundOffMono`
- `@ChTalkName`
- `msg`
- `name`
- `branch` / `#if` / `#elseif` / `#else` / `#endif`
- 未登録キャラクターID保持
- 未知コマンドレポート
- Evidence情報保持

演出コマンドは完全解析を急がず、まずは `stage_direction` として破棄せず保存する。
