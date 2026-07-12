# AI PR Playbook（AIエージェント向けPR作業の共通ルール）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/AI_PR_Playbook.md`

---

# 1. 目的

このprojectでは、AIエージェント（Claude Code等）へのPR作業指示を1つずつ独立したプロンプトとして与える運用が続いている。これまで各プロンプトは「PRワークフロー」「commit禁止リスト」「検証コマンド」「Non-goals」「最終報告様式」を毎回ほぼ同じ内容で書き直しており、冗長だった。

本文書はこれらの**恒常的なルールを一度だけ集約**し、以降の個別PRプロンプトは「このPlaybookに従うこと」を宣言した上で、そのPR固有の情報（目的・参照docs・作業内容・固有のNon-goals追加分）のみを書けばよいようにする。

**新しいルールを追加する文書ではない。** 既存の`AI_CONTEXT.md` §3.11・`.gitignore`・各PRのNon-goals記述・`docs/runbooks/Evidence_Index_Promotion_Copy.md`等のチェックリストを正として、その内容を整理・集約したものである。矛盾が生じた場合は`AI_CONTEXT.md`・`.gitignore`・各機能領域の設計docsを優先する。

---

# 2. 使い方（個別PRプロンプトの書き方）

個別PRの指示プロンプトは、以下のテンプレートに従って書く。

```text
PR #NNNをマージ後、mainを最新化し、ブランチ {branch-name} を作成してください。
docs/runbooks/AI_PR_Playbook.md のワークフロー・制約・検証・報告に従うこと。
PR種別: {docs-only | 実装 | dry-run}（§4参照）

目的: {2〜3行}

背景・確定事項: {このPRの前提となる決定・固定値のみ。数値等は変更させない場合は明記}

参照: {このPR固有のdocs/scriptsのみ。Playbook自体・AI_CONTEXT.md・TASKS.mdは前提として省略可}

作業内容:
- {箇条書き}

このPR固有のNon-goals（Playbookの恒常リスト§7に追加）:
- {あれば}
```

これにより、個別プロンプトは「そのPRで何が新しいか」だけに集中できる。ワークフロー・commit禁止リスト・検証コマンド・報告様式は本文書を参照するだけでよい。

---

# 3. PRワークフロー（恒常）

1. 前PRをsquash mergeする（`gh pr merge <前PR番号> --squash --delete-branch=false`、ユーザーからマージ方針の指定が無い場合はこれを既定とする）
2. `git checkout main && git pull origin main`でmainを最新化する
3. `git checkout -b <branch-name>`で新規ブランチを作成する
4. 作業を実施する（§4のPR種別プリセットに従う）
5. §6の標準検証コマンドをすべて実行し、PASSを確認する
6. `git status --short`で差分を確認し、§4の許容差分・§7のcommit禁止リストと照合する
7. 意図したファイルのみを`git add`し、`Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`を含むcommitメッセージでcommitする
8. `git push -u origin <branch-name>`し、`gh pr create`でPRを作成する（Summary/Non-goals/Test planを含む本文）
9. `gh pr checks <PR番号> --watch`（または同等の方法）でCI PASSを確認する
10. §8の最終報告テンプレートに従ってユーザーへ報告する

マージ方法・commit方針についてユーザーから明示的な指定が無い場合の判断に迷う場合のみ確認を挟む。それ以外は上記フローをそのまま実行してよい。

---

# 4. PR種別プリセットと許容差分

### docs-only PR

実装変更を一切行わない。許容されるcommit対象:

- `docs/`配下のMarkdown
- `TASKS.md`
- `AI_CONTEXT.md`
- `tests/docs/`配下のdocs tests

### 実装PR

上記に加えて以下も許容:

- `agents/`・`scripts/`・`schemas/`配下の実装変更
- `tests/`配下のtests（**合成fixtureのみ**。実データ由来のfixtureは追加しない）

### dry-run PR

複数story・batch処理等をworkspace限定で試行するPR。許容差分は原則docs-only PRと同じ（docs/TASKS/AI_CONTEXT/docs tests）。dry-run自体の生成物（Registry候補・projection output・mapping・各種report・review note・rendered Markdown/HTML等）は**すべてworkspace限定とし、一切commitしない**（§7）。

---

# 5. 匿名化ルール

- 実sourceKey・実タイトル・実サブタイトル・実ファイル名・実イベント名・raw path・URLをdocs/testsに書かない
- 実データ由来のIDは、必要に応じて`{publicStoryId}`のようなプレースホルダー、または`匿名化表記`・`匿名workspace ID`のような一般的な言い回しにする
- 特定のdocsファイル（`Evidence_Index_Public_ID_Policy.md`・`TASKS.md`等）は、既存のdocs tests（`tests/docs/`配下の`REAL_DATA_HINTS`方式）によって特定の文字列パターン（例: 実データ日付断片、内部storyIdの一部）が機械的に禁止されている場合がある。**docs編集後は必ず該当するdocs testsを実行し、新たに禁止文字列を書き込んでいないか確認する**
- 新しい実データ由来の断片（新しいdry-run候補storyの内部ID等）を扱う場合は、既存の`REAL_DATA_HINTS`相当のリストにその断片を追加し、以降のdocsで誤って書き込まれないようにする

---

# 6. 標準検証コマンド（恒常）

すべてのPRで、コミット前に以下を実行しPASSを確認する。

```powershell
uv run pytest
uv run python scripts/check_invisible_unicode.py
uv run python scripts/check_dry_run_inputs.py
uv run ruff format scripts agents tests --check
uv run ruff check scripts agents tests
uv run mkdocs build --strict
```

加えて、PR作成後は`gh pr checks <PR番号>`（またはウォッチモード）でGitHub Actions CIのPASSを確認する。

個別のPRで追加のscript実行（例: `validate_evidence_index.py`・`check_evidence_index_promotion.py`等）が必要な場合は、そのPR固有のプロンプトに明記する。

---

# 7. Commit禁止リスト（恒常）

以下は、個別PRのプロンプトで明示的に上書きされない限り、**どのPRでもcommit対象にしない**。`.gitignore`と`AI_CONTEXT.md` §3.11を正とし、本節はその要約である。

## 7.1 実データ・生成物

- 実`.dec`（`data/raw/**/*.dec`、および実データ由来ファイル名パターンに一致するtests/fixtures混入分。具体的なパターンは`.gitignore`を正とする）
- 実データ由来の`story_manifest.yaml`
- 実Normalized Story JSON（`data/normalized/**/*.json`）
- 実extraction/merged collection JSON（`data/extracted/**/*.json`等）
- 実Wiki Markdown・raw HTML（`workspace/wiki_preview/`・`workspace/wiki_render/`・`site/`等）
- 実データ由来のfixture（合成fixtureのみ許可）
- ローカル絶対パスを含む結果ファイル
- MkDocs site出力・一時MkDocs設定ファイル

## 7.2 workspace配下の生成物一般

以下のディレクトリ配下の内容は、既存の`.gitignore`により恒常的にignore対象である（`.gitkeep`等の骨組みファイルを除く）:

`workspace/dry_runs/`・`workspace/wiki_preview/`・`workspace/wiki_render/`・`workspace/evidence_index_dry_runs/`・`workspace/public_episode_ids/`・`workspace/profile_import/`・`workspace/review_packets/`・`workspace/local_inputs/`・`workspace/summary_drafts/`・`workspace/story_manifest/`

これらの配下で生成されるRegistry候補・projection output・mapping（内部ID⇔公開IDの対応表を含む）・各種check/promotion report・human review note・batch dry-run report等は、**すべてworkspace限定・非commit**とする。

## 7.3 その他

- `.env`・APIキー・`*.log`
- 実データ由来のprofile候補・title/subtitle候補等の各種`*_candidates_*`ファイル（`.gitignore`参照）

## 7.4 commit可否の最終確認

`git status --short`実行後、上記に該当するファイルが差分に含まれていないことを目視確認してからcommitする。含まれている場合は、意図しない生成物混入の可能性が高いため、commitを中止して原因を調査する。

---

# 8. 恒常Non-goals

以下は、個別PRのプロンプトで明示的に指示されない限り、**どのPRでも行わない**。個別PRのプロンプトでは、この恒常リストへの追加分・例外のみを記載すればよい。

- 自動昇格（GitHub Actions等での自動promotion）
- `promote_evidence_index.py --execute`の、指示のない実行
- schema（Evidence Index/Public ID Registry/Summary等）の破壊的変更
- `agents/extractor/`のLLM呼び出し本体・provider連携実装（ユーザーの明示的指示があるまで、`AI_CONTEXT.md` §4）
- LLM provider実装・prompt実装
- 実データSummary生成
- AI Analysis / Speculation schemaの実装
- Jinja2導入・MkDocsテーマ移行
- public publishing設定（GitHub Pages / Cloudflare Pages等）
- Knowledge Graph生成
- Parserの大規模再設計
- Docker/devcontainer整備
- Internal Review Evidence Packet生成（設計未確定のため、明示的な設計PRでのみ着手）
- `reference/parser/story_parse_reference.py`・`characters_reference.json`の直接改造（読み取り専用参照資料、`AI_CONTEXT.md` §5）

---

# 9. 最終報告テンプレート

作業完了後、以下の項目でユーザーへ報告する。

- `git diff --stat`
- 追加・変更ファイル一覧
- 実装変更の有無
- そのPR固有の作業結果サマリー（3〜5行程度）
- 標準検証結果（pytest / check_invisible_unicode.py / check_dry_run_inputs.py / ruff format --check / ruff check / mkdocs build --strict）
- GitHub Actions CI結果
- あえて実装しなかった内容（Non-goals該当分）
- 次に着手するなら何か（次PR候補）
- §7のcommit禁止物がcommit対象に含まれていないことの確認

---

# 10. 関連ドキュメント

- `AI_CONTEXT.md`（プロジェクト全体の設計思想・やってはいけないこと §4・実データ非commit方針 §3.11）
- `TASKS.md`（現在の作業状態、Current Focus/Next/Backlog）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（Evidence Index batch promotion固有の運用ルール、本Playbookとは別レイヤー）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md` / `Evidence_Index_Promotion_Check.md`（Evidence Index promotion固有の手順）
- `.gitignore`（commit禁止対象の正式な定義）
