# Evidence Index Batch Promotion Policy（Public Evidence Indexの複数story昇格運用方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`

---

# 1. Purpose（目的）

`knowledge/evidence/stories/`を1 storyから複数storyへ広げる際の運用方針（batch size上限・Registry entry review条件・promotion前後チェックリスト・visual review方針・failed story/rollback方針・PR分割方針）、および公開済みEvidence Indexの更新（re-promotion）方針（§11）を定義する。**本文書は設計・運用ルールのみを扱い、batch promotion scriptの実装・実際のbatch promotion実行/re-promotion実行はいずれも対象外**（§14 Non-goals）。

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
- **promotion対象外カテゴリが存在する**（`docs/architecture/01_Project/03_Scope.md`のコンテンツスコープ方針を正とする。§17参照）。当該カテゴリのstoryは、機械的checkが全PASSであってもbatch候補に含めない

---

# 4. Batch size policy（batch size方針）

| Phase | 内容 | story数上限 | 状態 |
|---|---|---|---|
| Phase 1: `evidence-index-promotion-first-reviewed-sample-retry` / `-first-sample-visual-review` | 初回1 storyのpromotion・Wiki表示最終確認 | 1 | 完了（PR #99・#100） |
| Phase 2: `evidence-index-promotion-first-batch-dry-run`（本PR） | 複数story分のRegistry候補・Public-safe projection・validation・render・visual reviewをworkspace限定でdry-run確認する（実commitなし） | 最大3（2 storyで実施） | **完了（本PR、tooling観点はPASS。ただし選定した2 storyは`unknown`比率が高くreal promotion対象としては非推奨、§4.2参照）** |
| Phase 3: 初回実batch promotion | Phase 2のdry-runで問題が無かったstoryのみ、実際に`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`へ追加する | 最大3 | **完了（`evidence-index-promotion-first-real-batch`、2 story昇格。§4.6参照）** |
| Phase 4: 通常small batch | 運用が安定した後の通常運用 | 最大5 | **2巡完了（初回`evidence-index-stage2-batch-promotion`5 story・§4.10、2巡目`evidence-index-stage3-promotion-execution`5 story・§4.12）** |
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

- ~~演出系（H_scene等）2,006件のスコープ判断・対応~~ → `feature/h-scene-content-scope-policy`（§17）で解決済み。H_scene系は内部KB対象・公開対象外（恒久除外）と決定
- 5桁キャラID帯の辞書登録
- 未登録キャラクターID（`unknownCharacterIdCount`）の解消
- 対象storyのEvidence Index候補選定・batch promotionの実行（本節は辞書拡張の効果測定のみ）
- 再実行結果ファイル自体のcommit（本節の集計値のみを記録した）

## 4.8 Stage 2 first candidate selection（`evidence-index-stage2-candidate-selection`実施結果、匿名化）

Phase 4（通常small batch、最大5 story）に向けた次batch候補選定の初回実施結果を記録する。§4.3の選定基準を、`data/raw/` event categoryの全量（export dir単位で167 story）へ機械的に適用した。

### 4.8.1 スクリーニング結果

- 対象: event category（export dir単位で167 story）。既存昇格3 storyのうち、event categoryに該当するのは1 storyのみ（他2 storyはevent category以外のディレクトリに配置されているため、この母集団には元々含まれない）で、これを除外した
- 母集団からの一次フィルタ（全episodeが`compatible`/`warning`であること、`needs_update`/`blocked`が1件でもあれば除外）を適用した結果、**候補プール166 story**（`needs_update`/`blocked`のepisodeを含むstoryは0件）
- 候補プールから、episode数2〜5・行数昇順（entry数600以下見込みを優先する代理指標）で上位5 storyを選定した

### 4.8.2 選定5 storyのdry-run判定matrix（§4.3.4様式、匿名化）

`--story-id`/`--episode-id`に仮のtentative ID（storyIdパターン`^[A-Z][A-Z0-9_-]+$`に適合するsourceKey由来の値）を指定してmanifest無しでnormalize（`--check-compat`込み）→extraction→merge→`build_evidence_index_candidates.py --public-profile default`を実行し、story別にfilter後entry構成を集計した。

| Story（匿名） | episodes | total（filter後） | unknown比率 | 意味あるentry比率 | parserCompat（worst） | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|
| Story A | 2 | 110 | 9.09% | 90.91% | warning | 候補可（600以下） | promotion-candidate |
| Story B | 3 | 159 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story C | 4 | 156 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story D | 3 | 183 | 0% | 100% | warning | 候補可（600以下） | promotion-candidate |
| Story E | 4 | 155 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |

5 story合計763 entry（unknown合計10件、いずれもStory A由来）。unknown比率が0%を超えたのはStory Aのみで、9.09%は§4.3.1(a)の10%以下閾値を満たすため個別review note escalationは不要と判定した。

### 4.8.3 結論

**選定5 storyすべてが`promotion-candidate`に分類された。** Failed story count: 0、excluded story count: 0（母集団166 storyの時点で`needs_update`/`blocked`は0件のため、`parser-improvement-wait`/`excluded`に該当するstoryは今回の選定結果には現れていない）。

### 4.8.4 本PRでは実装しないこと

- Public ID Registry候補作成・`publicStoryId`/`publicEpisodeId`値の確定・提案（`workspace/public_episode_ids/`配下も含め、ユーザー確定待ち）
- `story_manifest.yaml`の実データ変更・manifest併用での再normalize
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check（いずれも確定済み`publicStoryId`が前提のため、本PRのスコープ外）
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行
- dry-run生成物（normalize/extraction/merge/candidates出力）自体のcommit（すべてworkspace限定）

## 4.9 Stage 2 candidate reselection（sourceKey日付接頭辞限定、`evidence-index-stage2-candidate-reselection`実施結果、匿名化）

`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16で確定したpublicStoryId命名規約v2（`{CATEGORY}_{seq:03d}_{YYMMDD}`）は、`YYMMDD`部分をsourceKeyの日付接頭辞から採る設計である。§4.8で選定した5 storyのうち大半は、sourceKeyが日付接頭辞を持たない旧来の2桁連番形式（例: 2桁の通し番号+イベント名）だったため、命名規約v2の適用対象にできないことが判明した。ユーザー決定（2026-07-14）により、選定対象を**sourceKeyが`YYMMDD`日付接頭辞（`^\d{6}_`）を持つeventカテゴリstoryに限定**して選定をやり直す。

**§4.8で選定した5 storyは、本節の5 storyへ差し替える。旧5 storyは`excluded`判定ではなく、選定条件変更による差し替えとして記録する**（機械的checkの結果自体は§4.8.2のとおりいずれも`promotion-candidate`であり、除外理由があったわけではない）。

### 4.9.1 スクリーニング結果

- 対象母集団: event category全量（export dir単位で167 story、§4.8.1と同じ）
- sourceKeyが`^\d{6}_`にマッチする（日付接頭辞を持つ）export dir: 129
- 既に昇格済みのEVENT story（2件）のうち、この母集団に該当するのは1件のみ（他1件は`data/raw/event/`配下のexport dir命名パターンに一致しない別配置のため、元々この母集団に含まれない）で、これを除外し、**候補プール128 story**とした
- 候補プール128 storyは全件、全episodeが`compatible`/`warning`のみ（`needs_update`/`blocked`は0件）
- episode数2〜5でfilterした結果、**127 story**が対象（1 storyがepisode1件のみのため除外）
- 候補プールから、§4.8と同じ優先順位（episode数2〜5・行数昇順・古いsourceKey順のtie-break）で上位5 storyを選定した

### 4.9.2 選定5 storyのdry-run判定matrix（§4.3.4様式、匿名化）

§4.8.2と同じ手順（`--story-id`/`--episode-id`にtentative IDを指定してmanifest無しでnormalize（`--check-compat`込み）→extraction→merge→`build_evidence_index_candidates.py --public-profile default`）で、18 episode全件を再実行した。

| Story（匿名） | episodes | total（filter後） | unknown比率 | 意味あるentry比率 | parserCompat（worst） | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|
| Story A | 2 | 110 | 9.09% | 90.91% | warning | 候補可（600以下） | promotion-candidate |
| Story B | 4 | 185 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story C | 4 | 240 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story D | 4 | 198 | 1.01% | 98.99% | warning | 候補可（600以下） | promotion-candidate |
| Story E | 4 | 204 | 0.98% | 99.02% | warning | 候補可（600以下） | promotion-candidate |

5 story合計937 entry（unknown合計14件、Story Aが10件・Story D/Eが2件ずつ）。unknown比率が0%を超えたのはStory A/D/Eの3件で、いずれも§4.3.1(a)の10%以下閾値を満たすため個別review note escalationは不要と判定した。18 episode全件が`compatible`/`warning`のいずれかで、`needs_update`/`blocked`は無し。未登録キャラクターIDも0件だった。

Story Aは§4.8.2のStory Aと同一story（sourceKeyが元々日付接頭辞形式のため、新旧どちらの母集団にも該当する）。他4 storyはいずれも新規（§4.8.2の他4 storyは旧来の2桁連番sourceKeyのため、本節の母集団には含まれない）。

### 4.9.3 結論

**選定5 storyすべてが`promotion-candidate`に分類された。** Failed story count: 0、excluded story count: 0（候補プール128 storyの時点で`needs_update`/`blocked`は0件のため、`parser-improvement-wait`/`excluded`に該当するstoryは今回の選定結果には現れていない）。

publicStoryId命名規約v2に基づく提案値（`EVENT_003_{YYMMDD}`〜`EVENT_007_{YYMMDD}`、sourceKey日付の古い順にseqを付与）は、Registry未登録のため本docsには記載しない。ユーザー確認用ファイル（`workspace/evidence_index_dry_runs/stage2_batch001_v2/candidate_summary_for_user.md`、非commit）に実sourceKey・提案publicStoryId値を記載した。

### 4.9.4 本PRでは実装しないこと

- Public ID Registry候補作成・`publicStoryId`/`publicEpisodeId`値の確定・実登録（提案値はユーザー確認用ファイルにのみ記載、Registry未登録）
- `story_manifest.yaml`の実データ変更・manifest併用での再normalize
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check（いずれも確定済み`publicStoryId`が前提のため、本PRのスコープ外）
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行
- dry-run生成物（normalize/extraction/merge/candidates出力）自体のcommit（すべてworkspace限定）

## 4.10 `evidence-index-stage2-batch-promotion`実施結果（Phase 4、通常small batch初回、§12.1案B採用、匿名化）

§4.9で選定した5 story（`publicStoryId`確定値はユーザー承認済み、`EVENT_041_210526`/`EVENT_044_210707`/`EVENT_045_210721`/`EVENT_046_210804`/`EVENT_086_230315`、いずれもevent category）について、Registry entry追加とEvidence Index実データ昇格を同一PRで実施した（§12.1の案B）。Phase 4（通常small batch、最大5 story）の初回実施であり、ユーザーが5 story一括・実データcommitを事前に明示承認した上での実施である。

### 4.10.1 コマンド辞書拡充（先行実施）

§4.9のdry-runで検出された未登録コマンド3種を、実データraw行（該当箇所を直接確認した上で）`config/script_commands.yaml`・`agents/parser/parser.py`の両方へ追加した（`script-command-dictionary-expansion-batch-002`と同じ方式）。

| コマンド | 分類 | 根拠 |
|---|---|---|
| `vol` | stage_direction (sound) | `sound Bgm ...`直後に続く`vol 0`/`vol 1`形式。BGM/SE音量制御と判断 |
| `{` | stage_direction (character_display) | 複数`ch`スロットへの`@visible`/`@facelow`/`@motionwait`等を同時グループ化する構文の開始 |
| `}` | stage_direction (character_display) | 同上、グループ化構文の終了 |

`agents/parser/tokenizer.py`の`KEYWORD_TOKENS`にも対で追加した（`{`/`}`は`@`始まりでないため`ch`/`pos`等と同様の追加が必要だった）。合成fixtureテスト（`tests/parser/test_parser_basic.py::test_stage2_batch_promotion_new_commands_become_stage_direction`）を追加し、既存テストは無変更のまま全件PASSを確認した。

### 4.10.2 manifest割当と再normalize結果

5 storyの確定`publicStoryId`/`publicEpisodeId`をローカルmanifest（workspace限定、非commit）へ設定し、`normalize_story.py --manifest ... --raw-root ... --manifest-strict --validate --check-compat`で全18 episodeを再normalizeした。

- 全18 episodeで`manifestMatched=true`（`matchedBy=raw_path`）、`metadata.publicStoryId`/`episodes[].metadata.publicEpisodeId`の伝播を確認
- **全18 episodeで`unknownCommandCount: 0`、`parserCompatibility: compatible`を達成**（§4.10.1の辞書拡充により、§4.9のdry-run時点で観測されたunknown 14件・一部`warning`判定がすべて解消された）

### 4.10.3 判定matrix再作成（§4.3.4様式）

`extract_story.py --validate` → `merge_extractions.py`（resolved=18 valid=18 invalid=0 skipped=0）→ `build_evidence_index_candidates.py --public-profile default --clean`を実行し、判定matrixを再作成した。

| Story（匿名） | episodes | total（filter後） | unknown比率 | 意味あるentry比率 | parserCompat（worst） | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|
| Story A | 4 | 185 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story B | 4 | 196 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story C | 4 | 202 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story D | 4 | 240 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |
| Story E | 2 | 100 | 0% | 100% | compatible | 候補可（600以下） | promotion-candidate |

5 story合計923 entries（unknown合計0件、§4.9時点の14件からすべて解消）。**5 storyすべて`promotion-candidate`に分類された。** Failed story count: 0、excluded story count: 0。

### 4.10.4 Registry entry追加とreview条件確認

`knowledge/public_ids/story_public_ids.yaml`に5 story分のentry（`publicStoryId`/`category: event`/`episodes[].publicEpisodeId`/`episodeOrder`のみ）を追加した。既存3 story分のentryは無変更のまま維持した。§5の8項目レビュー条件をすべて確認した:

- sourceKey非由来のpublicStoryId: 確認済み（`workspace/local_inputs/event_numbering_table.tsv`のsourceKey→publicStoryId対応表に基づきユーザーが確定した値であり、Registry entry自体にsourceKeyは一切含まれない）
- `{publicStoryId}_E{episodeOrder:02d}`形式のpublicEpisodeId: 確認済み
- episodeOrderがstory内表示順(1始まり)と一致: 確認済み（5 storyともraw episodeファイル番号順と一致）
- entry内にsourceKey・internal ID・raw title・raw path非含有: schema `additionalProperties: false`による構造的保証＋目視確認済み
- Registry内duplicate publicStoryId無し: 確認済み
- Registry内duplicate publicEpisodeId無し: 確認済み
- 追加対象entryの人間レビュー完了: 完了（ユーザー事前承認済み）
- `check_public_episode_ids.py --registry`との整合確認: `assigned=18 missing=0`でPASS

### 4.10.5 Promotion前チェックリスト（§6）実施結果

| チェック項目 | 結果 |
|---|---|
| `check_public_episode_ids.py --registry`（正式Registry、`--strict`） | PASS（assigned=18, missing=0） |
| `project_evidence_index_public_ids.py --projection-mode public-safe --registry`（正式Registry） | PASS（5 story・923 entries、`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`、conflicts=0、missing_after_registry=0） |
| `validate_evidence_index.py` | PASS（5 files・923 entries） |
| `check_evidence_index_promotion.py`（`--policy public-default`） | PASS |
| `check_evidence_index_promotion.py --story-summaries`（`knowledge/summaries/stories`） | PASS（新5 story分は既存Summaryから参照されていないため対象外。48件の警告は既存3 storyのSummary evidenceRefsが5 story限定inputに含まれないことによるもので、想定内） |
| `render_wiki.py --evidence-index`（5 story分のmerged collection、workspace限定） | 成功。Evidence page 5件・Story page 5件・Episode page 18件を含む生成。Story page → Evidence index導線がすべて正しく解決されることを確認 |
| internal/source ID exposure check（projection output・rendered Markdown） | クリア（内部storyId/sourceKeyフラグメント・`.dec`/`@ChTalk`/`@Scenario`/`$num`/ローカル絶対パス等いずれも0件。非ASCII文字混入確認では「未登録」等の定型プレースホルダーのみを検出、それ以外は0件） |
| `mkdocs build --strict`（workspace限定一時config経由） | 成功（0 warnings/errors） |
| human review note | 作成済み（workspace限定、非commit）。Decision: `Approved for promotion`、Notesにユーザー事前承認済みである旨を記載 |
| `promote_evidence_index.py`（dry-run） | PASS。planned copy 5件（`{publicStoryId}.yaml`ベースのファイル名であることを確認） |

### 4.10.6 Promote execute

`promote_evidence_index.py --execute`を実行し、`knowledge/evidence/stories/`へ5ファイルのみがcopyされたことを確認した。`git status --short`でも、`knowledge/public_ids/story_public_ids.yaml`の変更1件（既存entry維持＋5 story分追加）と`knowledge/evidence/stories/`への新規5ファイルのみであることを確認した（既存の昇格済み3 storyのファイルには一切触れていない）。

### 4.10.7 Promotion後チェックリスト（§7、batch単位）実施結果

copy後、既存の昇格済み3 storyを含む**全8ファイル**に対して再検証した。既存3 storyについても、post-promotion検証専用としてworkspace限定でraw episodeを再normalize・extraction・mergeし直し（Registryの`publicStoryId`/`publicEpisodeId`値と一致する範囲のepisodeのみ）、新5 story分と統合した22 episode分のmerged knowledge collectionをrender入力として用いた。

| チェック項目 | 結果 |
|---|---|
| `validate_evidence_index.py --input knowledge/evidence/stories` | PASS（8 files・1313 entries） |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories` | PASS |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories --story-summaries` | PASS（警告0件、全evidenceRefsが解決可能） |
| `render_wiki.py --evidence-index knowledge/evidence/stories` | 成功。既存3件を含む8件のEvidence pageすべてを再生成 |
| 新規追加分Evidence pageのspot check | 5 storyともEvidence page見出しが`publicEvidenceId`形式、`stage_direction`0件、raw text/raw command/internal ID非表示を確認 |
| Story page → Evidence page導線（新規追加分） | 5 storyとも正しく解決されることを確認 |
| internal/source ID exposure check | committed YAML 8ファイル・再render後のMarkdown/HTML（記事本体）いずれもクリア |
| `mkdocs build --strict`（workspace限定一時config経由） | 成功 |
| `git status --short` | 意図しない追加・変更無し（`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`新規5ファイル・辞書拡充3ファイル・テスト1ファイルのみ） |

### 4.10.8 結論

- Failed story count: 0
- 5 story（`EVENT_041_210526`/`EVENT_044_210707`/`EVENT_045_210721`/`EVENT_046_210804`/`EVENT_086_230315`）とも`knowledge/evidence/stories/`への実データ昇格を完了した
- 既存の昇格済み3 story（`EVENT_164_260425`/`EVENT_168_260624`/`RAID_027_260504`）には一切影響なし（rollback不要）
- コマンド辞書拡充（3コマンド）により、対象5 storyのunknownCommandCount・unknown entry比率をいずれも0にした状態でのpromotionとなった
- **Phase 4（通常small batch）の初回実施を完了とする**（§4参照）

### 4.10.9 本PRでは実装しないこと

- 既存3 story（Registry entry・Evidence Index file）への変更
- RAIDカテゴリの採番方式設計
- Stage 2以降の追加story選定
- `agents/extractor/`等、summarizer以外の未実装エージェントパッケージへの着手
- Story Summary（`knowledge/summaries/stories/`）の生成・昇格

## 4.11 Stage 3 first candidate selection（`evidence-index-stage3-candidate-selection`実施結果、匿名化）

Phase 4（通常small batch、最大5 story）2巡目に向けた次batch候補選定を実施した。**本PRは候補選定とレポート作成まで（Registry追加・実昇格はいずれも行わない）。** 母集団を、Stage 2（§4.8〜§4.10）まではevent categoryのみに限定していたところから、**event category（遅延発見6件込みで174 story）とraid category（v2.1採番確定済み27 story）の合算**へ初めて拡大した点がStage 2との差分である。

### 4.11.1 スクリーニング結果

- 対象母集団: event category全量174 story＋raid category全量27 story（計201 story）
- 既公開8 story（EVENT 7・RAID 1）を母集団から除外
- `scripts/check_script_compatibility.py`をevent/raid双方に個別実行した結果、`needs_update`/`blocked`のepisodeを含むstoryは母集団中**0件**（コマンド辞書拡充・キャラクター辞書拡充の既存効果により両カテゴリとも`unknownCommandCount: 0`・`unknownCharacterIdCount: 0`）
- 一次フィルタ後の候補プール: 193 story。episode数2〜5でさらにfilterした結果、**186 story**
- sourceKey（raw export dir名）から採番表の`sourceKey`列への対応付けは、`csl_script_<category>_`prefixと`_export`suffixを機械的に除去する方式で全193 storyが解決した（未解決0件）。この対応規則は採番表のドキュメント化された仕様ではなく、raw配置の命名慣習から今回のPRで特定したものであり、次回以降のselection PRでも再利用できるよう本節に記録する

### 4.11.2 選定結果と発見事項（category混在時の優先順位の偏り）

Stage 2と同じ優先順位（episode数昇順→行数昇順、entry数600以下見込みの代理指標）をevent+raid合算プールへ適用したところ、**上位はraidカテゴリに偏った**（上位8 storyがいずれもraid category）。raidカテゴリ全27 storyが一律2 episode構成であり、行数もevent側の典型的なstoryより少ない傾向があるためで、選定基準自体の欠陥ではなく「entry数の少なさを優先する」既存方針がそのまま反映された結果と判断した。**この観察を、category合算時の優先順位挙動に関する既知の性質として本節に記録する**。

**2026-07-18ユーザー決定（open question解決）**: category別の最小保証枠を設けるかどうかについて、ユーザーは「現行基準のまま維持（枠は設けない）」と明示決定した。entry数の少なさを優先する既存の優先順位ロジック（episode数昇順→行数昇順）はそのまま維持し、category混在時に特定categoryへ選定が偏ること自体は許容する。選定優先順位ロジック自体の変更は行わない。

上位8 story（dry-run用tentative ID）に対し、`normalize_story.py`（`--check-compat --validate`）→`extract_story.py`→`merge_extractions.py`→`build_evidence_index_candidates.py --public-profile default`のフルdry-runパイプラインを実行し、§4.3判定matrixを作成した。

| Story（匿名） | episodes | total（filter後） | unknown比率 | 意味あるentry比率 | parserCompat（実測） | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|
| Story A | 2 | 87 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| Story B | 2 | 109 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| Story C | 2 | 102 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| Story D | 2 | 99 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| Story E | 2 | 110 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| （buffer、未選定） | 2 | 125 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| （buffer、未選定） | 2 | 79 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| （buffer、未選定） | 2 | 120 | 0% | 100% | compatible | 候補可 | promotion-candidate |

**選定5 story（Story A〜E）すべてが`promotion-candidate`に分類された。** 5 story合計10 episode・507 entries（unknown合計0件）。Failed story count: 0、excluded story count: 0。5 storyすべてraid categoryに属する（§4.11.2冒頭の発見事項どおり）。

**判定基準の細部の補足**: `check_script_compatibility.py`（standalone checker）は対象ファイルを`nonSpeakerNumericAssignmentCount`等の情報フィールドにより総合`warning`表示していたが、§4.3.1(c)が正とする指標である実際のNormalized Story JSONの`compatibilityReport.parserCompatibility`はdry-run 8 story全件で`compatible`だった。standalone checkerとreal parserの判定基準が異なる（既知の非統一、`CLAUDE.md`記載どおり両checkerは統一されていない）ことによる差であり、§4.3.1(c)の判定は正しくreal parser側の値を採用した。

候補の実sourceKey・実publicStoryId値は、ユーザー確認用ファイル（`workspace/evidence_index_dry_runs/stage3_candidate_selection/candidate_selection_report.md`、非commit）に記載した。

### 4.11.3 本PRでは実装しないこと

- Public ID Registry候補作成・`knowledge/public_ids/story_public_ids.yaml`への実登録
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check（いずれもRegistry確定が前提のため、実昇格PRのスコープ）
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行（`promote_evidence_index.py --execute`を含む）
- category別の最小保証枠等、選定優先順位ロジック自体の変更（§4.11.2の発見事項はopen questionとして記録するのみ）
- dry-run生成物（normalize/extraction/merge/candidates出力・selection report）自体のcommit（すべてworkspace限定）

## 4.12 `evidence-index-stage3-promotion-execution`実施結果（Phase 4、通常small batch 2巡目、実昇格）

§4.11で選定した5 story（`publicStoryId`確定値、`RAID_012_221118`/`RAID_013_221230`/`RAID_001`/`RAID_015_230630`/`RAID_005_210702`、いずれもraid category）について、Registry entry追加とEvidence Index実データ昇格を実施した。ユーザーが2026-07-18に5 story一括・実データcommitを事前に明示承認した上での実施であり、手順・検証はStage 2実昇格（§4.10、`evidence-index-stage2-batch-promotion`）を踏襲した。

### 4.12.1 判定matrix再作成

workspace限定manifestで5 storyの確定`publicStoryId`/`publicEpisodeId`を設定し、`normalize_story.py --manifest ... --raw-root ... --manifest-strict --validate --check-compat`で全10 episodeを再normalizeした。全10 episodeで`manifestMatched=true`・`parserCompatibility: compatible`・`publicStoryId`/`publicEpisodeId`の伝播を確認した。`extract_story.py --validate`（10/10 schema検証PASS）→`merge_extractions.py`（resolved=10 valid=10 invalid=0 skipped=0）→`build_evidence_index_candidates.py --public-profile default --clean`を実行し、判定matrixを再作成した。

| Story | episodes | total（filter後） | unknown比率 | 意味あるentry比率 | parserCompat | entry数判定 | 分類 |
|---|---|---|---|---|---|---|---|
| RAID_012_221118 | 2 | 87 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| RAID_013_221230 | 2 | 109 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| RAID_001 | 2 | 102 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| RAID_015_230630 | 2 | 99 | 0% | 100% | compatible | 候補可 | promotion-candidate |
| RAID_005_210702 | 2 | 110 | 0% | 100% | compatible | 候補可 | promotion-candidate |

5 story合計507 entries（unknown合計0件）。§4.11.2の選定時見込み（10 episode・507 entries）と実測が完全一致した。**5 storyすべて`promotion-candidate`に分類された。** Failed story count: 0、excluded story count: 0。

### 4.12.2 Registry entry追加とreview条件確認

`knowledge/public_ids/story_public_ids.yaml`に5 story分のentry（`publicStoryId`/`category: raid`/`episodes[].publicEpisodeId`/`episodeOrder`のみ）を追加した。既存8 story分のentryは無変更のまま維持した。§5の8項目レビュー条件をすべて確認した:

- sourceKey非由来のpublicStoryId: 確認済み（`workspace/local_inputs/raid_numbering_table.tsv`のv2.1採番表に基づき確定済みの値であり、Registry entry自体にsourceKeyは一切含まれない）
- `{publicStoryId}_E{episodeOrder:02d}`形式のpublicEpisodeId: 確認済み
- episodeOrderがstory内表示順(1始まり)と一致: 確認済み（5 storyともraw episodeファイル番号順と一致、各2episode）
- entry内にsourceKey・internal ID・raw title・raw path非含有: schema `additionalProperties: false`による構造的保証＋目視確認済み
- Registry内duplicate publicStoryId無し: 確認済み
- Registry内duplicate publicEpisodeId無し: 確認済み
- 追加対象entryの人間レビュー完了: 完了（ユーザー事前承認済み、2026-07-18）
- `check_public_episode_ids.py --registry`との整合確認: `assigned=10 missing=0`でPASS（`--strict`）

### 4.12.3 Promotion前チェックリスト（§6）実施結果

| チェック項目 | 結果 |
|---|---|
| `check_public_episode_ids.py --registry`（正式Registry、`--strict`） | PASS（assigned=10, missing=0） |
| `project_evidence_index_public_ids.py --projection-mode public-safe --registry`（正式Registry） | PASS（5 story・507 entries、`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`、Registry補完0件・conflict 0件、`publicEpisodeId`は入力側に既に確定済みだったため） |
| `validate_evidence_index.py` | PASS（5 files・507 entries） |
| `check_evidence_index_promotion.py`（`--policy public-default`） | PASS |
| `check_evidence_index_promotion.py --story-summaries`（`knowledge/summaries/stories`） | PASS（48件の警告は既存3 storyのSummary evidenceRefsが5 story限定inputに含まれないことによるもので、§4.10.5と同じ想定内パターン） |
| `render_wiki.py --evidence-index`（5 story分のmerged collection、workspace限定） | 成功。Evidence page 5件・Story page 5件・Episode page 10件を含む生成。Story page → Evidence index導線がすべて正しく解決されることを確認 |
| internal/source ID exposure check（projection output・rendered Evidence page記事本体） | クリア（内部storyId/sourceKeyフラグメント・`.dec`/`@ChTalk`/`@Scenario`等いずれも0件。Evidence page記事本体はPython による`<article>`スコープ走査でも0件を確認） |
| `mkdocs build --strict`（workspace限定一時config経由） | 成功（0 warnings/errors） |
| human review note | 作成済み（workspace限定、非commit）。Decision: `Approved for promotion`、Notesにユーザー事前承認済み（2026-07-18）である旨を記載 |
| `promote_evidence_index.py`（dry-run） | PASS。planned copy 5件（`{publicStoryId}.yaml`ベースのファイル名であることを確認） |

### 4.12.4 Promote execute

`promote_evidence_index.py --execute`を実行し、`knowledge/evidence/stories/`へ5ファイルのみがcopyされたことを確認した。`git status --short`でも、`knowledge/public_ids/story_public_ids.yaml`の変更1件（既存entry維持＋5 story分追加）と`knowledge/evidence/stories/`への新規5ファイルのみであることを確認した（既存の昇格済み8 storyのファイルには一切触れていない）。

### 4.12.5 Promotion後チェックリスト（§7、batch単位）実施結果

copy後、既存の昇格済み8 storyを含む**全13ファイル**に対して再検証した。既存8 storyについても、post-promotion検証専用としてworkspace限定でraw episodeを再normalize・extraction・mergeし直し（Registryの`publicStoryId`/`publicEpisodeId`値と一致する範囲のepisodeのみ）、新5 story分と統合した32 episode分のmerged knowledge collectionをrender入力として用いた。

| チェック項目 | 結果 |
|---|---|
| `validate_evidence_index.py --input knowledge/evidence/stories` | PASS（13 files・1820 entries） |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories` | PASS |
| `check_evidence_index_promotion.py --input knowledge/evidence/stories --story-summaries` | PASS |
| `render_wiki.py --evidence-index knowledge/evidence/stories` | 成功。既存8件を含む13件のEvidence pageすべてを再生成 |
| 新規追加分Evidence pageのspot check | 5 storyともEvidence page見出しが`publicEvidenceId`形式、`stage_direction`0件、raw text/raw command/internal ID非表示を確認 |
| Story page → Evidence page導線（新規追加分） | 5 storyとも正しく解決されることを確認 |
| internal/source ID exposure check | committed YAML 13ファイル・再render後のEvidence page記事本体（`<article>`スコープ走査）いずれもクリア |
| `mkdocs build --strict`（workspace限定一時config経由） | 成功 |
| `git status --short` | 意図しない追加・変更無し（`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`新規5ファイルのみ） |

**既知の制約の再確認**: mkdocs build後のHTML全体（グローバルナビゲーション部分）には、merged knowledge collection側の内部episodeId断片が表示される（PR #98/#100/#105/§4.6.4/§4.10.7で判明済みの制約、Story/Episode page navigationの既存挙動であり、workspace限定previewのみに現れる。Evidence Index/Evidence page本体のコンテンツには影響しない、Evidence page記事本体は`<article>`スコープの走査で内部ID非露出を確認済み）。

### 4.12.6 結論

- Failed story count: 0
- 5 story（`RAID_012_221118`/`RAID_013_221230`/`RAID_001`/`RAID_015_230630`/`RAID_005_210702`）とも`knowledge/evidence/stories/`への実データ昇格を完了した
- 既存の昇格済み8 storyには一切影響なし（rollback不要）
- **公開Evidence Indexは8→13 story・計1,820 entriesに拡大した**
- §4.11.2のopen question（category別最小保証枠）は2026-07-18ユーザー決定により解決済み（現行基準のまま維持、枠は設けない）
- **Phase 4（通常small batch）2巡目を完了とする**（§4参照）

### 4.12.7 本PRでは実装しないこと

- 6件目以降（buffer 3件、`RAID_018_231230`/`RAID_004`/`RAID_009_220325`）の追加
- Story Summary生成
- Stage 4以降の候補選定
- 既存13 story（Registry entry・Evidence Index file）への変更
- `agents/`・`scripts/`配下の実装変更
- workspace生成物（manifest・candidates・projection output・merged collection・review note・各種report）自体のcommit（すべてworkspace限定）

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

# 11. 公開済みEvidence Indexの更新（re-promotion）方針

`knowledge/evidence/stories/`へ既に昇格済みのstoryを、辞書・parser改善後に再生成した候補で更新（re-promotion）する場合の運用方針を定義する。**本文書は方針のみを扱い、更新の実行（`promote_evidence_index.py --execute --overwrite`）は対象外**（§14 Non-goals）。

## 11.1 背景

キャラクター辞書（confirmed 14→184件）・コマンド辞書の大幅拡充により、既に`knowledge/evidence/stories/`へ昇格済みのstory（現在3 story・392 entries）についても、再生成すると内容が変化する可能性が生じた。新規storyのbatch promotion（§1〜§10）とは異なり、re-promotionは**公開済みで既に外部から参照され得るIDを書き換えるリスク**があるため、別建ての方針として整理する。

## 11.2 公開ID不変の絶対条件（最重要ゲート）

再生成候補（public-safe projection後）と公開済みYAMLを機械比較し、以下を**必須ゲート**とする。

- **`publicEvidenceId`の集合が完全一致すること**（story/episode/type別の件数も一致すること）
- 各`publicEvidenceId`の内容（`evidenceType`・`speaker`を除く全フィールド）が完全一致すること（Evidence Indexは元々raw textを保持しない設計のため、`text`そのものの比較対象は存在しない。内容の同一性は、entryの集合・型・trace関連フィールドの不変性で担保する）

**増減・上記の変化が1件でもあれば、そのstoryの更新はblockingで見送る**（更新しない。公開済みYAMLはそのまま維持する）。このケースは既存の運用ルールでは解決できないため、**versioning方針（例: 旧entryを残したまま新entryを追加する等）の設計へエスカレーションする**。

### 11.2.1 限定例外: unknown型entryの非公開型再分類による削除

上記の増減blockingには、以下の限定例外を認める。`unknown`型entryがparser改善（コマンド辞書拡張等）により非公開型（`stage_direction`等）へ再分類されたことによる削除は、次の3条件を**すべて**満たす場合に限り許可する。

1. 削除entryがどのSummary evidenceRefsからも参照されていないこと
2. 削除される公開IDを更新記録に列挙し、当該IDは以後再利用しないこと
3. 残る全entryの公開ID・内容一致（§11.2のゲート）が成立していること

**セリフ型（`dialogue`/`monologue`/`narration`/`choice`）にはこの例外を適用しない。** セリフ型entryの増減は、理由を問わずblockingのまま維持する。

## 11.3 許可される差分の範囲

上記ゲートを通過したstoryについてのみ、以下の差分を「metadata改善」として許可する。

- `speaker`の`resolutionStatus`が`unresolved`→`resolved`へ変化すること、または`speaker`が未設定（null）から新たに設定されること
- `speaker`の`speakerId`/`displayName`の追加・変更（上記に付随するもののみ）
- `relatedEntities`の追加・変更（`speaker`解決の結果として機械的に導出される、直接の付随フィールドであるため許可する）

`text`・`evidenceType`・公開ID・件数の変化は一切許可しない（§11.2のゲートで既にblockされているはずだが、念のため明記する）。

## 11.4 手順

1. workspace限定で対象storyを再生成する（re-normalize → extraction → merge → `build_evidence_index_candidates.py --public-profile default` → `project_evidence_index_public_ids.py --projection-mode public-safe --registry`）
2. 再生成候補と公開済みYAMLの比較レポートを作成する（§11.2・§11.3の基準で機械的に判定、workspace限定・非commit）
3. 人間レビュー（比較レポートを確認し、許可された差分のみであることを確認する）
4. `promote_evidence_index.py`のdry-run（`--execute`なし）でPASSを確認する
5. `promote_evidence_index.py --execute --overwrite`を実行する（**ユーザーの明示的な事前承認が必須の停止点**。§3の`--execute`実行方針・`AI_PR_Playbook.md` §8の恒常Non-goals「`promote_evidence_index.py --execute`の、指示のない実行」と同様に扱う）
6. 昇格後の全再検証を実施する: `validate_evidence_index.py`・`check_evidence_index_promotion.py --story-summaries`・`render_wiki.py --evidence-index`・`mkdocs build --strict`・internal/source ID exposure check（§6・§7と同じ基準）

## 11.5 Summary側の扱い

`knowledge/summaries/stories/`のSummary本体は変更しない。更新対象storyのSummaryが持つ全`evidenceRefs`が、再生成後のEvidence Indexでも引き続き解決できることのみを機械的に再照合する（§11.2のゲートを通過していれば`publicEvidenceId`集合は不変のため、通常は問題にならない想定だが、念のため明示的に確認する）。

## 11.6 Rollback方針

既存§10をそのまま継承する。**公開IDは§11.2のゲートにより不変が保証されているため、re-promotionのrollbackでID再利用問題は発生しない**（更新前のfile内容へ`git revert`で戻すだけで済む）。

## 11.7 `evidence-index-republication-policy-dry-run`実施結果（本PR、匿名化）

昇格済み全3 story（392 entries）を対象に、現行main（辞書confirmed 184件・コマンド辞書拡張後）で再normalize（4 episode、`unknownCommands: 0`・`publicStoryId`/`publicEpisodeId`伝播を確認）→extraction→merge→候補生成→Public-safe projection（Registry使用）までworkspace限定で実行し、§11.2の機械比較を行った。

**publicEvidenceId集合の一致**: 3 storyのうち2 story（合計205 entries）は完全一致（増減0件）。残り1 story（**昇格済み最初のstory**、2 episodes）は、公開済み187 entriesに対し再生成後185 entriesとなり、**2 entry減少**した（機械比較で検出）。

**原因の特定**: 減少した2 entryは、いずれも公開済み側で`evidenceType: unknown`だったentry（1 episodeあたり1件ずつ）だった。コマンド辞書拡張により該当raw commandが`unknown`から`stage_direction`として正しく認識されるようになった結果、`--public-profile default`のfilter（`stage_direction`除外）で候補から外れたことが原因と判明した（parser/辞書の品質改善が意図せずEvidence Index側の公開entry集合を変化させたケース）。

**text相当の内容一致**: 上記2 entryを除く全390 entry（＝2 storyの205 entry＋1 storyの185 entry）は、`speaker`を除く全フィールドが完全一致した。

**metadata改善（許可差分）の内訳**: 390 entry中148 entryで`speaker`差分を検出し、全件が「未設定（null）→`resolutionStatus: resolved`」への変化だった（story別内訳: 昇格済み最初のstory 75件、2 story目 32件、3 story目 41件）。既に解決済みだった`speaker`の値が変化したentryは0件（誤った再割当は無し）。`speaker`変化に付随して`relatedEntities`も同数（148件）変化しており、いずれも新たに解決された`speaker`から機械的に導出された値のみだった（§11.3の許可範囲に収まる）。

**Summary evidenceRefs再照合**: 3 story分のSummaryが持つ全`evidenceRefs`は、公開済み・再生成後のいずれのEvidence Indexに対しても100%解決可能だった（欠落した2 entryはいずれのSummaryからも参照されていなかった）。

**追加検証**: 再生成後のpublic-safe projection出力（390 entries、3 files）に対する`validate_evidence_index.py`・`check_evidence_index_promotion.py --story-summaries`はいずれもPASSした。

**結論**: 2 storyは§11.2のゲートを通過し（metadata改善のみ）、更新候補として適格と判定した。**残り1 story（減少2件を検出）はblockingとし、本PRでは更新を見送る**（§11.2のとおりversioning方針の設計へエスカレーションする）。**本PRでは公開済みYAML・Registry・Summaryのいずれも変更していない**（dry-runのみ）。

**追記（`evidence-index-republication-001`、§11.2.1限定例外の追加により解除）**: 本PR時点でblockingと判定した残り1 story（昇格済み最初のstory）は、減少した2 entryがいずれも`evidenceType: unknown`からparser改善による`stage_direction`への再分類が原因であり、セリフ型entryの増減ではなかった。後続PR`evidence-index-republication-001`で§11.2.1として上記の限定例外を新設し、(1)削除entryがどのSummary evidenceRefsからも参照されていないこと（本PRの時点で確認済み、§11.7参照）、(2)削除される公開IDを更新記録に列挙し以後再利用しないこと、(3)残る全entryの公開ID・内容一致（§11.2のゲート）が成立していること、の3条件を満たすことを確認した上で、当該storyのblockingを解除し3 storyすべてを更新対象とした。詳細は`evidence-index-republication-001`の実施記録（TASKS.md）を参照。

### 11.7.1 本PRでは実装しないこと

- 公開済み`knowledge/evidence/stories/`・`knowledge/public_ids/story_public_ids.yaml`・`knowledge/summaries/stories/`のいずれの変更
- `promote_evidence_index.py --execute`の実行
- ゲートをblockingしたstoryに対するversioning方針の設計そのもの（Next候補として記録するのみ）
- 再生成出力・比較レポート自体のcommit（すべてworkspace限定）

---

# 12. PR分割方針

複数storyへ広げる際のPR分割候補:

- **案A**: Registry entry追加PR → Evidence Index promotion PR（2 PRに分割）
- **案B**: Registry entryとEvidence Indexを同一PRに含める（PR #99の前例）
- **案C**: batch dry-run docs PR（workspace限定、実commitなし） → 実promotion PR（2段階）

## 12.1 採用方針

- **初回batch（Phase 2・Phase 3）は案Cを採用する**: まずbatch dry-run PR（`evidence-index-promotion-first-batch-dry-run`、§13）でworkspace限定の確認を行い、問題が無ければ次PRで初回実batch promotionを行う
- **通常small batch（Phase 4以降）では案B（Registry entryとEvidence Indexの同一PR）も許可する**（実績が蓄積し、フローが安定していることが前提）
- **Registryの確定に不安があるstory（`publicEpisodeId`未確定・episodeOrderの根拠が曖昧等）は、Phaseによらず案A（Registry entry先行PR）に分割する**

---

# 13. `evidence-index-promotion-first-batch-dry-run`のスコープ

**実施済み（§4.2参照）。** 以下は当初のスコープ定義であり、実施結果は§4.2・`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.11を参照。

## 13.1 やること

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

## 13.2 やらないこと

- 実promotion（`promote_evidence_index.py --execute`の実行）
- batch copy（複数storyの一括copy）
- Registry entryの実commit（`knowledge/public_ids/story_public_ids.yaml`への追加）
- 新規Evidence Indexの実commit（`knowledge/evidence/stories/`への追加）
- batch promotion scriptの実装

---

# 14. Non-goals（本文書のスコープ外）

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

`evidence-index-republication-policy-dry-run`（本PR、§11新設・re-promotion dry-run）でも以下は行っていない:

- 公開済み`knowledge/evidence/stories/`・`knowledge/public_ids/story_public_ids.yaml`・`knowledge/summaries/stories/`のいずれの変更
- `promote_evidence_index.py --execute`の実行
- ゲートをblockingしたstoryに対するversioning方針の設計そのもの
- 再生成出力・比較レポート自体のcommit（すべてworkspace限定）

`evidence-index-stage2-candidate-selection`（本PR、§4.8新設）でも以下は行っていない:

- Public ID Registry候補作成・`publicStoryId`/`publicEpisodeId`値の確定・提案
- `story_manifest.yaml`の実データ変更・manifest併用での再normalize
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行
- dry-run生成物（normalize/extraction/merge/candidates出力）自体のcommit

`feature/public-id-naming-v2-design`（本PR、§16新設・移行実行手順の設計のみ）でも以下は行っていない:

- `knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`・`knowledge/summaries/stories/`の実データ変更（改名・ID値置換を含む）
- 過去のdocs記載済み旧publicStoryId値（§4.6・§4.5等）の更新
- §16.2の検証suiteの実行
- `scripts/`配下の変更、candidate再選定

`evidence-index-stage2-candidate-reselection`（本PR、§4.9新設）でも以下は行っていない:

- Public ID Registry候補作成・`publicStoryId`/`publicEpisodeId`値の確定・実登録（提案値はユーザー確認用ファイルにのみ記載）
- `story_manifest.yaml`の実データ変更・manifest併用での再normalize
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行
- dry-run生成物（normalize/extraction/merge/candidates出力）自体のcommit
- §4.8の記録内容自体の削除（差し替えの経緯として残す。旧5 storyを`excluded`として再分類することもしない）

`evidence-index-stage2-batch-promotion`（本PR、§4.10新設・Phase 4初回実batch promotion）でも以下は行っていない:

- 既存3 story（Registry entry・Evidence Index file）への変更
- RAIDカテゴリの採番方式設計
- Stage 2以降の追加story選定
- `agents/extractor/`等、summarizer以外の未実装エージェントパッケージへの着手
- Story Summary（`knowledge/summaries/stories/`）の生成・昇格
- ローカルmanifest・dry-run再生成物・review note・projection outputのcommit（すべてworkspace限定）

`evidence-index-stage3-candidate-selection`（本PR、§4.11新設）でも以下は行っていない:

- Public ID Registry候補作成・`knowledge/public_ids/story_public_ids.yaml`への実登録
- Public-safe projection・`validate_evidence_index.py`・`check_evidence_index_promotion.py`・`render_wiki.py`・visual review・exposure check
- 複数story分のEvidence Index/Registry entryのcommit、batch promotionの実行（`promote_evidence_index.py --execute`を含む）
- category別の最小保証枠等、選定優先順位ロジック自体の変更
- dry-run生成物（normalize/extraction/merge/candidates出力・selection report）自体のcommit

---

# 15. 関連ドキュメント

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

---

# 16. publicStoryId命名規約v2への移行実行手順（`feature/public-id-naming-v2-design`で新設）

`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16で確定した命名規約v2（`{CATEGORY}_{seq:03d}_{YYMMDD}`）へ、既公開3 story（`knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`・`knowledge/summaries/stories/`）を移行するための実行手順を定義する。**本節は手順の定義のみを行う。実行（Registry書き換え・ファイル改名・ID値置換）は次PR（移行実行PR）のスコープであり、本PRでは一切実施しない。**

## 16.1 前提

- 移行対象・新旧mappingの形式（`{CATEGORY}_{seq:03d}_{YYMMDD}`、seqはカテゴリ別昇格順）は`Evidence_Index_Public_ID_Policy.md` §16.2・§16.3で確定済み
- 新publicStoryIdの実値（`YYMMDD`部分）は、移行実行PR側でRegistryへ正式登録する時点で初めてdocsに記載可能になる（本PR時点ではまだ未確定・未記載、§16.3参照）
- `publicEpisodeId`（`{publicStoryId}_E{NN}`）・`publicEvidenceId`（`{publicEpisodeId}_{PREFIX}{seq:04d}`）の形式自体は不変。旧publicStoryId値を新publicStoryId値へ置換すれば、派生ID群も機械的に再構成できる

## 16.2 移行実行手順（次PRで実施）

1. **Registry書き換え**: `knowledge/public_ids/story_public_ids.yaml`の既存3 story entryの`publicStoryId`・`episodes[].publicEpisodeId`を、v2形式の新値へ書き換える（`category`・`episodeOrder`は不変）。schema（`schemas/public_id_registry.schema.json`）検証・重複チェック（`scripts/check_public_episode_ids.py`の`_load_registry`）を実施する
2. **`knowledge/evidence/stories/`3 fileの改名+全ID値置換**: 3 file（現行`EVT_260707_001.yaml`/`EVT_260712_001.yaml`/`RAID_260712_001.yaml`相当）を新publicStoryId名へ改名し、ファイル内の`storyId`・`episodeId`・`evidenceId`・`publicStoryId`・`publicEpisodeId`・`publicEvidenceId`の全ID値を新形式へ置換する。Public-safe projection出力の性質上（`Evidence_Index_Public_ID_Policy.md` §6.8）、`storyId`/`episodeId`の値自体が旧`publicStoryId`/`publicEpisodeId`と同値になっているため、置換対象はこれらすべてに及ぶ
3. **`knowledge/summaries/stories/`3 fileの改名+置換**: 3 fileを新publicStoryId名へ改名し、`storyId`・`publicStoryId`・`episodeSummaries[].episodeId`・`publicEpisodeId`・`evidenceRefs`（旧`publicEvidenceId`値を新`publicEvidenceId`値へ）を置換する
4. **docs内の旧ID値記録の更新**: 過去のdocsに記録済みの旧publicStoryId値（`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.12、本文書§4.6・§4.5等、`docs/architecture/06_AI/Public_ID_Registry_Design.md` §8.6等）を、移行実行PRで一括して新値へ更新する。**本PR（`feature/public-id-naming-v2-design`）では、これらの既存docs記載箇所はいずれも変更しない**（§16.5参照）
5. **検証suite**: 以下をすべて実施しPASSを確認する
   - 全`evidenceRefs`の解決性再照合（Summary側`evidenceRefs`が新Evidence Index entryへ解決できること、`check_evidence_index_promotion.py --story-summaries`相当）
   - `render_wiki.py --evidence-index`によるrender確認（Evidence page/Story page導線が新publicStoryIdベースで解決されること）
   - `mkdocs build --strict`
   - internal/source ID exposure check（既存の`Evidence_Index_Promotion_Policy.md` §11検索文字列を継続使用）
   - **新旧mapping逆引き検証**: 旧publicStoryId値がRegistry・Evidence Index・Summaryのいずれにも一切残っていないこと、かつ新publicStoryId値から`Evidence_Index_Public_ID_Policy.md` §16.3のmapping表を逆引きして正しい旧IDに対応することを機械的に確認する
6. **マージ前の停止点**: 実行自体はユーザーが事前承認済みだが（本PRのプロンプト前提）、**検証suite（手順5）の結果をFableが確認してからマージする**。`AI_PR_Playbook.md` §8の恒常Non-goals「`promote_evidence_index.py --execute`の、指示のない実行」と同様、実データ書き換えを伴う移行はこの停止点を経てから完了とする

## 16.3 Rollback方針

既存§10を継承する。ただし移行はfile改名を伴うため、rollbackは「新ファイルの削除＋旧ファイルの復元（`git revert`）」で行う。旧publicStoryId値自体は`Evidence_Index_Public_ID_Policy.md` §16.4のとおり以後再利用しない前提のため、rollback後に旧IDへ戻すこと自体はID安定性原則には抵触しない（あくまで移行を取り消すだけであり、新規に別の意味で旧IDを再割当てするわけではない）。

## 16.4 本PRでは実装しないこと

- `knowledge/public_ids/story_public_ids.yaml`・`knowledge/evidence/stories/`・`knowledge/summaries/stories/`の実データ変更（改名・ID値置換を含む）
- 過去のdocs記載済み旧publicStoryId値（§13.12・§4.6・§8.6等）の更新
- 検証suiteの実行
- `scripts/`配下の変更（移行はすべて既存script（`promote_evidence_index.py --execute --overwrite`相当）とファイル改名・手動置換で行う想定であり、新規migration scriptの実装は本PRのスコープ外。移行実行PR側で必要性を判断する）

---

# 17. Promotion対象外カテゴリ（`feature/h-scene-content-scope-policy`で新設）

`script-command-dictionary-expansion-batch-002`（§4.7.4）以来保留だった「演出系（H_scene等）2,006件のスコープ判断・対応」を、ユーザー決定（2026-07-15）に基づき解決する。詳細な方針・根拠・open questionsは`docs/architecture/01_Project/03_Scope.md`を正とし、本節はEvidence Index batch promotion運用への影響のみを記す。

## 17.1 結論

**`character`カテゴリのH_scene系（H_sceneN本体・変種・純コマンド演出ファイルすべて）由来のstoryは、promotion-ineligible（promotion対象外）として恒久的に除外する。** 該当storyは、`Evidence_Index_Batch_Promotion_Policy.md` §4.3のselection criteria（unknown比率・意味あるentry比率・parserCompatibility・entry数）による機械的checkが仮に全PASSであっても、batch候補・real batch promotionのいずれにも含めない。

理由は`03_Scope.md`の two-tier方針（軸(A)内部KB対象・軸(B)公開対象を分離）による: H_scene系は内部KB（正規化・抽出・キャラクター知識）の対象には含めるが、Wiki出力・Evidence Index promotionを含む公開面からは対象外とする decision 1（`03_Scope.md` §4.2）が、本文書のpromotion運用に直接適用される形である。

## 17.2 対象範囲

- 対象: `data/raw/character/`配下のH_sceneN本体・`H_scene_s`・その他変種（`_n`/`_VR`/`_spine`/`#N`）・camera/finish/episode_bgm等の純コマンド演出ファイル由来のstory全件
- 対象外（従来どおりpromotion対象であり続ける）: `main`/`event`/`raid`カテゴリの全story、および`character`カテゴリ内の本編系エピソード（`episode1`〜`episode3`/`episode_EX`、`03_Scope.md` §6）

## 17.3 選定手順への反映

`Evidence_Index_Batch_Promotion_Policy.md` §4.8以降で実施している候補selection（母集団screening→§4.3判定matrix）の母集団抽出段階において、`character`カテゴリのH_scene系はそもそも母集団に含めない（selection criteriaの3分類—`promotion-candidate`/`parser-improvement-wait`/`excluded`—とは別軸の、母集団段階での事前除外として扱う）。

## 17.4 将来の変更条件

`03_Scope.md` §4.2に明記されているとおり恒久除外であり、方針転換には`03_Scope.md`の改訂とユーザーによる新たな明示的決定を要する。本節も`03_Scope.md`の改訂と同期して更新する。

## 17.5 本PRでは実装しないこと

- H_scene系の実パース・正規化・manifest生成
- 変種の全キャラクター横断部分集合性検証（`03_Scope.md` §5.3、後続dry-run PR）
- 5〜6桁キャラクターID帯の辞書登録（`03_Scope.md` §5.2）
- `@ToCloud`/`@VR`/`VRSelect`の`config/script_commands.yaml`・`agents/parser/parser.py`への登録（後続実装PR）
- selection criteria（§4.3）・`check_evidence_index_promotion.py`等scriptsへの、母集団事前除外ロジックの機械的実装（現状は運用ルールの明文化のみ）
