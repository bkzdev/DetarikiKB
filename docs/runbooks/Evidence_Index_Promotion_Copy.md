# Evidence Index Promotion Copy Procedure（Evidence Index昇格copyの手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Evidence_Index_Promotion_Copy.md`

---

# 1. Purpose（目的）

`scripts/promote_evidence_index.py`を使い、`docs/runbooks/Evidence_Index_Promotion_Check.md`のpromotion checkをPASSしたPublic Evidence Index候補を、`knowledge/evidence/stories/`へ安全にcopyする手順を定義する。

**デフォルトは常にdry-run。**`--execute`を明示指定しない限り一切ファイルを書き込まない（`feature/evidence-index-promotion-copy-script`）。本手順は「昇格checkに通った候補をどうやって安全にcopyするか」を扱う。checkそのものの内容（entry type policy・source text exposure・Summary evidenceRefs整合性等）は`docs/runbooks/Evidence_Index_Promotion_Check.md`を参照。

**実データ・生成物は一切Gitにcommitしない。** このドキュメントも`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`/`Evidence_Index_Promotion_Check.md`と同じ方針を踏襲する。

---

# 2. 前提（prerequisites）

- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（Evidence Index候補生成dry-run手順）を先に読んでいること
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（promotion check手順）を先に読み、対象候補が`scripts/check_evidence_index_promotion.py`相当のcheckをPASSしていること
- `docs/templates/evidence_index_promotion_review_template.md`を使ったhuman review記録（review note）が作成済みで、Decisionで`Approved for promotion`がcheckされていること
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria）を把握していること

---

# 3. Required inputs（必須入力）

| 引数 | 必須 | 内容 |
|---|---|---|
| `--input` | 必須 | Evidence Index YAMLファイル、またはdirectory（直下の`*.yaml`/`*.yml`を収集） |
| `--review-note` | 必須 | human review記録ファイル（Decisionで`Approved for promotion`がcheckされている必要がある） |
| `--target` | 必須 | copy先directory（既定では`knowledge/evidence/stories`のみ許可。tests等で一時ディレクトリを使う場合は`--allow-nonstandard-target`を明示指定） |
| `--report` | 任意 | check結果をMarkdownで書き出すファイルパス（workspace配下を推奨、commitしない） |
| `--schema` | 任意 | `schemas/evidence_index.schema.json`のパス（デフォルトあり） |
| `--story-summaries` | 任意 | promotion checkに渡すStory Summary YAML（`--story-summaries`未指定ならSummary evidenceRefs整合性チェックは行わない） |
| `--policy` | 任意 | promotion checkに渡すpolicy（デフォルト`public-default`、現状唯一の選択肢） |
| `--execute` | 任意 | 実際にfileをcopyする（指定しない場合はdry-runのみ） |
| `--overwrite` | 任意 | copy先に既存ファイルがある場合、上書きを許可する（既定は禁止） |
| `--allow-nonstandard-target` | 任意 | `knowledge/evidence/stories`以外のtargetを許可する（tests用） |
| `--quiet` | 任意 | 進捗メッセージを抑制する |

---

# 4. Dry-run command（既定、何もcopyしない）

```bash
uv run python scripts/promote_evidence_index.py \
    --input workspace/evidence_index_dry_runs/<run>/default/stories \
    --review-note workspace/evidence_index_dry_runs/<run>/review_note.md \
    --target knowledge/evidence/stories \
    --report workspace/evidence_index_dry_runs/<run>/promote_report.md
```

- `--execute`を指定しない限り、ファイルは一切書き込まれない
- stdoutに`DRY RUN: no files were copied.`と`Would copy:`一覧が表示される
- `--report`を指定した場合、同内容がMarkdownとしても出力される（workspace配下、非commit）

---

# 5. Execute command（実copy、明示的な`--execute`が必要）

```bash
uv run python scripts/promote_evidence_index.py \
    --input workspace/evidence_index_dry_runs/<run>/default/stories \
    --review-note workspace/evidence_index_dry_runs/<run>/review_note.md \
    --target knowledge/evidence/stories \
    --report workspace/evidence_index_dry_runs/<run>/promote_report.md \
    --execute
```

`--execute`時、以下がすべて満たされない限りcopyしない（1つでも満たさない場合はblockingとしてexit code 1、ファイルは一切書き込まれない）。

- `check_evidence_index_promotion.py`相当のpromotion checkがPASS
- `--review-note`が存在し、Decisionセクションで`- [x] Approved for promotion`がcheckされている（`Needs revision`/`Rejected`がcheckされている、または未決定の場合はblocking）
- review note自体にraw/source text禁止文字列が含まれていない
- 1ファイル1story方針が守られている（`entries[].storyId`が単一）
- copy先に既存ファイルがある場合は`--overwrite`が指定されている

copy自体は入力ファイルのbyte-for-byte copy（`shutil.copy2`）で行い、内容の再生成・変換は行わない。`--execute`成功後は、copy先に対してもschema+整合性検証を再実行する（sanity re-check、report上の「Post-copy validation」）。

---

# 6. Overwrite policy（上書き方針）

- **既定では上書き禁止**。copy先に同名ファイルが既に存在する場合、`--overwrite`を指定しない限りblocking error（`overwrite_conflict`）として扱われ、そのファイルはcopyされない
- `--overwrite`を指定した場合のみ、既存ファイルへの上書きを許可する
- overwrite conflictの一覧は`--report`のMarkdown「Overwrite conflicts」section、およびstdout（stderr）に出力される

---

# 7. Review note requirement（human review記録の必須化）

- `--review-note`は必須引数。指定しない場合はargparseのusageエラーになる
- ファイルが存在しない場合はexit code `2`（IO/config error）
- ファイルは存在するが、Decisionセクションで`Approved for promotion`がcheckされていない場合（`Needs revision`/`Rejected`がcheckされている、または何もcheckされていない）はexit code `1`（blocking validation failure）
- 判定は正規表現による簡易チェック（`- [x] Approved for promotion` / `- [X] Approved for promotion`）。`Rejected`/`Needs revision`がcheckされている場合は、`Approved for promotion`も同時にcheckされていても安全側で非承認として扱う
- review note自体もraw/source text禁止文字列scanの対象。ただし`docs/templates/evidence_index_promotion_review_template.md`の「## Source Text Exposure」チェックリスト自体が`` no `.dec` ``のように禁止文字列パターンをラベルとして含むため、チェックリスト行（`- [ ] ...`/`- [x] ...`）はscan対象から除外し、それ以外の自由記述行（Target/Notes等）のみをscanする
- review note自体はcommitしない想定（`workspace/`配下等）

---

# 8. Target path方針

- copy先ファイル名は`{storyId}.yaml`（Evidence Index document内の`entries[].storyId`から決定、`docs/architecture/06_AI/Evidence_Index_Design.md`の保存場所方針`knowledge/evidence/stories/{storyId}.yaml`と一致）
- 1ファイル内のentriesが複数のstoryIdを含む場合は「1ファイル1story」方針違反としてskipし、blocking errorになる（新しいID生成・自動分割は行わない）
- `--target`は既定で`knowledge/evidence/stories`（プロジェクトルート基準の絶対パス比較）のみを許可する。それ以外のpathを指定する場合は`--allow-nonstandard-target`を明示指定する必要がある（tests専用、実運用では使用しない）

---

# 9. Report出力

`--report`でMarkdown reportを出力できる（workspace配下を推奨、**commitしない**）。

内容:

- mode（`dry-run`/`execute`）・input path・target path・review note path・source file count
- Promotion Check（PASS/FAIL、entry数、type別内訳、violations/issues）
- Review Note（path、decision、approved有無、source text issues）
- Planned copies（source → target一覧）
- Skipped files（1ファイル1story違反等の理由付き）
- Overwrite conflicts
- Copied files（execute時のみ）
- Post-copy validation（execute時のみ、schema+整合性検証の再実行結果）
- Final Decision（`DRY RUN PASS` / `EXECUTE PASS` / `FAILED`）

---

# 10. Safety checks（実装済みの安全策）

- デフォルトdry-run、`--execute`必須
- promotion check（schema検証・raw text scan・entry type policy）を必ず実行
- review note必須・承認状態confirmation・review note自体のsource text scan
- 1ファイル1story方針の強制
- 上書き禁止（既定）、`--overwrite`必須
- copy後のsanity re-validation（schema+整合性検証）
- `--target`の既定値制限（`knowledge/evidence/stories`以外は明示opt-in）

---

# 11. Commit safety checklist（commit前チェック）

`docs/runbooks/Evidence_Index_Promotion_Check.md` §10のチェックリストに加え、以下を確認する。

- [ ] `--report`で出力したMarkdownがcommit対象に含まれていない（`workspace/`配下は`.gitignore`で保護済み）
- [ ] `--execute`を実データに対して実行した場合、`knowledge/evidence/stories/`へのcommitは別途人間が明示的な判断を行うまで実施しない（本scriptはcopyのみを行い、`git add`/`git commit`は行わない）
- [ ] `git status --short`で`knowledge/evidence/stories/`配下の意図しない変更が無いことを確認する
- [ ] **`storyId`（ファイル名・`evidenceId`等の主キーに使われる、sourceKey由来の可能性がある文字列）をGit履歴に永続的に残してよいか、commit前に人間が確認済みである**（§13.1の初回実施で確認された懸念事項、`publicStoryId`が別途存在してもファイル名・主キーはsourceKey由来のstoryIdのまま）

---

# 12. Non-goals

- 自動昇格（GitHub Actions等での自動promotion実行）
- `knowledge/evidence/stories/`への実データcommit自体（本scriptはcopyのみ、`git add`/`git commit`は行わない。commitするかどうかは人間が別途判断する）
- Internal Review Evidence Packet生成
- Evidence page renderer・evidenceRefsリンク化ロジックの変更
- Evidence Index generation filter（`scripts/build_evidence_index_candidates.py`）の変更
- 複数storyを1ファイルに分割・統合するロジック（1ファイル1story違反は常にskip、自動修復はしない）

---

# 13. First reviewed sample flow（初回の実データ昇格を行う場合の想定フロー）

将来、実データで初めて`knowledge/evidence/stories/`への昇格を行う場合の想定フロー（本PRでは実行しない）。

1. `scripts/build_evidence_index_candidates.py --public-profile default`でfiltered候補を生成
2. `scripts/validate_evidence_index.py`で基本検証
3. `scripts/check_evidence_index_promotion.py`でpromotion check（`--story-summaries`も可能なら指定）
4. `docs/templates/evidence_index_promotion_review_template.md`を使い人間がreview、Decisionで`Approved for promotion`をcheck
5. `scripts/promote_evidence_index.py`（`--execute`なし）でdry-run確認
6. 問題なければ`scripts/promote_evidence_index.py --execute`で実copy
7. `scripts/validate_evidence_index.py --input knowledge/evidence/stories`でcopy後の状態を再確認
8. `render_wiki.py --evidence-index knowledge/evidence/stories`・`mkdocs build --strict`で表示確認
9. 人間が`git status`/`git diff`を確認した上で、別途`git add knowledge/evidence/stories/{storyId}.yaml` + commitを判断する（本scriptはcommitしない）

## 13.1 初回実施結果（`feature/evidence-index-promotion-first-reviewed-sample`、匿名化）

上記フローのstep 1〜5（filtered候補生成〜dry-run確認）を実データ小規模サンプル（EVENTカテゴリ1story・episode2件）で実施し、以下を確認した。

| step | 結果 |
|---|---|
| filtered候補生成（`--public-profile default`） | 成功。1 story・187 entries（`dialogue`153・`monologue`6・`narration`26・`unknown`2・`choice`0・`stage_direction`0） |
| `validate_evidence_index.py` | 成功 |
| `check_evidence_index_promotion.py`（`--story-summaries`あり/なし） | 両方PASS |
| Human review note作成 | 実施。ただし後述の理由でDecisionは`Needs revision`とした |
| `promote_evidence_index.py`（dry-run） | review noteが未承認（`Needs revision`）のため`FAILED`と正しく判定された（実copyなし） |

**step 6以降（`--execute`による実copy）は実施しなかった。** 理由は以下の通り。

生成されたEvidence Index YAMLを確認したところ、`storyId`（sourceKey由来、`knowledge/evidence/stories/{storyId}.yaml`のファイル名としても使われる）が、ファイル内の全187 entryの`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`フィールドに数百回規模で繰り返し出現することを確認した。`publicStoryId`/`publicEpisodeId`という匿名化済みの公開用IDはentryごとに別途存在するが、**保存先ファイル名と主キー（`evidenceId`等）は依然としてsourceKey由来の`storyId`を使う設計**になっている（`Evidence_Index_Design.md`の`{storyId}.yaml`保存場所方針、`build_evidence_index_candidates.py`/`promote_evidence_index.py`共通の挙動）。

この状態でcommitすると、sourceKey由来の識別子がGit履歴に永続的に残る。当該識別子（イベント名相当の語を含む可能性がある）の公開可否は本Runbookの範囲では判断できないため、人間による最終確認を待つこととし、**今回のPRでは`knowledge/evidence/stories/`への実データ追加を見送った**（安全側の判断、`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §15参照）。

### 見送りの結果、今後検討すべき選択肢

1. 該当storyIdの内容が公開して問題ないことを人間が確認した上で、次PRで改めてpromotionを試みる
2. `knowledge/evidence/stories/`の保存先ファイル名・Evidence Index内の主キーを`publicStoryId`/`publicEpisodeId`基準に変更する設計変更を検討する（`Evidence_Index_Design.md`・`Identifier_Specification.md`の見直しが必要、影響範囲が大きいため別PRでの検討が必要）
3. 上記いずれも解決しない場合、`knowledge/evidence/stories/`へのfirst promotionはさらに後続タスクへ持ち越す

### 13.2 進捗（`feature/evidence-index-public-id-schema-design`）

選択肢2の設計を`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`で決定し（案C: public ID projectionとして保存）、`publicEvidenceId`のschema（`schemas/evidence_index.schema.json`へのoptional追加）を実装した。ただし、この時点では`promote_evidence_index.py`のtarget filename決定ロジック（`storyId`から`{storyId}.yaml`を決める`_extract_story_id`）自体はまだ変更していない。**promotion再開には、projection層の実装（`evidence-index-public-id-projection`）と`promote_evidence_index.py`側の対応（`publicStoryId`ベースのtarget filename化）が別途必要**（`Evidence_Index_Public_ID_Policy.md` §11・§12参照）。

### 13.3 進捗（`feature/evidence-index-public-id-projection`、匿名化）

`scripts/project_evidence_index_public_ids.py`（Compatible projection、案A）を、§13.1と同じ匿名化実データサンプル（EVENTカテゴリ1story・episode2件、187 entries）に対して`--policy public-default`（既定）でdry-run実行した。

- Episode 1（92 entries、`dialogue`/`monologue`/`narration`/`unknown`）は`publicEpisodeId`が確定済みのため、全件`publicEvidenceId`を正しく生成できた（`existing_matched=0`、`generated=92`、重複なし）
- Episode 2（95 entries）は、`story_manifest.yaml`側でこのepisodeの`publicEpisodeId`がまだ確定していない（`feature/story-page-manual-review`でfallback確認用にあえて未設定のまま残した既知の状態）ため、本scriptの「entryにpublicEpisodeIdが欠落している場合はblocking error」という安全策が正しく発火し、projection結果は全体として`FAIL`（exit code 1）となった
- projected出力（`--output`）は`validate_evidence_index.py`でschema検証PASS、内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）はentry内に変更なく残存していることを確認した
- `--mapping-output`（CSV）・`--report`（Markdown）ともに正しく生成され、source text exposure check（`.dec`/`@ChTalk`/`@Scenario`/`$num`/local path等の禁止文字列）はいずれもクリアだった
- 本実行の出力（projection結果・mapping CSV・report）はいずれも`workspace/evidence_index_dry_runs/public_id_projection/`配下（`.gitignore`保護）にのみ存在し、`knowledge/evidence/stories/`・Gitへのcommitは一切行っていない

**この結果は、Compatible projectionの安全策（publicEpisodeId欠落のblocking error）が実データに対しても正しく機能することを示す一方、Episode 2のpublicEpisodeId確定（`public-id-manifest-assignment-policy`、Backlog）が完了しない限り、このサンプルの全entryをprojectionできないことも明らかにした。** promotion再開（`evidence-index-promotion-first-reviewed-sample-retry`）を試みる前に、対象storyの全episodeで`publicEpisodeId`が確定していることを確認する必要がある。

### 13.4 進捗（`feature/evidence-index-public-id-public-safe-projection`、匿名化）

`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`を、§13.3と同じ匿名化実データサンプル（1story・187 entries）に対して`--policy public-default`（既定）でdry-run実行した。

- Episode 1（92 entries）は§13.3と同様`publicEpisodeId`が確定済みのため、全件をpublic-safe entryへ変換できた（`evidenceId`/`storyId`/`episodeId`がそれぞれ`publicEvidenceId`/`publicStoryId`/`publicEpisodeId`の値に置換され、`sceneId`/`blockId`/`referencedBy`/document-level`generatedFrom`は出力から除去された）
- Episode 2（95 entries）は`publicEpisodeId`未確定のため、§13.3のCompatible projectionと同様にblocking FAIL（exit code 1）になった。これは想定どおりの安全側挙動であり、public-safe modeでも`publicEpisodeId`欠落の自動補完・推測は行わない
- 出力ファイル名は入力ファイル名（sourceKey由来の内部storyId）ではなく`{publicStoryId}.yaml`になることを確認した
- projectされたEpisode 1の92 entryに対して`validate_evidence_index.py`・`check_evidence_index_promotion.py`をいずれも実行し、PASSを確認した
- source text exposure check（`.dec`/`@ChTalk`/`@Scenario`/`$num`/local path等の禁止文字列に加え、入力サンプルの内部storyId・sceneId・blockId文字列そのもの）をpublic-safe出力ファイルに対して手動grepで確認したところ、いずれも検出されなかった（scriptのinternal ID exposure scanも`0 occurrence(s)`を報告）
- 本実行の出力（projection結果・mapping CSV・report）はいずれも`workspace/evidence_index_dry_runs/public_safe_projection/`配下（`.gitignore`保護）にのみ存在し、`knowledge/evidence/stories/`・Gitへのcommitは一切行っていない

**この結果は、Public-safe projectionが実データに対しても内部ID非露出・schema互換・promotion check通過という3点を同時に満たせることを示す一方、renderer（Evidence page見出し・anchor・Summary evidenceRefsリンク）がまだ内部`evidenceId`中心のままであるため、たとえEpisode 1のみでもこの時点で実promotionへ進むことはしない。** 次のステップはrenderer切替（`evidence-index-public-id-renderer-switch`）と、Episode 2側の`publicEpisodeId`確定（`evidence-index-public-episode-id-assignment`）である。

### 13.5 進捗（`feature/evidence-index-public-episode-id-assignment`、匿名化）

§13.4で判明したEpisode 2の`publicEpisodeId`未確定問題について、`scripts/check_public_episode_ids.py`を同じ匿名化実データサンプルに対してdry-run実行した。

- `--input`に§13.1と同じ1 story・187 entriesのEvidence Index候補を指定した結果、Episode 1は`publicEpisodeId`割当済み（assigned）、Episode 2は欠落（missing）と正しく検出された
- `suggestions.yaml`には`missingEpisodeOrder: 2`・`suggestedPublicEpisodeId: {publicStoryId}_E02`形式の割当候補が1件出力され、`reviewRequired: true`が設定されていることを確認した
- exit codeは`1`（missing publicEpisodeId検出）、reportの`Missing publicEpisodeId count`は`1`だった
- `report.md`/`suggestions.yaml`に対して内部storyId・内部episodeId文字列を手動grepで確認したところ、いずれも検出されなかった（`publicStoryId`/`publicEpisodeId`候補と`episodeOrder`整数のみが出力されている）
- 出力（`report.md`/`suggestions.yaml`）は`workspace/public_episode_ids/`配下（本PRで`.gitignore`へ追加）にのみ存在し、`knowledge/evidence/stories/`・`knowledge/public_ids/`・Gitへのcommitは一切行っていない

続けて、`workspace/`側だけでEpisode 2に提案どおりの`publicEpisodeId`を仮補完した入力（`workspace/public_episode_ids/patched_for_projection/`、commit禁止）を作成し、`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`を再実行した。

- 仮補完後は`check_public_episode_ids.py`が`missing=0`・PASSを報告した
- Public-safe projectionは**187 entries全件**（Episode 1の92件 + Episode 2の95件）を正しくprojectし、`generated=187`・`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`でPASSした
- projectされた出力に対して`validate_evidence_index.py`・`check_evidence_index_promotion.py`をいずれも実行し、187 entries全件でPASSを確認した

**この結果は、`publicEpisodeId`未確定問題さえ解消すれば、Public-safe projectionが1 story全entriesに対して正しく通ることを実データで裏付けている。** ただし、この仮補完はあくまでworkspace限定のdry-run確認用であり、`story_manifest.yaml`・実Public ID Registry・実Evidence Indexのいずれにも反映していない。実際の`publicEpisodeId`確定は、人間が`suggestions.yaml`をレビューした上で`story_manifest.yaml`（または将来のPublic ID Registry）へ個別に反映する必要がある。次のステップはrenderer切替（`evidence-index-public-id-renderer-switch`）と、Public ID Registry統合（`evidence-index-public-id-registry-integration`）である。

### 13.6 進捗（`feature/evidence-index-public-id-registry-integration`、匿名化）

§13.5で提案された割当候補（`{publicStoryId}_E02`）を元に、workspace限定の仮Registry（`workspace/public_episode_ids/sample_registry.yaml`、`.gitignore`保護、commit禁止）を作成し、Episode 1・Episode 2両方の`publicEpisodeId`を登録した（実storyId/実sourceKeyは含まない）。

```yaml
registryVersion: 1
stories:
  - publicStoryId: EVT_260707_001
    category: event
    episodes:
      - publicEpisodeId: EVT_260707_001_E01
        episodeOrder: 1
      - publicEpisodeId: EVT_260707_001_E02
        episodeOrder: 2
```

この仮Registryを`--registry`に指定し、§13.1と同じ匿名化実データサンプル（1 story・187 entries）に対して`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`を再実行した。

- Episode 1（92 entries）は入力に既存`publicEpisodeId`があり、Registry値と一致（conflictなし）
- Episode 2（95 entries）は入力に`publicEpisodeId`が無かったため、Registryから`EVT_260707_001_E02`を補完した
- **187 entries全件がPublic-safe projectionを通過**（`generated=187`・`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）
- reportの`## Registry`sectionは、Registry stories count 1・Registry episodes count 2・Entries with publicEpisodeId from input 92・Entries with publicEpisodeId from registry 95・Missing publicEpisodeId after registry lookup 0・Registry conflicts 0を報告した
- projectされた出力に対して`validate_evidence_index.py`・`check_evidence_index_promotion.py`をいずれも実行し、187 entries全件でPASSを確認した
- 出力（projection結果・mapping CSV・report）・仮Registry自体はいずれも`workspace/`配下（`.gitignore`保護）にのみ存在し、`knowledge/evidence/stories/`・`knowledge/public_ids/`・Gitへのcommitは一切行っていない
- 出力・reportに対して内部storyId・内部episodeId文字列を手動grepで確認したところ、いずれも検出されなかった（mapping CSVのみ、既存方針通り内部IDを含む。commit禁止のまま）

**この結果は、PR #96で見送った「Registry統合」を実装することで、実データでもPublic ID Registryを介した`publicEpisodeId`補完が正しく機能し、Public-safe projectionが1 story全entriesに対して通ることを実証している。** ただしこのworkspace仮Registryは実Registryではなく、`story_manifest.yaml`・実Public ID Registry・実Evidence Indexのいずれにも反映していない。次のステップはrenderer切替（`evidence-index-public-id-renderer-switch`）と、実データ1 storyの初回昇格再試行（`evidence-index-promotion-first-reviewed-sample-retry`）である。

### 13.7 進捗（`feature/evidence-index-public-id-renderer-switch`、匿名化）

§13.6で生成したPublic-safe projection output（187 entries、Registry補完込み）を`scripts/render_wiki.py --evidence-index`に渡し、renderer switch後の表示を確認した。`--input`には既存の匿名化実データmerged knowledge collection（同じstoryの過去dry-run成果物）を使用した。

```powershell
uv run python scripts/render_wiki.py `
  --input <匿名化実データのmerged_knowledge_collection.json> `
  --output workspace/wiki_preview/public_id_renderer_switch `
  --evidence-index workspace/evidence_index_dry_runs/public_safe_projection_with_registry/default/stories `
  --character-profiles knowledge/dictionaries/character_profiles.yaml `
  --validate `
  --clean
```

- render成功、Evidence pageは`evidence/EVT_260707_001.md`（`publicStoryId`ベースのファイル名）として生成された
- Evidence page内の各entry見出しは`publicEvidenceId`（例: `### EVT_260707_001_E01_DLG0001`）になり、内部`evidenceId`は一切表示されないことを確認した
- Evidence page内のScene ID/Block IDは、Public-safe projection outputにこれらのfieldが無いため「未登録」表示になる（想定どおり）
- Evidence page・rendered Markdown全体に対して内部storyId・内部episodeId・内部evidenceId文字列を手動grepで確認したところ、いずれも検出されなかった
- **新たに判明した問題**: このmerged knowledge collectionはEvidence Index側の`publicStoryId`割当（本PRシリーズで新たに確定したもの）より前に生成されたものであり、`publicStoryId`フィールドを持たない。そのため、Story pageの「Review Links → Evidence index」導線は、内部`storyId`だけでは解決できずリンクが表示されなかった。これを受けて`resolve_story_evidence_entries`（内部`storyId`→`publicStoryId`の順でfallback）を実装し、`publicStoryId`が伝播しているstoryであれば正しく解決できることを合成テストで確認した（`tests/wiki/test_wiki_renderer.py::test_story_page_review_links_resolves_evidence_link_via_public_story_id`）。実データでの再現・恒久的な解消には、`story_manifest.yaml`側の`publicStoryId`確定と再normalize/mergeが必要であり、本PRのスコープ外（Non-goals）とした
- 出力（`workspace/wiki_preview/public_id_renderer_switch/`）はGit管理外（`.gitignore`保護）にのみ存在し、`knowledge/`・Gitへのcommitは一切行っていない

**この結果は、renderer switchがEvidence page単体としては完全に機能する（内部ID非露出）ことを実データで裏付ける一方、Story page側の導線はEvidence Indexとmerged knowledge collectionの双方が同じ`publicStoryId`を持つ必要があるという前提条件を明らかにした。** 次のステップは実データ1 storyの初回昇格再試行（`evidence-index-promotion-first-reviewed-sample-retry`）である。

### 13.8 進捗（`feature/evidence-index-promotion-first-reviewed-sample-retry`、匿名化。実データEvidence Indexの初回commit）

§13.1〜§13.7で整備したPublic-safe projection・Public ID Registry統合・renderer switchが出揃った状態で、実データ1 storyの初回昇格を再試行した。

1. **Public ID Registry実データcommit**: `knowledge/public_ids/story_public_ids.yaml`に、1 story分（匿名化表記`publicStoryId: EVT_260707_001`、`category: event`、episode 2件）のPublic ID Registry entryを正式commitした。内容は§13.6のworkspace限定サンプルRegistryと同一で、sourceKey由来の内部ID・実タイトル・raw pathは一切含まない（schema `additionalProperties: false`により構造的に保証）。
2. **Registry check**: `scripts/check_public_episode_ids.py --registry knowledge/public_ids/story_public_ids.yaml`を実行したところ、入力候補自体（Episode 2）はまだ`publicEpisodeId`を持たないためexit code 1（missing）のままだったが、suggestionが正式Registry entry（`EVT_260707_001_E02`）と完全一致することを確認した。**これは想定どおりの挙動である**: `check_public_episode_ids.py`はRegistryを「既存登録値の再利用によるsuggestion」にのみ使い、入力candidateへの書き込みは行わない設計（§7.6・`Public_ID_Registry_Design.md` §6.3）のため、実際の`publicEpisodeId`補完は次のprojectionステップで行われる。
3. **Public-safe projection（実Registry使用）**: `project_evidence_index_public_ids.py --projection-mode public-safe --registry knowledge/public_ids/story_public_ids.yaml`を実行し、Episode 1（92 entries、input由来）+ Episode 2（95 entries、実Registry補完）の**187 entries全件がPublic-safe projectionを通過**した（`generated=187`・`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）。
4. **validation/promotion check**: `validate_evidence_index.py`・`check_evidence_index_promotion.py`（`--story-summaries`あり/なし両方）はいずれもPASSした。
5. **render確認**: `render_wiki.py --evidence-index`でEvidence page（`evidence/EVT_260707_001.md`）をrenderし、`mkdocs build --strict`も成功した。Evidence page全体（187 entries）をgrepで内部ID・raw text禁止文字列scanし、いずれも検出されないことを確認した。
6. **human review**: `docs/templates/evidence_index_promotion_review_template.md`を元にreview note（`workspace/evidence_index_dry_runs/first_reviewed_sample_retry/review_note.md`、非commit）を作成し、上記結果を踏まえてDecisionを`Approved for promotion`とした。
7. **promote dry-run→execute**: `promote_evidence_index.py`のdry-runでplanned copy 1件（`knowledge/evidence/stories/EVT_260707_001.yaml`）を確認した後、`--execute`を実行し、**`knowledge/evidence/stories/EVT_260707_001.yaml`1件のみが正しくcopyされたことを確認した**（`git status --short`でも1件のみの追加を確認）。
8. **copy後の再確認**: `validate_evidence_index.py --input knowledge/evidence/stories`・`check_evidence_index_promotion.py --input knowledge/evidence/stories`をいずれもPASSで再確認し、`render_wiki.py --evidence-index knowledge/evidence/stories`のEvidence page・`mkdocs build --strict`のHTML出力に対しても内部ID・raw text露出が無いことを再度grepで確認した。

**新たに確認された既知の制約**: merged knowledge collection側にEpisode 2の`publicStoryId`/`publicEpisodeId`が伝播していないため（§13.7で判明した制約と同一原因）、Story page/Character page（いずれもworkspace限定のpreviewのみ、`knowledge/`にはcommitしない）に内部storyId/episodeId断片が現れることを再確認した。**ただし今回commitしたEvidence Index YAML自体・そのEvidence pageには内部ID非露出を確認済みであり、この制約は今回のpromotion対象に影響しない。** 根本解決には`story_manifest.yaml`側の`publicStoryId`確定・再normalize/mergeが必要であり、本PRのNon-goals。

**この結果は、`evidence-index-promotion-first-reviewed-sample`（PR #91）で発見されたsourceKey由来ID問題が、Public-safe projection + Public ID Registry統合 + renderer switchの組み合わせによって実データでも解消され、`knowledge/evidence/stories/`への実データ昇格が安全に行えることを実証している。** 対象は1 storyのみに限定し、複数story・batch promotionは行っていない。

### 13.9 進捗（`feature/evidence-index-promotion-first-sample-visual-review`、匿名化。昇格済み1 storyの最終目視確認）

§13.8で`knowledge/evidence/stories/EVT_260707_001.yaml`へ昇格した1 storyについて、Wiki表示として公開して問題ないかを最終確認した。**本PRでは実装変更を一切行っていない。**

1. **Registry確認**: `knowledge/public_ids/story_public_ids.yaml`が`registryVersion: 1`・1 story分（`publicStoryId`/`category`/`episodes[].publicEpisodeId`/`episodeOrder`のみ）で構成され、`publicEpisodeId`が`{publicStoryId}_E01`/`{publicStoryId}_E02`形式・`episodeOrder`が1/2であることを確認した。sourceKey由来ID・raw title・raw path・URL・local pathはいずれも含まれない。
2. **Evidence Index YAML確認**: `knowledge/evidence/stories/EVT_260707_001.yaml`をPythonスクリプトで機械的に検証し、187 entries全件で`evidenceId == publicEvidenceId`・`storyId == publicStoryId`・`episodeId == publicEpisodeId`が成立し、`sceneId`/`blockId`/`referencedBy`が0件、`visibility.public: true`・`visibility.rawTextIncluded: false`が全entryで成立することを確認した。entries by typeは`dialogue`153・`monologue`6・`narration`26・`unknown`2（`choice`/`stage_direction`は0件）。
3. **再validation**: `validate_evidence_index.py --input knowledge/evidence/stories`・`check_evidence_index_promotion.py --input knowledge/evidence/stories`（`--story-summaries`あり/なし両方）をいずれも再実行しPASSを確認した（Summary未登録のため`Checked documents: 0`）。
4. **render確認**: `render_wiki.py --evidence-index knowledge/evidence/stories`でEvidence page（`evidence/EVT_260707_001.md`）を再renderし、187件の見出しがすべて`publicEvidenceId`形式（例: `### EVT_260707_001_E01_DLG0001`）であること、`stage_direction`が0件であることを確認した。
5. **Story page導線確認**: Story pageの「Review Links」sectionに`[Evidence index](../evidence/EVT_260707_001.md)`が正しく生成され、`publicStoryId`ベースのEvidence pageへ実際に解決されることを実データで確認した（`resolve_story_evidence_entries`のfallbackが実際に機能していることの実証）。Summary未登録のため`evidenceRefs`リンクの実データ確認はできなかった（合成テストで確認済みのまま）。
6. **mkdocs build --strict**: local previewで成功（broken linkなし）。
7. **internal/source exposure check**: committed Registry・committed Evidence Index YAML・rendered Evidence page（Markdown/HTML）のいずれにも、sourceKey由来ID・`.dec`・`@ChTalk`系コマンド・`$num`・local absolute path・`<script`（DEC由来の意味ではなくMkDocs Materialのフレームワーク標準JSタグのみ検出、raw content露出ではないことを確認）が含まれないことをgrepで確認した。

**新たに再確認された既知の制約**: merged knowledge collection側にEpisode 2の`publicStoryId`/`publicEpisodeId`が伝播していないため、Story page（workspace限定previewのみ）のサイト全体ナビゲーションに内部storyId断片が現れることを再確認した（PR #98/#99で判明済みの制約と同一）。**ただしこれはEvidence Index YAML自体・Evidence page本体には影響しない**（§7参照）。根本解決には`story_manifest.yaml`側の`publicStoryId`確定・再normalize/mergeが必要であり、本PRのNon-goals。

**この結果は、PR #99で初めて昇格したPublic Evidence Indexが、Wiki表示として安全に公開できる状態にあることを実証している。** 対象は1 storyのみ、実装変更・新規Evidence Index追加・batch promotionはいずれも行っていない。次は`evidence-index-promotion-batch-policy`（複数story昇格の運用方針検討）または`internal-review-evidence-packet-design`。

---

# 14. 関連ドキュメント

- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（Evidence Index候補生成dry-run手順）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（promotion check手順）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria/public entry type policy）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・保存場所方針）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（§13.1で判明したsourceKey由来ID問題への設計方針、promotion再開の前提条件）
- `docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）
- `scripts/promote_evidence_index.py`（本手順のcopy script）
- `scripts/check_evidence_index_promotion.py`（promotion check script、本scriptが内部で再利用）
- `scripts/validate_evidence_index.py`（schema/整合性検証CLI）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（`publicEpisodeId`未確定問題の整理、Public ID Registry設計）
- `scripts/check_public_episode_ids.py`（publicEpisodeId未確定episodeの検出・割当候補提案script）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.16（Evidence page renderer統合・publicEvidenceId中心へのrenderer切替）
- `agents/wiki_generator/evidence_index.py`（`display_evidence_id`/`resolve_evidence_entry`/`resolve_story_evidence_entries`）
- `agents/wiki_generator/renderer.py`（`render_evidence_page`、`_evidence_anchor`、`_format_evidence_ref_display`）
- `TASKS.md`（次PR候補の追跡）
