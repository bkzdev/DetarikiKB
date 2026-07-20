# AGENTS

このファイルは、OpenAI Codexを含むAIコーディングエージェント向けのガイダンスの入口である。

## 最初に読むもの

1. **`AI_CONTEXT.md`** — このプロジェクトの正典（canonical handoff doc）。日本語で書かれており、作業開始前に最優先で読むこと。プロジェクト概要・パイプライン・最重要方針・やってはいけないこと・重要な設計書リンクをまとめている。
2. **`CLAUDE.md`** — プロジェクトの詳細ガイダンス（コマンド一覧・アーキテクチャ詳細・不変則の詳細説明）。ファイル名・一部の表記はClaude Code向けだが、内容自体は特定のAIエージェントに依存しない。
3. **`TASKS.md`** — 現在の作業状態（Current Focus/Next/Backlog/Known Issues）を正とする。

本ファイルは上記3文書の要約・入口に留め、詳細を二重管理しない。内容の不一致がある場合は`AI_CONTEXT.md`・`CLAUDE.md`側を正とする。

## 最小限の運用事実

- 環境は`uv`（Python 3.12、`pyproject.toml`参照）を使う。
- テスト: `uv run pytest`（一部のみ実行する場合は`uv run pytest tests/parser/`等）
- Lint/Format: `uv run ruff check .` / `uv run ruff format .`（Blackは不使用）
- `pre-commit run --all-files`でtrailing-whitespace/yaml check/ruff/ruff-formatを実行できる。
- パーサpipelineの主要script（`scripts/check_script_compatibility.py`・`scripts/normalize_story.py`等）は、`agents/`をimportできるようrepo rootから実行すること。

## 重要不変則（要点、詳細は`AI_CONTEXT.md`）

- **不明情報を破棄しない**: 未知コマンド・未登録キャラID・分類不能行は捨てず、`compatibilityReport`または`type: "unknown"`として保持する（`AI_CONTEXT.md` §3.2/§13.3）。
- **IDにタイトルを含めない**: `storyId`/`episodeId`等は安定性が命。表示名・順序はmetadata側に置く。
- **`reference/parser/`は読み取り専用**: `story_parse_reference.py`・`characters_reference.json`は旧プロジェクトの参照資料であり、直接改造しない。新規実装は`agents/parser/`に置く。
- **コマンド辞書の二重登録**: 新しいscriptコマンドをパース対象にする場合、`config/script_commands.yaml`と`agents/parser/parser.py`側のマップ（`DIRECTION_TYPE_MAP`等）の両方に追加する必要がある（現状これらは自動同期していない）。
- **Japanese-docs / English-code方針**: 設計docs（`docs/architecture/**`・`AI_CONTEXT.md`等）は日本語、コード（Python識別子・JSON key・schema field・ファイル/ディレクトリ名・CLIコマンド・ID）は英語で統一する。

## PR作業

PRを作成する場合は`docs/runbooks/AI_PR_Playbook.md`のワークフロー・commit禁止リスト・標準検証コマンド・Non-goals・最終報告様式に従うこと。

## 未実装の空placeholderパッケージ

`agents/analysis`・`agents/consistency_checker`・`agents/extractor`・`agents/graph_builder`・`agents/orchestrator`・`agents/wiki_generator`は、現時点では空のplaceholderパッケージである。ユーザーからの明示的な指示がない限り実装しないこと。
