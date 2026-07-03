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
- `TimelineCandidate` 最小実装: 実装完了。`feature/timeline-candidate-extraction`をPR #12としてmainへマージ済み
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
- Stage A統合レビュー: 実施完了。`feature/stage-a-integration-review`をPR #13としてmainへマージ済み
  - 全8種Candidate（Character/Location/Organization/Item/Lore/Event/Relationship/Timeline）について、設計・schema・実装・semantic validation・CLI・テストの整合性を横断確認。結果、出力JSON構造・required field・confidence/sourceType/evidenceIdsの扱いは全種で一貫しており、schema/impl間に不整合は無いことを確認
  - 小修正のみ実施（新機能追加・出力構造変更・大規模リファクタリングは無し）:
    - 古い記述の修正: `agents/extractor/__init__.py`・`scripts/extract_story.py`のdocstringが「候補配列は空のまま出力する」と記載されていたが、現在は8種すべてrule-based生成されるため実態に合わせて更新
    - `scripts/validate_extraction_json.py`の`--semantic`ヘルプにtimeline基本チェックを追記（`check_timeline_basic`追加後も記載が漏れていた）
    - `tests/extractor/test_stage_a_integration.py`を新規追加（7件）: 全8種Candidateが1エピソード内で共存し、candidate id重複無し・全evidenceIdsがevidenceIndexに実在・CandidateEnvelope共通フィールド一貫・schema validation・semantic validation・CLI連携（extract_story.py --validate → validate_extraction_json.py --semantic）すべてに通ることを確認
  - 確認済みで問題無しだった点: duplicate candidate id検出は全8配列（`CANDIDATE_ARRAY_KEYS`）に効いている / candidate id接頭辞（CHAR/LOC/ORG/ITEM/LORE/EVENT/REL/TL）が種別ごとに分かれ衝突しない / evidenceIndexは「根拠として使ったもののみ追加」方針がepisode-level・stage_direction両方で守られている / relationship・timelineのbasic validationはwarning中心で過度に厳しくない
- Stage B（Merged Knowledge）設計: 設計書作成完了。`feature/stage-b-merged-knowledge-design`をPR #14としてmainへマージ済み
  - `docs/architecture/06_AI/Merged_Knowledge_Design.md` を新規作成（設計のみ。schema・Python実装・LLM・provider・promptは未着手）
  - 主要な設計決定:
    - マージ4原則: 既存ID最優先 / 名前一致だけで自動マージしない（マージ候補の「提案」に留め確定は手動補正） / Stage Aのevidence・provenanceを失わない / factとinferenceを混ぜない
    - merge key: existing*Id（Characterは第2キーとしてsourceCharacterId、Locationは背景コマンド完全一致も許容）。未解決candidateは`merged/_unresolved/`へ集約し暫定merge ID（`UNRESOLVED_{TYPE}_{number}`）を採番、canonical昇格は手動補正で行う
    - confidence集約はmax（平均・加重は採らない）。`confidence < 0.4`は要レビュー隔離
    - Relationship: (resolved source, resolved target, relationshipType)がキー。両端解決済みのみ`merged/relationships/`へ昇格（未解決は`_unresolved/relationships.json`、Extraction_Result_Schema.md §15の「Stage Aに留め置く」から変更）。direction矛盾はbroad側（bidirectional）暫定採用。MEMBER_OF/AFFILIATED_WITHは別キーのまま統合せず格上げは提案止まり。fact系とinference系Relationshipは同一キーでも別レコード
    - Timeline: エンティティ統合せず、kind別（explicit_order/temporal_marker）のエピソード横断集約`timeline_entries.json`までがStage B責務（Extraction_Pipeline.md §4.8の「マージ対象外」から位置づけ調整）。orderField間の優先順位付け・順序矛盾の本格検出はしない
    - 手動補正: 独立overrideファイル（`knowledge/overrides/`、Git管理）をマージ時に適用。merged/配下は常に再生成可能な生成物。`sourceType: manual`/`confidence: 1.0`は再マージで上書きしない。`manualOverridesApplied`と適用先なしoverride検出でaudit trail
    - conflict handling: 黙って解決せず暫定採用ルール+マージレポート（`data/extracted/reports/merge_report.json`）記録を必須化
    - provenance: `sourceCandidates`（candidate ID保持）+ `extractionRuns`辞書（runRefs参照方式で重複排除）+ evidence埋め込みで、merged entityからRaw Script行まで遡及可能
    - directory: 生成物は`data/extracted/`（_raw/merged/reports、Git管理外）、手動管理ソースは`knowledge/`（overrides/dictionaries、Git管理）に分離するハイブリッド案を推奨
  - 実装PR分割案は同設計書§13（schema→merge engine skeleton→char/loc/org→item/lore/event→relationship→timeline→override loader→report generator）
- Stage B schema作成: 初版完了。`feature/merged-knowledge-schema`をPR #15としてmainへマージ済み
  - `schemas/merged_knowledge.schema.json`: 8種のmerged entity（character/location/organization/item/lore/event/relationship/timeline_entry）を`type`でoneOf判別。共通ベース`MergedEntityBase`（id/type/canonicalId/mergedId/displayName/aliases/status/sourceTypes/confidence/evidenceRefs/sourceCandidates/extractionRunRefs/fieldValues/conflicts/manualOverridesApplied/mergedFrom）を`allOf`で各typeが継承
    - Stage Aのevidence/provenanceを失わない担保: `evidenceRefs`（埋め込みEvidenceRef）と`sourceCandidates`（candidateId/candidateType/sourceDocumentId/episodeId/evidenceIds/extractionRunRef保持）を**最低1件必須**（minItems: 1）。`extractionRunRefs`はepisodeId→ExtractionRunの辞書（runRefs参照方式で重複排除、設計§10.3）
    - `fieldValues`: 属性単位のFieldValue（value/sourceType/confidence/evidenceIds/sourceCandidateIds/isManualOverride）でfact/inference分離を維持
    - `conflicts`: conflictType/field/values/severity(info/warning/error)/resolutionStatus(unresolved/auto_selected/manual_resolved/ignored)/selectedValue。黙って解決しない方針をschema化
    - `status`: merged/unresolved/conflict/deprecated。`relationshipType`はtaxonomy未確定のため自由文字列、`direction`はenum制限
  - `schemas/manual_overrides.schema.json`: overrides配列。各overrideは`sourceType: manual`固定（const）+ overrideId/overrideType/operation(set_field/add_alias/remove_alias/merge_entities/split_entity/ignore_candidate/resolve_conflict/set_relationship_type/set_timeline_order)/targetType/reason/author/createdAt必須。merged/を直接編集せずGit管理overrideで補正する方針を反映
  - `schemas/canonical_knowledge.schema.json`: Stage C用の予約placeholder（`additionalProperties: true`、実体定義なし）
  - `tests/merged/test_merged_knowledge_schema.py`（21件）+ fixture4件（minimal_merged_character / minimal_merged_relationship / minimal_merged_timeline_entry / minimal_manual_override）。schema自体のDraft-07妥当性・正常fixture受理・evidenceRefs/sourceCandidates空の拒否・confidence範囲・status/sourceType/operation enum・relationship必須フィールド・override sourceType=manual固定などを検証
  - 未着手（このPRのスコープ外）: Python merge engine実装、Stage B実データ生成、data/extracted/出力、Knowledge Graph、Wiki、LLM merge判断、relationshipType taxonomy確定、timeline矛盾検出
- merge engine skeleton: 実装完了（最小スコープ）。`feature/merge-engine-skeleton`をPR #16としてmainへマージ済み
  - `agents/merger/`を新規作成: `models.py`（`MergeReport`データクラス、`CANDIDATE_ARRAY_KEYS`/`MERGED_ENTITY_KEYS`定数）、`engine.py`（`MergeEngine`。検証ゲート+collection組み立てを1ファイルに統合）、`__init__.py`
  - スコープを最小化: **単一入力ファイルのみ対応**（複数ファイル・ディレクトリ入力・`--overrides`予約引数は今回見送り、次PRへ持ち越し）
  - 検証ゲート（`MergeEngine.validate_file`/`validate_document`）: `schemas/extraction.schema.json`によるJSON Schema検証 → 通過分のみ`agents/extractor/validator.py`の`run_semantic_validation`を実行。どちらかに失敗した入力はmerge対象にせず、`report.errors`/`report.skippedInputs`へ記録（黙って除外しない）
  - `MergeEngine.merge_file`: 検証結果から`MergeReport`（inputFiles/validInputs/invalidInputs/skippedInputs/candidateCounts/warnings/errors）を構築し、`build_collection`で空のmerged knowledge collectionを組み立てる。entities配下8配列（characters/locations/organizations/items/lore/events/relationships/timeline）は常に空
  - candidateCountsはStage A 8配列（`characters`/`locations`/`organizations`/`items`/`lore`/`events`/`relationships`/`timelineCandidates`）をそのままキーとして集計（本格mergeはまだ行わないため件数のみ）
  - `scripts/merge_extractions.py`: `--input`（単一ファイル）/`--output`/`--quiet`のみ。invalidInputsが1件でもあればexit code 1、入力ファイル不在・ディレクトリ指定・出力失敗はexit code 2
  - collection wrapperと`schemas/merged_knowledge.schema.json`の関係: **A案を採用**（collection wrapperはmerge engine previewの独自形式であり、`merged_knowledge.schema.json`自体はcollection全体ではなく個別entityの形を定義したスキーマのまま。collection wrapperのschema化（B案 `merged_knowledge_collection.schema.json`）は本格merge実装以降、collection構造が安定してから検討）
  - `tests/merger/test_merge_engine_skeleton.py`（10件）: valid input成功、candidateCounts集計の正確性、8種entity配列の存在、schema-invalid/semantic-invalid inputの拒否、CLI成功/失敗/入力不在のexit code。既存の`tests/fixtures/extraction/`（minimal_episode_extraction.json / invalid_missing_evidence.json / invalid_semantic_missing_evidence_ref.json）を再利用し、新規fixtureは追加していない
  - 未着手（次のPRへ持ち越し）: 複数ファイル入力、ディレクトリ入力、`--overrides`引数（manual override適用は未実装なので当面追加しない）、本格的なcandidate merge、canonical ID割り当て、relationship merge、timeline aggregation、collection schema化
- merge engine 複数入力対応: 実装完了。`feature/merge-multiple-inputs`をPR #17としてmainへマージ済み
  - `agents/merger/input_resolver.py`を新規作成: `resolve_input_entries(inputs, recursive)`。ファイルパス／ディレクトリパス（直下`*.json`、`--recursive`で`**/*.json`）／globパターン文字列（`*`/`?`/`[`を含む場合、Pythonの`glob`モジュールで展開しシェル展開に依存しない）を解決。同一ファイルを指す重複raw引数は最初の1回のみ処理。1件も解決できなかったraw引数は`path=None`のエントリとして残し黙って無視しない
  - `MergeEngine.merge_inputs(inputs, recursive)`を追加（`merge_file`は`merge_inputs([str(path)])`への薄いラッパーとして維持、後方互換）。inputResultsの各エントリを3状態で区別: `valid`（検証通過）／`invalid`（読み込めたが schema またはsemantic validationに失敗）／`skipped`（1件もファイルへ解決できなかった raw 引数）
  - `MergeReport`を拡張: `resolvedInputFiles`（展開・重複排除後に実際に見つかったファイル件数）、`inputResults`（path/status/errors/warningsを持つオブジェクト配列）を追加。`inputFiles`はraw `--input`引数の件数（展開前）のまま維持
  - `candidateCounts`は全valid input合算のまま（`build_collection`が`(path, document)`のリストを受け取るよう変更、集計ロジック自体は不変）
  - `sourceDocuments`を拡張: 既存の`episodeId`/`storyId`/`storyCategory`は維持しつつ、`path`/`documentId`（=episodeId）/`extractionVersion`（`extractionRun.extractionVersion`）/`candidateCounts`（そのドキュメント単体の内訳）を追加
  - `scripts/merge_extractions.py`: `--input`を`nargs="+"`化（`--input a.json b.json`形式。複数`--input`フラグの繰り返しより実装・ヘルプがシンプルなためこちらを採用）、`--recursive`/`-r`を追加。exit code方針: 1件も解決できなければexit 2（早期return、出力は書かない）、invalidまたはskippedが1件でもあればexit 1、すべてvalidならexit 0
  - 既存の単一入力テストのうち1件を新仕様に合わせて調整: `test_merge_file_with_schema_invalid_input_is_rejected`が`report["skippedInputs"]`を見ていた箇所を、3状態分離後の意味（skipped=未解決、invalid=検証失敗）に合わせて`inputResults`のstatus="invalid"チェックへ変更（他の単一入力テストは無変更で通過）
  - `tests/fixtures/merger/second_valid_episode_extraction.json`を新規追加（複数入力・ディレクトリ入力テスト用の2件目のvalidフィクスチャ、LocationCandidate 1件）
  - `tests/merger/test_merge_engine_skeleton.py`に9件追加（計19件）: 複数ファイル入力・candidateCounts合算・sourceDocuments件数・valid/invalid混在・ディレクトリ入力・存在しないpathの扱い（単独/valid混在）・CLI複数入力/ディレクトリ入力成功
  - 未着手（次のPRへ持ち越し）: 本格的なcandidate merge、canonical ID割り当て、manual override適用、conflict解決、relationship merge、timeline aggregation、collection schema作成、Knowledge Graph、Wiki、LLM/provider/prompt
- merged knowledge collection schema作成: 実装完了。`feature/merged-knowledge-collection-schema`をPR #18としてmainへマージ済み
  - `schemas/merged_knowledge_collection.schema.json`を新規作成: merge engine (`agents/merger/engine.py`の`build_collection`/`MergeReport.to_dict`/`InputResult.to_dict`)が実際に返している形をそのままスキーマ化。トップレベル`schemaVersion`/`documentType`（const: `merged_knowledge_collection`）/`generatedAt`/`sourceDocuments`/`entities`/`report`はすべて`additionalProperties: false`で実装とずれたら検知できるようにした
  - `CandidateCounts`共通定義: `characters`/`locations`/`organizations`/`items`/`lore`/`events`/`relationships`/`timelineCandidates`の8フィールド、すべて`integer`・`minimum: 0`・`additionalProperties: false`必須。`report.candidateCounts`と`sourceDocuments[].candidateCounts`の両方で同一定義を`$ref`共有
  - `SourceDocument`: 必須`path`/`documentId`/`extractionVersion`/`candidateCounts`、任意`storyId`/`episodeId`/`storyCategory`（実装が実際に出す値）/`extractionRunId`（将来拡張用の予約フィールド、現状未使用でも許容）
  - `MergeReport`: `inputFiles`/`resolvedInputFiles`/`validInputs`/`invalidInputs`/`skippedInputs`/`candidateCounts`/`inputResults`/`warnings`/`errors`をすべて必須化。`inputResults[].status`は`valid`/`invalid`/`skipped`のenumで制限
  - `entities`配下8配列（`characters`/`locations`/`organizations`/`items`/`lore`/`events`/`relationships`/`timeline`。`candidateCounts`の`timelineCandidates`とキー名が異なる点はMerged_Knowledge_Design.md §7の既存設計通り）は現状常に空のため、要素の型は`object`のみに緩め、`schemas/merged_knowledge.schema.json`への本格的な`$ref`は見送った（下記TODO参照）
  - **TODO（次のPR以降）**: `entities`配下の各配列要素を`schemas/merged_knowledge.schema.json`の各entity定義へ`$ref`で接続する。クロスファイル参照は`jsonschema.Draft7Validator`にRefResolver/base_uriの設定が必要になり、現状の「schemaは自己完結・`Draft7Validator(schema)`を素で呼ぶだけ」という他schemaとの一貫した運用から外れるため、entitiesが実際にmerged entityを持つようになった（本格candidate merge実装）タイミングで着手する
  - `tests/fixtures/merged_knowledge/minimal_merged_collection.json`を新規追加（自作の最小collection fixture）
  - `tests/merged/test_merged_knowledge_collection_schema.py`（15件）: schema自体のDraft-07妥当性、自作fixtureの受理、空entities配列の許容、`MergeEngine.merge_file`/`merge_inputs`の実出力（単一/複数/invalid混在/missing path混在）がすべてこのschemaに通ることの確認、`candidateCounts`必須検証（report/sourceDocuments両方）、`inputResults[].status`のenum制約、`candidateCounts`の負値拒否、`documentType`固定値検証、`entities`欠落キー検出、CLI (`scripts/merge_extractions.py`)出力のschema通過
  - MergeEngine側のPythonコードは変更していない（schema側を現在の実装出力に合わせる方針を優先）
- Character / Location / Organization 最小merge: 実装完了。`feature/merge-character-location-organization`をPR #19としてmainへマージ済み
  - `agents/merger/entity_base.py`を新規作成（3種共通処理）: `build_merged_entities`（グルーピング→evidence/sourceCandidates/confidence集約→entity組み立てのオーケストレーション。当初cyclomatic complexity 14でruffのC901に抵触したため、`_group_candidates`/`_resolve_entity_identity`/`_build_entity_for_group`の3ヘルパーへ分割）、`build_merged_evidence_refs`（Stage AのevidenceIndex参照をMergedEvidenceRefへ変換。episode内のBlock走査からevidenceType（dialogue/monologue/narration/choice/scene/episode）を可能な範囲で判定）、`build_source_candidate`、`aggregate_name_candidates`（nameCandidates集約 + displayName conflict検出）
  - `agents/merger/character.py`/`location.py`/`organization.py`を新規作成（`agents/extractor/`のbase.py + 種別ごとファイルという既存パターンを踏襲）
  - merge key方針（Merged_Knowledge_Design.md §5.1〜§5.3、「迷った場合: 構造化IDありだけ自動merge、名前のみは個別unresolved entity」を採用）:
    - Character: 優先1 `existingCharacterId`（canonical、status: merged）→ 優先2 `sourceCharacterId`（同値同士はmergeするがcanonical化しない、status: unresolved、IDは`UNRESOLVED_CHAR_SRC_{値}`で決定的に組み立て再マージでも安定）→ どちらも無ければ候補ごとに個別unresolved entity（`UNRESOLVED_CHAR_{連番4桁}`）。CharacterCandidateスキーマには`existingCharacterId`/`sourceCharacterId`以外の解決済み識別子フィールドが無いため、指示にあった優先度3「speakerId/characterId相当」は実質的に優先度1と同一フィールドを指す（既存フィールドで代替可能なため追加実装なし）
    - Location: 優先1 `existingLocationId`（canonical）→ 無ければ個別unresolved entity（locationNameのみでの自動mergeは行わない）
    - Organization: 優先1 `existingOrganizationId`（canonical）→ 無ければ個別unresolved entity
    - 名前一致だけの複数candidate（同名・別episode）は自動でmergeしないことをテストで明示的に確認済み
  - confidence集約: 構成candidateのconfidenceの最大値（max）
  - sourceTypes: 構成candidateのsourceTypeを重複排除した配列
  - evidenceRefs: Stage AのevidenceIndexから解決し、evidenceId/storyId/episodeId/sceneId/blockId/sourceDocumentId/evidenceType/confidenceを保持。evidenceが1件も無いgroupは出力しない
  - sourceCandidates: candidateId/candidateType/sourceDocumentId/episodeId/evidenceIds/extractionRunRef/sourceType/confidenceを保持（元candidateの情報を失わない）
  - extractionRunRefs: episodeIdをキーにした辞書で重複排除（同一episodeの`extractionRun`を複数candidateで共有していても1回のみ格納）
  - conflicts: 同一構造化ID配下でnameCandidatesの表記が複数ある場合、`conflictType: field_value_conflict`/`field: displayName`/`severity: warning`/`resolutionStatus: unresolved`を記録（表記自体はaliasesへ全保持、高度な自動解決はしない）
  - `agents/merger/engine.py`: `build_collection`が`build_character_entities`/`build_location_entities`/`build_organization_entities`を呼び出し、`entities.characters`/`locations`/`organizations`へ反映（Item/Lore/Event/Relationship/Timelineは引き続き空配列）
  - `agents/merger/models.py`: `MergeReport`に`mergedEntityCounts`（8種の生成件数）/`conflictsCount`（全entityのconflicts合計）/`unresolvedCount`（status: unresolvedのentity件数）を追加
  - **schema変更（理由付き）**: `schemas/merged_knowledge_collection.schema.json`のMergeReport定義に`mergedEntityCounts`（新規`MergedEntityCounts`共通定義、8フィールド。`candidateCounts`とは`timelineCandidates`/`timeline`のキー名が異なる点に注意）/`conflictsCount`/`unresolvedCount`を必須項目として追加。理由: `models.py`側でこれら3項目を常時出力するようにしたため、collection wrapperの実出力とschemaを一致させる必要があった（`schemas/merged_knowledge.schema.json`＝個別entity用schemaへの変更は無し、既存フィールドのみで表現できたため）
  - `schemas/merged_knowledge.schema.json`への変更は無し（既存のMergedEntityBase/MergedCharacter/MergedLocation/MergedOrganization/Conflict定義で表現可能だったため）
  - 既存テスト1件を新機能に合わせて調整: `test_output_collection_has_all_eight_entity_arrays`が「8配列すべて空」を検証していたが、`minimal_episode_extraction.json`フィクスチャに`sourceCharacterId`ありのCharacterCandidateが含まれるため、Character merge実装により`characters`が1件になった。テストを「characters以外は空、charactersは非空」に更新（他の単一/複数入力テストは無変更で通過）
  - `tests/merger/test_entity_merge.py`（13件、新規）: `build_character_entities`/`build_location_entities`/`build_organization_entities`を直接呼び出すユニットテスト（実ファイルI/O不要、episode_extraction dictをインラインで組み立て）。existingCharacterId一致の統合、複数episodeにまたがるmerge、名前のみでの自動merge抑止、sourceCharacterIdのみの保守的merge、Location/Organizationの構造化ID一致・名前のみ抑止、evidenceRefs/sourceCandidates保持、extractionRunRefs重複排除、displayName conflict記録・非衝突時の無記録を検証
  - `tests/merger/test_merge_engine_entities.py`（6件、新規）: `MergeEngine`経由の統合テスト（tmp_pathへ実ファイルを書き出し）。Character/Location/Organization同時生成、複数episode合算、`schemas/merged_knowledge.schema.json`（個別entity）への準拠、`schemas/merged_knowledge_collection.schema.json`（collection全体）への準拠、CLI (`scripts/merge_extractions.py`)出力のcollection schema通過
  - 未着手（次のPRへ持ち越し）: Item/Lore/Event merge、Relationship merge、Timeline aggregation、canonical ID本格割り当て（手動補正）、manual override適用、conflictの本格解決、`entities`配下の`schemas/merged_knowledge.schema.json`への`$ref`接続（PR #18のTODOのまま据え置き。理由: 本PRはentitiesへの populate を実装したが、cross-file $refのRefResolver設定という別軸の判断は依然未着手のため）
- Item / Lore / Event 最小merge: 実装完了。`feature/merge-item-lore-event`ブランチで作業中
  - `agents/merger/entity_base.py`: `build_merged_entities`/`aggregate_name_candidates`に`name_field`引数を追加（デフォルト`"nameCandidates"`）。LoreCandidateのみ名前候補配列が`termCandidates`（Extraction_Result_Schema.md §10）であるため、Character/Location/Organization/Item/Eventの共通処理をそのまま再利用しつつLoreだけ`name_field="termCandidates"`を渡す形にした
  - `agents/merger/item.py`/`lore.py`/`event.py`を新規作成（Character/Location/Organizationと同じ`entity_base.py`利用パターン）
  - merge key方針（構造化IDありのみ自動merge、無ければ個別unresolved entityという既存方針をそのまま適用。Item/Lore/Eventにはsource*Idのような中間的な第2キーが無いため、Location/Organizationと同じ2値のkind「id」/「unresolved」のみ）:
    - Item: `existingItemId`のみ
    - Lore: `existingLoreId`のみ
    - Event: `existingEventId`のみ
  - EventCandidateの`participantCandidates`/`locationCandidates`は、merged entityの`participantEntityIds`/`locationEntityIds`（`schemas/merged_knowledge.schema.json` MergedEvent定義）へ解決していない（空のまま）。理由: candidate ID → merged entity IDの対応表（Merged_Knowledge_Design.md §10.2）が無いと安全に解決できず、それはRelationship merge実装で扱う予定のため、今回のスコープでは意図的に見送った（TASKS.mdに明記）
  - confidence集約（max）/sourceTypes重複排除/evidenceRefs/sourceCandidates/extractionRunRefs重複排除/displayName conflict検出は、既存のCharacter/Location/Organization実装と完全に共通の`entity_base.py`ロジックをそのまま再利用（新規実装なし）
  - `agents/merger/engine.py`: `build_collection`が`build_item_entities`/`build_lore_entities`/`build_event_entities`を追加呼び出しし、`entities.items`/`lore`/`events`へ反映（Relationship/Timelineは引き続き空配列）
  - schema変更は無し（`schemas/merged_knowledge.schema.json`・`schemas/merged_knowledge_collection.schema.json`とも既存定義で表現可能だったため。Character/Location/Organization merge実装時に追加した`mergedEntityCounts`等がそのまま8種フルに機能する）
  - `tests/merger/test_entity_merge_item_lore_event.py`（13件、新規）: `build_item_entities`/`build_lore_entities`/`build_event_entities`を直接呼び出すユニットテスト。既存ID一致の統合、複数episodeにまたがるmerge、名前/用語のみでの自動merge抑止、evidenceRefs/sourceCandidates保持、extractionRunRefs重複排除、displayName conflict記録（LoreのtermCandidates経由も含む）、Character/Location/Organizationとの共存を検証
  - `tests/merger/test_merge_engine_entities.py`に9件追加（計12件）: `MergeEngine`経由でItem/Lore/Eventが生成されること、`mergedEntityCounts`に反映されること、複数episode合算、個別entity schema・collection schema両方への準拠、CLI出力のcollection schema通過
  - 既存テストへの影響: 無し（`test_output_collection_has_all_eight_entity_arrays`が使う`minimal_episode_extraction.json`にItem/Lore/Event candidateは含まれないため、既存アサーションはそのまま成立）
  - 未着手（次のPRへ持ち越し）: Relationship merge、Timeline aggregation、canonical ID本格割り当て、manual override適用、conflictの本格解決、EventCandidateのparticipant/location解決、`entities`配下の`$ref`接続

---

## 2. Next Actions

1. `feature/merge-item-lore-event` の PR を作成し、レビュー・マージする
2. マージ後、`Merged_Knowledge_Design.md` §13 の順で Stage B 実装に進む（着手前にユーザーへ確認する）
   1. Relationship merge（両端解決済みのみ昇格するゲート条件、Merged_Knowledge_Design.md §6。candidate ID → merged entity IDの対応表を作る必要があり、これが完成すればEventCandidateのparticipant/location解決も可能になる）
   2. Timeline aggregation（kind別集約、§7）
   3. manual override loader
   4. `entities`配下の`schemas/merged_knowledge.schema.json`への`$ref`接続（cross-file $ref方針の決定待ち）
3. その他、優先順位未確定の候補（着手前にユーザーへ確認する）
   - choice内話者・choice内location/organization/item/lore/event情報も含めた抽出への拡張
   - semantic validationの拡充（FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証、Timelineの順序整合性チェックなど）
   - story/episode metadataのrelatedOrganizations相当への対応（Story/Episode単位のevidence設計を詰めてから）
   - Scene定義への拡張フィールド許容（`additionalProperties`）の要否検討（scene metadataからのItem/Event/Timeline抽出に必要）
   - `relationshipType`のtaxonomy本格整理（`docs/architecture/04_Knowledge_Graph/Relationships.md`確定）
   - invalid direction（RelationshipCandidate）のwarning化
   - extractor各moduleの重複ヘルパー集約検討（Stage A統合レビューで確認: item.py/event.py/timeline.py/location.pyに「EVIDENCE_BLOCK_TYPES外のBlock（stage_direction等）のEvidenceRefを`source.confidence`フォールバック付きでextra_evidenceへsetdefault」する類似ロジックが分散。base.pyへ小ヘルパーとして集約できるが、4ファイル横断のため今回のレビューでは挙動維持を優先し据え置き。将来まとめる場合は既存テストで挙動不変を担保すること）

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
- semantic validationは`agents/extractor/validator.py`で実装済み（evidenceIds実在確認・duplicate candidate id・empty evidenceIndex・extractionRun整合性・relationship基本チェック・timeline基本チェック）。FieldValue単位のevidenceIds検証、Relationshipの両端がcandidate配列中に実在するかの検証、Timelineの順序整合性チェックは未実装（Next Actions参照）。

---

## 5. Rules

- 実スクリプト全文（`.dec` 由来の生データ）をcommitしない
- `data/extracted/` 配下の生成物をcommitしない
- APIキーをcommitしない（`.env` は `.gitignore` 管理）
- 外部LLM Providerはopt-in、デフォルトはローカルLLM
- Raw Scriptを直接LLMに渡さない（必ずNormalized Story JSON経由）
- `agents/extractor/` のLLM呼び出し本体・provider連携の実装着手はユーザーの明示的な指示を待つ（最小skeletonの実装は完了。CLAUDE.mdの方針）
- Stage B（Merged Knowledge）では、Stage A candidateのevidence・provenance（sourceType/confidence/evidenceIds/candidate ID/extractionRun）をマージ後も失わない（`Merged_Knowledge_Design.md` §4.1 / §10）
