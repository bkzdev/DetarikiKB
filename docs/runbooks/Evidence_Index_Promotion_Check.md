# Evidence Index Promotion Check Procedure（Evidence Index昇格checkの手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Evidence_Index_Promotion_Check.md`

---

# 1. Purpose（目的）

`scripts/check_evidence_index_promotion.py`を使い、`workspace/evidence_index_dry_runs/.../stories`に生成されたPublic Evidence Index候補が`knowledge/evidence/stories/`へ昇格可能かをcheckする手順を定義する。

`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（PR #86）で設計したpromotion criteria/exclusion criteriaを機械的にcheckするgatekeeperであり、**実際のcopy・commit・自動昇格は行わない**（check-only、`feature/evidence-index-promotion-policy-implementation`）。昇格そのもの（`knowledge/evidence/stories/`へのファイル配置）は、このscriptがPASSした上で人間レビュー（§6）を経て手動で行う運用とする。

**実データ・生成物は一切Gitにcommitしない。** このドキュメントも`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`と同じ方針を踏襲する。

---

# 2. 前提

- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（Evidence Index候補生成dry-run手順）を先に読んでいること
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria/public entry type policy）を読んでいること
- `schemas/evidence_index.schema.json`・`agents/wiki_generator/evidence_index.py`・`scripts/validate_evidence_index.py`を把握していること

---

# 3. スコープ

## 3.1 checkするもの

- schema検証（`schemas/evidence_index.schema.json`）
- `agents.wiki_generator.evidence_index.validate_evidence_index_collection`と同等の整合性検証（duplicate evidenceId・enum・`visibility.rawTextIncluded`/`public`・構造化フィールド中のraw text禁止文字列）
- Evidence Index YAMLファイル**全文**に対するraw/source text禁止文字列scan（構造化フィールド単位のチェックだけでは取りこぼす可能性があるフィールドも対象にする）
- entry type policy（`--policy public-default`、既定値かつ現状唯一のpolicy）。`dialogue`/`monologue`/`narration`/`choice`/`unknown`のみ許可し、`stage_direction`/`scene`/`episode`/`story`/`speaker_label`はblocking errorとする
- `--story-summaries`指定時のみ、reviewed/approvedかつgeneratedなStory/Episode Summaryの`evidenceRefs`が対象Evidence Indexに存在するかの確認（missingはwarning）

## 3.2 checkしないもの（Non-goals）

- **実際のcopy・commit**（`knowledge/evidence/stories/`への配置は本scriptの対象外、常に人間が手動で行う）
- **自動昇格**（review未実施のPASSを昇格の十分条件にはしない、§6参照）
- **Internal Review Evidence Packet生成**
- **Evidence Index generation filterの変更**（`scripts/build_evidence_index_candidates.py`は変更しない）
- **Evidence page rendererの変更**
- Summary側のevidenceRefsを自動修正すること（missingを検出するのみ、修正はしない）

---

# 4. public-default policy

| evidenceType | 扱い |
|---|---|
| `dialogue` / `monologue` / `narration` / `choice` / `unknown` | 許可（PASS） |
| `stage_direction` | **blocking error**（専用メッセージ、`Evidence_Index_Promotion_Policy.md` §3） |
| `scene` / `episode` / `story` / `speaker_label` | blocking error（`Evidence_Index_Promotion_Policy.md` §4.2） |

`--policy`は現状`public-default`のみが選択可能（デフォルト値でもある）。`full-review`のような緩いpolicy（`stage_direction`等を許容するreview用途）は将来候補として`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §15に残すのみで、本PRではCLI上に実装しない。

---

# 5. 実行手順

## 5.1 基本

```bash
uv run python scripts/check_evidence_index_promotion.py \
    --input workspace/evidence_index_dry_runs/evidence_index_filtering/default/stories
```

## 5.2 Story Summaryとの整合性も確認する場合

```bash
uv run python scripts/check_evidence_index_promotion.py \
    --input workspace/evidence_index_dry_runs/evidence_index_filtering/default/stories \
    --story-summaries knowledge/summaries/stories
```

- `--story-summaries`は任意。未指定の場合、Summary evidenceRefs整合性チェックは行わない
- `knowledge/summaries/stories`（review済みcommit先）・`workspace/summary_drafts/`（draft）いずれのディレクトリも指定可能

## 5.3 report出力

```bash
uv run python scripts/check_evidence_index_promotion.py \
    --input workspace/evidence_index_dry_runs/evidence_index_filtering/default/stories \
    --report workspace/evidence_index_dry_runs/evidence_index_filtering/promotion_check_report.md
```

`--report`は任意。指定した場合、check結果をMarkdownとして書き出す（**出力先はworkspace配下を指定し、commitしないこと**）。

Exit code: `0` promotion check passed（blocking issueなし。warningがあっても0）、`1` promotion check failed（blocking issueあり）、`2` 入力パスが見つからない、またはIOエラー。

---

# 6. Validation sequence（推奨実行順）

昇格判断の前に、以下を順に実行することを推奨する（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §5 Promotion criteriaに対応）。

1. `scripts/validate_evidence_index.py --input <path>`（schema+整合性検証、冗長確認だが独立実行できる）
2. `scripts/check_evidence_index_promotion.py --input <path> [--story-summaries <path>] --report <report_path>`（本手順、promotion policy固有のcheck）
3. `scripts/render_wiki.py --input <merged_collection> --evidence-index <path> --validate --clean`（Evidence page生成確認）
4. `uv run mkdocs build --strict`（生成Markdown全体のbuild確認）
5. §7の人間レビュー記録

いずれか1つでも失敗（exit code非0、またはPASS以外の判定）した場合、昇格を見送る。

---

# 7. Human review記録

`scripts/check_evidence_index_promotion.py`のPASSは**必要条件であり十分条件ではない**。実際の昇格前には、`docs/templates/evidence_index_promotion_review_template.md`を使って人間レビュー記録を残すこと。

- テンプレート自体はcommitしない実施記録用の空欄見本（`docs/templates/`配下、合成データのみ）
- 記入した実施結果はローカル・社内共有ドライブ等commit対象外の場所に保存する（`docs/templates/mkdocs_local_preview_result_template.md`と同じ運用方針）
- チェック項目: Validation（§6の各step）、Entry Summary（type別件数）、Public Type Policy、Source Text Exposure、Summary Evidence Refs、Decision（Approved/Needs revision/Rejected）

---

# 8. Source text exposure check

`scripts/check_evidence_index_promotion.py`はEvidence Index YAMLファイル全文に対して、`docs/runbooks/Evidence_Index_Generation_Dry_Run.md` §8と同じ検索対象文字列（`.dec`/`@ChTalk`系/`@Scenario`系/`$num`/`C:\`/`D:\`/`/Users/`/`/home/`）を自動scanする。これはpromotion checkのblocking条件の一つである。

自動scanでは検出しきれない項目（非ASCII文字混入の目視確認、実セリフらしき短い特徴語の確認等）は、引き続き人間レビュー（§7）で確認すること。

---

# 9. Summary evidenceRefs整合性チェック方針

- `--story-summaries`指定時のみ実行する
- reviewed/approvedかつgenerationStatusがgeneratedなStory Summary/Episode Summaryの`evidenceRefs`のみを対象とする（unreviewed/rejected/needs_revision/draft/deprecatedは対象外）
- 対象Evidence Indexに存在しない`evidenceRef`は**warning**として報告する（**blockingにはしない**）
  - 理由: Summary側が先行して作成されている場合や、Summaryが`stage_direction`等のpromotion対象外typeを参照している場合があり、これらはPublic Evidence Index側の欠陥ではないため（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §10）
- missing refsが見つかった場合、人間レビュー時にSummary側の根拠を見直すか、該当entry typeを例外的に含めるかを個別判断する

---

# 10. commit前チェックリスト

`docs/runbooks/Evidence_Index_Generation_Dry_Run.md` §9のチェックリストに加え、以下を確認する。

- [ ] `--report`で出力したMarkdownがcommit対象に含まれていない（`git status --short`で確認、`workspace/`配下は`.gitignore`で保護済み）
- [ ] `knowledge/evidence/stories/`へ実データ由来のEvidence Index候補を誤って配置していない（本scriptは昇格を行わない、§3.2参照）
- [ ] Human review記録（§7）の実施結果を、commit対象のリポジトリ内に保存していない

---

# 11. Non-goals

- 実際のcopy・commit・自動昇格（§3.2）
- Internal Review Evidence Packet生成
- Evidence Index generation filter（`scripts/build_evidence_index_candidates.py`）の変更
- Evidence page renderer（`agents/wiki_generator/renderer.py`）の変更
- `full-review`等の追加policyの実装（将来候補として`Evidence_Index_Promotion_Policy.md`に残すのみ）

---

# 12. Dry-run result（`feature/evidence-index-promotion-dry-run`実施結果、匿名化）

PR #87で使用した匿名化済み実データサンプル（EVENTカテゴリ1story・episode2件）のfiltered default profile出力（`--public-profile default`で再生成）に対し、本手順を実施した。実イベント名・実ファイル名・実セリフはここに記載しない。

## 12.1 結果サマリー

| 項目 | 結果 |
|---|---|
| filtered出力の再生成 | 成功（1 story、187 entries、`stage_direction`は0件） |
| entries by type | dialogue 153 / monologue 6 / narration 26 / choice 0 / unknown 2 |
| `validate_evidence_index.py` | 成功（schema/整合性検証OK） |
| `check_evidence_index_promotion.py`（`--story-summaries`なし） | exit code 0、PASS |
| `check_evidence_index_promotion.py`（`--story-summaries knowledge/summaries/stories`あり） | exit code 0、PASS（`knowledge/summaries/stories/`は現時点で実データ未登録のため、Checked documents: 0・warningなし） |
| Summary evidenceRefs missing warning動作確認 | 合成データ（workspace専用、実データと非混在）でwarning発火・exit code 0維持を再確認 |
| Human review template試用 | `docs/templates/evidence_index_promotion_review_template.md`を使い`workspace/`配下にreview note作成。項目の過不足なし |
| `render_wiki.py --evidence-index` | 成功。Evidence page entry数187、`stage_direction`表示なし、Story page Review Links→Evidence page導線を確認 |
| `mkdocs build --strict` | 成功 |
| source text exposure check | 問題なし（Evidence Index YAML・promotion check report・review note・Evidence page Markdown・MkDocs HTML対象） |
| 実Evidence Index/promotion report/review note | いずれもcommitしていない（`workspace/`配下のみ） |

## 12.2 Promotion check運用評価

- `check_evidence_index_promotion.py`の出力（stdout要約 + `--report`のMarkdown）は、entry数・type別内訳・PASS/FAIL理由が一目で分かり、human reviewの起点として十分機能した
- `report.md`はHuman review templateの「Entry Summary」「Public Type Policy」「Source Text Exposure」項目とほぼ1対1で対応しており、転記の手間が小さい
- Human review templateの項目は今回のdry-runでは過不足なし。「Target」セクションのstoryId/publicStoryIdは匿名化のため空欄運用にせざるを得なかった点は、実運用（人間が直接記入する場合）では問題にならない想定
- `stage_direction`除外により、entry数がPR #85時点の1793件から187件に縮小し、Evidence pageとして現実的な規模になったことを確認した（`Evidence_Index_Promotion_Policy.md` §8のPage size policyと整合）
- Summary evidenceRefs整合性チェックは、`knowledge/summaries/stories/`に実データが投入されていない現時点では実運用確認ができていない（`Checked documents: 0`で早期リターンする挙動自体は正しい）。合成データでのwarning発火は別途確認済み

## 12.3 Known limitations

- Summary evidenceRefs整合性チェックの実データでの動作は、実際にreviewed/approvedなStory Summaryが`knowledge/summaries/stories/`へ投入されるまで確認できない
- `check_evidence_index_promotion.py`はfile単位でのみ実行するため、複数storyを含む大規模ディレクトリでの実行時間・出力の見やすさは未検証（今回は1 storyのみ）
- Human review templateはMarkdown手動記入のみで、`check_evidence_index_promotion.py`のreportから自動転記する仕組みは無い（将来的な改善余地）

## 12.4 Follow-up tasks

- `evidence-index-promotion-copy-script`: PASSした候補を`knowledge/evidence/stories/`へ実際にcopyする昇格script（人間承認フロー込み）
- `evidence-index-promotion-first-reviewed-sample`: 実データで最初にreviewed/approvedなStory Summaryが揃った際、Summary evidenceRefs整合性チェックを実データで再確認する
- `internal-review-evidence-packet-design`: `stage_direction`等を含むInternal Review Evidence Packetの詳細設計

---

# 13. Next steps

- `evidence-index-promotion-copy-script`: `check_evidence_index_promotion.py`がPASSした候補を`knowledge/evidence/stories/`へ実際にcopyする昇格script → **実装済み**（`scripts/promote_evidence_index.py`、`docs/runbooks/Evidence_Index_Promotion_Copy.md`参照。dry-run既定・`--execute`必須・実データcommitはまだ未実施）
- `evidence-index-promotion-first-reviewed-sample`: 実データreviewed/approved Summary投入後にSummary evidenceRefs整合性チェックを再確認する
- `internal-review-evidence-packet-design`: `stage_direction`等を含むInternal Review Evidence Packetの詳細設計
- `evidence-index-public-id-public-safe-projection`（実装済み、`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`）: 本checkは、内部ID中心のCompatible projection・公開ID中心のPublic-safe projectionのどちらの出力に対しても実行できる（schema/entry type policyは共通）。ただし本script自体はsourceKey由来ID混入の専用scanを持たない（それはprojection script側のinternal ID exposure scanが担う、`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §6.9）。この統合（promotion check側でのsourceKey混入scan追加）は未着手のまま
- `evidence-index-public-id-registry-integration`（実装済み、`scripts/project_evidence_index_public_ids.py --registry`）: Public ID Registryで補完されたPublic-safe projection出力に対しても、本checkは無変更のまま実行できる（Registry補完はprojection script側の責務であり、本checkはprojectionの最終出力を検証するのみ）
- `evidence-index-public-id-renderer-switch`（実装済み、Evidence page見出し・anchor・Summary evidenceRefsリンクの`publicEvidenceId`中心切替）: 本checkはrenderer出力そのものは検証しない（Evidence Index YAML入力のみを検証する）ため無変更。renderer switch後もpromotion再開の前提条件は`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §5.1を参照

---

# 14. 関連ドキュメント

- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（Evidence Index候補生成dry-run手順）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（本checkをPASSした候補を`knowledge/evidence/stories/`へcopyする手順）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria/public entry type policy/candidate references方針）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・実装フェーズ）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（Compatible/Public-safe projectionの違い、internal ID exposure scan方針）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（`publicEpisodeId`未確定問題・Public ID Registry設計）
- `docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）
- `scripts/check_evidence_index_promotion.py`（本手順のcheck script）
- `scripts/promote_evidence_index.py`（promotion checkをPASSした候補のcopy script）
- `scripts/project_evidence_index_public_ids.py`（Compatible/Public-safe projection script）
- `scripts/check_public_episode_ids.py`（publicEpisodeId未確定episodeの検出・割当候補提案script）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `TASKS.md`（次PR候補の追跡）
