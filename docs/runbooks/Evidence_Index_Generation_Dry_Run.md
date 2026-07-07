# Evidence Index Generation Dry-Run Procedure（Evidence Index候補生成dry-run手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`

---

# 1. Purpose（目的）

`scripts/build_evidence_index_candidates.py`を使い、Normalized Story JSON（必要ならExtraction Resultも補助的に）からPublic Evidence Index候補YAML（`schemas/evidence_index.schema.json`準拠）を生成する手順を定義する。

`docs/architecture/06_AI/Evidence_Index_Design.md` §10 Phase 4（`evidence-index-generation-dry-run`）の実装であり、**本格的な自動生成パイプラインの完成ではなく、dry-runで生成可能性と安全性を確認するためのもの**である。生成したEvidence Index候補は人間レビューを経るまで`knowledge/evidence/stories/`へは昇格しない（§7参照）。

**実データ・生成物は一切Gitにcommitしない。** このドキュメントも`docs/runbooks/Real_Data_Dry_Run.md`と同じ方針を踏襲する。

---

# 2. 前提

- `docs/runbooks/Real_Data_Dry_Run.md`（Normalized Story JSON/Extraction Result/Merged Knowledge Collectionまでの生成手順）を先に読んでいること
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・raw text非表示方針・データモデル）を読んでいること
- `schemas/evidence_index.schema.json`・`agents/wiki_generator/evidence_index.py`・`scripts/validate_evidence_index.py`・`scripts/render_wiki.py --evidence-index`（`feature/evidence-index-schema-implementation`/`evidence-index-renderer-integration`で実装済み）を把握していること

---

# 3. スコープ（このスクリプトが生成するもの・しないもの）

## 3.1 生成するもの

- Block単位のEvidence Index entry（`evidenceType`は`dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`の6種、`Normalized_Story_JSON.md` §13.2のBlock typeと1対1対応）
- `--public-profile`/`--include-types`/`--exclude-types`によるentry type filtering（`feature/evidence-index-generation-filtering`で追加、§3.3参照）
- `storyId`/`publicStoryId`/`episodeId`/`publicEpisodeId`/`sceneId`/`blockId`（既存ID体系そのまま、新しいID生成ルールは追加しない）
- `speaker`（`isResolved: true`かつ`speakerId`がある場合のみ、`displayName`は常に`null`）
- `relatedEntities`（解決済みspeakerの`character`、Sceneの`locationId`が設定されている場合の`location`のみ）
- `referencedBy.candidates`（`--extractions`指定時のみ、Extraction Resultのcandidate配列`evidenceIds`からの逆引き）
- `visibility: {public: true, rawTextIncluded: false}`（常に固定）
- `generatedFrom.normalizedStoryRefs`/`generatedFrom.extractionRefs`（storyId/episodeIdのみ、local pathは含めない）
- dry-run report（`report.md`/`report.json`、件数サマリーのみ）

## 3.2 生成しないもの（Non-goals、`Evidence_Index_Design.md` §3・§5.2と同じ方針）

- **Scene/Episode/Story単位の粗い粒度のEvidence entry**（Block単位のみ。既存Block IDが無い場合に新しい粗い粒度のIDを合成することはしない）
- **`speaker_label`（Special Speaker Label由来）のevidenceType**（`name`コマンド/`@ChTalkName`由来のspeaker labelは、Block単位のtypeとして表現されないため本スクリプトの対象外。将来の検討課題）
- **Story Summary/Episode Summaryとの`referencedBy.summaries`連携**（Summary側のデータは読まない、常に空配列）
- **Internal Review Evidence Packet**（raw textを含みうる内部review用データは一切生成しない）
- **`knowledge/evidence/stories/`への直接書き込み**（出力先は必ず`workspace/`配下、人間レビュー後の昇格は別途手動で行う）
- **review済みEvidence Indexへの自動昇格**

## 3.3 entry type filtering（`feature/evidence-index-generation-filtering`で追加）

`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（PR #86）で決定したPublic Evidence Indexの初期公開対象entry type方針を、`scripts/build_evidence_index_candidates.py`のCLIオプションとして実装した。

- `--public-profile default|full|review`（**デフォルト`default`**）でPublic向け/全件/review向けのevidenceType集合を切り替える
  - `default`: `dialogue`/`monologue`/`narration`/`choice`/`unknown`のみ生成（`stage_direction`は除外）
  - `full`: このスクリプトが生成しうる全type（`dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`）を生成（PR #85相当）
  - `review`: 本PRでは`full`と同じ挙動（将来Internal Review Evidence Packetに寄せる可能性がある名称のみ予約）
- `--include-types`/`--exclude-types`（comma区切りのevidenceType一覧）でprofileのtype集合を上書き・追加除外できる。優先順位は「profile → `--include-types`（指定時はprofileのinclude集合を丸ごと置き換え） → `--exclude-types`（常に最後に適用、includeと衝突時はexcludeが勝つ）」
- 未知のevidenceTypeを`--include-types`/`--exclude-types`/`--public-profile`に指定した場合はexit code `2`でエラーになる
- **skipとfilterは区別する**: IDが無い/未対応typeで「そもそも候補化できない」ものは`skippedBlockCount`（変わらず`missing_block_id`/`unmapped_block_type:*`）、候補化はできるがprofileにより出力しなかったものは`filteredEntryCount`/`filteredByTypeCounts`/`filteredReasonCounts`（`excluded_by_profile:{evidenceType}`形式）としてreportに記録する
- `referencedBy.candidates`はfilterで出力対象になったentryにのみ付与する。filteredで除外されたentryのcandidate referencesは出力YAML・reportいずれにも含まれない
- raw text非表示（§4）はfilterの有無にかかわらず常に維持される

---

# 4. raw text非表示の実装方針

`Evidence_Index_Design.md` §6の踏襲として、スクリプトは以下を徹底する。

- Blockの`text`/`rawText`/`raw`/`rawCommand`/`args`/`choiceText`/`optionText`フィールドは**値を一切読み取らない**（存在の有無だけを検知し、report上の`rawTextFieldsIgnoredCount`としてカウントする）
- `source`（`sourceFile`/`sourcePath`/`raw`等）はEvidence entryへコピーしない
- Scene`location.locationName`は出力しない（`locationId`のみ）。speaker`speakerName`/`displayName`も出力しない（`speakerId`のみ）
- 生成したEvidence Index候補は、`scripts/build_evidence_index_candidates.py`内部で`schemas/evidence_index.schema.json` + `validate_evidence_index_collection`（raw text禁止文字列検出含む）による検証を**必ず**実行する。検証に失敗したstoryは書き出しをskipし、report上にissueとして記録する（NGな出力を書き出さない）

---

# 5. evidenceId方針

- 既存のBlock ID（`block.id`）があるBlockのみ候補化する
- IDが無いBlockは`missing_block_id`としてskipし、reportにカウントする（**新しいID生成ルールはこのスクリプトで追加しない**、`Identifier_Specification.md`の体系を変更しない）
- Choice Blockのoption内blocksも再帰的にたどり、それぞれのBlock IDでEvidence entry化する
- `dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`以外のtype（想定外のBlock type）は`unmapped_block_type:{type}`としてskipし、reportにカウントする（エラーにはしない）

---

# 6. 実行手順

## 6.1 前段（Normalized Story JSON/Extraction Result生成）

`docs/runbooks/Real_Data_Dry_Run.md` §7〜10の手順で、Normalized Story JSON・（任意で）Extraction Result・Merged Knowledge Collectionを生成しておく。

## 6.2 Evidence Index候補生成

```bash
# --public-profileを省略した場合はdefault（Public向け、stage_direction除外）
uv run python scripts/build_evidence_index_candidates.py \
    --input workspace/dry_runs/<timestamp>/normalized \
    --extractions workspace/dry_runs/<timestamp>/extracted \
    --output workspace/evidence_index_dry_runs/<timestamp>/default \
    --clean

# stage_directionも含めた全type生成 (review/internal用途)
uv run python scripts/build_evidence_index_candidates.py \
    --input workspace/dry_runs/<timestamp>/normalized \
    --extractions workspace/dry_runs/<timestamp>/extracted \
    --output workspace/evidence_index_dry_runs/<timestamp>/full \
    --public-profile full \
    --clean
```

- `--extractions`は任意（未指定なら`referencedBy.candidates`は常に空、`generatedFrom.extractionRefs`は常に空配列）
- `--input`/`--extractions`はファイル・directory（直下の`*.json`を非recursiveに収集）のどちらも指定可能
- `--public-profile`/`--include-types`/`--exclude-types`は任意（§3.3参照、未指定時は`default`プロファイル）
- 出力先直下に`stories/{storyId}.yaml`・`report.md`・`report.json`を書き出す

Exit code: `0`成功（0件の場合も含む）、`1`生成したEvidence Index候補がschema/整合性検証に失敗した場合（該当storyの書き出しはskipされる）または全入力の読み込みに失敗した場合、`2`入力パスが見つからない場合、または`--include-types`/`--exclude-types`/`--public-profile`に未知の値が指定された場合。

## 6.3 生成候補の検証

```bash
uv run python scripts/validate_evidence_index.py \
    --input workspace/evidence_index_dry_runs/<timestamp>/stories
```

`scripts/build_evidence_index_candidates.py`自体が内部で同等の検証を行うため、通常はこの手順は冗長確認だが、生成後に手動編集した場合等のために独立して実行できる。

## 6.4 render確認

```bash
uv run python scripts/render_wiki.py \
    --input workspace/dry_runs/<timestamp>/merged_knowledge_collection.json \
    --output workspace/wiki_preview/<timestamp> \
    --evidence-index workspace/evidence_index_dry_runs/<timestamp>/default/stories \
    --validate --clean
```

- Story SummaryがまだレビューされていないEVT等の場合、`--story-summaries`は省略してよい（Evidence page生成確認が優先、`evidenceRefs`のリンク化確認は`tests/fixtures/`のsynthetic fixtureで代替できる）
- 生成された`evidence/{publicStoryId or storyId}.md`と、Story pageの「Review Links」セクションのEvidence pageリンクを確認する

## 6.5 report確認ポイント

`workspace/evidence_index_dry_runs/<timestamp>/report.json`（またはreport.md）を確認する。

| フィールド | 確認内容 |
|---|---|
| `inputFileCount` / `extractionInputFileCount` | 入力ファイル数 |
| `storyCount` / `episodeCount` | 生成対象のstory/episode数 |
| `publicProfile` | 適用されたprofile（`default`/`full`/`review`） |
| `includedTypes` / `excludedTypes` | 最終的に出力対象/対象外となったevidenceType一覧（§3.3の優先順位適用後） |
| `generatedEntryCount` | 生成されたEvidence entry総数（filter適用後、`generatedEntryCountAfterFilter`と同値） |
| `generatedEntryCountBeforeFilter` / `generatedEntryCountAfterFilter` | filter適用前後のentry数 |
| `filteredEntryCount` / `filteredByTypeCounts` / `filteredReasonCounts` | profileにより出力しなかったentry数と内訳（`skippedReasonCounts`とは別集計、§3.3参照） |
| `skippedBlockCount` / `skippedReasonCounts` | skipされたBlock数と理由別内訳（`missing_block_id`/`unmapped_block_type:*`。filterとは別集計） |
| `entriesByEvidenceType` | evidenceType別のentry数（filter適用後） |
| `rawTextFieldsIgnoredCount` | raw text系フィールドを検知し無視したBlock数（除外の証跡） |
| `candidateReferencesAttachedCount` | `referencedBy.candidates`が付与されたentry数（`--extractions`指定時のみ非0。filterで除外されたentryには付与されない） |
| `validation.schemaValid` / `validation.issuesByStoryId` | 生成candidate自体の検証結果。`false`の場合、該当storyのYAMLは書き出されていない |

---

# 7. dry-run結果からEvidence Indexへの昇格（本ドキュメントでは行わない）

生成されたEvidence Index候補（`workspace/evidence_index_dry_runs/`配下）は**人間レビュー前のローカル専用データ**であり、以下はこのdry-run手順の対象外である。

- `knowledge/evidence/stories/{storyId}.yaml`への昇格判断・実際の配置
- 生成候補の妥当性レビュー（speaker解決の正確性、related entities過不足等）のワークフロー
- 複数回のdry-run結果の差分比較

`evidence-index-generation-review`でPR #85の実データdry-run結果をレビューし、Public Evidence Indexの初期公開対象entry type・`knowledge/evidence/stories/`への昇格条件（promotion criteria）・除外条件（exclusion criteria）・filter policy・Evidence page size policyを`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`にまとめた。**同文書でもpromotion script実装・filter機能実装・実Evidence Indexのcommitは行っていない**（設計のみ、次候補`evidence-index-generation-filtering`/`evidence-index-promotion-policy-implementation`）。

---

# 8. source text exposure check

生成したEvidence Index YAML・report・render後のEvidence page Markdownに対して、以下を確認する（`docs/runbooks/Real_Data_Dry_Run.md`と同じ方針、`Evidence_Index_Design.md` §6）。

検索候補: `.dec` / `@ChTalk` / `@ChTalkMono` / `@ChTalkName` / `@Scenario` / `@ScenarioCos` / `$num` / `C:\` / `D:\` / `/Users/` / `/home/` / `<script` / `</script>` / raw root directory名 / 実データ由来の短い特徴語。

非ASCII文字の混入確認も有効（Evidence Index entryは構造化ID・英語ラベルのみで構成されるべきであり、YAML上に日本語等の非ASCII文字が現れる場合は「未登録」等の定型プレースホルダー文言以外に想定外の漏洩が無いか個別に確認すること）。

問題が見つかった場合:

- 該当entryをPublic Evidence Index候補から除外する
- rendererに出さない
- reportに記録する
- 実データ生成物はcommitしない（§9参照）

---

# 9. commit前チェックリスト

`docs/runbooks/Real_Data_Dry_Run.md` §15のチェックリストに加え、以下を確認する。

- [ ] `git status --short`に`workspace/evidence_index_dry_runs/`配下の出力が出ていない（`.gitignore`で保護済み、確認コマンド: `git check-ignore -v workspace/evidence_index_dry_runs/<timestamp>/report.json`）
- [ ] `tests/fixtures/`に追加したfixtureが合成データ（`TEST_*`等の合成ID）のみで、実データ由来の名前・本文・IDを含まない
- [ ] `knowledge/evidence/stories/`へ実データ由来のEvidence Index候補を誤って配置していない（本手順は昇格を行わない、§7参照）

---

# 10. 関連ドキュメント

- `docs/runbooks/Real_Data_Dry_Run.md`（Normalized Story JSON/Extraction Result/Merged Knowledge Collection生成手順）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・raw text非表示方針・データモデル・実装フェーズ）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（本手順で生成した候補のPublic entry type方針・昇格条件・除外条件・filter policy）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.16（Evidence page renderer統合）
- `TASKS.md`（次PR候補の追跡）
