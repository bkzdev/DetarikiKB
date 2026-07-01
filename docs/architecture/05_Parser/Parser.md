# Parser Architecture

## Reference Implementation
既存のパーサー（`reference/parser/story_parse_reference.py` および `characters_reference.json`）は、仕様確認や比較用のリファレンス実装（Reference Implementation）として保持します。これらのファイルを直接改造することはせず、新しいDKB Parserは `agents/parser/` 配下にクリーンに再設計します。

## Entry Point
将来的に `scripts/normalize_story.py` は、新しいパーサーアーキテクチャ（`agents/parser/`）を呼び出すための入口（エントリーポイント）として機能する方針です。
