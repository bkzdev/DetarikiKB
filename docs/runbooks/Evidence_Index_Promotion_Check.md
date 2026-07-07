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

# 12. Next steps

- `evidence-index-promotion-dry-run`: 実データfiltered outputに対して本手順を実施し、結果を匿名化してレビューする
- `evidence-index-promotion-copy-script`: `check_evidence_index_promotion.py`がPASSした候補を`knowledge/evidence/stories/`へ実際にcopyする昇格scriptを検討する（人間承認フロー込み）
- `internal-review-evidence-packet-design`: `stage_direction`等を含むInternal Review Evidence Packetの詳細設計

---

# 13. 関連ドキュメント

- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（Evidence Index候補生成dry-run手順）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria/public entry type policy/candidate references方針）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・実装フェーズ）
- `docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）
- `scripts/check_evidence_index_promotion.py`（本手順のcheck script）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `TASKS.md`（次PR候補の追跡）
