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
| `unknown` | 公開対象（件数が少ない場合のみ。件数が多い場合はreview対象とし、個別に判断する） |

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
| Phase 12: `evidence-index-public-id-schema-design`（本PR） | `publicEvidenceId`の形式・prefix mapping・採番方針確定、`schemas/evidence_index.schema.json`へのoptional追加 | **完了（本PR、schema/loaderの最小変更のみ）** |
| Phase 13: `evidence-index-public-id-projection` | projection層の実装（`publicEvidenceId`の実際の値の付与） | 未着手 |
| Phase 14: `evidence-index-promotion-first-reviewed-sample-retry` | projection実装後、実データ1 storyの初回昇格を再試行する | 未着手 |
| Phase 15: `internal-review-evidence-packet-design` | `stage_direction`等を含むInternal Review Evidence Packetの詳細設計 | 未着手 |

**実装状況（`feature/evidence-index-generation-filtering`で実施）**: `scripts/build_evidence_index_candidates.py`に`--public-profile default|full|review`（デフォルト`default`）・`--include-types`・`--exclude-types`を追加した。default profileは`stage_direction`を除外し、PR #85と同じ匿名化サンプルで再実行したところentry数は1793件→187件（`dialogue`153・`narration`26・`monologue`6・`unknown`2）に縮小、`--public-profile full`では1793件（PR #85相当）を再現できることを確認した。filterで除外されたentryは`skippedBlockCount`ではなく`filteredEntryCount`/`filteredByTypeCounts`/`filteredReasonCounts`として区別してreportに記録する。`referencedBy.candidates`はfilterで出力対象になったentryにのみ付与し、同サンプルでcandidate references付与件数は159件から155件に減少した。`validate_evidence_index.py`・`render_wiki.py --evidence-index`・source text exposure checkいずれも問題なし。**promotion script実装・Evidence page renderer変更・Internal Review Evidence Packet生成・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-promotion-policy-implementation`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-policy-implementation`で実施）**: `scripts/check_evidence_index_promotion.py`を追加した（詳細手順は`docs/runbooks/Evidence_Index_Promotion_Check.md`）。schema検証・`validate_evidence_index_collection`と同等の整合性検証に加え、Evidence Index YAML全文に対するraw/source text禁止文字列scan、`--policy public-default`によるentry type policy check（`dialogue`/`monologue`/`narration`/`choice`/`unknown`のみ許可、`stage_direction`は専用メッセージでblocking error、`scene`/`episode`/`story`/`speaker_label`もblocking error）を実装した。`--story-summaries`指定時のみ、reviewed/approvedかつgeneratedなSummaryの`evidenceRefs`がEvidence Indexに存在するかを確認し、missingはwarning（blockingにしない）として`--report`のMarkdownに記録する。**実際のcopy・commit・自動昇格は行っていない**（check-onlyのgatekeeper script。次候補`evidence-index-promotion-dry-run`/`evidence-index-promotion-copy-script`/`internal-review-evidence-packet-design`）。`docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート、合成データのみ）を追加した。

**実装状況（`feature/evidence-index-promotion-dry-run`で実施）**: PR #87と同じ匿名化サンプルのfiltered default profile出力（1 story・187 entries、`stage_direction`は0件）に対し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`--story-summaries`あり/なし両方）・`render_wiki.py --evidence-index`・`mkdocs build --strict`・source text exposure checkを実施し、いずれも成功/PASSを確認した。`knowledge/summaries/stories/`は現時点で実データSummary未登録のため、Summary evidenceRefs整合性チェックは`Checked documents: 0`で正しく早期リターンすることを確認し、warning発火自体は別途合成データ（実データと非混在）で確認した。`docs/templates/evidence_index_promotion_review_template.md`を使ったreview noteを`workspace/`配下に作成し、項目の過不足がないことを確認した。詳細は`docs/runbooks/Evidence_Index_Promotion_Check.md` §12を参照。**実装変更・実際のcopy・commit・自動昇格は行っていない**（次候補`evidence-index-promotion-copy-script`/`evidence-index-promotion-first-reviewed-sample`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-copy-script`で実施）**: `scripts/promote_evidence_index.py`を追加した（詳細手順は`docs/runbooks/Evidence_Index_Promotion_Copy.md`）。**デフォルトは常にdry-run**で、`--execute`を明示指定しない限り一切ファイルを書き込まない。`--execute`時も、`check_evidence_index_promotion.py`の`_build_report`を直接importして再利用したpromotion check PASS・`--review-note`のDecisionで`Approved for promotion`がcheckされていること（`Rejected`/`Needs revision`がcheckされている場合は安全側で非承認扱い）・review note自体のraw/source text禁止文字列scan（テンプレートのチェックリスト行自体は誤検知しないよう除外）・1ファイル1story方針（`entries[].storyId`が単一）・copy先の上書き禁止（`--overwrite`で明示許可）のすべてを満たさない限りcopyしない。copyは`shutil.copy2`によるbyte-for-byte copyで内容は変換しない。copy後は`--target`に対してもschema+整合性検証を再実行する（sanity re-check）。`--target`は既定で`knowledge/evidence/stories`のみ許可し、他のpathを使うには`--allow-nonstandard-target`が必要（tests専用）。`--report`でMarkdown report（Promotion Check/Review Note/Planned copies/Skipped files/Overwrite conflicts/Copied files/Post-copy validation/Final Decision）を出力できる。合成fixtureで26件のtestsを追加、PR #89と同じ匿名化サンプルでdry-run確認（copy対象1件のみ検出、実copyなし）を行った。**実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commitは行っていない**（本scriptはcopyのみでgit操作は行わない、実データcommitの判断は人間に委ねる。次候補`evidence-index-promotion-first-reviewed-sample`/`internal-review-evidence-packet-design`）。

**実施結果（`feature/evidence-index-promotion-first-reviewed-sample`、匿名化）**: 実データ小規模サンプル（EVENTカテゴリ1story・episode2件）で初回のfirst reviewed sample promotionを試行した。`build_evidence_index_candidates.py --public-profile default`によるfiltered候補生成（1 story・187 entries、`stage_direction`0件）・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`--story-summaries`あり/なし両方）はいずれも成功/PASSした。しかし、生成されたEvidence Index YAMLを確認したところ、`storyId`（sourceKey由来、`knowledge/evidence/stories/{storyId}.yaml`のファイル名としても使われる）が全187 entryの`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`フィールドに数百回規模で繰り返し出現することが判明した。`publicStoryId`/`publicEpisodeId`という匿名化済みの公開用IDはentryごとに別途存在するが、**保存先ファイル名と主キーは依然としてsourceKey由来の`storyId`を使う設計**であるため、commitするとsourceKey由来の識別子がGit履歴に永続的に残ることになる。当該識別子の公開可否はこのPRの範囲では判断できないため、**安全側の判断として今回は`knowledge/evidence/stories/`への実データ追加を見送った**（human review noteのDecisionも`Needs revision`とし、`promote_evidence_index.py`のdry-runが正しく`FAILED`と判定することも確認した）。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.1を参照。**実装変更・実データcommitはいずれも行っていない**（次候補`evidence-index-promotion-target-filename-policy`/`evidence-index-promotion-first-sample-visual-review`/`internal-review-evidence-packet-design`）。

**設計方針決定（`feature/evidence-index-promotion-target-filename-policy`で実施）**: `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`を新設し、内部trace ID（`storyId`/`evidenceId`等）と公開ID（`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`）を分離する方針（案C）を長期方針として採用した。**実装・schema変更・実データcommitはいずれも行っていない**（設計のみ）。

**実装状況（`feature/evidence-index-public-id-schema-design`で実施）**: `publicEvidenceId`の形式（`{publicEpisodeId}_{PREFIX}{sequence:04d}`）・evidenceType prefix mapping・採番方針を`Evidence_Index_Public_ID_Policy.md` §6で確定し、`schemas/evidence_index.schema.json`に`publicEvidenceId`をoptionalフィールドとして追加した（`evidenceId`/`storyId`/`episodeId`のrequiredは不変）。`agents/wiki_generator/evidence_index.py`のloaderにも対応するフィールドを追加し、schema/loader testsを追加した。**projection実装（実際の値の付与）・promotion script変更・renderer変更・実Evidence Indexのcommitは行っていない**（次候補`evidence-index-public-id-projection`/`evidence-index-promotion-first-reviewed-sample-retry`）。

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

`feature/evidence-index-promotion-first-reviewed-sample`（本PR）でも以下は行っていない: **実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commit**（§15の`storyId`/ファイル名の公開可否判断待ちのため安全側で見送り）、`promote_evidence_index.py`/`check_evidence_index_promotion.py`の変更、複数story promotion、batch promotion、Internal Review Evidence Packet生成。

---

# 15. 未確定事項（Open questions）

- Story別Evidence pageのentry数しきい値を具体的な数値で確定するか（§8.2、実データ複数storyサンプルが揃ってから再検討）
- Summary `evidenceRefs`が`stage_direction`を指す場合の一律ルール（§10、例外許容 vs Summary根拠再選択のどちらを既定にするか）
- `unknown`型entryの件数が多い場合の具体的な除外基準（§4.1、「件数が少ない場合のみ」の閾値）
- promotion承認者（誰が最終承認するか）の運用ルール（`TASKS.md` Next「evidence-index-promotion-policy」参照）
- Scene/Episode/Story単位の粗い粒度entryを将来追加する場合、Public/Internal振り分けをどうするか
- `speaker_label`型entryを将来追加する場合の公開方針
- **【`feature/evidence-index-promotion-first-reviewed-sample`で新たに判明】`knowledge/evidence/stories/{storyId}.yaml`のファイル名およびEvidence Index内の`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`主キーが、sourceKey由来の`storyId`をそのまま使う設計になっている問題** → **`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（`feature/evidence-index-promotion-target-filename-policy`）で設計方針を決定した**。内部trace IDと公開IDを分離し、Public Evidence Indexは`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`中心のprojectionとして保存する方針（案C）を採用。`publicEvidenceId`のschema（optional追加）は`feature/evidence-index-public-id-schema-design`で実装済み。projection層・renderer切替は後続PR（`evidence-index-public-id-projection`）で行う。promotion再開はprojection実装完了まで停止する

---

# 16. 参照

- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・Public/Internal分離・実装フェーズ）
- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（dry-run生成手順、§7で本文書へ委譲）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Story/Episode Summaryとevidence RefsのSchema）
- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page設計、Evidence pageへの導線）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§9.16 Evidence page renderer統合）
- `schemas/evidence_index.schema.json`（evidenceType enum、visibility.rawTextIncluded固定）
- `scripts/build_evidence_index_candidates.py`（dry-run生成スクリプト、`--public-profile`/`--include-types`/`--exclude-types`は`feature/evidence-index-generation-filtering`で実装済み）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `scripts/check_evidence_index_promotion.py`（promotion check script、`feature/evidence-index-promotion-policy-implementation`で実装済み、check-onlyで実copyは行わない）
- `scripts/promote_evidence_index.py`（promotion checkをPASSした候補のcopy script、`feature/evidence-index-promotion-copy-script`で実装済み、dry-run既定・`--execute`必須）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（promotion check手順）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（promotion checkをPASSした候補のcopy手順、§13.1に初回試行結果）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（内部trace ID/公開ID分離方針、`publicEvidenceId`方針、promotion再開の前提条件）
- `docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）
- `TASKS.md`（次PR候補の追跡）
