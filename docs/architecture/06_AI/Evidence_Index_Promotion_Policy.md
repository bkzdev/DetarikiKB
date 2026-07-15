# Evidence Index Promotion Policy（Evidence Index候補のPublic昇格方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`

---

# 1. Background

`evidence-index-generation-dry-run`（PR #85）で、`scripts/build_evidence_index_candidates.py`によりNormalized Story JSON（および任意でExtraction Result）からPublic Evidence Index候補YAMLを`workspace/evidence_index_dry_runs/`配下へdry-run生成できるようになった（`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`）。

生成された候補は`docs/architecture/06_AI/Evidence_Index_Design.md` §5.1で定義したPublic Evidence Indexの形式に従うが、**人間レビュー前のローカル専用データ**であり、`knowledge/evidence/stories/`へは自動昇格しない（`Evidence_Index_Generation_Dry_Run.md` §7で明示的にscope外とされている）。

本文書は、PR #85の実データdry-run結果（§2、匿名化済み）を踏まえ、

- dry-run候補のどのentry typeを初期Public Evidence Indexの対象にするか
- `workspace/evidence_index_dry_runs/`から`knowledge/evidence/stories/`へ昇格する条件
- 昇格させない・保留する条件
- Evidence pageが巨大化しすぎないための方針

を設計する。**本PRでは実装変更・filter機能追加・promotion scriptの実装・実Evidence Indexのcommitはいずれも行わない**（§13・§14参照）。

---

# 2. Dry-run result summary（PR #85実データdry-run結果、匿名化）

対象は匿名化サンプル1件（EVENTカテゴリ、1 story / 2 episodes、既存の匿名化サンプルを再利用）。実イベント名・実ファイル名・実セリフ・raw pathは記載しない。

| 項目 | 値 |
|---|---|
| story count | 1 |
| episode count | 2 |
| generated entry count | 1793 |
| うち `stage_direction` | 1606 |
| うち `dialogue` | 153 |
| うち `narration` | 26 |
| うち `monologue` | 6 |
| うち `unknown` | 2 |
| skipped count | 0 |
| candidate references attached（`referencedBy.candidates`） | 159 |
| `validate_evidence_index.py` | 成功 |
| `render_wiki.py --evidence-index` | 成功（Evidence page生成成功） |
| Story page Review Links → Evidence pageの導線 | 確認済み |
| source text exposure check | 問題なし |
| 実Evidence Indexのcommit | 行っていない（`workspace/evidence_index_dry_runs/`のみ、非commit） |

`choice`型entryは今回のサンプルに0件だった（選択肢を含まないepisodeだったため）。

## 2.1 filtering実装後の再実行結果（`feature/evidence-index-generation-filtering`、匿名化）

同じ匿名化サンプルで`--public-profile default`/`--public-profile full`を再実行し、以下を確認した。

| 項目 | default profile | full profile |
|---|---|---|
| generated entry count | 187 | 1793（PR #85と一致） |
| filtered entry count | 1606（すべて`stage_direction`） | 0 |
| うち `dialogue` | 153 | 153 |
| うち `narration` | 26 | 26 |
| うち `monologue` | 6 | 6 |
| うち `unknown` | 2 | 2 |
| うち `stage_direction` | 0（filter済み） | 1606 |
| candidate references attached | 155 | 159 |
| `validate_evidence_index.py` | 成功 | 成功 |
| `render_wiki.py --evidence-index` | 成功（Evidence page entry数187） | 未確認（review用途、本PRでは未render） |
| source text exposure check | 問題なし | 問題なし |

candidate referencesがdefault profileで159件から155件に減少したのは、`stage_direction`entryを根拠にしていた4件がentry自体の出力対象外化に伴い失われたため（§9.2参照）。

---

# 3. Problem: stage_direction explosion（stage_direction大量生成問題）

1793 entries中1606件（約89.6%）が`stage_direction`だった。これはBlock単位でEvidence entryを1:1生成する現行スクリプトの仕様（`Evidence_Index_Generation_Dry_Run.md` §3.1・§5）通りの挙動であり、バグではない。ただし、この比率のままPublic Evidence Indexへ昇格すると、Story別Evidence page（`Evidence_Index_Design.md` §9.4で採用したStory別1ページ方針）が`stage_direction` entryでほぼ埋め尽くされる。

## 3.1 候補比較

### 候補A: `stage_direction`もPublic Evidence Indexに含める

- 長所: parserが保持した全構造を追跡しやすい／演出・場面転換の根拠になる／将来の詳細分析に使いやすい
- 短所: entry数が激増する／Evidence pageが読みにくくなる／公開Wiki上でノイズになりやすい／raw command自体は露出しないが意味の薄いentryが多くなる

### 候補B: `stage_direction`は初期Public Evidence Indexから除外する

- 長所: Evidence pageが読みやすい／Summary根拠確認に集中しやすい／公開Wikiのノイズを減らせる
- 短所: 演出根拠が辿れない／一部のAI抽出candidateが`stage_direction`を根拠にする場合にリンク先が不足する

### 候補C: 生成はするが、Public promotion時に除外・折りたたみ・別扱いにする

- 長所: dry-run生成では情報を確認できる／promotion時に公開範囲を制御できる／Internal Review用途にも回しやすい
- 短所: promotion policyがやや複雑になる／将来filter/表示切替の実装が必要になる

## 3.2 採用方針

**初期は候補Cを基本としつつ、実質的な扱いは候補B寄り（原則除外）とする。**

- `scripts/build_evidence_index_candidates.py`は引き続き`stage_direction`をdry-run候補として生成してよい（§3.2の実装は変更しない）
- ただし`knowledge/evidence/stories/`へのPublic promotion時は、`stage_direction` entryを**原則含めない**
- 演出根拠として`stage_direction`が必要になるケース（重要イベント・場面転換等）は、明示的opt-inまたはInternal Review Evidence Packet側（`Evidence_Index_Design.md` §5.2、未実装）で扱う余地を残す
- 全面廃止はしない（`AI_CONTEXT.md` §3.2「不明情報を破棄しない」の精神を踏まえ、dry-run生成物自体からは消さない。あくまでPublic promotionの入口で絞る）

---

# 4. Public evidence type policy（初期公開対象entry type）

## 4.1 初期公開対象

| evidenceType | 方針 |
|---|---|
| `dialogue` | 公開対象 |
| `monologue` | 公開対象 |
| `narration` | 公開対象 |
| `choice` | 公開対象 |
| `unknown` | 公開対象（件数が少ない場合のみ。件数が多い場合はreview対象とし、個別に判断する。**具体的な閾値は`evidence-index-batch-candidate-selection-policy`で確定した`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3を参照**（unknown比率10%以下: 候補可、10%超〜30%以下: 保留、30%超: 除外）） |

## 4.2 初期公開対象から除外・保留

| evidenceType | 方針 |
|---|---|
| `stage_direction` | 除外（§3参照、明示opt-inまたはInternal Review Evidence Packet候補） |
| `scene` | 保留（本スクリプトは生成しない粒度、`Evidence_Index_Generation_Dry_Run.md` §3.2。将来Scene単位entryを追加する場合も、Summary evidenceRefsの直接リンク先としては後続でよい） |
| `episode` | 保留（同上、より粗い粒度） |
| `story` | 保留（同上、最も粗い粒度） |
| `speaker_label` | 保留（本スクリプトは対象外、`Evidence_Index_Design.md` §8・`Evidence_Index_Generation_Dry_Run.md` §3.2。将来対応時に検討） |

理由: `scene`/`episode`/`story`は粗い粒度のentryであり、Summary `evidenceRefs`の直接リンク先としてはBlock単位（`dialogue`/`monologue`/`narration`/`choice`/`unknown`）を優先し、粗い粒度は後続タスクで検討する。`stage_direction`は件数が多く、公開Evidence pageの可読性を下げる可能性が高い（§3参照）。

---

# 5. Promotion criteria（`knowledge/evidence/stories/`への昇格条件）

`workspace/evidence_index_dry_runs/`の候補を`knowledge/evidence/stories/{storyId}.yaml`へ昇格させてよいのは、以下を**すべて**満たす場合のみとする。

- [ ] `schemas/evidence_index.schema.json`によるschema validationが成功している
- [ ] `scripts/validate_evidence_index.py`の実行が成功している（exit code 0）
- [ ] `scripts/check_evidence_index_promotion.py`の実行が成功している（exit code 0、`docs/runbooks/Evidence_Index_Promotion_Check.md`参照。ただしPASSは必要条件であり、人間レビューを省略してよい十分条件ではない）
- [ ] §11のsource text exposure checkが完了し、問題が見つかっていない
- [ ] raw text / raw DEC command / local absolute pathを含むentryが存在しない
- [ ] 各entryの`evidenceType`が§4.1の公開対象entry typeである（`stage_direction`/`scene`/`episode`/`story`/`speaker_label`を含む場合は、それらを除外またはInternal Review側へ切り出した上で昇格する）
- [ ] Story別Evidence pageのentry数が§8のしきい値以下である、またはしきい値超過の理由が明確に記録されている
- [ ] `publicStoryId`/`publicEpisodeId`が確認済みである、または未設定時のfallback方針（`storyId`/`episodeId`使用）が明確である
- [ ] `referencedBy.candidates`が付与されている場合も、raw情報（candidate本文・extraction JSON dump）を含まない（candidateId/entityTypeのみ、§9参照）
- [ ] `render_wiki.py --evidence-index`によるStory page/Evidence page renderが成功している
- [ ] 人間によるレビューが完了している（§12 Human review checklist）
- [ ] レビュー実施記録が`TASKS.md`またはreview note（`workspace/`配下等、commit対象外でも可）に残っている
- [ ] 実データ由来のローカルパス・sourceKey等の過剰露出が無いことを確認済みである
- [ ] commit前に`git status --short`および`git check-ignore -v`で対象外パスに含まれていないことを確認済みである

## 5.1 Public-safe projection + renderer switch後の追加条件（`feature/evidence-index-public-id-renderer-switch`で追記）

Public-safe projection（`evidence-index-public-id-public-safe-projection`）・Public ID Registry統合（`evidence-index-public-id-registry-integration`）・renderer switch（本PR）が出揃った時点で、promotion再開の前提条件を以下のとおり明確化する。**このPR自体はpromotion checkスクリプトを変更しない**（check-onlyの実装は次PR`evidence-index-promotion-first-reviewed-sample-retry`または§4のPhase 4で検討する）。

- [ ] `scripts/project_evidence_index_public_ids.py --projection-mode public-safe`の出力であること（内部ID非露出、`evidenceId`/`storyId`/`episodeId`が`publicEvidenceId`/`publicStoryId`/`publicEpisodeId`と同値になっている）
- [ ] 全entryに`publicEvidenceId`があること（`--policy`対象外typeのentryはPublic-safe projectionの時点で出力から除外されるため、出力に残るentryは全件`publicEvidenceId`を持つ）
- [ ] 全entryに`publicStoryId`/`publicEpisodeId`があること（`publicEpisodeId`欠落はPublic-safe projection自体がblockingにする）
- [ ] `--registry`使用時、Registry由来の`publicEpisodeId`補完がすべて人間review済みのPublic ID Registryに基づくこと（`scripts/project_evidence_index_public_ids.py`は自動採番しない、`Public_ID_Registry_Design.md` §7.6）
- [ ] rendererが`publicEvidenceId`中心の表示になっていること（Evidence page見出し・anchor・Summary evidenceRefsリンク、`Evidence_Index_Public_ID_Policy.md` §9.3）
- [ ] rendered Markdown（Evidence page/Story page）に対するinternal ID exposure checkに通っていること
- [ ] `promote_evidence_index.py`実行前に、上記すべてを満たした状態で`check_evidence_index_promotion.py`によるpromotion checkを通すこと

---

# 6. Exclusion criteria（昇格対象外とする条件）

以下のいずれかに該当する場合、`knowledge/evidence/stories/`への昇格を行わない。

- unreviewed（人間レビュー未実施）のdry-run output
- `stage_direction`大量entryを含む未フィルタ状態のindex（§3・§5参照）
- source text exposure check未実施のもの
- local path / raw source file名の露出があるもの
- schema validation failure
- 実セリフ・raw command混入が確認されたもの
- `workspace/evidence_index_dry_runs/`の出力そのものを無編集でcommitしようとするもの

---

# 7. Filter policy（`feature/evidence-index-generation-filtering`で実装済み）

`scripts/build_evidence_index_candidates.py`にfilter機能を実装した。

```powershell
--public-profile default   # 既定値。Public向け (dialogue/monologue/narration/choice/unknown)
--public-profile full      # stage_directionを含む全type (review/internal用途)
--public-profile review    # 本PRではfullと同じ挙動 (将来Internal Review Evidence Packetに寄せる可能性がある名称のみ予約)
--include-types dialogue,narration   # profileのinclude集合を丸ごと置き換え
--exclude-types stage_direction      # 常に最後に適用、includeと衝突時はexcludeが勝つ
```

## 7.1 実装方針（実装済み）

- `--public-profile`のデフォルトは`default`（Public向け、`stage_direction`を除外）。**このスクリプトのdefault挙動自体をPR #85時点（全type生成）から変更した**。PR #85相当の全type生成が必要な場合は明示的に`--public-profile full`を指定する
- 優先順位: `--public-profile`のinclude集合 → `--include-types`指定時はそれで置き換え → `--exclude-types`は常に最後に適用（includeと衝突時はexcludeが勝つ）
- 未知のevidenceTypeを指定した場合はexit code `2`でargparseがエラーを返す
- filterで除外されたentryは`skippedBlockCount`ではなく`filteredEntryCount`/`filteredByTypeCounts`/`filteredReasonCounts`として区別してreportに記録する（§5・§6参照、`missing_block_id`等の「候補化自体できない」skipとは意味が異なるため）
- `referencedBy.candidates`はfilterで出力対象になったentryにのみ付与する（§9参照）
- raw text非表示（Blockの`text`/`rawText`/`raw`/`rawCommand`/`args`等を読み取らない方針）はfilterの有無にかかわらず常に維持する

詳細は`docs/runbooks/Evidence_Index_Generation_Dry_Run.md` §3.3を参照。

---

# 8. Evidence page size policy（Evidence pageが巨大化しすぎないための方針）

## 8.1 検討項目

- 1 Story Evidence pageあたりのentry数しきい値
- しきい値を超えた場合の対応
- type別section分割
- `stage_direction`除外
- Episode別Evidence pageへの分割（将来）
- Evidence top pageの導入（将来）
- Summary referenced entriesだけを優先表示する方針（将来）

## 8.2 初期方針

- まずはStory別Evidence page（`Evidence_Index_Design.md` §9.4で採用済み）を維持する
- Public対象entry type（§4.1）を絞ることでentry数を抑える。PR #85と同じ匿名化サンプルで`--public-profile default`を再実行し、1793件→187件（`dialogue`153 + `narration`26 + `monologue`6 + `unknown`2 + `choice`0）まで縮小することを確認した（`feature/evidence-index-generation-filtering`、§7参照）。`--public-profile full`では1793件（PR #85相当）を再現できることも確認した
- 1 pageが大きすぎる場合は、Episode別Evidence pageへの分割を後続検討する（`Evidence_Index_Design.md` §9.3の候補C）
- `stage_direction`はPublic pageには原則出さない（§3・§4.2）
- 具体的な数値しきい値（例: 1ページあたり◯件）は本PRでは確定しない。実データでの複数storyサンプルが揃った時点で`evidence-index-promotion-policy-implementation`で再検討する（§15未確定事項）

---

# 9. Candidate references policy（`referencedBy.candidates`の扱い）

PR #85のdry-runでは`referencedBy.candidates`が159件付与された（`--extractions`指定時のみ、`Evidence_Index_Generation_Dry_Run.md` §3.1）。

## 9.1 方針

- Public Evidence Indexのデータには`referencedBy.candidates`（`candidateId`/`entityType`）を保持してよい
- ただしcandidate本文やextraction JSONの生dumpは含めない（既存の実装方針通り、`build_evidence_index_candidates.py`は元々raw情報を読み取らない）
- Public Evidence pageでの表示は最小限にとどめる。`candidateId`が内部的すぎる場合、初期public表示では非表示でもよい
- review用途では有用なため、データ（YAML）自体には保持し続ける
- rendererでの表示要否は別方針として扱ってよい（表示するかは`agents/wiki_generator/renderer.py`側の設計判断であり、本PRでは変更しない）
- 将来的にReview modeやInternal Review Evidence Packetへ表示を寄せる可能性を残す

## 9.2 filteringとの関係（`feature/evidence-index-generation-filtering`で実装済み）

`referencedBy.candidates`はfilterで出力対象になったentryにのみ付与する。filteredで除外されたentry（`stage_direction`等）のcandidate referencesは、出力YAML・reportいずれにも含まれない。PR #85と同じ匿名化サンプルで`--public-profile default`を再実行したところ、candidate references付与件数は159件から155件に減少した（`stage_direction`を根拠に付与されていた4件が、entry自体の出力対象外化に伴い失われた）。この4件は`--public-profile full`で確認できる（review/internal用途）。

---

# 10. Summary evidenceRefsとの関係

Story Summary / Episode Summaryの`evidenceRefs`は引き続きPublic Evidence Indexの主なリンク元である（`Story_Summary_Design.md`、`Evidence_Index_Design.md` §11.3）。

- Summaryから参照される`evidenceId`は、Public promotion対象として**優先する**（§5の昇格条件を満たしやすいentryから優先的に昇格させる）
- Summary `evidenceRefs`が`stage_direction`を指す場合は、例外的に該当entryのみ公開対象に含めるか、Summary側の根拠選択を見直すかのいずれかとする。どちらを取るかはSummaryレビュー時に個別判断する（本PRでは一律ルールを確定しない、§15未確定事項）
- 未解決の`evidenceRefs`（該当`evidenceId`がEvidence Indexに存在しない場合）は、既存実装通りリンク化されずID表示のままとする（非エラー、`Evidence_Index_Design.md` §10実装状況の通り）
- promotion時には、Summary側の`evidenceRefs`一覧とEvidence Index候補の`evidenceId`一覧との整合性チェック（Summaryが参照しているのに候補側に存在しない/除外されたIDが無いか）を行うことが望ましい。チェック手順の自動化は本PRでは行わない

---

# 11. Source text exposure checklist（promotion条件としてのsource text exposure check）

`knowledge/evidence/stories/`への昇格前に、`Evidence_Index_Generation_Dry_Run.md` §8のsource text exposure checkを**promotion条件として必須実施**する。

検索対象: 昇格候補のEvidence Index YAML・report・render後のEvidence page Markdown。

検索候補文字列: `.dec` / `@ChTalk` / `@ChTalkMono` / `@ChTalkName` / `@Scenario` / `@ScenarioCos` / `$num` / `C:\` / `D:\` / `/Users/` / `/home/` / `<script` / `</script>` / raw root directory名 / 実データ由来の短い特徴語。

非ASCII文字混入確認: Evidence Index entryは構造化ID・英語ラベルのみで構成されるべきであり、「未登録」等の定型プレースホルダー文言以外の非ASCII文字が現れていないか確認する。

問題が見つかった場合:

- 該当entryを昇格対象から除外する
- rendererに出さない
- reportに記録する
- 実データ生成物はcommitしない

---

# 12. Human review checklist（人間レビューチェックリスト）

昇格前に人間レビューアが確認する項目。

- [ ] speaker解決の正確性（`speakerId`が妥当か、誤解決が無いか）
- [ ] `relatedEntities`の過不足（関連が薄いentityが混入していないか、必要な関連が欠けていないか）
- [ ] §4.1の公開対象entry typeのみで構成されているか
- [ ] `scripts/check_evidence_index_promotion.py`がPASSしているか（`docs/runbooks/Evidence_Index_Promotion_Check.md`、機械的checkの実行結果を確認する）
- [ ] §11のsource text exposure checkが完了しているか
- [ ] Evidence page（`mkdocs serve`経由）を目視確認し、可読性に問題が無いか
- [ ] Story page Review Links → Evidence pageの導線が機能しているか
- [ ] Summary `evidenceRefs`とのリンク切れが無いか（§10）
- [ ] レビュー結果を`TASKS.md`またはreview noteに記録したか

---

# 13. Implementation phases（実装フェーズ案）

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1〜4 | Evidence Index設計・schema・renderer統合・dry-run生成（PR #82〜#85） | 完了 |
| Phase 5: `evidence-index-generation-review`（PR #86） | dry-run結果レビュー、public entry type方針、promotion/exclusion criteria、filter policy設計、Evidence page size policy、candidate references方針、Summary evidenceRefs優先方針の整理 | 完了 |
| Phase 6: `evidence-index-generation-filtering`（PR #87） | `--include-types`/`--exclude-types`/`--public-profile`によるfilter機能実装（§7） | 完了 |
| Phase 7: `evidence-index-promotion-policy-implementation`（PR #88） | 本文書のpromotion criteriaを実装するpromotion check script・human review template・promotion runbook | 完了（check-onlyのみ、実昇格copyは未実装） |
| Phase 8: `evidence-index-promotion-dry-run`（PR #89） | 実データfiltered outputに対する本scriptの実行結果レビュー | 完了 |
| Phase 9: `evidence-index-promotion-copy-script`（PR #90） | PASSした候補を`knowledge/evidence/stories/`へ実際にcopyする昇格script（人間承認フロー込み） | 完了（dry-run既定・実データcommitは未実施） |
| Phase 10: `evidence-index-promotion-first-reviewed-sample`（PR #91） | 実データ1 storyの初回昇格試行 | 見送り（§15参照） |
| Phase 11: `evidence-index-promotion-target-filename-policy`（PR #92） | 内部ID/公開ID分離方針の設計（`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`） | 完了（設計のみ） |
| Phase 12: `evidence-index-public-id-schema-design`（PR #93） | `publicEvidenceId`の形式・prefix mapping・採番方針確定、`schemas/evidence_index.schema.json`へのoptional追加 | 完了（schema/loaderの最小変更のみ） |
| Phase 13: `evidence-index-public-id-projection`（PR #94） | Compatible projection（案A）層の実装。`scripts/project_evidence_index_public_ids.py`で`publicEvidenceId`の実際の値を付与する（内部IDは削除しない） | 完了 |
| Phase 13.5: `evidence-index-public-id-public-safe-projection`（PR #95） | Public-safe projection（案B）の実装。内部IDを公開ID中心へ置換・除去したPublic Evidence Index本体を生成する | 完了 |
| Phase 13.6: `evidence-index-public-episode-id-assignment`（PR #96） | 実データで未確定な`publicEpisodeId`の検出・割当候補提案。Public ID Registry設計と`scripts/check_public_episode_ids.py`を実装 | 完了 |
| Phase 13.7: `evidence-index-public-id-registry-integration`（PR #97） | Public ID Registryを`project_evidence_index_public_ids.py`へ入力として渡す | 完了 |
| Phase 13.8: `evidence-index-public-id-renderer-switch`（本PR） | Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替える | **完了（本PR）** |
| Phase 14: `evidence-index-promotion-first-reviewed-sample-retry`（PR #99） | projection・renderer切替完了後、実データ1 storyの初回昇格を再試行する | 完了（実Evidence Index 1件を`knowledge/evidence/stories/`へ昇格済み） |
| Phase 14.5: `evidence-index-promotion-first-sample-visual-review`（PR #100） | PR #99で昇格した1 storyについて、Wiki表示・導線・内部ID非露出・raw text非露出を最終確認する | 完了（実装変更なし） |
| Phase 15: `internal-review-evidence-packet-design` | `stage_direction`等を含むInternal Review Evidence Packetの詳細設計 | 未着手 |
| Phase 16: `evidence-index-promotion-batch-policy`（PR #101） | 複数storyへ広げる前のbatch promotion運用方針（batch size・Registry review条件・promotion前後チェックリスト・visual review・failed story/rollback・PR分割方針）を設計する | 完了（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`新設、実装変更なし） |
| Phase 17: `evidence-index-promotion-first-batch-dry-run`（PR #102） | Phase 16のbatch policyに基づき、2〜3 storyを対象にworkspace限定でbatch dry-runを実施する | 完了（tooling観点はPASS。選定storyの見直しが必要と判明、実commitなし） |
| Phase 18: `evidence-index-batch-candidate-selection-policy`（PR #103） | Phase 17で判明した品質問題を受け、promotion候補storyの機械的選定基準（unknown比率等の閾値・3分類・real batch promotion前提条件）を確定する | 完了（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3新設、実装変更なし） |
| Phase 19: `script-command-dictionary-expansion-batch-001`（PR #104） | selection基準確定を受け、対象2 storyのunknown比率を下げるparser command辞書拡充 | 完了（`config/script_commands.yaml`・`agents/parser/parser.py`へ1コマンド追加） |
| Phase 20: `story-manifest-public-story-id-real-data-assignment`（PR #105） | 対象2 storyの`publicStoryId`/`publicEpisodeId`確定→再normalize/merge→Story page導線の動作確認、second batch dry-run | 完了（`Evidence_Index_Batch_Promotion_Policy.md` §4.5、tooling・導線ともPASS、実commitなし） |
| Phase 21: `evidence-index-promotion-first-real-batch`（本PR） | Phase 20でPASSした2 storyについて、Public ID Registry実データentry追加＋`knowledge/evidence/stories/`への初回実batch promotion（Phase 3）を実施する | **完了（本PR、2 story昇格。`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.6・`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.12参照）** |

**実装状況（`feature/evidence-index-generation-filtering`で実施）**: `scripts/build_evidence_index_candidates.py`に`--public-profile default|full|review`（デフォルト`default`）・`--include-types`・`--exclude-types`を追加した。default profileは`stage_direction`を除外し、PR #85と同じ匿名化サンプルで再実行したところentry数は1793件→187件（`dialogue`153・`narration`26・`monologue`6・`unknown`2）に縮小、`--public-profile full`では1793件（PR #85相当）を再現できることを確認した。filterで除外されたentryは`skippedBlockCount`ではなく`filteredEntryCount`/`filteredByTypeCounts`/`filteredReasonCounts`として区別してreportに記録する。`referencedBy.candidates`はfilterで出力対象になったentryにのみ付与し、同サンプルでcandidate references付与件数は159件から155件に減少した。`validate_evidence_index.py`・`render_wiki.py --evidence-index`・source text exposure checkいずれも問題なし。**promotion script実装・Evidence page renderer変更・Internal Review Evidence Packet生成・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-promotion-policy-implementation`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-policy-implementation`で実施）**: `scripts/check_evidence_index_promotion.py`を追加した（詳細手順は`docs/runbooks/Evidence_Index_Promotion_Check.md`）。schema検証・`validate_evidence_index_collection`と同等の整合性検証に加え、Evidence Index YAML全文に対するraw/source text禁止文字列scan、`--policy public-default`によるentry type policy check（`dialogue`/`monologue`/`narration`/`choice`/`unknown`のみ許可、`stage_direction`は専用メッセージでblocking error、`scene`/`episode`/`story`/`speaker_label`もblocking error）を実装した。`--story-summaries`指定時のみ、reviewed/approvedかつgeneratedなSummaryの`evidenceRefs`がEvidence Indexに存在するかを確認し、missingはwarning（blockingにしない）として`--report`のMarkdownに記録する。**実際のcopy・commit・自動昇格は行っていない**（check-onlyのgatekeeper script。次候補`evidence-index-promotion-dry-run`/`evidence-index-promotion-copy-script`/`internal-review-evidence-packet-design`）。`docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート、合成データのみ）を追加した。

**実装状況（`feature/evidence-index-promotion-dry-run`で実施）**: PR #87と同じ匿名化サンプルのfiltered default profile出力（1 story・187 entries、`stage_direction`は0件）に対し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`--story-summaries`あり/なし両方）・`render_wiki.py --evidence-index`・`mkdocs build --strict`・source text exposure checkを実施し、いずれも成功/PASSを確認した。`knowledge/summaries/stories/`は現時点で実データSummary未登録のため、Summary evidenceRefs整合性チェックは`Checked documents: 0`で正しく早期リターンすることを確認し、warning発火自体は別途合成データ（実データと非混在）で確認した。`docs/templates/evidence_index_promotion_review_template.md`を使ったreview noteを`workspace/`配下に作成し、項目の過不足がないことを確認した。詳細は`docs/runbooks/Evidence_Index_Promotion_Check.md` §12を参照。**実装変更・実際のcopy・commit・自動昇格は行っていない**（次候補`evidence-index-promotion-copy-script`/`evidence-index-promotion-first-reviewed-sample`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-copy-script`で実施）**: `scripts/promote_evidence_index.py`を追加した（詳細手順は`docs/runbooks/Evidence_Index_Promotion_Copy.md`）。**デフォルトは常にdry-run**で、`--execute`を明示指定しない限り一切ファイルを書き込まない。`--execute`時も、`check_evidence_index_promotion.py`の`_build_report`を直接importして再利用したpromotion check PASS・`--review-note`のDecisionで`Approved for promotion`がcheckされていること（`Rejected`/`Needs revision`がcheckされている場合は安全側で非承認扱い）・review note自体のraw/source text禁止文字列scan（テンプレートのチェックリスト行自体は誤検知しないよう除外）・1ファイル1story方針（`entries[].storyId`が単一）・copy先の上書き禁止（`--overwrite`で明示許可）のすべてを満たさない限りcopyしない。copyは`shutil.copy2`によるbyte-for-byte copyで内容は変換しない。copy後は`--target`に対してもschema+整合性検証を再実行する（sanity re-check）。`--target`は既定で`knowledge/evidence/stories`のみ許可し、他のpathを使うには`--allow-nonstandard-target`が必要（tests専用）。`--report`でMarkdown report（Promotion Check/Review Note/Planned copies/Skipped files/Overwrite conflicts/Copied files/Post-copy validation/Final Decision）を出力できる。合成fixtureで26件のtestsを追加、PR #89と同じ匿名化サンプルでdry-run確認（copy対象1件のみ検出、実copyなし）を行った。**実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commitは行っていない**（本scriptはcopyのみでgit操作は行わない、実データcommitの判断は人間に委ねる。次候補`evidence-index-promotion-first-reviewed-sample`/`internal-review-evidence-packet-design`）。

**実施結果（`feature/evidence-index-promotion-first-reviewed-sample`、匿名化）**: 実データ小規模サンプル（EVENTカテゴリ1story・episode2件）で初回のfirst reviewed sample promotionを試行した。`build_evidence_index_candidates.py --public-profile default`によるfiltered候補生成（1 story・187 entries、`stage_direction`0件）・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`--story-summaries`あり/なし両方）はいずれも成功/PASSした。しかし、生成されたEvidence Index YAMLを確認したところ、`storyId`（sourceKey由来、`knowledge/evidence/stories/{storyId}.yaml`のファイル名としても使われる）が全187 entryの`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`フィールドに数百回規模で繰り返し出現することが判明した。`publicStoryId`/`publicEpisodeId`という匿名化済みの公開用IDはentryごとに別途存在するが、**保存先ファイル名と主キーは依然としてsourceKey由来の`storyId`を使う設計**であるため、commitするとsourceKey由来の識別子がGit履歴に永続的に残ることになる。当該識別子の公開可否はこのPRの範囲では判断できないため、**安全側の判断として今回は`knowledge/evidence/stories/`への実データ追加を見送った**（human review noteのDecisionも`Needs revision`とし、`promote_evidence_index.py`のdry-runが正しく`FAILED`と判定することも確認した）。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.1を参照。**実装変更・実データcommitはいずれも行っていない**（次候補`evidence-index-promotion-target-filename-policy`/`evidence-index-promotion-first-sample-visual-review`/`internal-review-evidence-packet-design`）。

**設計方針決定（`feature/evidence-index-promotion-target-filename-policy`で実施）**: `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`を新設し、内部trace ID（`storyId`/`evidenceId`等）と公開ID（`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`）を分離する方針（案C）を長期方針として採用した。**実装・schema変更・実データcommitはいずれも行っていない**（設計のみ）。

**実装状況（`feature/evidence-index-public-id-schema-design`で実施）**: `publicEvidenceId`の形式（`{publicEpisodeId}_{PREFIX}{sequence:04d}`）・evidenceType prefix mapping・採番方針を`Evidence_Index_Public_ID_Policy.md` §6で確定し、`schemas/evidence_index.schema.json`に`publicEvidenceId`をoptionalフィールドとして追加した（`evidenceId`/`storyId`/`episodeId`のrequiredは不変）。`agents/wiki_generator/evidence_index.py`のloaderにも対応するフィールドを追加し、schema/loader testsを追加した。**projection実装（実際の値の付与）・promotion script変更・renderer変更・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-public-id-projection`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-id-projection`で実施）**: `scripts/project_evidence_index_public_ids.py`を追加し、Compatible projection（案A）を実装した。`--policy public-default`で許可されたevidenceType（`dialogue`/`monologue`/`narration`/`choice`/`unknown`）のentryのみ`(publicEpisodeId, evidenceType)`単位で連番を振り`publicEvidenceId`を付与し、内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）は一切削除しない。documentのpublicStoryId欠落・entryのpublicEpisodeId欠落・既存publicEvidenceIdとの不一致・重複・projected出力のschema検証失敗はいずれもblocking error（exit code 1）とした。`--output`/`--mapping-output`/`--report`は`knowledge/evidence/`配下を指定するとexit code 2で拒否する安全策を実装し、内部IDを含む`--mapping-output`（CSV）はcommit禁止として明示した。**Compatible projectionの出力は内部IDが残るため引き続きpromotion対象ではない**（`promote_evidence_index.py --execute`は未実行）。`tests/scripts/test_project_evidence_index_public_ids.py`（28件）で検証した。**Public-safe projection（案B）実装・promotion script/renderer変更・実promotion retry・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-public-id-public-safe-projection`/`evidence-index-public-id-renderer-switch`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-id-public-safe-projection`で実施）**: `scripts/project_evidence_index_public_ids.py`に`--projection-mode public-safe`を追加し、内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）を公開ID中心へ置換・除去したPublic Evidence Index本体を生成できるようにした（`compatible`モードは無変更）。出力ファイル名は`{publicStoryId}.yaml`、`publicEpisodeId`欠落は引き続きblocking error、sourceKey由来ID exposure scanを実装した。匿名化実データサンプルではEpisode 2の`publicEpisodeId`未確定によりblocking FAILし、この未確定問題が本PR（`evidence-index-public-episode-id-assignment`）の直接の動機になった。詳細は`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §6.7.1〜§6.9、`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.4を参照。**renderer変更・実promotion retry・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-public-id-renderer-switch`/`evidence-index-public-episode-id-assignment`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-episode-id-assignment`で実施）**: PR #95で判明したEpisode 2の`publicEpisodeId`未確定問題を受け、`docs/architecture/06_AI/Public_ID_Registry_Design.md`（新設）で`publicEpisodeId`の役割・採番方針（`{publicStoryId}_E{episodeOrder:02d}`）・永続化場所を整理した。**長期方針としてPublic ID Registry（`schemas/public_id_registry.schema.json`、内部ID混入をschema構造上防止）を採用**しつつ、`story_manifest.yaml`が引き続きsource of truthであることは変更しない。`scripts/check_public_episode_ids.py`（新規）を追加し、Public Evidence Index候補からepisode単位の`publicEpisodeId`欠落を検出し、`{publicStoryId}_E{episodeOrder:02d}`形式の割当候補（常に`reviewRequired: true`）をworkspace限定で提案する。`--registry`併用時は既存Registry登録値を優先して再利用し、一度公開したIDの安定性を保つ。`--report`/`--suggestions-output`にはsourceKey由来の内部ID・raw title・raw pathを一切出力しない（`publicStoryId`欠落時は`unidentified-story-group-{N}`の匿名ラベル）。`tests/scripts/test_check_public_episode_ids.py`（16件）で検証した。**実Registry・実`story_manifest.yaml`への実データ追加、`project_evidence_index_public_ids.py`との統合、renderer変更、実Evidence Indexのcommitはいずれも行っていない**（次候補`evidence-index-public-id-registry-integration`）。

**実装状況（`feature/evidence-index-public-id-registry-integration`で実施）**: `scripts/project_evidence_index_public_ids.py`に`--registry`/`--registry-schema`を追加し、Public ID Registryをprojectionへ統合した。`check_public_episode_ids.py`のRegistry loader・episode grouping/orderロジックを共有importで再利用し、`publicStoryId + episodeOrder`でRegistryを引いて欠落`publicEpisodeId`を補完する（既存値との不一致はblocking、Registryに該当が無い既存値はwarning）。補完後に`publicEvidenceId`を生成し、mapping/reportにRegistry補完状況を記録する。tests 15件追加（既存67件は無変更）。匿名化実データサンプルでは、Episode 1（92 entries、input由来）+ Episode 2（95 entries、Registry補完）の**187 entries全件がPublic-safe projectionを通過**し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`ともPASSすることを確認した。**実Registryへの実データ追加・renderer変更・実promotion retryはいずれも行っていない**（次候補`evidence-index-public-id-renderer-switch`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-id-renderer-switch`で実施）**: Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替えた（`agents/wiki_generator/evidence_index.py`の`display_evidence_id`/`resolve_evidence_entry`/`resolve_story_evidence_entries`、`agents/wiki_generator/renderer.py`の`_render_evidence_entry`/`_format_evidence_ref_display`）。§5.1に「Public-safe projection + renderer switch後の追加条件」を新設し、今後のpromotion再開条件を整理した。匿名化実データサンプル（Public-safe projection、187 entries）を`render_wiki.py --evidence-index`でrenderし、Evidence pageの内部ID非露出を確認した。**本PRではpromotion checkスクリプト自体は変更していない。実Evidence Indexのcommit・実promotion retryはまだ行っていない**（次候補`evidence-index-promotion-first-reviewed-sample-retry`）。

**実施結果（`feature/evidence-index-promotion-first-reviewed-sample-retry`で実施）**: §5.1の追加条件がすべて出揃った状態で、実データ1 story（匿名化表記`EVENT_164_260425`、event category、episode 2件、187 entries）の初回昇格を再試行し、**今回初めて`knowledge/evidence/stories/EVENT_164_260425.yaml`への実データcommitを実施した**。まず`knowledge/public_ids/story_public_ids.yaml`に1 story分のPublic ID Registry entryを正式commitし（`docs/architecture/06_AI/Public_ID_Registry_Design.md` §8.5）、これを`project_evidence_index_public_ids.py --projection-mode public-safe --registry`に指定してPublic-safe projectionを再生成した。Episode 1（92 entries、input由来）+ Episode 2（95 entries、Registry補完）の187 entries全件が`generated=187`・`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`でPASSし、`validate_evidence_index.py`・`check_evidence_index_promotion.py`（Story Summary整合性チェック込み）もPASSした。`render_wiki.py --evidence-index`・`mkdocs build --strict`でEvidence page（`evidence/EVENT_164_260425.md`）を確認し、見出し・anchorが`publicEvidenceId`になり内部`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`が一切表示されないことをgrep・目視の両方で確認した。human review noteを作成しDecisionを`Approved for promotion`とした上で、`promote_evidence_index.py`のdry-run→`--execute`を実行し、`knowledge/evidence/stories/EVENT_164_260425.yaml`1件のみを正しくcopyしたことを確認した（copy後の再validation・promotion check・render・internal ID exposure checkもすべて再実施しPASS）。merged knowledge collection側にEpisode 2の`publicStoryId`/`publicEpisodeId`が伝播していないため、Story page/Character page側（workspace限定のpreviewのみ）に内部ID断片が現れる既知の制約は今回も再現したが、**今回commitしたEvidence Index YAML自体・そのEvidence pageには内部ID非露出を確認済み**であり、この制約は昇格対象に影響しない。**複数story昇格・batch promotion・`promote_evidence_index.py`等のscript本体変更・`story_manifest.yaml`の実データ変更はいずれも行っていない**（次候補`internal-review-evidence-packet-design`/`evidence-index-promotion-batch-policy`/`story-manifest-public-story-id-real-data-assignment`）。

**実施結果（`feature/evidence-index-promotion-first-sample-visual-review`で実施）**: PR #99で昇格した1 story（`knowledge/evidence/stories/EVENT_164_260425.yaml`、187 entries）を対象に、Wiki表示として公開して問題ないかを最終確認した。**実装変更は行っていない。** `validate_evidence_index.py`・`check_evidence_index_promotion.py`（Story Summary整合性チェック込み、`Checked documents: 0`で正常終了）を`knowledge/evidence/stories`に対して再実行しいずれもPASSを確認した。`render_wiki.py --evidence-index knowledge/evidence/stories`でEvidence pageを再renderし、187件全entryの見出しが`publicEvidenceId`形式であること、`stage_direction`が0件であることを確認した。Story pageの「Review Links → Evidence index」リンクが`publicStoryId`ベースのEvidence pageへ正しく解決されることも実データで確認した（`resolve_story_evidence_entries`のfallbackが実際に機能していることの実証）。merged knowledge collection側にEpisode 2の`publicStoryId`/`publicEpisodeId`が伝播していないため、Story page（workspace限定previewのみ）のサイト全体ナビゲーションに内部ID断片が現れる既知の制約（PR #98/#99で判明済み）を再確認したが、**Evidence Index YAML自体・Evidence page本体には内部ID・raw text・raw command・local pathの露出が無いことをgrep・目視で確認した**。`mkdocs build --strict`も成功した。**新規Evidence Index追加・新規Public ID Registry実データentry追加・複数story promotion・batch promotionはいずれも行っていない**（次候補`evidence-index-promotion-batch-policy`/`internal-review-evidence-packet-design`/`story-summary-generation-planning`/`public-publishing-platform-evaluation`）。

**設計方針決定（`feature/evidence-index-promotion-batch-policy`で実施）**: PR #99・#100で1 storyのpromotion・visual reviewが実証されたことを踏まえ、複数storyへ広げる前のbatch promotion運用方針を`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（新設）にまとめた。段階的batch size方針（Phase 2: dry-run最大3 story → Phase 3: 初回実batch最大3 story → Phase 4: 通常small batch最大5 story → Phase 5: 大規模batchは明示的承認まで許可しない）、Registry entry review条件（8項目のチェックリスト）、story単位のpromotion前チェックリスト・batch単位のpromotion後チェックリスト、visual review方針（初回batchでは全story必須）、failed story handling（初回batchでは1件でもfailureがあればbatch全体を停止、失敗理由9分類）、rollback方針（1 story 1 fileの削除で対応、ただし一度公開した`publicStoryId`/`publicEpisodeId`は再利用しない、Git履歴混入防止は事前のexposure checkが本筋）、PR分割方針（初回batchは案C: dry-run PR→実promotion PRの2段階）を整理した。次PR候補`evidence-index-promotion-first-batch-dry-run`のスコープ（やること/やらないこと）も明記した。**本PRでは実装変更・実Evidence Index/Registry entryの追加・batch promotion実行はいずれも行っていない**（設計・runbook・docs testsのみ、次候補`evidence-index-promotion-first-batch-dry-run`/`internal-review-evidence-packet-design`/`story-summary-generation-planning`/`public-publishing-platform-evaluation`）。

**実施結果（`feature/evidence-index-promotion-first-batch-dry-run`で実施）**: 上記batch policyのPhase 2に基づき、2 story（匿名化、合計2039 entries）を対象にworkspace限定でbatch dry-runを実施した。**実Registry entry・実Evidence Indexのcommitはいずれも行っていない。** Registry候補作成・`check_public_episode_ids.py`・Public-safe projection（`generated=2039`・`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（Summary込み）・extraction/merge・`render_wiki.py --evidence-index`・`mkdocs build --strict`・visual review・internal/source ID exposure checkのすべてをPASSで完走し、**tooling自体には問題が無いことを実証した**。一方、選定した2 storyは`parserCompatibility: warning`状態で`unknown`比率が約90%と高く、`Evidence_Index_Promotion_Policy.md` §4.1の方針に照らしreal promotion対象としては非推奨と判断した。また、`story_manifest.yaml`のpublicStoryId割当を経ていない新規storyではStory pageの「Review Links → Evidence index」導線がデフォルトで機能しないことも判明した。**Failed story count 0・excluded story count 0**（機械的failureは無い）。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.2、`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.11を参照。**本PRでも実装変更・実データcommit・batch promotion実行はいずれも行っていない**（次候補`evidence-index-promotion-first-real-batch`〔story候補見直し後〕/`story-manifest-public-story-id-real-data-assignment`/`internal-review-evidence-packet-design`）。

**設計方針決定（`feature/evidence-index-batch-candidate-selection-policy`で実施）**: 上記で判明した「機械的checkは全PASSでも品質の低いstoryが素通りする」問題に対応するため、promotion候補storyの選定基準を`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3に確定した。判定指標（unknown比率・意味のあるentry比率・parserCompatibility・entry数）とその閾値（unknown比率10%以下候補可/10%超〜30%以下保留/30%超除外、意味あるentry比率70%以上候補可、entry数600以下候補可）、3分類ラベル（`promotion-candidate`/`parser-improvement-wait`/`excluded`）、判定手順、記録様式を定義した。PR #102の2 storyを`parser-improvement-wait`に分類し、real batch promotionへ進むための最低条件（selection基準PASS＋Story page導線動作確認済み＋Registry review済み＋既存チェックリストPASS＋最大3 story）を明文化した。ロードマップ（script command辞書拡充→story_manifest publicStoryId確定→second batch dry-run→first real batch）も記録した。**本PRでは実装変更・selection基準のcheck script組み込み・実データcommitはいずれも行っていない**（設計のみ、次候補`script-command-dictionary-expansion-batch-001`）。

**実装状況（`feature/script-command-dictionary-expansion-batch-001`で実施）**: 対象2 storyのunknown比率を下げるため、`config/script_commands.yaml`・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`に未登録演出コマンド1種を追加した。調査の結果、§4.2で観測されたunknown比率約90%はstaleなローカル生成物由来の数値であり、本PR着手前のmain時点で再normalizeし直すと既に約1%まで下がっていたことが判明した。残っていた1コマンドの追加登録により、対象2 storyのunknown比率を0%まで低減した。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.4を参照。**`story_manifest.yaml`の実データ変更・second batch dry-run・real batch promotionの実行はいずれも行っていない**。

**実施結果（`feature/story-manifest-public-story-id-real-data-assignment`で実施）**: 対象2 storyの`publicStoryId`/`publicEpisodeId`をローカルworkspace限定のstory_manifest経由で確定し、再normalize/merge後のmerged knowledge collectionで**Story pageの「Review Links → Evidence index」導線が実データで機能することを実証した**（PR #98の`resolve_story_evidence_entries`fallbackが実際に機能していることの初回実データ確認）。続けてsecond batch dry-run（Registry候補・Public-safe projection・validation/promotion check・全story visual review・exposure check）を実施し、両storyとも`promotion-candidate`判定・`internal_id_exposure=0`でPASSした。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.5を参照。**Public ID Registry実データentry・実Evidence Indexのcommit、`promote_evidence_index.py`のdry-run/`--execute`実行はいずれも行っていない**（次候補`evidence-index-promotion-first-real-batch`）。

**実施結果（`feature/evidence-index-promotion-first-real-batch`で実施）**: §5.1の追加条件・`Evidence_Index_Batch_Promotion_Policy.md`の全チェックリストを満たした状態で、初回実batch promotion（Phase 3、2 story）を実施した。`knowledge/public_ids/story_public_ids.yaml`に2 story分（`publicStoryId: EVENT_168_260624`〔event〕・`publicStoryId: RAID_027_260504`〔raid〕）のRegistry entryを追加し（既存1 story分は無変更）、§5の8項目レビュー条件をすべて確認した。正式Registryを用いて`project_evidence_index_public_ids.py --projection-mode public-safe --registry`を実行し、**2 story・205 entries全件がPublic-safe projectionを通過**した（`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）。`validate_evidence_index.py`・`check_evidence_index_promotion.py`（Summary込み）・`render_wiki.py --evidence-index`・`mkdocs build --strict`はいずれもPASS/成功し、両storyのStory page「Review Links → Evidence index」導線が正しく解決されることを確認した。human review note（Decision: `Approved for promotion`、ユーザー事前承認済みである旨を記録）を作成した上で、`promote_evidence_index.py`のdry-run→`--execute`を実行し、**`knowledge/evidence/stories/EVENT_168_260624.yaml`・`RAID_027_260504.yaml`の2件のみが正しくcopyされたことを確認した**（既存の昇格済み1 storyには一切触れていない）。copy後、既存1 story分を含む全3ファイル（392 entries）に対して再検証・再render・exposure checkを実施しすべてPASSした。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.6・`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.12を参照。**3 story目以降の追加・既存の昇格済みstory/Registry entryの変更・batch promotion scriptの実装はいずれも行っていない**（次候補`internal-review-evidence-packet-design`/`evidence-index-promotion-batch-tooling`/`story-summary-generation-planning`）。

---

# 14. Non-goals

`evidence-index-generation-review`（PR #86、本文書の初版）時点でのNon-goals:

- Evidence Index filter実装（`--include-types`/`--exclude-types`等） → **`feature/evidence-index-generation-filtering`で実装済み**（§7参照）
- Evidence Index promotion script実装 → **`feature/evidence-index-promotion-policy-implementation`で実装済み**（check-onlyのみ、§13参照）
- 実Evidence Indexの`knowledge/evidence/stories/`へのcommit
- Internal Review Evidence Packet生成
- raw text review packet生成
- raw dialogue text / raw DEC command表示
- Evidence page renderer変更（`agents/wiki_generator/renderer.py`）
- evidenceRefsリンク化ロジック変更
- Episode page変更・Episode別Evidence page生成
- Evidence Index schema変更
- `scripts/build_evidence_index_candidates.py`の変更 → **`feature/evidence-index-generation-filtering`で変更済み**（filtering機能追加のみ、raw text非表示方針・skip判定ロジックは変更していない）

`feature/evidence-index-generation-filtering`（PR #87）でも以下は行っていない: Evidence Index promotion script実装、実Evidence Indexの`knowledge/evidence/stories/`へのcommit、Internal Review Evidence Packet生成、raw text review packet生成、Evidence page renderer変更、evidenceRefsリンク化ロジック変更、Episode page変更、Evidence Index schema変更。

`feature/evidence-index-promotion-policy-implementation`（PR #88）でも以下は行っていない: 実際のcopy・commit・自動昇格、`knowledge/evidence/stories/`への実データ昇格、promotion copy script実装 → **`feature/evidence-index-promotion-copy-script`で実装済み**（§13参照）、Internal Review Evidence Packet生成、raw text review packet生成、Evidence page renderer変更、evidenceRefsリンク化ロジック変更、Evidence Index generation filterの変更、Episode page変更、Evidence Index schema変更、Story Summary schema変更。

`feature/evidence-index-promotion-dry-run`（PR #89）でも以下は行っていない: 実装変更、実際のcopy・commit・自動昇格、promotion copy script実装。

`feature/evidence-index-promotion-copy-script`（PR #90）でも以下は行っていない: **実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commit**（`--execute`はtests/合成データでのみ確認、実データはdry-runのみ）、自動昇格、GitHub Actionsでの自動promotion、Internal Review Evidence Packet生成、raw text review packet生成、Evidence page renderer変更、evidenceRefsリンク化ロジック変更、Evidence Index generation filter変更、Episode page変更、Evidence Index schema変更、Story Summary schema変更。

`feature/evidence-index-promotion-first-reviewed-sample`（PR #91）でも以下は行っていない: **実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commit**（§15の`storyId`/ファイル名の公開可否判断待ちのため安全側で見送り）、`promote_evidence_index.py`/`check_evidence_index_promotion.py`の変更、複数story promotion、batch promotion、Internal Review Evidence Packet生成。

`feature/evidence-index-public-id-projection`（PR #94）でも以下は行っていない: 実Evidence Indexの`knowledge/evidence/stories/`への実copy・commit、Public-safe projection（案B、内部ID完全除去）実装、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`の変更、`promote_evidence_index.py --execute`の実行、実promotion retry、Internal Review Evidence Packetの正式な設計・保管場所確定。

`feature/evidence-index-public-id-public-safe-projection`（PR #95）でも以下は行っていない: 実Evidence Indexの`knowledge/evidence/stories/`への実copy・commit、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更（Evidence page見出し・anchor・evidenceRefsリンクの`publicEvidenceId`中心切替は次候補`evidence-index-public-id-renderer-switch`）、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`の変更、`promote_evidence_index.py --execute`の実行、実promotion retry（次候補`evidence-index-promotion-first-reviewed-sample-retry`）、`publicEpisodeId`の自動補完・推測（次候補`evidence-index-public-episode-id-assignment`）、`schemas/evidence_index.schema.json`の破壊的変更、Internal Review Evidence Packet生成。

`feature/evidence-index-public-episode-id-assignment`（PR #96）でも以下は行っていない: 実Evidence Indexの`knowledge/evidence/stories/`への実copy・commit、`promote_evidence_index.py --execute`の実行、実promotion retry、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、`publicEpisodeId`の自動補完・本番反映、`story_manifest.yaml`の実データ変更、実Public ID Registryへの実データ追加、`scripts/project_evidence_index_public_ids.py`/`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更、`schemas/evidence_index.schema.json`の破壊的変更、Internal Review Evidence Packet生成。

`feature/evidence-index-public-id-registry-integration`（PR #97）でも以下は行っていない: 実Evidence Indexの`knowledge/evidence/stories/`への実copy・commit、`promote_evidence_index.py --execute`の実行、実promotion retry、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、`publicEpisodeId`の自動採番・自動本番反映（Registry補完は人間review済みRegistry値の再利用のみ）、`story_manifest.yaml`の実データ変更、実Public ID Registryへの実データ追加、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更、`schemas/evidence_index.schema.json`/`schemas/public_id_registry.schema.json`の破壊的変更、Internal Review Evidence Packet生成。

`feature/evidence-index-public-id-renderer-switch`（本PR）でも以下は行っていない: 実Evidence Indexの`knowledge/evidence/stories/`への実copy・commit、実Public ID Registryへの実データ追加、`promote_evidence_index.py --execute`の実行、実promotion retry、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`本体の変更、Public ID Registry/Evidence Index schema変更、Summary schema変更、`publicEpisodeId`の自動採番・自動本番反映、`story_manifest.yaml`の実データ変更、Episode page変更、Internal Review Evidence Packet生成。

`feature/evidence-index-promotion-first-reviewed-sample-retry`（本PR）でも以下は行っていない: 複数story分のEvidence Index/Registry commit、batch promotion、自動昇格（GitHub Actions等）、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、Evidence Index/Public ID Registry/Summary schemaの変更、`publicEpisodeId`の自動採番・自動本番反映、`story_manifest.yaml`の実データ変更・再normalize/merge、Internal Review Evidence Packet生成、Episode page変更。

`feature/evidence-index-promotion-first-sample-visual-review`（PR #100）でも以下は行っていない: 実装変更全般（renderer/paths.py/script本体の変更なし）、新規Evidence Index追加、新規Public ID Registry実データentry追加、複数story promotion、batch promotion、`story_manifest.yaml`の実データ変更・再normalize/merge、Internal Review Evidence Packet生成。

`feature/evidence-index-promotion-batch-policy`（PR #101）でも以下は行っていない: 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行、batch promotion scriptの実装、自動昇格、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、Evidence Index/Public ID Registry/Summary schemaの変更、Internal Review Evidence Packet生成。

`feature/evidence-index-promotion-first-batch-dry-run`（PR #102）でも以下は行っていない: 複数story分のEvidence Index/Registry entryのcommit（`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`は無変更）、`promote_evidence_index.py --execute`の実行、実batch promotion、batch promotion scriptの実装、`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更、`agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更、Evidence Index/Public ID Registry/Summary schemaの変更、Internal Review Evidence Packet生成。

`feature/evidence-index-batch-candidate-selection-policy`（PR #103）でも以下は行っていない: selection基準の`check_evidence_index_promotion.py`等への実装、`config/script_commands.yaml`/`agents/parser/parser.py`の変更、`story_manifest.yaml`の実データ変更・再normalize/merge、second batch dry-run・real batch promotionの実行、複数story分のEvidence Index/Registry entryのcommit。

`feature/script-command-dictionary-expansion-batch-001`（PR #104）でも以下は行っていない: `story_manifest.yaml`の実データ変更・再normalize/merge本体の実行、second batch dry-run・real batch promotionの実行、selection基準の自動check実装、複数story分のEvidence Index/Registry entryのcommit。

`feature/story-manifest-public-story-id-real-data-assignment`（PR #105）でも以下は行っていない: Public ID Registry実データentry・実Evidence Indexのcommit、`promote_evidence_index.py`のdry-run・`--execute`いずれの実行、`agents/`・`scripts/`配下の実装変更、ローカルmanifest・Registry候補・projection output・merged collection・batch dry-run report自体のcommit。

`feature/evidence-index-promotion-first-real-batch`（本PR）でも以下は行っていない: 3 story目以降の追加、既存の昇格済みstory・Registry entryの変更、batch promotion scriptの実装、`agents/`・`scripts/`配下の実装変更、story_manifest実データ・review note・projection output・mapping・report類のcommit。

---

# 15. 未確定事項（Open questions）

- Story別Evidence pageのentry数しきい値を具体的な数値で確定するか（§8.2、実データ複数storyサンプルが揃ってから再検討）
- Summary `evidenceRefs`が`stage_direction`を指す場合の一律ルール（§10、例外許容 vs Summary根拠再選択のどちらを既定にするか）
- ~~`unknown`型entryの件数が多い場合の具体的な除外基準（§4.1、「件数が少ない場合のみ」の閾値）~~ → **`evidence-index-batch-candidate-selection-policy`で確定済み**（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3、unknown比率10%/30%の2段階閾値）
- promotion承認者（誰が最終承認するか）の運用ルール（`TASKS.md` Next「evidence-index-promotion-policy」参照）
- Scene/Episode/Story単位の粗い粒度entryを将来追加する場合、Public/Internal振り分けをどうするか
- `speaker_label`型entryを将来追加する場合の公開方針
- **【`feature/evidence-index-promotion-first-reviewed-sample`で新たに判明】`knowledge/evidence/stories/{storyId}.yaml`のファイル名およびEvidence Index内の`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`主キーが、sourceKey由来の`storyId`をそのまま使う設計になっている問題** → **`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（`feature/evidence-index-promotion-target-filename-policy`）で設計方針を決定した**。内部trace IDと公開IDを分離し、Public Evidence Indexは`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`中心のprojectionとして保存する方針（案C）を採用。`publicEvidenceId`のschema（optional追加）は`feature/evidence-index-public-id-schema-design`で実装済み、Compatible projection（案A）は`feature/evidence-index-public-id-projection`で実装済み（内部IDは削除しない）、Public-safe projection（案B）は`feature/evidence-index-public-id-public-safe-projection`（PR #95）で実装済み（内部IDを公開ID中心へ置換・除去、出力ファイル名も`publicStoryId`ベース）。**renderer切替は`feature/evidence-index-public-id-renderer-switch`（本PR）で実装済み**。promotion再開は§5.1の追加条件をすべて満たし、実データでの安全性再確認を行うまで停止する
- **【PR #95で新たに判明】実データEpisode 2の`publicEpisodeId`が未確定のため、Public-safe projectionも（Compatible projectionと同様に）blocking FAILする** → **`feature/evidence-index-public-episode-id-assignment`（PR #96）で設計・最小実装、`feature/evidence-index-public-id-registry-integration`（PR #97）でprojectionへの統合まで完了**: `docs/architecture/06_AI/Public_ID_Registry_Design.md`で採番方針・永続化場所（長期的にはPublic ID Registry）を整理し、`scripts/check_public_episode_ids.py`で欠落episodeの検出・割当候補提案を実装した後、`scripts/project_evidence_index_public_ids.py`に`--registry`を追加してRegistryから実際に`publicEpisodeId`を補完できるようにした。匿名化実データサンプルで187 entries全件のPublic-safe projection通過を確認済み。実Registryへの実データ追加は未着手のまま
- `episodeOrder`の正式な根拠（`story_manifest.yaml`の`episodeNumber`との一致保証）、episode追加・順序変更時のmigration policyは`Public_ID_Registry_Design.md` §8で未確定のまま
- **【本PRで新たに判明】merged knowledge collection側に`publicStoryId`が伝播していないstoryでは、Public-safe Evidence Indexを渡してもStory pageの「Review Links → Evidence index」導線が解決できない場合がある** → `resolve_story_evidence_entries`（内部`storyId`→`publicStoryId`の順でfallback）で対応したが、根本的には`story_manifest.yaml`側の`publicStoryId`確定・再normalize/mergeが必要（本PRのNon-goals）。実データでの再現・解消は次PR以降で検討する

---

# 16. 参照

- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・Public/Internal分離・実装フェーズ）
- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（dry-run生成手順、§7で本文書へ委譲）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Story/Episode Summaryとevidence RefsのSchema）
- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page設計、Evidence pageへの導線）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§9.16 Evidence page renderer統合）
- `schemas/evidence_index.schema.json`（evidenceType enum、visibility.rawTextIncluded固定）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（`publicEpisodeId`未確定問題の整理、Public ID Registry設計）
- `scripts/build_evidence_index_candidates.py`（dry-run生成スクリプト、`--public-profile`/`--include-types`/`--exclude-types`は`feature/evidence-index-generation-filtering`で実装済み）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `scripts/check_evidence_index_promotion.py`（promotion check script、`feature/evidence-index-promotion-policy-implementation`で実装済み、check-onlyで実copyは行わない）
- `scripts/promote_evidence_index.py`（promotion checkをPASSした候補のcopy script、`feature/evidence-index-promotion-copy-script`で実装済み、dry-run既定・`--execute`必須）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（promotion check手順）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（promotion checkをPASSした候補のcopy手順、§13.1に初回試行結果）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（内部trace ID/公開ID分離方針、`publicEvidenceId`方針、promotion再開の前提条件）
- `docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（複数storyへ広げる際のbatch size・Registry review条件・promotion前後チェックリスト・visual review・failed story/rollback・PR分割方針）
- `TASKS.md`（次PR候補の追跡）
