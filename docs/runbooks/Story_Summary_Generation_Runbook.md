# Story Summary Generation Runbook（Story Summary生成〜昇格の実行手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Story_Summary_Generation_Runbook.md`

---

# 1. Purpose（目的）

`Story_Summary_Generation_Plan.md` §5 Stage 0（PoC）で確立し、`summary-promotion-copy-script`（`scripts/promote_story_summaries.py`）で完結した、Story/Episode Summary AI生成〜人間レビュー〜Public-safe projection〜`knowledge/summaries/stories/`への昇格までの全手順を1つのrunbookとして整備する。

**本文書はPoCで実証済みの手順を正として文書化したものであり、新しいルールを発明しない。** 各stepのCLI引数・blocking条件・safety策は、対応するscriptのdocstring/`--help`および`docs/architecture/06_AI/Story_Summary_Generation_Plan.md`・`docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`を正とする。本文書はそれらの手順を実行順に並べ、PoCで得られた運用上の知見（品質ゲート後の人間レビュー観点・既知の制約）を補足するものである。

---

# 2. 前提（prerequisites）

- `docs/architecture/06_AI/Story_Summary_Generation_Plan.md`（AI要約生成パイプライン全体計画、§5 Pipeline stage design・§8 Quality gate）を読んでいること
- `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`（Public-safe projectionのCLI仕様・field変換表・evidenceRefs変換仕様）を読んでいること
- `docs/architecture/06_AI/Story_Summary_Design.md`（Summaryのデータモデル・保存場所・status/review workflow）を読んでいること
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（本Runbookが体裁・safety方針を踏襲するEvidence Index側のpromotion copy手順）を読んでいること
- 対象storyが**Evidence Index昇格済み**であること（`knowledge/evidence/stories/`に該当storyの`{publicStoryId}.yaml`が存在し、evidenceRefs変換用のmapping CSVを再生成できること。Evidence Index未昇格のstoryはevidenceRefsを空配列にしてでも生成・昇格は可能だが、本Runbookは`Story_Summary_Generation_Plan.md` §5 Stage 0/1の前提どおりEvidence Index昇格済みstoryを対象とする）
- ローカルOllamaが起動していること（生成stepでのみ必要。`docker-compose.yml`の`ollama`サービス、または devcontainer外で起動したローカルOllama）
- LLM呼び出し・実データSummary生成の着手には、`AI_CONTEXT.md` §4の方針どおり**ユーザーの明示的な指示**が必要（本Runbookはその指示が既に得られている状態での実行手順を扱う）

---

# 3. Pipeline overview（8ステップ概要）

| Step | 内容 | 主なscript | 実行環境 |
|---|---|---|---|
| 1 | 対象story選定 | - | 人間判断 |
| 2 | 再normalize | `scripts/normalize_story.py` | ローカル、`uv run`必須 |
| 3 | 生成（Episode Summary→Story Summary合成） | `scripts/generate_story_summaries.py` | ローカルOllama必要 |
| 4 | Quality gate | `scripts/check_story_summary_drafts.py` | ローカル、check-only |
| 5 | 人間レビュー | - | 人間判断 |
| 6 | Public-safe projection | `scripts/project_story_summary_public_ids.py` | ローカル |
| 7 | 昇格（promotion） | `scripts/promote_story_summaries.py` | ローカル、`--execute`は実データcommit相当 |
| 8 | commit前検証 | `validate_story_summaries.py`・`check_evidence_index_promotion.py`・`check_story_summary_drafts.py`＋標準検証 | ローカル |

Step 1〜6の生成物は**すべてworkspace限定・非commit**（§12参照）。commit対象になるのはStep 7で`knowledge/summaries/stories/`へcopyされたfileのみである。

---

# 4. Step 1: 対象story選定

- Evidence Index昇格済みstory（`knowledge/evidence/stories/{publicStoryId}.yaml`が存在するstory）のうち、evidenceRefs変換が可能なものを選ぶ
- batch sizeは`Story_Summary_Generation_Plan.md` §5のStage制約に従う（Stage 0: PoC=1 story、Stage 1: small batch=最大3〜5 story、Stage 2: 通常運用=段階的拡大）
- 対象storyのstoryId/publicStoryId等の実データはworkspace限定のメモにのみ記録し、本Runbook・`TASKS.md`には`{publicStoryId}`のようなプレースホルダー表記で記録する（§14参照）

---

# 5. Step 2: 再normalize

staleなローカル生成物（過去の別PRで生成したNormalized Story JSON）を使わず、確定済みのmanifestから対象episodeを再normalizeする。

```bash
uv run python scripts/normalize_story.py \
    --input <対象episodeのraw .decファイルパス> \
    --manifest <確定済みstory_manifest.yamlのパス> \
    --raw-root <ローカルraw rootディレクトリ> \
    --manifest-strict \
    --validate \
    --output <再normalize出力先ディレクトリ>
```

- `--manifest`/`--raw-root`/`--manifest-strict`により、manifest側で確定済みの`storyId`/`episodeId`/`publicStoryId`/`publicEpisodeId`等が`metadata`へ伝播する。対象episodeが複数ある場合は、episodeごとに`--input`を変えてこのコマンドを繰り返す
- **`uv run`を必ず使うこと。** `--validate`はJSON Schema検証を`import jsonschema`で行うが、素の`python`（`uv`が管理する仮想環境を経由しない実行）では`jsonschema`パッケージが見つからず、`[警告] jsonschema がインストールされていません。スキップします。`と表示されて検証が黙ってskipされる。この状態でもexit codeは0のまま進んでしまうため、`--validate`を指定したのにschema検証が実際には行われていないことに気づかないまま次stepへ進むリスクがある
- 実行後、以下を確認する:
  - 出力JSONの`compatibilityReport`（またはstdout）で`unknownCommands: 0`相当であること（`unknown`ブロックが残っている場合は、そのepisodeを対象から外すか`config/script_commands.yaml`の辞書拡充を先に行う）
  - 出力JSONの`metadata.publicStoryId`/`episodes[].metadata.publicEpisodeId`が期待するpublic IDに正しく伝播していること（`--manifest`側で確定済みの値と一致するか目視確認する）

---

# 6. Step 3: 生成（Episode Summary→Story Summary合成）

ローカルOllamaが起動していることを確認した上で、Step 2で再normalizeしたディレクトリを入力に生成を行う。

```bash
uv run python scripts/generate_story_summaries.py \
    --input <Step 2の出力ディレクトリ> \
    --output workspace/summary_drafts/<batch>/drafts/ \
    --model <Ollamaモデル名> \
    --timeout 600 \
    --report workspace/summary_drafts/<batch>/generation_report.md \
    --clean
```

- `--output`/`--report`は`workspace/`配下のみ許可される（`knowledge/`配下を指定するとexit code 2で拒否される）
- 同一`storyId`の複数episodeファイル（Phase 1 parserは1 episode 1ファイルのため、複数episodeを持つstoryは必ず複数ファイルに分かれる）は自動的にstoryId単位でグルーピング・episodeNumberでrenumberされ、1つのdraft YAMLとして出力される（`summary-generation-multi-episode-grouping`/`summary-generation-episode-renumbering`で修正済みのバグ、PR #115/#116参照）
- Story Summaryは既定で合成される（Episode Summary群からLLM再要約、`--no-story-synthesis`でopt-out可能だが本Runbookの通常フローでは指定しない）
- `--timeout`はEpisodeの長さに応じて調整する（PoCでの実測を踏まえ600秒を目安値として例示している。既定は120.0秒）
- 生成directのdraftは`generationStatus: draft`のまま出力される。Step 4のquality gateへ進む

---

# 7. Step 4: Quality gate

```bash
uv run python scripts/check_story_summary_drafts.py \
    --input workspace/summary_drafts/<batch>/drafts/ \
    --normalized <Step 2の出力ディレクトリ> \
    --report workspace/summary_drafts/<batch>/quality_gate_report.md
```

- `--normalized`を指定することで、schema検証・禁止文字列scanに加えてevidenceRefs実在性検証・長文verbatim引用検出（既定閾値30文字）も行われる（`--normalized`省略時はこの2項目がskipされ、reportにその旨が明記される）
- 検証4項目（schema検証・evidenceRefs実在性・禁止文字列scan・長文verbatim引用検出）のいずれかでblocking issueが検出された場合、exit codeが1になり、そのdraftは昇格不可となる。reportの`## Issues`を確認し、Step 3のprompt調整・再生成、またはStep 5の人間レビューで個別に判断する
- 全PASS（exit code 0）を確認してからStep 5へ進む。人間レビューは機械的検証をすべて通過したdraftのみを対象にする（`Story_Summary_Generation_Plan.md` §8.3の分担原則）

---

# 8. Step 5: 人間レビュー

Quality gateをPASSしたdraftの内容を人間がレビューする。**PoC（Stage 0）で実証されたレビュー観点を以下のチェックリストとして固定する。**

## 8.1 レビューチェックリスト

- [ ] **(a) 主語の取り違え**: イベント名・グループ略称等の固有名詞を行為主体として誤用していないか（PoCで実際に検出された誤り。要約対象の物語には登場人物とは別に「イベント名」「組織の略称」等の固有名詞が頻出するため、LLMがこれらを人物名と取り違えて主語に使うことがある）
- [ ] **(b) 引用の妥当性**: 要約の中核主張を支える引用（`evidenceRefs`）が選ばれているか。引用blockの原文を`--normalized`出力（またはStep 2出力のNormalized Story JSON）で照合し、要約文の主張と引用元の内容が実際に対応しているか確認する（PoCでは、内容自体は妥当だが根拠として弱い引用が選ばれているケースが検出された）
- [ ] **(c) 原文にない状況説明の混入（歪曲）**: 要約文に、参照元Blockの原文には無い状況描写・因果関係・心情描写が追加されていないか（`Story_Summary_Design.md` §7.2「Summaryに含めない」範囲の混入チェック）
- [ ] **(d) 用語・略称の正式名称との対応**: 原作固有の用語・略称が、正式名称と食い違った形で使われていないか（原作domain知識が必要なため、レビュー担当者が個別に確認する）

## 8.2 修正手順

- 上記チェックで問題が見つかった場合、draftの`storySummary.text`/`episodeSummaries[].text`および該当する`evidenceRefs`を**直接編集**する（自動修正ロジックは無い）
- 修正内容は`review.notes`に記録する（何を・なぜ修正したかが後から追跡できる粒度で記述する）
- 修正後、`review.status: approved`（または`reviewed`）・`generationStatus: generated`へ更新し、`review.reviewer`にレビュー担当者を記名する
- `source.sourceType`は`ai_generated`のまま変更しない（AI生成であることの記録は維持する）
- 修正後のdraftに対して、Step 4のquality gateを**再実行**し、PASSを再確認する（本文編集によって禁止文字列やverbatim閾値超過が新たに発生していないかの機械的再チェック）

---

# 9. Step 6: Public-safe projection

人間レビューで`review.status: approved`（または`reviewed`）・`generationStatus: generated`になったdraftに対して、Public-safe projectionを実行する。evidenceRefs変換には、対象storyのEvidence Index public-safe projection時に生成したmapping CSV（`scripts/project_evidence_index_public_ids.py --projection-mode public-safe --mapping-output <path>`の出力）を使う。

```bash
uv run python scripts/project_story_summary_public_ids.py \
    --input workspace/summary_drafts/<batch>/drafts/ \
    --output workspace/summary_drafts/<batch>/public_safe/stories/ \
    --mapping-output workspace/summary_drafts/<batch>/public_safe/mapping.csv \
    --report workspace/summary_drafts/<batch>/public_safe/report.md \
    --projection-mode public-safe \
    --registry knowledge/public_ids/story_public_ids.yaml \
    --evidence-mapping <Evidence Index側public-safe projectionのmapping CSVまたはdirectory>
```

- `--output`/`--mapping-output`/`--report`はいずれも`workspace/`配下のみ許可される（`knowledge/summaries/`・`knowledge/public_ids/`配下は拒否）
- 実行後、reportで以下を確認する:
  - `evidenceRefs`が全件変換されていること（`## Evidence Refs Conversion`のConverted count / Cleared count。Cleared countが0でない場合、mapping CSVに未収録の内部ID参照が残っている可能性があるため原因を確認する）
  - `## Public-safe Projection`の`Internal ID exposure scan result`が0件であること（`internal_id_exposure=0`）
  - `Promotion readiness`が`promotion-candidate`であること
- blocking issue（`publicStoryId`/`publicEpisodeId`欠落、Registry値との矛盾、exposure scan検出等）が1件でもあればexit code 1となり、projectionは失敗する。Step 5のレビュー内容ではなくID解決側の問題であることが多いため、`knowledge/public_ids/story_public_ids.yaml`のRegistry entryとEvidence Index側mapping CSVを確認する

---

# 10. Step 7: 昇格（promotion）

Public-safe projection済みfile（`{publicStoryId}.yaml`）を`knowledge/summaries/stories/`へ昇格する。**まずdry-runで確認し、問題なければ`--execute`する。**

```bash
# dry-run（既定、何もcopyしない）
uv run python scripts/promote_story_summaries.py \
    --input workspace/summary_drafts/<batch>/public_safe/stories/ \
    --target knowledge/summaries/stories \
    --registry knowledge/public_ids/story_public_ids.yaml \
    --evidence-index knowledge/evidence/stories/ \
    --report workspace/summary_drafts/<batch>/promote_report.md
```

dry-run結果（Planned copies / Skipped files / Overwrite conflicts）を確認し、意図した件数のみがplanned copyに含まれていることを確認したら、`--execute`を追加して実copyする。

```bash
uv run python scripts/promote_story_summaries.py \
    --input workspace/summary_drafts/<batch>/public_safe/stories/ \
    --target knowledge/summaries/stories \
    --registry knowledge/public_ids/story_public_ids.yaml \
    --evidence-index knowledge/evidence/stories/ \
    --report workspace/summary_drafts/<batch>/promote_report.md \
    --execute
```

**`--execute`は`AI_PR_Playbook.md` §3/停止点ルールにおける「実データcommitに相当する」操作であり、ユーザーの明示的な承認が必須である。** dry-run結果をユーザーへ提示し、承認を得てから`--execute`する（Evidence Index側`promote_evidence_index.py --execute`と同じ運用、`docs/runbooks/Evidence_Index_Promotion_Copy.md` §5参照）。

- copyは`shutil.copy2`によるbyte-for-byte copyで、内容の変換は行わない
- `--execute`成功後は、`--target`（`knowledge/summaries/stories/`）に対しても前提条件1〜5が再実行される（sanity re-check、reportの`## Post-copy validation`）
- `promote_story_summaries.py`自体は`git add`/`git commit`を行わない。commitは人間が別途`git status`/`git diff`を確認した上で判断する

---

# 11. Step 8: commit前検証

`knowledge/summaries/stories/`へcopyされたfileに対して、以下をすべて実行しPASSを確認する。

```bash
uv run python scripts/validate_story_summaries.py \
    --input knowledge/summaries/stories/ \
    --require-reviewed

uv run python scripts/check_evidence_index_promotion.py \
    --input knowledge/evidence/stories/ \
    --story-summaries knowledge/summaries/stories/

uv run python scripts/check_story_summary_drafts.py \
    --input knowledge/summaries/stories/
```

続けて、`AI_PR_Playbook.md` §6の標準検証コマンドをすべて実行しPASSを確認してからPRを作成する。

```powershell
uv run pytest
uv run python scripts/check_invisible_unicode.py
uv run python scripts/check_dry_run_inputs.py
uv run ruff format scripts agents tests --check
uv run ruff check scripts agents tests
uv run mkdocs build --strict
```

---

# 12. 生成物のcommit可否表

| 生成物 | 生成step | commit可否 |
|---|---|---|
| 再normalize出力（Normalized Story JSON） | Step 2 | 非commit（`data/normalized/**/*.json`は実データのためcommit禁止、`AI_PR_Playbook.md` §7.1） |
| draft YAML（`workspace/summary_drafts/<batch>/drafts/`） | Step 3 | 非commit（workspace限定） |
| 生成report（`generation_report.md`） | Step 3 | 非commit（workspace限定） |
| quality gate report | Step 4 | 非commit（workspace限定） |
| Public-safe projection output | Step 6 | 非commit（workspace限定） |
| mapping CSV（内部ID⇔公開ID対応表） | Step 6 | **非commit（内部IDを含むため恒常的にcommit禁止、Evidence Index側mapping CSVと同じ扱い）** |
| projection report | Step 6 | 非commit（workspace限定） |
| レビュー用抽出テキスト（原文照合用に一時的に書き出したもの） | Step 5 | 非commit（workspace限定） |
| promote dry-run/execute report | Step 7 | 非commit（workspace限定） |
| `knowledge/summaries/stories/{publicStoryId}.yaml` | Step 7（`--execute`後） | **commitするのはこのfileのみ** |

commitするのは`knowledge/summaries/stories/{publicStoryId}.yaml`のみであり、それ以外の生成物は`workspace/summary_drafts/`配下（`.gitignore`保護、`AI_PR_Playbook.md` §7.2）に置く。commit前に`git status --short`で意図しないfileが含まれていないことを必ず確認する。

---

# 13. Known limitations（既知の制約）

## 13.1 chunk分割未実装

`scripts/generate_story_summaries.py`の`--max-input-characters`（既定`50000`文字）を超える長さのepisodeは、chunk分割による2段階要約が未実装のため、生成自体がskipされる（`generationStatus: draft`にすら到達しない、issueとして記録されるのみ）。長文episodeを対象にする場合は、事前にNormalized Story JSONの文字数を確認し、上限を超える場合は本Runbookの対象から除外する（`Story_Summary_Generation_Plan.md` §6.4参照、chunk分割は将来PRのスコープ）。

## 13.2 LLMの傾向（人間レビュー必須の理由）

PoCで以下の傾向が実際に観測された。機械的なquality gate（schema検証・evidenceRefs実在性・禁止文字列scan・verbatim引用検出）はいずれもこれらを検出できないため、§8のレビューチェックリストによる人間レビューが必須である。

- 主語の取り違え（イベント名・グループ略称等の固有名詞を行為主体として誤用する）
- 弱い引用選択（要約文の中核主張に対して、根拠として直接的でない`evidenceRefs`を選ぶ）

## 13.3 コンソールがcp932の場合の生成テキスト確認方法

Windows環境のコンソール（PowerShell/コマンドプロンプト、既定コードページcp932）でscriptの`--help`やログ出力を直接確認すると、日本語部分が文字化けする（`uv run python scripts/xxx.py --help`のUsage文などで実際に発生する）。生成されたSummary本文の内容確認をコンソール出力に頼ると、この文字化けにより正しく読めない、または誤読するリスクがある。

**生成テキストの内容確認は、必ずUTF-8のfile経由で行う。** 具体的には:

- draft/reportはいずれもUTF-8で書き出されるため、コンソールに直接表示させず、UTF-8対応のエディタ（VS Code等）またはUTF-8を明示指定して読むツールで開く
- コンソールでどうしても内容を確認する必要がある場合は、`chcp 65001`でコードページをUTF-8に切り替える、またはPowerShellの`Get-Content -Encoding utf8`のようにencodingを明示指定する

---

# 14. 匿名化ルール

`AI_PR_Playbook.md` §5を継承する。本Runbook固有の補足:

- 実sourceKey・実タイトル・実サブタイトル・キャラクター名・要約本文（storySummary/episodeSummariesのtext）を、本Runbook・`TASKS.md`・その他docsに書かない
- 対象storyを記述する必要がある場合は`{publicStoryId}`のようなプレースホルダー表記を使う
- 本Runbookを編集した際は、`tests/docs/`配下の関連docs testsを実行し、既存の`REAL_DATA_HINTS`相当のリストに抵触する文字列を新たに書き込んでいないか確認する

---

# 15. Non-goals

本Runbook自体の整備（本PR）では以下を行わない。

- `agents/`・`scripts/`・`schemas/`配下の変更
- 実データ生成・昇格の実行
- `docs/runbooks/AI_PR_Playbook.md`自体の変更

---

# 16. 関連ドキュメント

- `docs/architecture/06_AI/Story_Summary_Generation_Plan.md`（AI要約生成パイプライン全体計画、§5 Pipeline stage design・§8 Quality gate・§9 Implementation phases）
- `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`（Public-safe projectionのCLI仕様・field変換表・evidenceRefs変換仕様・Registry共有設計）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Summaryのデータモデル・保存場所・status/review workflow）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（本Runbookが体裁・safety方針を踏襲するEvidence Index側のpromotion copy手順）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（batch size段階・Registry review条件・failed story/rollback方針、本Runbook §4のbatch size制約が参照する運用ルール）
- `docs/runbooks/AI_PR_Playbook.md`（PRワークフロー・commit禁止リスト・標準検証コマンド・停止点ルール）
- `scripts/normalize_story.py` / `scripts/generate_story_summaries.py` / `scripts/check_story_summary_drafts.py` / `scripts/project_story_summary_public_ids.py` / `scripts/promote_story_summaries.py` / `scripts/validate_story_summaries.py` / `scripts/check_evidence_index_promotion.py`（本Runbookが呼び出す各script、CLI引数の正確な仕様は各scriptの`--help`/docstringを正とする）
- `TASKS.md`（次PR候補の追跡）
