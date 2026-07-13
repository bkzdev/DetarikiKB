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
| Phase 3: 初回実batch promotion | Phase 2のdry-runで問題が無かったstoryのみ、実際に`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`へ追加する | 最大3 | **完了（`evidence-index-promotion-first-real-batch`、2 story昇格。§4.6参照）** |
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

## 4.4 `script-command-dictionary-expansion-batch-001`の効果測定結果（匿名化）

§4.3.7ロードマップ手順1を実施した結果を記録する。**実装はコマンド辞書拡張のみ**（`config/script_commands.yaml`・`agents/parser/parser.py`の対応マップに1コマンド追加、tokenizer.pyの変更は不要だった。追加コマンドは`@`始まりのため既存の分類ロジックでcommand tokenとして扱われ、`KEYWORD_TOKENS`への追加は不要）。

**重要な判明事項**: §4.2で参照したローカルNormalized Story JSON（2 story）は、本PR着手時点で調査したところ、`config/script_commands.yaml`・`agents/parser/parser.py`のstage_direction辞書が過去のPR（演出コマンド37種・7種追加、`unknown`比率90%が観測された時点より前にmerge済み）を反映する前に生成されたstaleなローカル生成物であり、再normalize未実施のまま残っていたことが判明した。そのため、§4.2で観測された「unknown比率約90%」は、その時点で既にmainへmerge済みだった辞書拡張が反映されていない状態の数値だった。

本PRでは、まず現行mainブランチのparser（本PR着手前、辞書拡張済み）で該当2 storyを再normalizeし直したところ、`unknown`比率は既に約1%まで下がっていた（stale local生成物とmain時点の実際の状態には大きな乖離があった）。その上で残っていた`unknown`コマンド1種を本PRで追加登録し、`unknown`比率を0%まで下げた。

### 4.4.1 before/after matrix（`build_evidence_index_candidates.py --public-profile default`のfilter後、匿名化workspace ID）

| Story（匿名） | 区分 | total | unknown数 | unknown比率 | 意味あるentry比率 | parserCompat | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|---|
| Story A（event category） | before（本PR着手前のmain、stale local生成物ではなく再normalize後の実測） | 99 | 1 | 約1.0% | 約99.0% | warning | 候補可（600以下） | promotion-candidate |
| Story A（event category） | after（本PR、追加登録コマンド1件反映後） | 98 | 0 | 0% | 100% | warning | 候補可（600以下） | promotion-candidate |
| Story B（raid category） | before（本PR着手前のmain、stale local生成物ではなく再normalize後の実測） | 108 | 1 | 約0.9% | 約99.1% | warning | 候補可（600以下） | promotion-candidate |
| Story B（raid category） | after（本PR、追加登録コマンド1件反映後） | 107 | 0 | 0% | 100% | warning | 候補可（600以下） | promotion-candidate |

（表内の`before`はいずれも「本PRの変更を含まないmain時点のparser」で再normalizeし直した実測値であり、§4.2記載の約90%はstale local生成物由来の数値のため参考値として区別する）

### 4.4.2 追加コマンドの内訳

- 追加数: **1コマンド**（`config/script_commands.yaml`のstage_direction・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`双方に追加、direction_type: character_display）
- 分類根拠: `@`始まりでキャラクター表示スロットへプレースホルダーモデルを割り当てる演出コマンドと判断し、既存の`@ScenarioCos`系・`costume`/`@ChColor2`系と同様にstage_direction（character_display）へ分類した。dialogue系への分類が妥当と判断できる根拠は無かった
- 残したunknown: なし（対象2 storyのfilter後`unknown`は本PR適用後に0件）。他のローカル生成物（character/main/other category、計4 story分）についても同じ手順で再normalizeし直し、本PR着手前の時点で`unknown`が0件であることを確認済み（stale local生成物のみに大量の`unknown`が記録されていた）

### 4.4.3 目標達成状況

対象2 storyとも、§4.3.1のunknown比率10%以下の基準を**達成した**（0%）。意味あるentry比率も70%以上を満たし、entry数も600件以下のため、両storyとも`promotion-candidate`に再分類される（§4.3.5でPR #102時点は`parser-improvement-wait`としていたが、辞書拡張とstale生成物の解消により本PR時点では`promotion-candidate`へ更新する）。

### 4.4.4 本PRでは実装しないこと

- `story_manifest.yaml`の実データ変更・再normalize/merge本体の実行（`story-manifest-public-story-id-real-data-assignment`のスコープ）
- second batch dry-run・real batch promotionの実行
- selection基準の自動check実装（`evidence-index-promotion-batch-tooling`）
- 再normalize出力・効果測定結果ファイル自体のcommit（本節の匿名化統計のみを記録した）

## 4.5 `story-manifest-public-story-id-real-data-assignment`実施結果（ロードマップ手順2+3統合実施、匿名化）

§4.3.7ロードマップ手順2（`publicStoryId`/`publicEpisodeId`確定→再normalize/merge→Story page導線の動作確認）と手順3（second batch dry-run）を1 PRで統合実施した結果を記録する。

### 4.5.1 実施内容

対象は§4.4と同じ2 story（匿名化Story A=event category・Story B=raid category）。人間確定済みの`{publicStoryId}`（Story A/Story B それぞれ1件ずつ、`{publicEpisodeId}`はepisodeOrder 1固定）を、ローカルworkspace限定のstory_manifest.yaml相当ファイル（commit対象外）へ設定し、`scripts/normalize_story.py --manifest ... --raw-root ... --manifest-strict`で両storyを再normalizeした。両storyとも`raw_path`一致で`manifestMatched`、`parserCompatibility: warning`・`unknownCommands: 0`のまま変化なし（`script-command-dictionary-expansion-batch-001`の辞書拡張はmain反映済みのため再確認のみ）。

再normalize後のNormalized Story JSONの`metadata.publicStoryId`/`episodes[].metadata.publicEpisodeId`から、workspace限定のextraction→merge（`scripts/extract_story.py`・`scripts/merge_extractions.py`）を経て、merged knowledge collectionの`sourceDocuments[].publicStoryId`/`publicEpisodeId`まで正しく伝播することを確認した。

### 4.5.2 Story page → Evidence index導線の解消実証（本PRの核心）

§4.2で判明していた「`story_manifest.yaml`のpublicStoryId未割当だとStory pageの「Review Links → Evidence index」リンクが生成されない」問題を、実データで解消実証した。手順3のPublic-safe projection（`{publicStoryId}`ベース）済みEvidence Indexと、手順2で`publicStoryId`が伝播したmerged knowledge collectionを組み合わせて`render_wiki.py --evidence-index`でrenderしたところ、**両storyのStory pageに`Review Links → Evidence index`リンクが生成され、`{publicStoryId}`ベースのEvidence pageへ正しく解決されることを確認した**。

解決経路も特定した: Public-safe projection後、Evidence Index entry側の`storyId`フィールドは`{publicStoryId}`の値へ書き換えられるため、merged collection側の内部`storyId`をキーにした一次索引（`by_story_id`）は一致しない。`evidence-index-public-id-renderer-switch`（PR #98）で追加した`resolve_story_evidence_entries`のfallback（`by_public_story_id`、merged collection側`sourceDocuments[].publicStoryId`をキーに使う）が実際に機能することで解決している。このfallback経路は、PR #98時点では合成テストでのみ確認されており、本PRが実データでの初回確認となる。`mkdocs build --strict`も成功した。

### 4.5.3 second batch dry-run 判定matrix（§4.3.4様式）

| Story（匿名） | total | unknown比率 | 意味あるentry比率 | parserCompat | entry数判定 | 分類 |
|---|---|---|---|---|---|---|
| Story A（event category） | 98 | 0% | 100% | warning | 候補可（600以下） | promotion-candidate |
| Story B（raid category） | 107 | 0% | 100% | warning | 候補可（600以下） | promotion-candidate |

§4.4の「after」値と一致する（本PRではparserへの変更を行っていないため一致は想定どおり）。Registry候補作成（`check_public_episode_ids.py --registry`: assigned=2/missing=0）・Public-safe projection（205 entries、`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（Summary込み）はいずれもPASS。**Failed story count: 0、excluded story count: 0。**

### 4.5.4 Visual review / exposure check結果

§8の確認項目を両story分実施し、すべてクリアした（Evidence page見出しが`publicEvidenceId`形式・pathが`{publicStoryId}`ベース・`stage_direction`非表示・raw text/raw command非表示・internal ID非表示・speaker/relatedEntities/referencedBy表示が安全・Story page導線が正しく解決）。Evidence page本体・Public-safe projection出力に対するgrep+目視のinternal ID/raw text露出checkもクリア（0件）。

Character page/Story page/Episode pageに内部`storyId`/`episodeId`/`evidenceId`断片が表示される既知の制約（PR #98/#100で確認済み、workspace限定previewのみ、Evidence Index promotion対象外の別rendererの既存挙動）を再確認したが、これはEvidence page/Evidence Index本体には影響しない。

### 4.5.5 判定: real batch promotionへ進めるか

§4.3.6の最低条件のうち、本PRのスコープ内で確認可能な項目はすべて満たした:

- 対象storyすべてが`promotion-candidate`判定（§4.5.3）
- `publicStoryId`/`publicEpisodeId`確定済みmanifestでの再normalize/merge済みmerged collectionで、Story page → Evidence index導線が実際に機能することをdry-runで確認済み（§4.5.2、本PRで新たに実証）
- Public-safe projection・validation・promotion check・render・exposure check・全story visual reviewがPASS（§4.5.3・§4.5.4）

残る条件（Public ID Registry entryの人間review・`promote_evidence_index.py --execute`の実行）は、`evidence-index-promotion-first-real-batch`のスコープとして意図的に本PRでは実施していない（§4.5.6）。

**結論: tooling・導線とも実データで問題が無いことを実証した。`evidence-index-promotion-first-real-batch`へ進める状態と判定する。**

### 4.5.6 本PRでは実装しないこと

- Public ID Registry実データentry（`knowledge/public_ids/story_public_ids.yaml`）・実Evidence Index（`knowledge/evidence/stories/`）のcommit
- `promote_evidence_index.py`のdry-run・`--execute`いずれの実行も行っていない
- `agents/`・`scripts/`配下の実装変更（伝播チェーンに問題は見つからなかったため変更不要と判断した）
- ローカルmanifest・Registry候補・projection output・merged collection・batch dry-run report自体のcommit（すべてworkspace限定）

## 4.6 `evidence-index-promotion-first-real-batch`実施結果（Phase 3、初回実batch promotion）

§4.5で`promotion-candidate`判定・Story page導線動作確認済みだった2 story（`{publicStoryId}`表記、event category 1件・raid category 1件）について、**Public ID Registry実データentryの追加と`knowledge/evidence/stories/`への実Evidence Index昇格を実施した**。ユーザーが2 story一括・実データcommitを事前に明示承認した上での実施である。

### 4.6.1 Registry entry追加とreview条件確認

`knowledge/public_ids/story_public_ids.yaml`に2 story分のentry（`publicStoryId`/`category`/`episodes[].publicEpisodeId`/`episodeOrder`のみ）を追加した。既存1 story分のentryは無変更のまま維持した。§5の8項目レビュー条件をすべて確認した:

- sourceKey非由来のpublicStoryId: 確認済み（両storyともsourceKeyとは無関係な採番形式）
- `{publicStoryId}_E{episodeOrder:02d}`形式のpublicEpisodeId: 確認済み
- episodeOrderがstory内表示順(1始まり)と一致: 確認済み（両storyともepisode 1件のみ、episodeOrder=1）
- entry内にsourceKey・internal ID・raw title・raw path非含有: schema `additionalProperties: false`による構造的保証＋目視確認済み
- Registry内duplicate publicStoryId無し: 確認済み
- Registry内duplicate publicEpisodeId無し: 確認済み
- 追加対象entryの人間レビュー完了: 完了（ユーザー事前承認済み）
- `check_public_episode_ids.py --registry`との整合確認: `assigned=2 missing=0`でPASS

### 4.6.2 Promotion前チェックリスト（§6）実施結果

正式Registry（`knowledge/public_ids/story_public_ids.yaml`）を用いて、§4.5のsecond batch dry-runで生成済みだったworkspace限定候補（`workspace/evidence_index_dry_runs/second_batch_dry_run/candidates/stories/`、非commit）に対し、以下を再実行した。

| チェック項目 | 結果 |
|---|---|
| `check_public_episode_ids.py --registry`（正式Registry） | PASS（assigned=2, missing=0） |
| `project_evidence_index_public_ids.py --projection-mode public-safe --registry`（正式Registry） | PASS（2 story・205 entries、`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`、Registry補完0件・conflict 0件、Episode publicEpisodeIdは入力側に既に確定済みだったため） |
| `validate_evidence_index.py` | PASS（2 files・205 entries） |
| `check_evidence_index_promotion.py`（`--policy public-default`） | PASS |
| `check_evidence_index_promotion.py --story-summaries`（Summary込み） | PASS（`knowledge/summaries/stories/`は実データ未登録のためChecked documents: 0） |
| `render_wiki.py --evidence-index`（merged collectionはsecond batch dry-run workspace生成物を再利用） | 成功。Evidence page 2件・Story page 2件を含む18ファイル生成 |
| Story page → Evidence index導線 | 両storyで`[Evidence index](../evidence/{publicStoryId}.md)`が正しく解決されることを確認 |
| internal/source ID exposure check（projection output・rendered Markdown） | クリア（内部storyId/episodeId・raw source filename・`.dec`/`@ChTalk`/`@Scenario`/`$num`等いずれも0件） |
| `mkdocs build --strict` | 成功（0 warnings/errors） |
| human review note | 作成済み（workspace限定、非commit）。Decision: `Approved for promotion`、Notesにユーザー事前承認済みである旨を記載 |
| `promote_evidence_index.py`（dry-run） | PASS。planned copy 2件（`{publicStoryId}.yaml`ベースのファイル名であることを確認） |

### 4.6.3 Promote execute

`promote_evidence_index.py --execute`を実行し、`knowledge/evidence/stories/`へ2ファイルのみがcopyされたことを確認した。`git status --short`でも、`knowledge/public_ids/story_public_ids.yaml`の変更1件（既存entry維持＋2 story分追加）と`knowledge/evidence/stories/`への新規2ファイルのみであることを確認した（既存の昇格済み1 storyのファイルには一切触れていない）。

### 4.6.4 Promotion後チェックリスト（§7、batch単位）実施結果

copy後、既存の昇格済み1 storyを含む**全3ファイル**に対して再検証した。

| チェック項目 | 結果 |
|---|---|
| `validate_evidence_index.py --input knowledge/evidence/stories` | PASS（3 files・392 entries） |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories` | PASS |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories --story-summaries` | PASS |
| `render_wiki.py --evidence-index knowledge/evidence/stories` | 成功。既存1件を含む3件のEvidence pageすべてを再生成 |
| 新規追加分Evidence pageのspot check | 両storyともEvidence page見出しが`publicEvidenceId`形式、`stage_direction`0件、raw text/raw command/internal ID非表示を確認 |
| Story page → Evidence page導線（新規追加分） | 両storyで正しく解決されることを確認 |
| internal/source ID exposure check | committed YAML 3ファイル・再render後のMarkdown/HTML（記事本体）いずれもクリア |
| `mkdocs build --strict` | 成功 |
| `git status --short` | 意図しない追加・変更無し |

**既知の制約の再確認**: mkdocs build後のHTML全体（グローバルナビゲーション部分）には、merged knowledge collection側に`publicStoryId`が未伝播な既存story分の内部episodeId断片が表示される（PR #98/#100/#105で判明済みの制約、Story/Episode page navigationの既存挙動であり、Evidence Index/Evidence page本体のコンテンツには影響しない。Evidence page記事本体・committed Evidence Index YAMLはいずれもクリーンであることを確認済み）。

### 4.6.5 結論

- Failed story count: 0
- 2 story（`{publicStoryId}`表記2件）とも`knowledge/evidence/stories/`への実データ昇格を完了した
- 既存の昇格済み1 storyには一切影響なし（rollback不要）
- **`docs/architecture/06_AI/Evidence_Index_Batch_Promotion_Policy.md` Phase 3を完了とする**（§4参照）

### 4.6.6 本PRでは実装しないこと

- 3 story目以降の追加
- 既存の昇格済みstory・Registry entryの変更
- batch promotion scriptの実装（本PRも既存scriptの手動連続実行のみ）
- `agents/`・`scripts/`配下の実装変更
- story_manifest実データ・review note・projection output・mapping・report類のcommit（すべてworkspace限定）

## 4.7 `script-command-dictionary-expansion-batch-002`の効果測定結果（本編系全量、匿名化）

§4.4（`script-command-dictionary-expansion-batch-001`、2 story限定）の大規模版。本編系raw script全量（`-episode\d+\.dec$`等4パターンでfilterした2,301件）に対するcompatibility checkで検出された、unique172種の未知コマンドを`config/script_commands.yaml`・`agents/parser/parser.py`へ一括登録した結果を記録する（個別story単位ではなく、corpus全体の集計値のみを記録するため、本節はstory名の匿名化対象自体を含まない）。

### 4.7.1 before/after matrix（本編系2,301件、同一filter条件で再実行）

| 指標 | before | after |
|---|---|---|
| 総合 parserCompatibility | needs_update | warning |
| unknown コマンド ユニーク数 | 172 | 0 |
| unknown コマンド 延べ出現数 | 18,469 | 0 |
| newSpeechCommandCount | 363 | 0 |
| compatible ファイル数 | 122 | 285 |
| warning ファイル数 | 1,887 | 2,016 |
| needs_update ファイル数 | 292 | 0 |
| blocked ファイル数 | 0 | 0 |

### 4.7.2 追加コマンドの内訳

- 追加数: **172種**（variable_assignment 7種・typo表記ゆれ1種・stage_direction新規84種・表記ゆれ80種）
- 分類根拠: コマンド名の意味から`character_display`/`camera`/`motion`/`ui`/`background`/`screen`/`system`へ機械的に分類した。判断に迷うもの（会話コマンドの表記ゆれに見えるが、speechブランチ判定ロジックの拡張はPRスコープ外のもの5種）は安全側で`stage_direction`（character_display）へ分類した
- 172種すべてが、standalone checker・実parser経由のどちらでも`unknownCommands`に現れなくなることを機械的に確認済み

### 4.7.3 目標達成状況

対象2,301件で`needs_update`だったファイルが292件から**0件**になり、`unknownCommandCount`（延べ）も18,469件から**0件**になった。総合`parserCompatibility`は`needs_update`から`warning`へ改善した（残る`warning`は主に未登録キャラクターID・制御文字除去に起因し、本PRのスコープ外）。

### 4.7.4 本PRでは実装しないこと

- 演出系（H_scene等）2,006件のスコープ判断・対応
- 5桁キャラID帯の辞書登録
- 未登録キャラクターID（`unknownCharacterIdCount`）の解消
- 対象storyのEvidence Index候補選定・batch promotionの実行（本節は辞書拡張の効果測定のみ）
- 再実行結果ファイル自体のcommit（本節の集計値のみを記録した）

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
