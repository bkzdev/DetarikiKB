# TASKS

作業TODO管理用ファイル。`AI_CONTEXT.md` はプロジェクトの設計思想・仕様・引き継ぎ情報を扱い、こちらは「今何をしていて、次に何をするか」の作業状態を扱う。

AI_CONTEXT.md にはこれ以上詳細なTODOを追記せず、作業状態の更新は本ファイルで行うこと。

作業を開始・完了・変更するたびに、該当する章を更新すること。

---

## 1. Current Focus

- Parser Phase 1: 完了（`agents/parser/` 一式、`schemas/story.schema.json`、compatibility checker、テスト。main にマージ済み）
- `docs/architecture/06_AI/Extraction_Pipeline.md`: 完了
- `docs/architecture/06_AI/Extraction_Result_Schema.md`: 完了
- `schemas/extraction.schema.json` 一式（validator: `scripts/validate_extraction_json.py`、fixture、schema tests: `tests/extraction/test_extraction_schema.py`）: 完了、`feature/extraction-json-schema` を PR #4 として main にマージ済み

現在、次のステップ（`agents/extractor/` 実装）の着手前段階。

---

## 2. Next Actions

1. `feature/extractor-skeleton` ブランチを作成する
2. Normalized Story JSON から最小構成の `episode_extraction` を生成する処理を `agents/extractor/` に実装する
3. `evidenceIndex` を構築する処理を実装する
4. 生成した `episode_extraction` を `schemas/extraction.schema.json` でバリデーションする
5. LLM呼び出しはこの段階では実装しない（スケルトン・構造生成のみ）

---

## 3. Backlog

- `relationshipType` の語彙を確定させる（`docs/architecture/04_Knowledge_Graph/Relationships.md`、現在空プレースホルダー）
- Candidate ID暫定形式（`Extraction_Result_Schema.md` §4.2）の実運用検証
- キャラクターIDの完全辞書化・主要キャラクターのcanonical ID確定
- イベント番号の正式な採番ルール
- `displayOrder` の正式計算式、`canonicalOrder` の扱い
- Neo4j Graph Model
- Wiki Page Template
- Stage Directionをどこまで詳細に意味解析するか
- 外部LLM Provider連携（opt-in、ローカルLLMがデフォルト）

---

## 4. Known Issues

- `uv run ruff check .` に既存エラーが多数ある（現時点で73件、うち30件は `--fix` で自動修正可能）。新規PRで無関係な既存エラーまで巻き取って直す必要はないが、自分が触ったファイルの新規エラーは残さないこと。
- `evidenceIds` が `evidenceIndex` に実在するかのsemantic validationは未実装（現状のschema/validatorは構造検証のみ）。今後の対応事項。

---

## 5. Rules

- 実スクリプト全文（`.dec` 由来の生データ）をcommitしない
- `data/extracted/` 配下の生成物をcommitしない
- APIキーをcommitしない（`.env` は `.gitignore` 管理）
- 外部LLM Providerはopt-in、デフォルトはローカルLLM
- Raw Scriptを直接LLMに渡さない（必ずNormalized Story JSON経由）
- `agents/extractor/` 本体の実装着手はユーザーの明示的な指示を待つ（CLAUDE.mdの方針）
