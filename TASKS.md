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
- Extractor semantic validation: 実装完了。`feature/extractor-semantic-validation` を PR #6 として main にマージ済み
  - `agents/extractor/validator.py`: evidenceIds実在確認 / duplicate candidate id検出 / empty evidenceIndex検出 / extractionRun整合性確認 / RelationshipCandidateの基本チェック（sourceCandidate・targetCandidate空文字はerror、自己参照はwarning）
  - `scripts/validate_extraction_json.py --semantic`: JSON Schema検証に加えてsemantic validationを実行するオプション
  - `tests/extractor/test_extraction_semantic_validation.py`、フィクスチャ2件（`invalid_semantic_missing_evidence_ref.json`、`invalid_semantic_duplicate_candidate_id.json`）
- `CharacterCandidate` 最小抽出: 実装完了。`feature/character-candidate-extraction` を PR #7 として main にマージ済み
  - speakerAssignments / dialogue・monologue Blockのspeakerからrule-baseでCharacterCandidateを生成。choice内の話者は対象外
  - 同一speakerId（無ければsourceCharacterId、それも無ければspeakerName）は1候補に統合し、発言Block IDをすべてevidenceIdsに集約
  - speakerIdが解決済みなら confidence 0.9・existingCharacterIdを設定、未解決（speakerName/sourceCharacterIdのみ）なら confidence 0.5・existingCharacterId は null
  - sourceTypeは "script"（Extraction_Pipeline.md §7.1の語彙のうち、本文から機械的に抽出した情報に対応する区分）
- `LocationCandidate` / `OrganizationCandidate` 最小抽出: 実装完了。`feature/location-organization-candidate-extraction` を PR #8 として main にマージ済み
  - Scene.location と directionType: background のstage_direction BlockからLocationCandidateを生成。本文の自然文からの場所推定は行わない
  - 明示的なorganizationId/organizationName（dialogue/monologue/narration/choice Block）、organizationId/organizationName/affiliation（speakerAssignments）からOrganizationCandidateを生成。本文中の固有名詞文字列推定は行わない
  - Scene.location由来の候補はScene IDを、speakerAssignments由来のOrganizationCandidateはEpisode IDをevidenceとして使う（Block単位の根拠が無い場合のフォールバック、Extraction_Pipeline.md §6.1）。stage_direction Blockはevidenceとして使う場合のみevidenceIndexへ追加する（EVIDENCE_BLOCK_TYPESには含めない）
  - story/episode metadataのrelatedOrganizations相当は今回のスコープ外（evidence粒度がStory/Episode単位のみになり検証が難しいため、Block/Episode単位で根拠が取れるものに限定）
  - 構造化ID（locationId/organizationId）ありなら confidence 0.9、名前のみなら confidence 0.5
- `ItemCandidate` / `LoreCandidate` / `EventCandidate` 最小抽出: 実装完了。`feature/item-lore-event-candidate-extraction` を PR #9 として main にマージ済み
  - 明示的なitemId/itemName（dialogue/monologue/narration/choice Block、stage_direction Block）からItemCandidateを生成
  - 明示的なloreId/termName（dialogue/monologue/narration/choice Blockのみ、最も保守的）からLoreCandidateを生成。stage_direction・speakerAssignments経由の抽出は行わない
  - 明示的なeventId/eventName（dialogue/monologue/narration/choice Block、stage_direction Block）からEventCandidateを生成
  - scene metadataからの抽出は今回のスコープ外（`schemas/story.schema.json`のScene定義が`additionalProperties: false`のため、Scene直下に任意の拡張フィールドを追加できない。Item/Event双方で同じ理由によりスコープ外とした）
  - stage_direction由来のItem/Event候補は、Location同様に実際に根拠として使ったBlockのみevidenceIndexへ追加
  - 構造化ID（itemId/loreId/eventId）ありなら confidence 0.9、名前/用語のみなら confidence 0.5
  - LLM呼び出し・provider連携・prompt作成・`RelationshipCandidate`抽出は未着手
- Extractor内部リファクタリング（`feature/extractor-refactor`）: 実装完了、PR準備中
  - `agents/extractor/extractor.py`（998行）が肥大化していたため、挙動を変えずにCandidate種別ごとのファイルへ分割
  - `agents/extractor/base.py`: 共通ヘルパー（`build_evidence_refs`/`evidence_from_block`/`merge_evidence_index`/`structured_identity_key`）
  - `agents/extractor/character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`: 各Candidate種別の抽出ロジック（`build_*_candidates`関数）
  - `agents/extractor/extractor.py`: `Extractor`クラスは各モジュールの`build_*_candidates`を呼び出すオーケストレーションのみ（115行に縮小）に変更
  - 出力JSON構造・candidate生成ルール・confidence値・sourceType・evidenceIdsの扱いはすべて変更なし（既存テスト135件がそのまま通ることで確認）
  - `agents/extractor/models.py`・`agents/extractor/validator.py`・`agents/extractor/__init__.py`・`scripts/extract_story.py`・`scripts/validate_extraction_json.py`は変更なし
  - 新しい抽出対象・新しい挙動は追加していない。`RelationshipCandidate`抽出・LLM関連もまだ含まない

---

## 2. Next Actions

1. `feature/extractor-refactor` の PR を作成し、レビュー・マージする
2. マージ後、`RelationshipCandidate` の最小実装に進む（rule-baseで検出できる範囲。LLM呼び出しはまだ含めない。着手前にユーザーへ確認する）
3. その他、優先順位未確定の候補（着手前にユーザーへ確認する）
   - choice内話者・choice内location/organization/item/lore/event情報も含めた抽出への拡張
   - semantic validationの拡充（FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証など）
   - story/episode metadataのrelatedOrganizations相当への対応（Story/Episode単位のevidence設計を詰めてから）
   - Scene定義への拡張フィールド許容（`additionalProperties`）の要否検討（scene metadataからのItem/Event抽出に必要）

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
