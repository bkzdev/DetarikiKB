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

# 7. Filter policy（将来のfilter機能、本PRでは未実装）

`scripts/build_evidence_index_candidates.py`にfilter機能を追加するかどうかを検討した。

候補インターフェース案:

```powershell
--include-types dialogue,monologue,narration,choice,unknown
--exclude-types stage_direction
--public-profile default
--public-profile full
--review-profile internal
```

## 7.1 推奨方針

- 次PR以降（`evidence-index-generation-filtering`）で`--include-types`/`--exclude-types`を追加する
- 初期defaultはPublic向けに`dialogue,monologue,narration,choice,unknown`とする
- `stage_direction`は明示指定時のみ含める（opt-in）
- **本PRでは実装しない**。次候補として`TASKS.md`に残す（§13参照）

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
- Public対象entry type（§4.1）を絞ることでentry数を抑える。PR #85のサンプルでは`stage_direction`除外により1793件→約187件（`dialogue`153 + `narration`26 + `monologue`6 + `unknown`2）まで縮小する
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
| Phase 5: `evidence-index-generation-review`（本PR） | dry-run結果レビュー、public entry type方針、promotion/exclusion criteria、filter policy設計、Evidence page size policy、candidate references方針、Summary evidenceRefs優先方針の整理 | **完了（本PR）** |
| Phase 6: `evidence-index-generation-filtering` | `--include-types`/`--exclude-types`等のfilter機能実装（§7） | 未着手 |
| Phase 7: `evidence-index-promotion-policy-implementation` | 本文書のpromotion criteriaを実装するpromotion script/運用手順（人間承認フロー含む） | 未着手 |
| Phase 8: `internal-review-evidence-packet-design` | `stage_direction`等を含むInternal Review Evidence Packetの詳細設計 | 未着手 |

---

# 14. Non-goals（本PRで行わないこと）

- Evidence Index filter実装（`--include-types`/`--exclude-types`等）
- Evidence Index promotion script実装
- 実Evidence Indexの`knowledge/evidence/stories/`へのcommit
- Internal Review Evidence Packet生成
- raw text review packet生成
- raw dialogue text / raw DEC command表示
- Evidence page renderer変更（`agents/wiki_generator/renderer.py`）
- evidenceRefsリンク化ロジック変更
- Episode page変更・Episode別Evidence page生成
- Evidence Index schema変更
- `scripts/build_evidence_index_candidates.py`の変更

---

# 15. 未確定事項（Open questions）

- Story別Evidence pageのentry数しきい値を具体的な数値で確定するか（§8.2、実データ複数storyサンプルが揃ってから再検討）
- Summary `evidenceRefs`が`stage_direction`を指す場合の一律ルール（§10、例外許容 vs Summary根拠再選択のどちらを既定にするか）
- `unknown`型entryの件数が多い場合の具体的な除外基準（§4.1、「件数が少ない場合のみ」の閾値）
- promotion承認者（誰が最終承認するか）の運用ルール（`TASKS.md` Next「evidence-index-promotion-policy」参照）
- Scene/Episode/Story単位の粗い粒度entryを将来追加する場合、Public/Internal振り分けをどうするか
- `speaker_label`型entryを将来追加する場合の公開方針

---

# 16. 参照

- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・Public/Internal分離・実装フェーズ）
- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（dry-run生成手順、§7で本文書へ委譲）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Story/Episode Summaryとevidence RefsのSchema）
- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page設計、Evidence pageへの導線）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§9.16 Evidence page renderer統合）
- `schemas/evidence_index.schema.json`（evidenceType enum、visibility.rawTextIncluded固定）
- `scripts/build_evidence_index_candidates.py`（dry-run生成スクリプト、本PRでは変更しない）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `TASKS.md`（次PR候補の追跡）
