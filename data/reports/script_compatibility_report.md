# Script Compatibility Report

生成日時: 2026-07-01 15:02:56 UTC

## サマリー

| 項目 | 値 |
|---|---|
| 総合互換性 | 🔶 **needs_update** |
| ファイル数 | 8 |
| 総行数 | 9993 |
| 未知コマンド種類 | 34 |
| 新規会話コマンド候補 | 8 |
| 未登録キャラクターID | 17 |
| 制御文字除去件数 | 19 |

## ファイル別結果

| ファイル | 互換性 | 行数 | 未知Cmd | 新規会話 | 未登録ID | 制御文字 |
|---|---|---:|---:|---:|---:|---:|
| basic_dialogue.dec | ✅ compatible | 35 | 0 | 0 | 0 | 0 |
| CAB-csl_script_charastory_character234-episode1.dec | 🔶 needs_update | 1331 | 5 | 2 | 3 | 7 |
| CAB-csl_script_event_260504_childwb_event-episode1.dec | ⚠️ warning | 2274 | 5 | 0 | 5 | 8 |
| CAB-csl_script_event_260609_tukasahome-episode1.dec | 🔶 needs_update | 2095 | 6 | 2 | 5 | 0 |
| CAB-csl_script_event_260624_cosplay_event-episode1.dec | 🔶 needs_update | 2159 | 7 | 1 | 2 | 0 |
| CAB-csl_script_mainstory_chapter68-main1.dec | 🔶 needs_update | 1862 | 5 | 2 | 0 | 2 |
| CAB-csl_script_surprise_character234Surprise_1.dec | 🔶 needs_update | 219 | 5 | 1 | 1 | 2 |
| unknown_char.dec | ⚠️ warning | 18 | 1 | 0 | 1 | 0 |

## 🔶 新規会話コマンド候補

これらのコマンドは本文抽出に影響する可能性があります。辞書への追加を検討してください。

- `@TalkCamera3` — Command name contains speech-related keyword. (severity: **high**)
- `@TalkFadeIn` — Command name contains speech-related keyword. (severity: **high**)
- `@TalkCamera4` — Command name contains speech-related keyword. (severity: **high**)

## ⚠️ 未知コマンド一覧

| コマンド | 出現回数 | サンプル行 |
|---|---:|---|
| `@MotionWait` | 545 | L39: `@MotionWait c_idle_103` |
| `@IsLoading` | 51 | L28: `@IsLoading` |
| `@FadeOutWhite` | 6 | L1327: `@FadeOutWhite` |
| `@TalkCamera3` | 4 | L56: `@TalkCamera3` |
| `@TalkFadeIn` | 3 | L78: `@TalkFadeIn` |
| `@ChColor2` | 3 | L1842: `@ChColor2 50` |
| `@DoubleScreen` | 2 | L253: `@DoubleScreen 3 0` |
| `@ChBlueMan/BlueMan2` | 2 | L344: `@ChBlueMan/BlueMan2 0 1 22` |
| `@ChColor2off` | 1 | L1921: `@ChColor2off 50` |
| `@TalkCamera4` | 1 | L105: `@TalkCamera4` |
| `@UnknownNewCommand` | 1 | L15: `@UnknownNewCommand 0 1 2` |

## ⚠️ 未登録キャラクターID

| キャラクターID | 出現回数 | サンプル行 |
|---|---:|---|
| `83` | 1 | L15: `$num4 = 83` |
| `85` | 1 | L12: `$num4 = 85` |
| `86` | 1 | L14: `$num5 = 86` |
| `222` | 2 | L9: `$num3 = 222` |
| `225` | 2 | L7: `$num2 = 225` |
| `228` | 1 | L26: `$num7 = 228` |
| `230` | 2 | L20: `$num8 = 230` |
| `232` | 1 | L17: `$num5 = 232` |
| `234` | 5 | L5: `$num1 = 234` |
| `257` | 1 | L8: `$num1 = 257` |
| `258` | 1 | L10: `$num2 = 258` |

---

*このレポートは DKB Script Compatibility Checker が自動生成しました。*
