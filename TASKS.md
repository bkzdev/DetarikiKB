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
- `agents/extractor/` の最小skeleton: 実装完了。`feature/extractor-skeleton` を PR #5 として main にマージ済み
  - Normalized Story JSON から最小 `episode_extraction` を生成（`agents/extractor/extractor.py`）
  - `evidenceIndex` を構築（dialogue/monologue/narration/choice Blockから収集）
  - `scripts/extract_story.py`（CLI）、`tests/extractor/test_extractor_skeleton.py`
  - `extractionRun.extractionMethod` は `rule_based`（LLM未呼び出しを明示。enumに`rule_based`/`llm`/`manual`/`hybrid`を追加）
  - 候補配列（characters/organizations/.../timelineCandidates）は空配列のまま。LLM呼び出し・provider連携・prompt作成は未実装
- Extractor semantic validation（`feature/extractor-semantic-validation`）: 実装完了、PR準備中
  - `agents/extractor/validator.py`: evidenceIds実在確認 / duplicate candidate id検出 / empty evidenceIndex検出 / extractionRun整合性確認 / RelationshipCandidateの基本チェック（sourceCandidate・targetCandidate空文字はerror、自己参照はwarning）
  - `scripts/validate_extraction_json.py --semantic`: JSON Schema検証に加えてsemantic validationを実行するオプション
  - `tests/extractor/test_extraction_semantic_validation.py`、フィクスチャ2件（`invalid_semantic_missing_evidence_ref.json`、`invalid_semantic_duplicate_candidate_id.json`）
  - LLM呼び出し・provider連携・prompt作成・`CharacterCandidate`本格抽出は未着手

---

## 2. Next Actions

1. `feature/extractor-semantic-validation` の PR を作成し、レビュー・マージする
2. マージ後、以下のいずれかに着手する（優先順位は未確定、着手前にユーザーへ確認する）
   - `CharacterCandidate` extraction の最小実装（ルールベースでの名前・話者候補抽出。LLM呼び出しはまだ含めない）
   - semantic validationの拡充（FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証など）

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

- `uv run ruff check .` に既存エラーが多数ある（`feature/extractor-semantic-validation`時点で約80件。内訳: 既存73件 + `scripts/extract_story.py`/`scripts/validate_extraction_json.py` の `E402`（sys.path追加後のimportで`normalize_story.py`と同じ既存パターン）+ 両スクリプトdocstring/epilogの既存長行）。新規PRで無関係な既存エラーまで巻き取って直す必要はないが、自分が触ったファイル内で自分が書いた新規コードにエラーを残さないこと（`agents/extractor/validator.py`はクリーン）。
- semantic validationは`agents/extractor/validator.py`で実装済み（evidenceIds実在確認・duplicate candidate id・empty evidenceIndex・extractionRun整合性・relationship基本チェック）。FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証は未実装（Next Actions参照）。

---

## 5. Rules

- 実スクリプト全文（`.dec` 由来の生データ）をcommitしない
- `data/extracted/` 配下の生成物をcommitしない
- APIキーをcommitしない（`.env` は `.gitignore` 管理）
- 外部LLM Providerはopt-in、デフォルトはローカルLLM
- Raw Scriptを直接LLMに渡さない（必ずNormalized Story JSON経由）
- `agents/extractor/` のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（最小skeletonの実装は完了。CLAUDE.mdの方針）
