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
- Extractor内部リファクタリング（`feature/extractor-refactor`）: 実装完了。`feature/extractor-refactor`をPR #10としてmainへマージ済み
  - `agents/extractor/extractor.py`（998行）が肥大化していたため、挙動を変えずにCandidate種別ごとのファイルへ分割
  - `agents/extractor/base.py`: 共通ヘルパー（`build_evidence_refs`/`evidence_from_block`/`merge_evidence_index`/`structured_identity_key`）
  - `agents/extractor/character.py`/`location.py`/`organization.py`/`item.py`/`lore.py`/`event.py`: 各Candidate種別の抽出ロジック（`build_*_candidates`関数）
  - `agents/extractor/extractor.py`: `Extractor`クラスは各モジュールの`build_*_candidates`を呼び出すオーケストレーションのみ（115行に縮小）に変更
  - 出力JSON構造・candidate生成ルール・confidence値・sourceType・evidenceIdsの扱いはすべて変更なし（既存テスト135件がそのまま通ることで確認）
  - `agents/extractor/models.py`・`agents/extractor/validator.py`・`agents/extractor/__init__.py`・`scripts/extract_story.py`・`scripts/validate_extraction_json.py`は変更なし
- `RelationshipCandidate` 最小実装: 実装完了。`feature/relationship-candidate-extraction`をPR #11としてmainへマージ済み
  - `agents/extractor/relationship.py`: `build_relationship_candidates`を新規追加。以下2種類の構造的な手がかりのみを対象とし、本文の自然文からの関係推定（「友人らしい」「敵対しているらしい」「同じ組織らしい」等）は一切行わない
    - dialogue/monologue/narration/choice Blockに明示された`relationshipType` + (`sourceCandidate`/`targetCandidate` または `subjectId`/`objectId`) のペア。`relationshipId`があれば`existingRelationshipId`に設定
    - `speakerAssignments`に明示された`organizationId`/`affiliation`からCharacter→Organizationの所属候補を生成（`organizationId`があれば`MEMBER_OF`、名前のみなら`AFFILIATED_WITH`）
  - 同一source+target+relationshipTypeは1候補に統合しevidenceIdsを集約。自己参照（source==target）は生成しない
  - confidenceは`relationshipId`ありまたはspeakerId+organizationId双方解決済みなら0.9、それ以外は0.5
  - `direction`は許可値（`source_to_target`/`target_to_source`/`bidirectional`）以外が来た場合`source_to_target`にフォールバック
  - `agents/extractor/extractor.py`: `build_relationship_candidates`を呼び出し、`relationships`配列に反映（従来は常に空配列）
  - `agents/extractor/models.py`: `RELATIONSHIP_CANDIDATE_*`定数・`RelationshipCandidateAccumulator`を追加
  - `agents/extractor/validator.py`は変更なし（既存の`check_relationship_basic`が空文字チェック・自己参照warningを既にカバー）
  - `tests/extractor/test_relationship_candidate_extraction.py`: 17件追加（Block由来生成、統合、自然文推定されないことの確認、speakerAssignments由来の所属候補、CharacterCandidate/OrganizationCandidateとの共存、schema/semantic validation、CLI経由の疎通）
  - `relationshipType`のtaxonomy本格整理・invalid directionのwarning化（現状は`source_to_target`へ静かにフォールバック）は今後の課題
- `TimelineCandidate` 最小実装: 実装完了。`feature/timeline-candidate-extraction`ブランチで作業中
  - `agents/extractor/timeline.py`: `build_timeline_candidates`を新規追加。以下3種類の構造的な手がかりのみを対象とし、本文の自然文からの時系列推定（「昔」「その後」「翌日」「回想」等）は一切行わない
    - `episode.metadata`に明示された`canonicalOrder`/`releaseOrder`/`displayOrder`（存在するフィールドごとに個別candidateを生成、優先順位付けはしない。scope: `episode`、evidenceはEpisode ID）
    - dialogue/monologue/narration/choice/stage_direction Blockに明示された`timelineId`/`timelineLabel`/`timePosition`/`orderValue`（scope: `block`。`timePosition`は数値なら順序値、文字列ならラベル扱い）
    - 同Blockに明示された`flashback`/`flashforward`/`dayChange`/`timeShift`/`sceneTime`構造フィールド（真偽値の有無のみ判定し値の中身は解釈しない。`kind: temporal_marker`）
  - `schemas/extraction.schema.json`のTimelineCandidate定義を拡張: `kind`enumに`explicit_order`/`temporal_marker`を追加（既存`relative_order`は維持）、`scope`/`sourceTimelineId`/`nameCandidates`/`orderValue`/`orderField`/`markerType`フィールドを新規追加
  - 同一timelineId、または同一scope+順序値/ラベル/マーカー種別の組み合わせは1候補に統合しevidenceIdsを集約
  - confidenceは`timelineId`/`orderValue`/episode.metadata順序値ありなら0.9、ラベルのみなら0.5、temporal_markerは固定0.7
  - Scene定義が`additionalProperties: false`かつmetadataフィールド自体を持たないため、scene単位の時系列情報は今回のスコープ外（Item/Event/LocationCandidateと同じ理由）
  - EventCandidateとの紐づけ（eventCandidateId等）は実装せず、共存のみ確認（推定でEvent-Timeline間を接続しない）
  - `agents/extractor/validator.py`: `check_timeline_basic`を追加（kindごとに付随フィールドが全て空のケースを緩いwarningとして検出。Timelineの本格的な矛盾検出・順序整合性チェックはまだ行わない）
  - `agents/extractor/extractor.py`: `build_timeline_candidates`を呼び出し、`timelineCandidates`配列に反映（従来は常に空配列）
  - `agents/extractor/models.py`: `TIMELINE_CANDIDATE_*`/`TIMELINE_KIND_*`/`TIMELINE_SCOPE_*`定数・`TimelineCandidateAccumulator`を追加
  - `tests/extractor/test_timeline_candidate_extraction.py`: 18件追加
  - LLM呼び出し・provider連携・prompt作成は未着手のまま

---

## 2. Next Actions

1. `feature/timeline-candidate-extraction` の PR を作成し、レビュー・マージする
2. その他、優先順位未確定の候補（着手前にユーザーへ確認する）
   - choice内話者・choice内location/organization/item/lore/event情報も含めた抽出への拡張
   - semantic validationの拡充（FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証、Timelineの順序整合性チェックなど）
   - story/episode metadataのrelatedOrganizations相当への対応（Story/Episode単位のevidence設計を詰めてから）
   - Scene定義への拡張フィールド許容（`additionalProperties`）の要否検討（scene metadataからのItem/Event/Timeline抽出に必要）
   - `relationshipType`のtaxonomy本格整理（`docs/architecture/04_Knowledge_Graph/Relationships.md`確定）
   - invalid direction（RelationshipCandidate）のwarning化

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
