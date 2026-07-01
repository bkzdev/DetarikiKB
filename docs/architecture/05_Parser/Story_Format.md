# Story Format

既存のスクリプト形式の特徴と、新しいパーサーで抽出する仕様を以下に整理します。

## キャラクター・話者割り当て
- `$numX` = `character_id` によるキャラクター割り当て
- `$valueX` = `character_id` によるキャラクター割り当て
- `@ScenarioCos` スロット `character_id` による直接割り当て
- `@ScenarioCosLoad` スロット `variable` による変数経由割り当て

## セリフ・地の文・話者
- `@ChTalk` スロットは `dialogue` (会話)
- `@ChTalkMono` スロットは `monologue` (モノローグ/独白)
- `msg` は `narration` (地の文)
- `name` は強制話者名
- 不明人物（未解決の話者）は破棄せず、`unknown speaker` として保持する

## 分岐・演出
- `branch` / `#if` / `#elseif` / `#else` / `#endif` は選択肢分岐 (`choice branch`) として扱う
- 演出コマンドは、今後 `stage_direction`（ト書き・舞台指示）として保持できるようにする
