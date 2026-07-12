# Evidence Index Batch Promotion Policy（Public Evidence Indexの複数story昇格運用方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`

---

# 1. Purpose（目的）

`knowledge/evidence/stories/`を1 storyから複数storyへ広げる際の運用方針（batch size上限・Registry entry review条件・promotion前後チェックリスト・visual review方針・failed story/rollback方針・PR分割方針）を定義する。**本文書は設計・運用ルールのみを扱い、batch promotion scriptの実装・実際のbatch promotion実行はいずれも対象外**（§13 Non-goals）。

---

# 2. Background（背景）

- PR #91（`evidence-index-promotion-first-reviewed-sample`）: sourceKey由来`storyId`がEvidence Index内に大量に残る問題により、初回promotionを見送った
- PR #92〜#98: 内部ID/公開ID分離方針（`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`）・`publicEvidenceId`・Public-safe projection（`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`）・Public ID Registry（`docs/architecture/06_AI/Public_ID_Registry_Design.md`、`knowledge/public_ids/story_public_ids.yaml`）・renderer switch（`publicEvidenceId`中心表示）を整備した
- PR #99（`evidence-index-promotion-first-reviewed-sample-retry`）: 上記が出揃った状態で、実データ1 story（2 episodes・187 entries）を`knowledge/evidence/stories/`へ初めて昇格した
- PR #100（`evidence-index-promotion-first-sample-visual-review`）: 昇格済み1 storyのWiki表示・Story page導線・内部ID非露出・raw text非露出を実装変更なしで最終確認した

この時点で「1 story分のpromotionフロー」は実データで実証済みだが、「複数storyへ広げる際の運用ルール」はまだ設計されていない。本文書はこのギャップを埋める。

---

# 3. Basic policy（基本方針）

- **batch promotionは一括大量投入ではなく、段階的に進める**（§4のPhase表に従う）
- **初回batchは小さくする**（dry-run 3 story以内、初回実batch 3 story以内、§4）
- Registry entryとEvidence Index YAMLの追加は、人間が1 PR単位でreview可能な粒度に保つ
- **失敗storyが混ざっても他storyを巻き込まない**設計にする（1 story 1 fileの既存方針を活かす、§7・§8）
- raw text / internal ID exposure checkは、batch中の**全story**に対して必須とする（1件でも省略しない）
- Public ID Registry entryは、batchに含める全storyについて人間reviewが完了していることを必須とする（§5）
- promotion対象は、Public-safe projection済み（`--projection-mode public-safe`の出力）のEvidence Indexのみとする（`Evidence_Index_Promotion_Policy.md` §5.1の既存条件を継続適用）
- **Visual reviewは、少なくとも初回batch（dry-run・実batchとも）では全story必須**とする（§8）
- batch size拡大（§4のPhase進行）は、その前段階のbatchで問題が出ていないことを確認してから行う。前段階で1件でもblocking failureが出た場合は、次のPhaseへ進まず同じ規模で再試行するか、規模を縮小する

---

# 4. Batch size policy（batch size方針）

| Phase | 内容 | story数上限 | 状態 |
|---|---|---|---|
| Phase 1: `evidence-index-promotion-first-reviewed-sample-retry` / `-first-sample-visual-review` | 初回1 storyのpromotion・Wiki表示最終確認 | 1 | 完了（PR #99・#100） |
| Phase 2: `evidence-index-promotion-first-batch-dry-run`（本PR） | 複数story分のRegistry候補・Public-safe projection・validation・render・visual reviewをworkspace限定でdry-run確認する（実commitなし） | 最大3（2 storyで実施） | **完了（本PR、tooling観点はPASS。ただし選定した2 storyは`unknown`比率が高くreal promotion対象としては非推奨、§4.2参照）** |
| Phase 3: 初回実batch promotion | Phase 2のdry-runで問題が無かったstoryのみ、実際に`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`へ追加する | 最大3 | 未着手（Phase 2で使用した2 storyはそのまま昇格しない。story候補の再選定が必要、§4.2） |
| Phase 4: 通常small batch | 運用が安定した後の通常運用 | 最大5 | 未着手（Phase 3完了・実績蓄積後） |
| Phase 5: 大規模batch | 5 storyを超える一括投入 | **明示的な承認があるまで許可しない** | 許可なし |

## 4.1 補足ルール

- 上記story数上限は「1 PRで新規に追加するstory数」を指す。既存の昇格済みstory（現在1件）は含めない
- **1 storyあたりのentry数が多い場合（目安: 数百件規模）は、同一PRに含めるstory数を上限より減らすことを検討する**（Evidence page可読性・レビュー負荷の観点、`Evidence_Index_Promotion_Policy.md` §8 Evidence page size policyと関連）
- **batch内で1件でもblocking failureが出た場合は、そのPRのstory数をさらに減らして再試行する**（failed storyだけ除外して残りを昇格する運用は、Phase 4以降の実績が十分に蓄積してから検討する。現時点ではNext候補としてのみ記録する、§7）
- Phase間の移行は、前Phaseの完了後にユーザーへ確認してから次PRとして着手する（他のEvidence Index関連作業と同様の運用）

## 4.2 Phase 2 dry-run実施結果（`feature/evidence-index-promotion-first-batch-dry-run`、匿名化）

2 story（匿名化workspace ID、event category 1件・raid category 1件、entry数948/1091・合計2039）を対象に、workspace限定でRegistry候補作成→`check_public_episode_ids.py`→Public-safe projection→`validate_evidence_index.py`→`check_evidence_index_promotion.py`（Summary込み）→extraction/merge（workspace限定）→`render_wiki.py --evidence-index`→`mkdocs build --strict`→visual review→internal/source ID exposure checkの全工程を実行した。

- **tooling観点はすべてPASS**: Registry補完（2039件全件）・projection（`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）・validation・promotion check・render・exposure checkのいずれも問題なく完走した
- **新たに判明した問題1（story選定の問題）**: 選定した2 storyは`compatibilityReport.parserCompatibility: warning`状態で、filter後のentry構成が`unknown`約90%（1834/2039件）と極端に偏っていた。`Evidence_Index_Promotion_Policy.md` §4.1の「`unknown`は件数が少ない場合のみ公開対象」という方針に照らすと、機械的checkはPASSしてもhuman reviewの観点では現状のままreal promotion対象にすべきではないと判断した
- **新たに判明した問題2（Story page導線の前提条件）**: 今回の2 storyはいずれも`story_manifest.yaml`によるpublicStoryId割当を経ていないため、Story pageの「Review Links → Evidence index」リンクが**生成されなかった**（PR #99の1 storyでは偶然publicStoryId伝播済みだったため機能していたが、真に新規のstoryではデフォルトで機能しないことが今回のdry-runで明らかになった）
- **Failed story count: 0、excluded story count: 0**（blocking failureは0件。上記2点はいずれも機械的failureではなく、real batch promotionへ進める前に対応すべき運用上の課題）
- **Final decision: batch dry-run PASS（tooling観点）、ただしこの2 storyでのfirst real batch promotionは推奨しない**

次のアクション候補: (1) `unknown`比率が低い別のstory候補を選び直す、または`config/script_commands.yaml`のコマンド辞書を拡充してから再度dry-runする、(2) real batch promotion対象storyについて`story_manifest.yaml` publicStoryId確定＋再normalize/mergeの手順を明確にする（`story-manifest-public-story-id-real-data-assignment`と関連）。**tooling自体（Registry/projection/validation/promotion check/render/exposure check）の追加修正は不要**と判断した。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.11を参照。

## 4.3 Candidate selection criteria（候補storyの選定基準、`feature/evidence-index-batch-candidate-selection-policy`で確定）

§4.2で判明した「機械的checkは全PASSでも品質の低いstoryが素通りする」問題に対応するため、promotion候補storyを機械的指標で分類する基準を定義する。

### 4.3.1 判定指標と閾値

対象は`build_evidence_index_candidates.py --public-profile default`でfilterした後のentry構成とする。

**(a) unknown比率** = unknown entries / total entries（filter後）

| 範囲 | 扱い |
|---|---|
| 10%以下 | 候補可 |
| 10%超〜30%以下 | 保留。unknown entryの内訳を人間が確認し、正当な理由をreview noteに記録した場合のみ個別許可 |
| 30%超 | blocking（候補から除外、parser改善待ちに分類） |

**(b) 意味のあるentry比率** = (dialogue + monologue + narration + choice) / total entries（filter後）

| 範囲 | 扱い |
|---|---|
| 70%以上 | 候補可 |
| 70%未満 | 保留または除外（(a)と併せて判定する。実質(a)の裏返しだが、将来evidenceTypeが増えた場合の独立した安全網として明記する） |

**(c) parserCompatibility**（Normalized Story JSONの`compatibilityReport.parserCompatibility`）

| 値 | 扱い |
|---|---|
| `compatible` | 候補可 |
| `warning` | (a)(b)の閾値を満たす場合のみ候補可（`warning`自体はblockerにしない。理由: `warning`は未知コマンドの存在しか意味せず、実害はunknown比率で測るべきという判断） |
| `needs_update` / `blocked` | 除外 |

**(d) 1 storyあたりentry数**（filter後）

| 範囲 | 扱い |
|---|---|
| 600件以下 | 候補可 |
| 600件超 | 保留（Evidence page可読性・レビュー負荷の観点。story数を減らす、または昇格を見送る判断材料とする。hard blockではない） |

§4.2の実績値を基準点として記録する: PR #99で昇格済みの1 story（187 entries、unknown約1%）は良好な状態の例。§4.2の2 story（合計2039 entries、unknown約90%）は`parser-improvement-wait`に該当する例（§4.3.3参照）。

### 4.3.2 分類ラベル

各候補storyを以下の3分類のいずれかに判定する。

- **`promotion-candidate`**: (a)〜(c)をすべて満たす（(d)は考慮事項であり分類そのものは左右しない）
- **`parser-improvement-wait`**: (a)または(b)を満たさないが、原因がparser未対応コマンド（unknown block化）であり、`config/script_commands.yaml`・`agents/parser/parser.py`の辞書拡充で改善が見込めるもの
- **`excluded`**: `needs_update`/`blocked`、またはその他の理由で当面対象外

### 4.3.3 判定手順（story単位）

1. `build_evidence_index_candidates.py --public-profile default`で候補生成
2. `report.json`/`report.md`の`entries by evidenceType`から(a)(b)(d)を算出
3. Normalized Story JSONの`compatibilityReport`から(c)を確認
4. 3分類のいずれかに判定し、判定結果をbatch dry-run report（workspace限定）に記録
5. `promotion-candidate`のstoryのみが以降のRegistry候補作成・projection工程へ進める

### 4.3.4 記録様式

batch dry-run report（workspace限定、非commit）に以下のmatrixを記録する。docsへ転記する場合は匿名化した統計値のみとする。

| Story（匿名） | total | unknown比率 | 意味あるentry比率 | parserCompat | entry数判定 | 分類 |
|---|---|---|---|---|---|---|

### 4.3.5 PR #102の2 storyの分類結果

§4.2で使用した2 story（匿名化workspace ID、event category 1件・raid category 1件）は、本基準に照らして**いずれも`parser-improvement-wait`に分類する**（unknown比率約90% > 30%閾値、`parserCompatibility: warning`）。real batch promotion対象からは除外し、`config/script_commands.yaml`のコマンド辞書拡充後に再評価する。

### 4.3.6 real batch promotionへ進むための最低条件

以下を**すべて**満たすこと:

- 対象storyすべてが§4.3.2の`promotion-candidate`判定であること
- 対象storyの`publicStoryId`/`publicEpisodeId`が`story_manifest.yaml`側で確定し、再normalize/merge済みのmerged collectionで**Story page → Evidence index導線が実際に機能することをdry-runで確認済み**であること（§4.2問題2、`story-manifest-public-story-id-real-data-assignment`のスコープ）
- Public ID Registry entryが人間review済みであること（§5）
- Public-safe projection・validation・promotion check・render・exposure check・全story visual reviewがPASSであること（§6〜§8）
- 最大3 story（§4）

### 4.3.7 ロードマップ

1. `script-command-dictionary-expansion-batch-001`: `config/script_commands.yaml`・`agents/parser/parser.py`両方への追加でunknown比率を下げる
2. `story-manifest-public-story-id-real-data-assignment`: 候補storyの`publicStoryId`確定→再normalize/merge→Story page導線の動作確認（辞書拡充後の再normalizeに相乗りさせ、再normalize回数を1回に抑える）
3. `evidence-index-promotion-second-batch-dry-run`: 改善後parser＋selection基準＋導線確認込みの再dry-run（最大3 story）
4. `evidence-index-promotion-first-real-batch`: 全条件PASS後の初回実batch promotion（最大3 story）

### 4.3.8 本PRでは実装しないこと

- selection基準の`check_evidence_index_promotion.py`等への実装（機械的な自動判定化）は、`evidence-index-promotion-batch-tooling`候補としてBacklogに残す（本PRでは行わない）
- `config/script_commands.yaml`・`agents/parser/parser.py`の変更（次PR`script-command-dictionary-expansion-batch-001`）
- `story_manifest.yaml`の実データ変更・再normalize/merge・second batch dry-run・real batch promotionの実行

---

# 5. Registry entry review条件

`knowledge/public_ids/story_public_ids.yaml`へ新しいstoryのentryを追加する場合、以下を**すべて**満たすことを必須とする。

- [ ] `publicStoryId`がsourceKey由来ではない（`Story_ID_Policy_Decision.md`・`Public_ID_Registry_Design.md` §5.3の既存方針どおり）
- [ ] `publicEpisodeId`が`{publicStoryId}_E{episodeOrder:02d}`形式である（`Public_ID_Registry_Design.md` §3.1）
- [ ] `episodeOrder`がstory内の表示順（1始まり）と一致している
- [ ] entry内にsourceKey・internal `storyId`・internal `episodeId`・raw title・raw subtitle・raw pathを一切含まない（schema `additionalProperties: false`による構造的保証に加え、人間目視でも確認する）
- [ ] Registry内でduplicate `publicStoryId`が無い
- [ ] Registry内でduplicate `publicEpisodeId`が無い（`scripts/check_public_episode_ids.py`の`_load_registry`が検出する既存チェックを利用する）
- [ ] 追加対象のentryについて人間レビューが完了している
- [ ] `scripts/check_public_episode_ids.py --registry`で整合確認済みである（suggestionが実際にRegistryへ反映しようとしている値と一致することを確認する）

## 5.1 Registry entry追加PRの方針

- Evidence Index本体と同じPRにRegistry entryを含めてもよい（PR #99の前例どおり）
- **ただし初回batch（Phase 2・Phase 3）では、Registry entryのみを先行する別PRに分割することも許可する**（対象storyのpublicStoryId/publicEpisodeId確定に不安がある場合、§9 PR分割方針の案A）
- 実データ由来のRegistry mapping・workspace suggestions（`workspace/public_episode_ids/`配下の実データ版）はいずれもcommitしない（既存の`Public_ID_Registry_Design.md` §9の方針を継続）

---

# 6. Promotion前チェックリスト（story単位、必須）

batchに含める**各story**について、以下を個別に実施する。1件でも未実施・未PASSのstoryはbatchから除外する（§7）。

- [ ] `scripts/check_public_episode_ids.py --registry`（Registry候補との整合確認）
- [ ] `scripts/project_evidence_index_public_ids.py --projection-mode public-safe --registry`（Public-safe projection生成）
- [ ] `scripts/validate_evidence_index.py`（schema/整合性検証）
- [ ] `scripts/check_evidence_index_promotion.py`（promotion check、`--policy public-default`）
- [ ] `scripts/check_evidence_index_promotion.py --story-summaries`（可能なら、Summary evidenceRefs整合性確認）
- [ ] `scripts/render_wiki.py --evidence-index`（Evidence page render確認）
- [ ] internal/source ID exposure check（projection output・rendered Markdown双方、`Evidence_Index_Promotion_Policy.md` §11の検索文字列を継続使用）
- [ ] human review note作成、Decisionが`Approved for promotion`
- [ ] `scripts/promote_evidence_index.py`のdry-run（`--execute`なし）でPASS
- [ ] commit対象ファイル（`knowledge/public_ids/story_public_ids.yaml`の追加分・`knowledge/evidence/stories/{publicStoryId}.yaml`）を`git status --short`で個別に確認

---

# 7. Promotion後チェックリスト（batch単位、必須）

実copy後、**batch全体**に対して以下を実施する。

- [ ] `scripts/validate_evidence_index.py --input knowledge/evidence/stories`（昇格済み全storyに対する再検証）
- [ ] `scripts/check_evidence_index_promotion.py --input knowledge/evidence/stories`（昇格済み全storyに対する再check）
- [ ] `scripts/render_wiki.py --evidence-index knowledge/evidence/stories`（全Evidence pageの再render）
- [ ] 新規追加した各storyのEvidence pageをspot check（§8参照）
- [ ] Story page → Evidence page導線の確認（新規追加分すべて）
- [ ] internal/source ID exposure check（`knowledge/`配下の追加ファイル・再render後のMarkdown/HTML）
- [ ] `mkdocs build --strict`
- [ ] `git status --short`で意図しない追加・変更が無いことを確認
- [ ] GitHub Actions CIがPASSすること

---

# 8. Visual review方針

## 8.1 要否（Phaseごと）

| Phase | Visual review範囲 |
|---|---|
| Phase 2: dry-run batch | **全story必須**（workspace限定previewでの確認） |
| Phase 3: 初回実batch promotion | **全story必須** |
| Phase 4: 通常small batch | 全storyのEvidence pageをspot check、entry数が多いstoryは重点review |
| Phase 5以降（大規模batch） | 許可されるまで方針自体が未確定（§4のとおりPhase 5は現時点で許可しない） |

**batch size拡大（次のPhaseへの移行）前は、直前のPhaseで昇格した分も含めて再度全件visual reviewを行う。**

## 8.2 確認項目（story単位）

- [ ] Evidence page見出しが`publicEvidenceId`形式である
- [ ] Evidence page pathが`publicStoryId`ベースである
- [ ] `stage_direction`が表示されない
- [ ] raw dialogue text / raw narration textが表示されない
- [ ] raw DEC commandが表示されない
- [ ] internal `evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`が表示されない
- [ ] speaker表示が安全（`resolutionStatus: resolved`のみ、不明人物placeholder等が混入していない）
- [ ] relatedEntities表示が安全（canonical dictionary由来のIDのみ）
- [ ] referencedBy表示が安全（存在する場合、raw情報を含まない）
- [ ] Story page → Evidence page導線が正しく解決される
- [ ] Summary evidenceRefsが安全（存在する場合、`publicEvidenceId`リンクとして解決される、または非表示のまま安全にfallbackする）

## 8.3 raw text / internal ID検出時の対応

**batch内のいずれか1 storyでもraw text / internal ID露出が見つかった場合、batch全体を止める**（該当storyのみ除外して残りを進める運用は現時点では採らない。Phase 4以降の実績蓄積後に再検討、§7）。

---

# 9. Failed story handling（failed storyの扱い）

## 9.1 基本方針

- **1 storyでもblocking failureがあれば、そのstoryはpromotion対象から除外する**
- **初回batch（Phase 2・Phase 3）では、failed storyが1件でも出たらbatch全体を止める**（他の正常storyも含めて今回のPRでは昇格しない）
- 通常batch（Phase 4以降）では、failed storyだけ除外して残りを昇格する運用を将来的に検討する（本文書時点ではNext候補としてのみ記録し、正式な運用ルールにはしない）
- 除外したstoryは、batch report（dry-run report・promotion reportいずれも該当）に理由付きで記録する

## 9.2 失敗理由の分類

| カテゴリ | 内容 |
|---|---|
| Registry missing | 対象storyのPublic ID Registry entryが未作成・未確定 |
| Registry conflict | 既存`publicEpisodeId`とRegistry値が矛盾する |
| publicEpisodeId missing | Registryにも該当が無く`publicEpisodeId`が確定できない |
| projection failure | `project_evidence_index_public_ids.py --projection-mode public-safe`がblocking errorで失敗する |
| validation failure | `validate_evidence_index.py`がFAILする |
| promotion check failure | `check_evidence_index_promotion.py`がFAILする（entry type policy違反・source text exposure等） |
| exposure failure | internal/source ID exposure checkで検出される |
| render failure | `render_wiki.py --evidence-index`が失敗する、またはEvidence page生成に問題がある |
| visual review failure | 人間によるvisual reviewで問題が見つかる（表示崩れ・safety懸念等） |

---

# 10. Rollback policy（rollback方針）

- Public Evidence Index YAMLは1 story 1 file（`knowledge/evidence/stories/{publicStoryId}.yaml`）であるため、**rollbackは該当fileの削除で行う**（他storyのfileには影響しない）
- 同じPRでRegistry entryも追加していた場合、**該当entryのみ`knowledge/public_ids/story_public_ids.yaml`から削除する**（他storyのentryには影響しない）
- **ただし、一度公開した`publicStoryId`/`publicEpisodeId`は、rollback後も原則再利用しない**（`Public_ID_Registry_Design.md` §2の安定性原則を継続適用。誤った内容で一度でも公開履歴がある値を、別のstory/episodeに後から割り当てると混乱の原因になるため）
- rollbackを行った場合、理由を`TASKS.md`または該当docsに記録する（sourceKey等の実データを記載しない、匿名化した理由のみ）
- **Git履歴から消す必要があるような情報（実sourceKey・raw text等）が万一混入した場合、通常のfile削除によるrollbackでは不十分**（Git履歴には残り続ける）。このケースを防ぐのはrollbackではなく**公開前のexposure check（§6・§7・§8）である**。exposure checkを通過しない限りcommitしない、という事前防止を最優先の方針とする

---

# 11. PR分割方針

複数storyへ広げる際のPR分割候補:

- **案A**: Registry entry追加PR → Evidence Index promotion PR（2 PRに分割）
- **案B**: Registry entryとEvidence Indexを同一PRに含める（PR #99の前例）
- **案C**: batch dry-run docs PR（workspace限定、実commitなし） → 実promotion PR（2段階）

## 11.1 採用方針

- **初回batch（Phase 2・Phase 3）は案Cを採用する**: まずbatch dry-run PR（`evidence-index-promotion-first-batch-dry-run`、§12）でworkspace限定の確認を行い、問題が無ければ次PRで初回実batch promotionを行う
- **通常small batch（Phase 4以降）では案B（Registry entryとEvidence Indexの同一PR）も許可する**（実績が蓄積し、フローが安定していることが前提）
- **Registryの確定に不安があるstory（`publicEpisodeId`未確定・episodeOrderの根拠が曖昧等）は、Phaseによらず案A（Registry entry先行PR）に分割する**

---

# 12. `evidence-index-promotion-first-batch-dry-run`のスコープ

**実施済み（§4.2参照）。** 以下は当初のスコープ定義であり、実施結果は§4.2・`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.11を参照。

## 12.1 やること

- 2〜3 storyを候補として選定する（匿名化して記録し、実storyId・実タイトルはdocsに書かない）
- workspace限定でPublic ID Registry候補（`workspace/public_episode_ids/`配下相当、commit禁止）を作成する
- 各storyに`scripts/check_public_episode_ids.py`を実行する
- 各storyに`project_evidence_index_public_ids.py --projection-mode public-safe`（workspace限定Registry使用）を実行する
- 各storyに`validate_evidence_index.py`・`check_evidence_index_promotion.py`を実行する
- 各storyに`render_wiki.py --evidence-index`でEvidence page/Story page導線を確認する
- 各storyに internal/source ID exposure checkを実施する
- **§8の基準で全story visual reviewを実施する**
- batch dry-run report（workspace限定、非commit）を作成する
- 結果を`docs/runbooks/Evidence_Index_Batch_Promotion_Copy.md`（本文書または新設ファイル）・`TASKS.md`に記録する（匿名化、entry数・PASS/FAIL件数などの統計情報のみ）

## 12.2 やらないこと

- 実promotion（`promote_evidence_index.py --execute`の実行）
- batch copy（複数storyの一括copy）
- Registry entryの実commit（`knowledge/public_ids/story_public_ids.yaml`への追加）
- 新規Evidence Indexの実commit（`knowledge/evidence/stories/`への追加）
- batch promotion scriptの実装

---

# 13. Non-goals（本文書のスコープ外）

`evidence-index-promotion-batch-policy`（PR #101）で以下は行っていない:

- 複数story分のEvidence Index/Registry entryのcommit
- batch promotionの実行
- batch promotion script（一括copy・一括validation等）の実装
- 自動昇格（GitHub Actions等での自動promotion）
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- Evidence Index/Public ID Registry/Summary schemaの変更
- Internal Review Evidence Packet生成

`evidence-index-promotion-first-batch-dry-run`（PR #102）でも以下は行っていない:

- 複数story分のEvidence Index/Registry entryのcommit（`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`は無変更のまま）
- `promote_evidence_index.py --execute`の実行、実batch promotion
- batch promotion scriptの実装
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- Evidence Index/Public ID Registry/Summary schemaの変更
- Internal Review Evidence Packet生成

`evidence-index-batch-candidate-selection-policy`（本PR、設計のみ）でも以下は行っていない:

- selection基準の`check_evidence_index_promotion.py`等への実装（§4.3.8、Backlog `evidence-index-promotion-batch-tooling`）
- `config/script_commands.yaml`・`agents/parser/parser.py`の変更（次PR`script-command-dictionary-expansion-batch-001`）
- `story_manifest.yaml`の実データ変更・再normalize/merge
- second batch dry-run・real batch promotionの実行
- 複数story分のEvidence Index/Registry entryのcommit

---

# 14. 関連ドキュメント

- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria、§5.1 Public-safe projection + renderer switch後の追加条件）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・実装フェーズ）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（内部trace ID/公開ID分離方針、`publicEvidenceId`方針）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（Public ID Registryの設計・`publicEpisodeId`採番方針・安定性原則）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（1 story単位のpromotion check手順）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（1 story単位のpromotion copy手順、§13.8・§13.9に実データ昇格・visual review実施結果を記録済み）
- `scripts/check_public_episode_ids.py`（publicEpisodeId未確定episodeの検出・割当候補提案）
- `scripts/project_evidence_index_public_ids.py`（Public-safe projection）
- `scripts/validate_evidence_index.py`（schema/整合性検証）
- `scripts/check_evidence_index_promotion.py`（promotion check）
- `scripts/promote_evidence_index.py`（promotion copy、dry-run既定・`--execute`必須）
- `TASKS.md`（次PR候補の追跡）
