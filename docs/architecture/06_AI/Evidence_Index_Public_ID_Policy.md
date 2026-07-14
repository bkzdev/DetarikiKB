# Evidence Index Public ID Policy（Public Evidence Indexの内部ID/公開ID分離方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`

---

# 1. Background

`evidence-index-promotion-first-reviewed-sample`（PR #91）で、実データ小規模サンプル（EVENTカテゴリ1story・episode2件）を`knowledge/evidence/stories/`へ初めて昇格しようと試みた。`build_evidence_index_candidates.py`によるfiltered候補生成・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`docs/runbooks/Evidence_Index_Promotion_Check.md`）はいずれも成功/PASSしたが、生成されたEvidence Index YAMLの内容を確認したところ、sourceKey由来の`storyId`がファイル名だけでなくファイル内の主要IDフィールドに大量に繰り返し出現することが判明し、安全側の判断でcommitを見送った（`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.1）。

本文書は、この問題を整理し、Public Evidence Indexにおける内部ID（trace用）と公開ID（Wiki/Git履歴に出してよいID）の分離方針を決定する。**`evidence-index-promotion-target-filename-policy`（PR #92）では実装・schema変更・実Evidence Indexのcommitはいずれも行わなかった**（設計のみ）。

`evidence-index-public-id-schema-design`（PR #93）で、`publicEvidenceId`の形式・prefix mapping・採番方針を確定し、`schemas/evidence_index.schema.json`への最小限のoptional追加（§10.3）を行った。

**`evidence-index-public-id-projection`（本PR）で、Compatible projection（案A）を実装した**。`scripts/project_evidence_index_public_ids.py`が実際に`publicEvidenceId`を生成・付与するが、内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）は削除しない（§6.7）。**実Evidence Indexのcommit・Public-safe projection（案B）実装・renderer変更・promotion再開はまだ行わない**（§13参照）。

---

# 2. Problem discovered in first promotion attempt（初回promotion試行で判明した問題）

実イベント名・実ファイル名・実`sourceKey`は本文書に記載しない。以下、匿名化した例で説明する。

```text
storyId:  EVT_YYYYMMDD_SOURCEKEY_EVENT   （sourceKey由来、内部ID）
publicStoryId: EVT_YYYYMMDD_NNN          （匿名化済み、公開向けに割り当てたID）
```

## 2.1 判明した事実

- `knowledge/evidence/stories/{storyId}.yaml`という保存場所方針（`Evidence_Index_Design.md`）により、**ファイル名自体がsourceKey由来の`storyId`になる**
- ファイル内では、全entry（実データサンプルでは187件）の`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`フィールドに、sourceKey由来の`storyId`が接頭辞として繰り返し出現する（例: `EVT_YYYYMMDD_SOURCEKEY_EVENT_E01_DLG0001`のように、1 entryあたり複数フィールドで最大5回程度）
- `publicStoryId`/`publicEpisodeId`という匿名化済みの公開向けIDは`entries[]`の各要素に別途フィールドとして存在するが、**主キー（`evidenceId`）や必須フィールド（`storyId`/`episodeId`）としては使われていない**
- さらに、レンダリングされたEvidence page自体（`agents/wiki_generator/renderer.py`の`render_evidence_page`）でも、見出し（`### {evidenceId}`）とSummary `evidenceRefs`のリンク表示（`` [`{evidenceId}`](...) ``）の両方で、この内部`evidenceId`（sourceKey由来の`storyId`を含む）がそのままWiki上に表示される（§9で詳述）
- この状態で`knowledge/evidence/stories/{storyId}.yaml`をcommitすると、sourceKey由来の識別子がGit履歴に永続的に残り、かつ公開Wiki上にもそのまま表示される

## 2.2 なぜファイル名だけの変更では解決しないか

`knowledge/evidence/stories/{publicStoryId}.yaml`のようにファイル名だけを`publicStoryId`に変えても、ファイルの中身（全entryの`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）には引き続きsourceKey由来のIDが大量に残る。ファイル名は「入り口」に過ぎず、実際にGit履歴・公開Wiki上に露出するのはファイルの中身である。**根本的な解決には、Evidence Index自体が持つIDの主キーを公開向けIDへ切り替える必要がある。**

## 2.3 このPRでの取り扱い

- `evidence-index-promotion-first-reviewed-sample`（PR #91）では、この問題が判明した時点で`knowledge/evidence/stories/`への実copyを見送った
- `promote_evidence_index.py`のdry-runは正常に動作し、review noteが未承認（`Needs revision`）であることを正しく検出した（gatekeeperとしての安全策自体は機能した）
- 本文書（`evidence-index-promotion-target-filename-policy`）は、promotion再開のために必要な設計判断を行う

---

# 3. ID categories（Evidence Indexで使われるIDの分類）

## 3.1 A. 内部trace ID（Internal trace ID）

Normalized Story JSON / Extraction Resultとの機械的な照合に必要なID群。

| フィールド | 説明 |
|---|---|
| `storyId` | sourceKey由来を含みうる内部Story ID（`Identifier_Specification.md`） |
| `episodeId` | 内部Episode ID |
| `sceneId` | 内部Scene ID |
| `blockId` | 内部Block ID（Normalized Story JSONのBlock IDと1対1） |
| `evidenceId` | 現状`blockId`と同値（`build_evidence_index_candidates.py`の実装、`Identifier_Specification.md` §8） |
| parser由来ID全般 | `_DLG{n}`/`_MONO{n}`/`_NAR{n}`/`_STAGE{n}`/`_UNKNOWN{n}`等のsuffix自体は安全（連番のみ）だが、prefixの`storyId`/`episodeId`部分にsourceKeyが含まれる |
| `sourceKey` | raw配置由来の識別子そのもの（`story_manifest.yaml`側で管理、`Story_ID_Policy_Decision.md`） |

## 3.2 B. 公開ID（Public-facing ID）

Wiki URL・promotion先ファイル名・公開表示に使ってよいID群。

| フィールド | 説明 |
|---|---|
| `publicStoryId` | `story_manifest.yaml`で人間が個別に確定する公開向けStory ID（`Story_ID_Policy_Decision.md` §7で採用決定済み、現状はrenderer側でEpisode page URLに部分利用） |
| `publicEpisodeId` | 公開向けEpisode ID |
| `publicEvidenceId`（未実装、本文書で提案） | 公開Evidence Index/Evidence page/Summary evidenceRefsで使う想定のEvidence単位ID（§6） |

## 3.3 C. 表示用label（Display label）

人間が読むための表示文字列。URLには使わない。

| フィールド | 説明 |
|---|---|
| `storyTitle` / `episodeSubtitle` / `displayTitle` | `story_manifest.yaml`由来の公式タイトル情報（`AI_CONTEXT.md` §3.8） |
| `metadataStatus` | タイトル情報の確定状況 |

**方針: タイトル由来のURL/IDは採用しない**（`Story_ID_Policy_Decision.md` §8.1と同じ理由。表記変更に弱い、日本語URL問題、DKBのevidence-first原則に反する）。

---

# 4. Options（保存先・主キーの選択肢比較）

## 4.1 案A: 現状維持

```text
knowledge/evidence/stories/{storyId}.yaml
```

Evidence Index内も内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）中心のまま。

- 長所: Normalized Story JSON/Extraction Resultとの照合が簡単、既存script変更が不要、evidenceRefsとの整合性が取りやすい
- 短所: sourceKey由来IDがPublic repoに残る、Git履歴に永続化される、`publicStoryId`導入の意味が薄くなる、公開Wiki用IDと内部trace IDが混ざる

## 4.2 案B: 保存ファイル名だけ`publicStoryId`にする

```text
knowledge/evidence/stories/{publicStoryId}.yaml
```

ただし内部entryは`storyId`/`evidenceId`等を維持。

- 長所: ファイル名・URLの見た目は改善する、変更範囲が比較的小さい
- 短所: YAML内部にはsourceKey由来IDが大量に残る（§2.2）、commit履歴リスクは解決しない、根本解決ではない

## 4.3 案C: Public Evidence Indexをpublic ID projectionとして保存する

保存先:

```text
knowledge/evidence/stories/{publicStoryId}.yaml
```

Public Evidence Index内では公開向けIDを中心にする。

- `storyId`は保持しない、または`internalTraceRef`のような非可逆・review限定の参照に隔離する
- `episodeId`は`publicEpisodeId`中心にする
- `evidenceId`は`publicEvidenceId`へ変換する（§6）
- 詳細な内部ID（sourceKey由来のものを含む）はPublic Evidence Indexから除外する
- 長所: Public repoにsourceKey由来IDを残しにくい、`publicStoryId`導入目的に合う、公開Wiki向けとして安全
- 短所: Normalized Story JSON/Extraction Resultとの照合にmapping layerが必要、evidenceRefsとの整合性を再設計する必要がある、rewrite/projection実装が必要

## 4.4 案D: Public Evidence Indexはcommitしない

Evidence Indexをworkspace生成のみとし、公開Wiki生成時だけローカルで渡す。repoにはEvidence Index自体を保存しない。

- 長所: Git履歴リスクを避けられる、すぐに安全
- 短所: 公開サイトの再現性が落ちる、CI/GitHub Pages/build processに乗せにくい、Knowledge Baseとしての蓄積が難しい

---

# 5. Adopted direction（採用方針）

- **案Aは採用しない**（sourceKey由来IDのGit履歴永続化・公開Wiki露出を放置することになる）
- **案Bも単独では採用しない**（ファイル名だけの変更では根本解決にならない、§2.2）
- **案Cを長期方針として採用する**。ただし実装には`publicEvidenceId`・public block IDの設計が前提として必要であり、本PRでは設計のみを行う
- **promotion再開（実データを`knowledge/evidence/stories/`へcommitすること）は、案Cの実装（少なくとも§12 Phase 1・Phase 2相当）が完了するまで停止する**
- **案Dは暫定回避策としては有効**（実際にPR #91で採った行動そのものが案D相当の運用である）が、最終方針にはしない。Knowledge Baseとしての永続的な蓄積という目的に反するため

**採用文言**: Public Evidence Indexは、公開repoに保存する場合、`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`を中心にしたprojectionとして保存する。内部trace ID（sourceKey由来の`storyId`/`episodeId`/`blockId`等）は、必要最小限のreview-only metadataに分離するか、`workspace/review_packets/evidence/`側（Internal Review Evidence Packet、未実装）に置く。

---

# 6. publicEvidenceId policy（`publicEvidenceId`方針）

## 6.1 現状の問題

- `evidenceId`は内部Block ID由来であり、sourceKey由来の`storyId`/`episodeId`を含む
- `publicStoryId`/`publicEpisodeId`は別途存在するが、`evidenceId`自体には反映されていない
- Summary `evidenceRefs`・Evidence page anchor・リンク表示は現状すべて内部`evidenceId`を使っている（§9）

## 6.2 候補比較

| 候補 | 内容 |
|---|---|
| A | `evidenceId`をそのまま公開する（現状） |
| B | `publicEvidenceId`を追加する（`evidenceId`は残す） |
| C | `evidenceId`を`publicEvidenceId`に置き換える（`evidenceId`自体を廃止） |
| D | `evidenceId`は内部専用、`publicEvidenceId`をリンク用に使う（B寄りだが公開Indexでは`evidenceId`を非表示にする） |

## 6.3 推奨

**候補Dに近い方向（`publicEvidenceId`追加＋Public Evidence Indexでは内部`evidenceId`を保持しない）を推奨する。**

- `publicEvidenceId`を追加する方向で検討する
- Public Evidence Index / Summary `evidenceRefs` / Evidence page anchorは`publicEvidenceId`を使う
- 内部`evidenceId`はPublic Evidence Indexでは保持しない、または`internalTraceRef`（§7）に隔離する
- ただし`publicEvidenceId` ⇔ 内部`evidenceId`のmappingはどこかで管理する必要があるため、実装は後続PRで行う（§12）

## 6.4 publicEvidenceId形式（決定）

**候補B（type別prefix付き連番）を採用する。**

```text
{publicEpisodeId}_{PREFIX}{sequence:04d}
```

例（匿名化済み`publicEpisodeId`を使用）:

```text
EVT_YYYYMMDD_NNN_E01_DLG0001
EVT_YYYYMMDD_NNN_E01_DLG0002
EVT_YYYYMMDD_NNN_E01_NAR0001
EVT_YYYYMMDD_NNN_E01_MONO0001
```

候補A（`{publicEpisodeId}_EVD0001`、種別非依存の連番）・候補C（`{publicEpisodeId}_E{sequence:04d}`、短縮形）は不採用とした。理由: `publicEvidenceId`はSummary `evidenceRefs`・Evidence page anchorとして人間が直接目にする機会が多く、既存の内部ID体系（`_DLG{n}`/`_NAR{n}`等、`Identifier_Specification.md` §5）とも見た目の一貫性を保てる候補Bの可読性を優先した。type変更時にIDが変わりうる短所は許容する（`publicEvidenceId`はcanonical IDではなく、あくまで生成時点のprojection結果であるため）。

## 6.5 evidenceType prefix mapping（決定）

| evidenceType | prefix | Public promotion対象 |
|---|---|---|
| `dialogue` | `DLG` | 対象（`Evidence_Index_Promotion_Policy.md` §4.1） |
| `monologue` | `MONO` | 対象 |
| `narration` | `NAR` | 対象 |
| `choice` | `CHO` | 対象 |
| `unknown` | `UNK` | 対象（件数次第でreview対象、同§4.1） |
| `stage_direction` | `STG` | **Public promotionでは原則未使用**（`--policy full`/`review`でのみ生成、同§3） |
| `speaker_label` | `SPK` | 将来対応時に検討（現状このevidenceTypeはEvidence Indexに存在しない、`Evidence_Index_Design.md` §8） |
| `scene` | `SCN` | 将来対応時に検討（本スクリプトはScene単位のentryを生成しない） |
| `episode` | `EP` | 将来対応時に検討 |
| `story` | `STORY` | 将来対応時に検討 |

`MONO`（`MONOLOGUE`の短縮）で表記を統一し、`MON`等の別表記は採用しない。`monologue`のBlock ID suffixが既に`_MONO{n}`であるため（`Normalized_Story_JSON.md`）、既存の内部ID命名慣習とも一致させた。

## 6.6 採番方針（決定）

- **Public promotion対象entry（`--policy public-default`でfilterされた後の出力）の表示順で、evidenceType別に連番を振る**
- `stage_direction`等の除外typeはpublicEvidenceId採番の対象に含めない。これにより、`stage_direction`をfilterで除外しても、`dialogue`/`narration`等の連番は詰まった状態で安定する（内部`blockId`の連番とは独立した採番空間になる）
- `publicEvidenceId`は**Public promotion用のprojection結果に対してのみ定義する**。`--policy full`/`review`（`stage_direction`を含む全件出力）については、当面`publicEvidenceId`を付与しない、または内部review用途の別命名空間とする（本文書では確定しない、§14未確定事項）
- `choice`のoption入れ子blockも、既存の`_iter_blocks_recursive`と同じ「出現順」でtype別連番に含める（Choice本体と入れ子dialogueが同じ`DLG`連番空間を共有するか、別空間にするかは実装PRで確定）
- 具体的な採番ロジック（`build_evidence_index_candidates.py`拡張か新規projection scriptか）は`evidence-index-public-id-projection`（§12 Phase 2）で実装する

## 6.7 projection実装状況（`feature/evidence-index-public-id-projection`で実施）

`scripts/project_evidence_index_public_ids.py`（新規script、`build_evidence_index_candidates.py`拡張ではなく独立scriptとして実装）を追加し、§6.4〜6.6で決定した形式・prefix mapping・採番方針を**Compatible projection（案A、§4.3案C路線の第一段階）**として実装した。

- **Compatible projectionのみ**: 既存の内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）は一切削除・改名しない。`publicEvidenceId`を追加するだけで、既存schema/loader/renderer/promotion scriptとの後方互換を維持する。内部IDを完全に取り除く"Public-safe projection"（案B）は`evidence-index-public-id-public-safe-projection`として別PRに委ねる
- **CLI**: `--input`/`--output`/`--mapping-output`/`--report`必須、`--schema`/`--policy`（デフォルト`public-default`）/`--strict`/`--quiet`任意。`--output`（projection結果のdirectory）・`--mapping-output`（内部ID⇔公開IDのmapping CSV）・`--report`（Markdown report）はいずれも`knowledge/evidence/`配下を指定するとexit code 2で拒否する
- **採番対象の絞り込み**: `--policy`で許可されたevidenceType（既定`public-default`＝`dialogue`/`monologue`/`narration`/`choice`/`unknown`）のentryのみ`publicEvidenceId`を採番する。`stage_direction`等policy対象外のtypeは既定では採番せず素通し（entry自体は出力に残る）、`--strict`指定時のみblocking errorにする
- **blocking条件**: documentにpublicStoryIdを持つentryが1件も無い、entryにpublicEpisodeIdが欠落している（evidenceTypeが`unknown`でも同様に必須）、既存`publicEvidenceId`が再生成結果と一致しない、`publicEvidenceId`が重複する、projected出力がschema検証に失敗する、のいずれかに該当するとexit code 1
- **exit codes**: `0`成功、`1`projection validation失敗、`2`IO/config error（安全確認拒否含む）
- **常に出力を書く**: `promote_evidence_index.py`のdry-run既定パターンとは異なり、本scriptは`--output`/`--mapping-output`/`--report`をworkspace配下の安全なpathである限り常に書き出す（blocking issueがあってもreview用に出力する）。ただし**Compatible projectionの出力は常にnot promotion-ready**であり、`promote_evidence_index.py --execute`には使わないこと
- **mapping output commit禁止**: `--mapping-output`のCSVは内部ID（`storyId`/`episodeId`/`evidenceId`等）と公開IDを1行に並べて記録するため、常にworkspace配下に留め、**commit禁止**とする。Internal Review Evidence Packet（`internal-review-evidence-packet-design`、未実装）の候補データとして位置づける
- `tests/scripts/test_project_evidence_index_public_ids.py`（28件）で、prefix生成・per-episode/per-type採番・publicStoryId/publicEpisodeId欠落・既存publicEvidenceIdの一致/不一致・重複検出・mapping/report出力・directory/file入力・projected出力のschema検証・入力ファイル不変・knowledge/evidence/への書き込み拒否を検証した

## 6.8 public-safe projection実装状況（`feature/evidence-index-public-id-public-safe-projection`で実施）

§4.3案C路線の第二段階として、`scripts/project_evidence_index_public_ids.py`に`--projection-mode {compatible,public-safe}`（デフォルト`compatible`）を追加し、**Public-safe projection（案B）**を実装した。

- **compatible modeの位置づけを明文化**: `--projection-mode compatible`（既定）は§6.7のCompatible projectionそのものであり、**migration/debugging/mapping確認用であって、Public promotion対象ではない**。既存の28件のcompatible modeテスト・既存挙動は本PRで一切変更していない
- **public-safe modeのfield rewrite方針**:
  - `evidenceId`の値を`publicEvidenceId`へ、`storyId`の値を`publicStoryId`へ、`episodeId`の値を`publicEpisodeId`へ置換する（schema互換のため、`evidenceId`/`storyId`/`episodeId`自体はrequired fieldとして維持しつつ、値だけを公開向けIDにする。§10.4で述べた「required化は別途検討」を待たずにschema互換を保つための現実的な選択）
  - `publicEvidenceId`/`publicStoryId`/`publicEpisodeId`は元の値のままentryに保持する（rewriteされた`evidenceId`等と重複するが、読み手が「これはpublic-safe projectionである」と機械的に確認できるようにするため）
  - `sceneId`/`blockId`/`referencedBy`/document-level`generatedFrom`は出力しない（`referencedBy.summaries.storyId`/`referencedBy.candidates.candidateId`は現行schemaでは内部ID/内部参照キーのままであり、公開向けの代替フィールドが存在しないため、本PRのスコープでは安全側に倒して除去する。将来`referencedBy`を公開ID中心に再設計する場合は別PRで扱う）
  - `speaker`は`resolutionStatus: resolved`のentryのみ保持し、`unresolved`/`ambiguous`/`unknown`（「不明人物」等のplaceholder表示を含みうる）は保持しない
  - `notes`/`relatedEntities`はそのまま保持する（`relatedEntities`はcanonical character/location等の辞書IDであり、sourceKey由来の内部trace IDではないため）。ただし§6.9のexposure scanが最終防波堤として機能する
  - `publicEvidenceId`を持たないentry（`--policy`対象外のevidenceType、既定では`stage_direction`等）はpublic-safe出力から除外する。schema上`evidenceId`はrequiredかつ`^[A-Z][A-Z0-9_]*$`のpattern一致必須のため、値を持たないentryをそのまま出力に含めることができないという技術的制約に加え、そもそも`stage_direction`はPublic promotion対象外という既存方針（`Evidence_Index_Promotion_Policy.md` §3/§4.2）とも整合する
- **出力ファイル名方針**: public-safe modeの出力ファイル名は`{publicStoryId}.yaml`（1 document = 1 publicStoryId）とする。1つの入力document内に複数の異なるpublicStoryIdが混在する場合、または複数の入力ファイルが同じpublicStoryIdへ解決される場合（出力ファイル名の衝突）は、いずれもblocking errorとする。**推測によるファイル分割・自動マージは行わない**
- **sourceKey由来ID exposure scan（§6.9で詳述）**: public-safe出力の直列化文字列に対し、入力entryのstoryId/episodeId/evidenceId/sceneId/blockIdの値のうち、対応する公開ID値と異なり4文字以上のものが残っていないかをscanし、検出した場合はblocking errorにする
- **publicEpisodeId欠落の扱い**: compatible modeと同様、public-safe modeでもentryの`publicEpisodeId`欠落はblocking errorのままとする。**自動補完・推測は行わない**（次PR候補`evidence-index-public-episode-id-assignment`、§12 Next参照）
- **mapping output**: `--mapping-output`はpublic-safe modeでも内部ID⇔公開IDのmappingを引き続き出力する（compatible modeと同じ列構成）。Internal Review Evidence Packet候補データであり、**commit禁止**は不変
- **report**: `projection mode`・`public-safe field rewrite summary`（rewritten ID fields count/removed internal fields count/excluded entry count）・`internal ID exposure scan result`・`promotion readiness`（`compatible`は常に`not-promotion-ready`、`public-safe`はvalidation/exposure scanをすべて通過した場合のみ`promotion-candidate`）を追加した
- `tests/scripts/test_project_evidence_index_public_ids.py`に23件のpublic-safe modeテストを追加した（field rewrite、filename policy、internal ID exposure、mapping、schema validation、promotion readiness reporting）。既存29件のcompatible modeテストは無変更のまま通過を確認した
- 匿名化実データサンプル（`workspace/evidence_index_dry_runs/first_reviewed_sample/default/stories`）へのpublic-safe modeでのdry-runでは、Episode 2の`publicEpisodeId`未確定によりcompatible mode時（PR #94）と同様にblocking FAILすることを確認した（想定どおりの安全側挙動、§6.7の既知の制約を引き継ぐ）

## 6.9 sourceKey由来ID exposure scanの実装詳細

- 収集対象: 入力entryの`storyId`/`episodeId`/`evidenceId`/`sceneId`/`blockId`の値
- 除外対象: `publicStoryId`/`publicEpisodeId`/`publicEvidenceId`と一致する値（偶然の一致は安全と判断する）
- 閾値: 4文字未満の値は誤検出防止のため対象外とする（実データの内部IDはいずれも十分に長いため、この閾値で実運用上の取りこぼしは生じないと判断した）
- scan対象: public-safe出力ドキュメントを直列化した文字列全体（entryの`notes`/`speaker.displayName`/`relatedEntities`等、field rewriteの対象外として保持したfield経由の混入も検出できるようにするため）
- 検出時の扱い: 1件でも検出すればblocking error（exit code 1）とし、reportに検出件数・該当内部ID一覧を記録する
- **本scanはヒューリスティックであり、実sourceKeyの一覧と突き合わせる方式ではない**（`Evidence_Index_Public_ID_Policy.md` §14の未確定事項のまま）。将来的な精度向上は別PRで検討する

## 6.10 Public ID Registry統合実装（`feature/evidence-index-public-id-registry-integration`で実施）

`scripts/project_evidence_index_public_ids.py`に`--registry`/`--registry-schema`を追加し、`docs/architecture/06_AI/Public_ID_Registry_Design.md`で長期方針として採用したPublic ID Registryを実際にprojectionへ統合した。詳細は`Public_ID_Registry_Design.md` §6.3・§7.7を参照。

- Registry lookupは`publicStoryId + episodeOrder`で行い、episodeOrderは`scripts/check_public_episode_ids.py`と同じ「内部episodeIdの出現順（1始まり）」ロジックを共有importで再利用する
- 欠落`publicEpisodeId`はRegistryに該当があれば補完（entryへ直接書き込み）、無ければ引き続きblocking
- 既存`publicEpisodeId`とRegistry値が矛盾する場合はblocking、Registryに該当が無い場合はwarning（PASSは維持）
- Registry補完後に`publicEvidenceId`を生成するため、補完されたepisodeのentryも正しいprefixの`publicEvidenceId`を得る
- compatible/public-safe両モードで同じRegistry補完ロジックを共有する
- mapping CSVに`episodeOrder`/`publicEpisodeIdSource`/`registryMatched`/`registryConflict`/`registryPublicEpisodeId`列を追加、reportに`## Registry`/`## Warnings`sectionを追加した
- 匿名化実データサンプルで、Episode 1（92 entries、input由来）+ Episode 2（95 entries、Registry補完）の**187 entries全件がPublic-safe projectionを通過**し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`ともPASSすることを確認した（`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.6）
- **実Registryへの実データ追加・renderer変更・実promotion retryはいずれも行っていない**

---

# 7. internalTrace policy（内部trace情報の扱い方針）

Public Evidence Indexでも、Normalized Story JSON/Extraction Resultとの照合・デバッグ・review用途のため、内部trace情報が必要になる場合がある。

## 7.1 候補比較

| 候補 | 内容 |
|---|---|
| A | 内部IDを完全に除外する |
| B | `internalTrace`のような専用fieldとして保持する |
| C | hash化して保持する（可逆性を犠牲にする） |
| D | `workspace/review_packets/evidence/`（Internal Review Evidence Packet、未実装）にのみ保持する |

## 7.2 推奨

- 公開repoに保存するPublic Evidence Indexでは、sourceKey由来の内部IDを**そのまま大量に保持しない**（候補Aに近い方向）
- ただし完全除外すると照合不能になり運用が困るため、**mapping strategyを先に設計してから除外を検討する**。具体的には、`internalTraceRef`のような1個の非可逆または短い管理ID（例: `publicEvidenceId`→内部`evidenceId`のmapping table）を`workspace/review_packets/evidence/`側に保持する運用（候補D寄り）を軸に検討する
- 「Public Evidence Index本体には内部IDを持たせない」「照合が必要な場合はInternal Review Evidence Packet（`internal-review-evidence-packet-design`、未実装）側のmapping tableを参照する」という役割分担を軸とする
- mapping table自体の生成・保管場所・破棄ポリシーは、`internal-review-evidence-packet-design`の実装時に合わせて設計する（本文書のスコープ外、§14参照）

---

# 8. Summary evidenceRefsへの影響

## 8.1 現状

Story Summary/Episode Summaryの`evidenceRefs`（`schemas/story_summary.schema.json`、`EVIDENCE_REF_PATTERN`）は、内部`evidenceId`と同じID形式（`^[A-Z][A-Z0-9_]*$`）を参照する設計になっている。reviewed/approvedなSummaryが内部`evidenceId`を参照している場合、Public Evidence Indexが`publicEvidenceId`中心に切り替わると、そのままではリンクできなくなる。

## 8.2 検討事項

- Summary schemaの`evidenceRefs`は最終的に`publicEvidenceId`を参照するべきか
- 既存のsynthetic fixture（`tests/fixtures/story_summaries/`）をどう扱うか（大量書き換えは本PRのNon-goals、§14）
- reviewed/approvedなSummaryのevidenceRefsが内部IDのままだと、public化されたEvidence Indexにリンクできない（unresolved扱いになる、`Evidence_Index_Design.md` §10の既存の安全側フォールバックは維持される）
- migrationが必要か、dual-fieldにするか

## 8.3 推奨

```yaml
# 候補: dual-fieldではなく、公開IDへの一本化を推奨
evidenceRefs:
  - EVT_YYYYMMDD_NNN_E01_EVD0001   # publicEvidenceId
```

- Summary `evidenceRefs`は最終的に`publicEvidenceId`を参照する方針とする（dual-field化は複雑さが増すため採用しない）
- 内部evidence refs（review用途）は、Summary本体ではなくInternal Review Evidence Packet側のmapping経由で必要な場合のみ参照する
- 既存fixtureの更新は本PRでは行わず、`evidence-index-public-id-projection`実装時に合わせて行う
- migrationが必要になる実データSummaryはまだ存在しない（`knowledge/summaries/stories/`は`.gitkeep`のみ）ため、影響は限定的

**実装レベルの詳細化（`summary-public-id-projection-design`で実施）**: 上記の推奨方針を、Summary側projection script（`scripts/project_story_summary_public_ids.py`、新設予定）の具体的な変換仕様として`docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md` §6に落とし込んだ。Evidence Index public-safe projectionの`--mapping-output`CSVをそのまま`--evidence-mapping`として入力し、内部blockId参照を`publicEvidenceId`参照へ変換する。該当storyがEvidence Index未昇格の場合は`evidenceRefs`を空にして昇格可とし、reportにwarningとして記録する。

---

# 9. Renderer / pathへの影響

## 9.1 現状の実装（確認結果）

- `agents/wiki_generator/paths.py`の`evidence_page_path(story_id, public_story_id)`は、**Evidence pageのファイル名・URL自体は既に`publicStoryId`優先**（`resolve_story_path_id`を再利用、`story_page_path`と同じ方針）
- 一方、`agents/wiki_generator/renderer.py`の`render_evidence_page`は、Evidence page内の各entry見出しに`### {entry.evidence_id}`（内部`evidenceId`）を使い、`_evidence_anchor(evidence_id)`（`evidence_id.lower()`）でanchorを生成している
- Summary `evidenceRefs`のリンク化（`_evidence_ref_link`）も、リンク表示テキストに内部`evidenceId`をそのまま使う（`` [`{evidenceId}`](../{path}#{anchor}) ``）
- **つまり、Evidence pageのURLだけは`publicStoryId`化されているが、ページ内の見出し・リンクテキストは内部`evidenceId`（sourceKey由来を含む）がそのまま公開Wiki上に表示される。これはPR #91で判明した問題の一部であり、YAMLファイルのcommit問題とは別に、rendererレベルでも修正が必要**

## 9.2 推奨

- Public向けrendererは`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`中心にする（Evidence page見出し・anchor・Summary evidenceRefsリンクテキストすべて）
- 内部`storyId`とのjoinにはmapping layerを使う（§7のInternal Review Evidence Packet側mapping、または`render_wiki.py`実行時にのみ一時的に保持するin-memory mapping）
- `render_wiki.py --evidence-index`は、**public ID projection済みのEvidence Index**を入力として受け取ることを前提にする（projectionされていない内部ID中心のEvidence Indexをそのままrenderする現行動作は、public promotion用途では非推奨とする）
- Merged Knowledge Collection側の`storyId`とのjoinは、`publicStoryId`が一致しない場合の扱い（既存の`resolve_story_summary`と同じ「矛盾時は安全側でNone」パターン）を踏襲する

**本PRではrenderer/paths.pyの変更は行わない**（§13 Non-goals）。上記は実装PR（`evidence-index-public-id-projection`）のスコープとして記録する。

## 9.3 実装状況（`feature/evidence-index-public-id-renderer-switch`で実施）

§9.2で示した推奨方針のうち、Evidence page見出し・anchor・Summary `evidenceRefs`リンクの`publicEvidenceId`中心切替を実装した。

- `agents/wiki_generator/evidence_index.py`に`display_evidence_id(entry)`（`publicEvidenceId`優先、無ければ`evidenceId`にfallback）・`build_public_evidence_id_index`（`publicEvidenceId -> EvidenceIndexEntry`索引、`build_evidence_id_index`と同じ「後勝ち」方針）・`resolve_evidence_entry(lookup, ref_id)`（`publicEvidenceId`索引→内部`evidenceId`索引の順でfallback解決）を追加した
- `EvidenceIndexLookup`に`by_public_evidence_id`・`by_public_story_id`を追加し、`build_evidence_index_lookup`で組み立てるようにした
- `agents/wiki_generator/renderer.py`の`_render_evidence_entry`見出し（`### {display_evidence_id(entry)}`）・`_format_evidence_ref_display`（`resolve_evidence_entry`で解決したentryの`display_evidence_id`をリンク表示テキスト・anchor双方に使う）を変更した。`_evidence_anchor`関数自体は変更していない（引数に渡す文字列がevidenceIdからdisplay idに変わっただけ）
- Summary `evidenceRefs`の値が内部`evidenceId`のままでも、`publicEvidenceId`のままでも（Public-safe projection outputでは両者が同値になる）、`resolve_evidence_entry`が両方のケースを解決できる
- **Evidence Index lookupの新たな課題を発見・修正**: Public-safe projection outputでは内部`storyId`自体が`publicStoryId`の値へ置換されるため、merged knowledge collection側が保持する内部`storyId`だけではStory pageの「Review Links → Evidence index」導線（`evidence_index_lookup.by_story_id[story_id]`）が引けなくなる。`resolve_story_evidence_entries(lookup, story_id, public_story_id)`（内部`storyId`で見つからなければ`publicStoryId`側の索引へfallback）を追加し、`render_story_page`側で使うようにした
- `evidence_page_path`（`agents/wiki_generator/paths.py`）自体は変更していない。既に`publicStoryId`優先でファイル名を決定しており（§9.1で確認済み）、この方針で問題ないことを再確認した
- `tests/wiki/test_evidence_index.py`・`tests/wiki/test_wiki_renderer.py`に合成テストを追加（見出し/anchor/リンクのpublicEvidenceId優先・fallback、`resolve_story_evidence_entries`のpublicStoryIdフォールバック含む）。既存テストは無変更のまま全PASSを確認した
- 匿名化実データサンプル（Public-safe projection、187 entries）を`render_wiki.py --evidence-index`でrenderし、Evidence page（`evidence/{publicStoryId}.md`）の見出し・anchorが`publicEvidenceId`になり、内部`storyId`/`episodeId`/`sceneId`/`blockId`がEvidence page内に一切表示されないことを確認した（詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.7）
- **renderer切替後も、実promotion再開・`promote_evidence_index.py --execute`の実行はまだ行わない**（renderer切替は実promotionの前提条件の1つに過ぎず、次はfirst reviewed sample retryまたはpromotion copy/policy調整）

---

# 10. Schemaへの影響

`schemas/evidence_index.schema.json`の変更要否を整理する。

## 10.1 検討項目

- `publicEvidenceId`の追加（optional）
- `evidenceId`を`internalEvidenceId`へ改名するか（破壊的変更になるため慎重に判断）
- `storyId`/`episodeId`を`internalTrace`相当のsub-objectへ移すか
- `publicStoryId`/`publicEpisodeId`をrequired化するか（現状optional、`Evidence_Index_Design.md`のデータモデル案）
- `internalTrace`フィールドを追加するか
- Public Evidence Index用schemaとInternal Evidence Index用schemaを分けるか

## 10.2 推奨

- **急に既存schemaを破壊しない**（`evidenceId`必須フィールドの削除・改名は既存fixture・既存loader・既存renderer全てに影響するため、段階移行が必要）
- 後続PR（`evidence-index-public-id-schema-design`）で`publicEvidenceId`のoptional追加から始める
- その後、実際にpublic promotionを再開するタイミングで、Public Evidence Index側のみ`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`をrequired化する運用・schema制約を検討する（`visibility.rawTextIncluded`の`const: false`と同様の「Public Evidence Indexであることの機械的な保証」パターン）
- Internal Review Evidence Packet用のschemaは別途用意する（`internal-review-evidence-packet-design`、未実装）。Public Evidence Index schemaとは混在させない（`Evidence_Index_Design.md` §5.3の既存方針を踏襲）

## 10.3 実装状況（`feature/evidence-index-public-id-schema-design`で実施）

`schemas/evidence_index.schema.json`の`EvidenceIndexEntry`定義に`publicEvidenceId`をoptional（`oneOf: [pattern string, null]`、既存`publicStoryId`/`publicEpisodeId`と同じパターン`^[A-Z][A-Z0-9_]*$`）として追加した。`evidenceId`/`storyId`/`episodeId`は引き続きrequiredのまま変更していない。`agents/wiki_generator/evidence_index.py`の`EvidenceIndexEntry`dataclassと`_parse_entry`にも`public_evidence_id`（デフォルト`None`）を追加し、loaderが新フィールドを読み込めるようにした（`agents/wiki_generator/evidence_index.py`は本PRのNon-goals対象外の最小限の追加的変更、renderer/paths.py/promotion scriptは変更していない）。schema tests・loader testsを追加し、既存fixture（`tests/fixtures/evidence_index/valid_evidence_index.yaml`）に合成`publicEvidenceId`を1件追加した。

## 10.4 publicStoryId / publicEpisodeId required化タイミング（整理）

- **本PRでは`publicStoryId`/`publicEpisodeId`のrequired化は行わない**（既存の任意フィールドのまま）
- 「Public promotion-ready（昇格可能）なEvidence Index」では、`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`が実質必須という運用上の期待値をdocsで明記するに留める（schema上のrequired制約ではなく、`check_evidence_index_promotion.py`側のpromotion check項目としてのenforcementを想定、§11参照）
- schema上のrequired化自体は、Public Evidence Index専用schemaを分離するタイミング（§10.2の3点目）と合わせて後続PRで判断する

---

# 11. Promotion copyへの影響

`scripts/promote_evidence_index.py`（`docs/runbooks/Evidence_Index_Promotion_Copy.md`）の現状と今後の方針を整理する。

## 11.1 現状

- `storyId`（entries内の`entries[].storyId`から抽出）から`{storyId}.yaml`というtarget filenameを決定している
- 1 file 1 story方針を強制している
- source file名と抽出した`storyId`の整合性は確認していない（filenameは`storyId`から機械的に決定するため、source file名自体は問わない設計）

## 11.2 今後（本PRでは実装しない）

- target filenameは`publicStoryId`を優先、またはpublic ID projectionが完了したEvidence Indexに対してのみ`publicStoryId`を必須にする
- 内部`storyId`由来のfilenameでのpromotionは禁止する（`_extract_story_id`相当のロジックを`_extract_public_story_id`に置き換え、`publicStoryId`が無い場合はblocking errorにする）
- sourceKey由来ID混入チェックを`check_evidence_index_promotion.py`のpromotion checkに追加する可能性を検討する（例: `entries[].evidenceId`/`storyId`等に`publicStoryId`以外のraw文字列パターンが含まれていないかのscan）
- human review noteのテンプレート（`docs/templates/evidence_index_promotion_review_template.md`）に「Public ID projection済みであることを確認」チェック項目を追加する
- promotion対象は、**projection済み（`publicEvidenceId`中心の）Evidence Indexのみ**とする（projectionされていない候補は`check_evidence_index_promotion.py`の時点でblocking errorにする方向性を検討する）

これらは`evidence-index-public-id-projection`実装後に、`promote_evidence_index.py`/`check_evidence_index_promotion.py`側の変更として別PRで行う。

---

# 12. Implementation phases（実装フェーズ案）

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 0: `evidence-index-promotion-target-filename-policy`（PR #92） | 問題整理・ID分類・案A/B/C/D比較・採用方針決定・publicEvidenceId/internalTrace方針の設計 | 完了（設計のみ） |
| Phase 1: `evidence-index-public-id-schema-design`（本PR） | `publicEvidenceId`の形式・prefix mapping・採番方針の確定、`schemas/evidence_index.schema.json`へのoptional追加、loader対応 | **完了（本PR、schema/loaderの最小変更のみ）** |
| Phase 2: `evidence-index-public-id-projection`（本PR） | Compatible projection（案A）の実装。`scripts/project_evidence_index_public_ids.py`で内部ID→公開IDのmapping生成、`publicEvidenceId`の実際の付与を行う（内部IDは削除しない） | **完了（本PR）** |
| Phase 2.5: `evidence-index-public-id-public-safe-projection`（本PR） | Public-safe projection（案B）の実装。`scripts/project_evidence_index_public_ids.py`に`--projection-mode public-safe`を追加し、内部IDを公開ID中心へ置換・除去したPublic Evidence Index本体を生成する | **完了（本PR、§6.8/§6.9参照）** |
| Phase 2.6: `evidence-index-public-episode-id-assignment` | 未確定`publicEpisodeId`の検出・割当候補提案の設計・実装。`docs/architecture/06_AI/Public_ID_Registry_Design.md`（新設）で役割・採番方針・永続化場所（Public ID Registry）を設計し、`scripts/check_public_episode_ids.py`（assignment候補提案script、常に人間review必須）を実装した | 完了 |
| Phase 2.7: `evidence-index-public-id-registry-integration`（PR #97） | Public ID Registryを`project_evidence_index_public_ids.py`へ入力として渡し、欠落`publicEpisodeId`を参照・補完できるようにする | 完了 |
| Phase 3: `evidence-index-public-id-renderer-switch`（本PR） | renderer/paths.py対応。Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替え | **完了（本PR、§9.3参照）** |
| Phase 4: `promote_evidence_index.py`/`check_evidence_index_promotion.py`対応 | target filenameの`publicStoryId`必須化、projection済みEvidence Indexのみpromotion対象にする、sourceKey混入scanの追加検討 | 未着手（§11.1の通り、Public-safe projection出力は`storyId`の値自体が`publicStoryId`に置換されるため、`promote_evidence_index.py`を変更しなくても正しい`{publicStoryId}.yaml`が生成されることをPhase 5で確認済み） |
| Phase 5: `evidence-index-promotion-first-reviewed-sample-retry` | Phase 1〜4完了後、実データ1 storyの初回昇格を再試行する | **完了（実Public ID Registry entry・実Evidence Index 1件を`knowledge/evidence/stories/`へ追加済み）** |
| Phase 6: `internal-review-evidence-packet-design` | 内部trace ID・mapping tableをInternal Review Evidence Packet側で扱う詳細設計 | 未着手 |

**promotion再開（`knowledge/evidence/stories/`への実データcommit）は、少なくともPhase 2.5（Public-safe projection実装）およびPhase 3（renderer切替）が完了するまで行わない。** Public-safe projectionがvalidation/exposure scanを通過し`promotion-candidate`と判定されても、renderer側がまだ内部`evidenceId`中心のままであるため、実promotionは行わない。**Phase 3完了後、Phase 5（本PR）でこの条件を満たした実データ1 storyのpromotionを実施した。**

---

# 13. Non-goals

`evidence-index-promotion-target-filename-policy`（PR #92、本文書の初版）時点でのNon-goals:

- 実Evidence Indexのcommit
- `knowledge/evidence/stories/`への実データ昇格
- `publicEvidenceId`のschema実装 → **`feature/evidence-index-public-id-schema-design`で最小実装済み**（optional追加のみ、§10.3参照）
- public ID projection実装（rewrite script等）
- ID rewrite実装
- `scripts/promote_evidence_index.py`の変更
- `scripts/check_evidence_index_promotion.py`の変更
- `scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`の変更 → **`feature/evidence-index-public-id-schema-design`で最小変更済み**（`publicEvidenceId`のoptional追加のみ、既存required構成は不変）
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- Evidence page anchorの変更
- `schemas/story_summary.schema.json`（Story Summary schema）の変更
- 既存fixtureの大量変更・migration
- Internal Review Evidence Packet生成
- raw text review packet生成
- Evidence Index batch promotion

`evidence-index-public-id-schema-design`（PR #93）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- public ID projection実装（`publicEvidenceId`の実際の値の付与・rewrite script） → **`feature/evidence-index-public-id-projection`でCompatible projection（案A）のみ実装済み**（§6.7参照）
- ID rewrite実装
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更（Evidence page anchor・Summary evidenceRefsリンク化ロジックは無変更）
- `schemas/story_summary.schema.json`の変更
- 既存fixtureの大量変更・migration（合成fixtureへの`publicEvidenceId`追加は1件のみの最小限）
- `publicStoryId`/`publicEpisodeId`のrequired化
- `evidenceId`のrequired解除
- Internal Review Evidence Packet生成

`evidence-index-public-id-projection`（本PR）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- **Public-safe projection（案B）実装**: 内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）の完全除去。本PRのCompatible projection（案A）は内部IDを保持したまま`publicEvidenceId`を追加するのみ（次PR候補`evidence-index-public-id-public-safe-projection`）
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更（Evidence page見出し・anchor・Summary evidenceRefsリンクの`publicEvidenceId`中心切替は次PR候補`evidence-index-public-id-renderer-switch`）
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`の変更（projection済みEvidence Indexのみをpromotion対象にする制約は未実装）
- `promote_evidence_index.py --execute`の実行、実promotion retry（次PR候補`evidence-index-promotion-first-reviewed-sample-retry`）
- Internal Review Evidence Packet生成（mapping CSVの出力自体は実装したが、正式なInternal Review Evidence Packetとしての設計・保管場所確定は次PR候補`internal-review-evidence-packet-design`）
- `schemas/evidence_index.schema.json`の変更（既存schemaのまま、追加フィールドなし）

`evidence-index-public-id-public-safe-projection`（本PR）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- `promote_evidence_index.py --execute`の実行、実promotion retry（次PR候補`evidence-index-promotion-first-reviewed-sample-retry`）
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更（Evidence page見出し・anchor・Summary evidenceRefsリンクの`publicEvidenceId`中心切替は次PR候補`evidence-index-public-id-renderer-switch`）
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`の変更（既存schemaのまま、破壊的変更なし。`evidenceId`/`storyId`/`episodeId`のrequired解除は行っていない）
- `schemas/story_summary.schema.json`の変更、Summary fixtureのmigration
- `publicEpisodeId`の自動補完・推測（次PR候補`evidence-index-public-episode-id-assignment`）
- `story_manifest.yaml`の変更
- Internal Review Evidence Packet生成

`evidence-index-public-episode-id-assignment`（本PR）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- `promote_evidence_index.py --execute`の実行、実promotion retry
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- `publicEpisodeId`の自動補完・本番反映（`scripts/check_public_episode_ids.py`は候補を提案するのみで、常に人間reviewを必須とする）
- `story_manifest.yaml`の実データ変更
- 実Public ID Registryへの実データ追加（`schemas/public_id_registry.schema.json`は追加したが、`knowledge/public_ids/`への実データ投入は行っていない）
- `scripts/project_evidence_index_public_ids.py`/`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`の破壊的変更
- Internal Review Evidence Packet生成

詳細は`docs/architecture/06_AI/Public_ID_Registry_Design.md`を参照。

`evidence-index-public-id-registry-integration`（PR #97）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- `promote_evidence_index.py --execute`の実行、実promotion retry
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- `publicEpisodeId`の自動採番・自動本番反映（Registry補完は人間review済みRegistryの値を再利用するのみ）
- `story_manifest.yaml`の実データ変更
- 実Public ID Registryへの実データ追加
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`/`schemas/public_id_registry.schema.json`の破壊的変更
- Internal Review Evidence Packet生成

`evidence-index-public-id-renderer-switch`（本PR）でも以下は行っていない:

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- 実Public ID Registryへの実データ追加
- `promote_evidence_index.py --execute`の実行、実promotion retry
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`本体の変更（`agents/wiki_generator/`側のみ変更）
- Public ID Registry schema変更
- `schemas/evidence_index.schema.json`の破壊的変更
- `schemas/story_summary.schema.json`の変更、Summary fixtureの全体migration
- `publicEpisodeId`の自動採番・自動本番反映
- `story_manifest.yaml`の実データ変更
- Episode page変更（Evidence page/Summary evidenceRefsのみが対象）
- Internal Review Evidence Packet生成

`evidence-index-promotion-first-reviewed-sample-retry`（本PR）で以下を実施した:

- `knowledge/public_ids/story_public_ids.yaml`への実Public ID Registry entry追加（1 story分のみ）
- 実データ1 story（187 entries、匿名化表記）の`knowledge/evidence/stories/{publicStoryId}.yaml`への初回昇格（`promote_evidence_index.py --execute`）

本PRでも以下は行っていない:

- 複数story分のEvidence Index/Registry追加、batch promotion
- `scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/project_evidence_index_public_ids.py`/`scripts/check_public_episode_ids.py`本体の変更
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- Public ID Registry/Evidence Index schema変更
- `story_manifest.yaml`の実データ変更・再normalize/merge
- Internal Review Evidence Packet生成

---

# 14. Open questions（未確定事項）

- ~~`publicEvidenceId`の具体的な採番ルール~~ → **`feature/evidence-index-public-id-schema-design`で決定済み**（§6.4〜6.6、type別prefix付き連番）
- ~~`choice`のoption入れ子blockの採番空間（本体と共有か別空間か）~~ → **`feature/evidence-index-public-id-projection`で確定**: 本scriptはEvidence Index entries配列をflatなリストとして扱い、入れ子構造の解決は行わない（`build_evidence_index_candidates.py`側で既にflat化されたentries順序をそのまま採番順として使う）。choice本体とoption入れ子blockが別entryとして存在する場合、両者は同じ`(publicEpisodeId, evidenceType)`連番空間を共有する
- ~~`publicEvidenceId`の採番が、同一storyの複数回のdry-run生成間で安定するか~~ → **`feature/evidence-index-public-id-projection`で確認**: 採番は入力entriesの出現順のみに依存する決定的なロジックのため、入力の順序が変わらない限り再現可能。ただし入力（`build_evidence_index_candidates.py`の出力）自体の順序が変われば`publicEvidenceId`も変わりうる（§6.4の既知の制約通り）
- `internalTrace`/mapping tableの生成方法（`build_evidence_index_candidates.py`の拡張か、別scriptか）
- mapping tableの保管場所・アクセス制御（`workspace/review_packets/evidence/`が適切か、`internal-review-evidence-packet-design`との統合方法）
- 既存の`evidenceId`（内部ID）を将来的に完全廃止するか、常に保持しつつPublic Evidence Indexでのみ非表示にするか
- ~~`check_evidence_index_promotion.py`のsourceKey混入scanをどう実装するか~~ → **`feature/evidence-index-public-id-public-safe-projection`で部分的に対応**: `scripts/project_evidence_index_public_ids.py`の`--projection-mode public-safe`側で、入力entryの内部ID値（公開IDと異なり4文字以上のもの）に基づくヒューリスティックscanを実装した（§6.9）。ただし`check_evidence_index_promotion.py`自体は本PRでは変更していない（Non-goals）ため、`story_manifest.yaml`の`sourceKey`一覧との突き合わせ方式への発展や、promotion check側への統合は引き続き未確定
- MAIN/RAID/OTHER/CHARACTERカテゴリでも同じ問題が起きるか（`Story_ID_Policy_Decision.md` §6の通り、EVENT/RAIDが優先対象、MAINは現行IDが既に短く意味を持つため影響が小さい可能性がある）
- Public Evidence Indexのschema変更（`publicEvidenceId`必須化等）をいつrequired化するか、既存Internal運用（`full`/`review` policy）との互換性をどう保つか
- `--policy full`/`review`（`stage_direction`含む全件出力）に対して`publicEvidenceId`を付与するか、Public promotion専用のprojectionにのみ付与するか（§6.6で「本文書では確定しない」とした点）
- `publicEvidenceId`の採番が、同一storyの複数回のdry-run生成間で安定するか（`build_evidence_index_candidates.py`の実行結果が決定的であることに依存する。現状の実装はBlockの出現順を保つため理論上は安定するが、実装PRで確認が必要）
- ~~実データで`publicEpisodeId`が未確定のepisodeをどう検出・割当するか~~ → **`feature/evidence-index-public-episode-id-assignment`で設計・最小実装済み**: `docs/architecture/06_AI/Public_ID_Registry_Design.md`で役割・採番方針（`{publicStoryId}_E{episodeOrder:02d}`）・永続化場所（長期的にはPublic ID Registry、当面`story_manifest.yaml`が引き続きsource of truth）を整理し、`scripts/check_public_episode_ids.py`で割当候補の検出・提案（人間review必須）を実装した
- ~~`project_evidence_index_public_ids.py`とRegistryの本格統合~~ → **`feature/evidence-index-public-id-registry-integration`で実装済み**: `--registry`/`--registry-schema`を追加し、欠落`publicEpisodeId`をRegistryから補完（自動採番ではなく、人間review済みRegistry値の再利用のみ）できるようにした。実Registryへの実データ追加は引き続き未着手
- `episodeOrder`の正式な根拠（`story_manifest.yaml`の`episodeNumber`との一致保証、episode追加・順序変更時のmigration policy）は`Public_ID_Registry_Design.md` §8で未確定のまま持ち越し
- ~~Evidence page見出し・anchor・Summary evidenceRefsリンクの`publicEvidenceId`中心切替~~ → **`feature/evidence-index-public-id-renderer-switch`で実装済み**（§9.3参照）。`display_evidence_id`/`resolve_evidence_entry`/`resolve_story_evidence_entries`を追加し、Public-safe projection outputで内部ID非露出を確認した。renderer切替後もpromotion再開はまだ行っていない
- merged knowledge collection側に`publicStoryId`が伝播していないstory（今回の匿名化実データdry-runのように、story_manifest.yamlのpublic ID割当が古いnormalize/merge実行より後になされたケース）では、Story pageのReview Links→Evidence indexリンクが解決できない場合がある。`resolve_story_evidence_entries`のfallback自体は合成テストで動作確認済みだが、実データでの再現・再normalize/mergeによる解消はこのPRのスコープ外（`story_manifest.yaml`の実データ変更はNon-goals）

---

# 15. 参照

- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（§13.1 初回実施結果、本文書の直接の発端）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（promotion check手順）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria、§15未確定事項で本問題を先出しで記録済み）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル・保存場所方針`{storyId}.yaml`）
- `docs/architecture/05_Parser/Story_ID_Policy_Decision.md`（`publicStoryId`/`publicEpisodeId`の採用決定、3役分離（raw traceability/Wiki公開URL/内部参照キー）の考え方の元）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（`publicStoryId`/`publicEpisodeId`のschema実装、§13.2）
- `docs/architecture/05_Parser/Identifier_Specification.md`（既存ID体系の定義、§2.1安定性原則、§8 Evidence ID）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Summary `evidenceRefs`のschema、§8で影響を整理）
- `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`（§8の推奨方針を実装レベルまで詳細化した設計、Summary側projection scriptのCLI仕様・field変換表・evidenceRefs変換仕様・Registry共有設計）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §14（URL/slug方針、`publicStoryId`/`publicEpisodeId`のrenderer反映状況）
- `agents/wiki_generator/paths.py`（`evidence_page_path`、`resolve_story_path_id`）
- `agents/wiki_generator/renderer.py`（`render_evidence_page`、`_evidence_anchor`、`_evidence_ref_link`）
- `scripts/promote_evidence_index.py`（promotion copy script、§11で今後の変更方針を整理）
- `scripts/check_evidence_index_promotion.py`（promotion check script）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（`publicEpisodeId`未確定問題の整理、Public ID Registry設計、`scripts/check_public_episode_ids.py`）
- `TASKS.md`（次PR候補の追跡）

---

# 16. publicStoryId命名規約v2（2026-07-14ユーザー決定、`feature/public-id-naming-v2-design`で設計）

**本節はユーザー決定・Fable設計を確定したものであり、覆さない。本PR（`feature/public-id-naming-v2-design`）はdocs整備のみを行い、Registry・Evidence Index・Summaryの実データ変更は次PR（移行実行PR）で行う。**

## 16.1 v1からの変更理由

- v1（旧規約）は`{CATEGORY}_{割当日:YYMMDD}_{seq:03d}`という**Registry entry追加日（割当日）ベース**の連番だった（例の形は§2で示した`EVT_YYYYMMDD_NNN`の系譜、実際の運用値は本節§16.3で扱う）。割当日は「いつRegistryへ登録したか」という運用上の付随情報であり、story/episode自体の内容（いつのイベントか）を表さない
- 割当日ベースのIDは、Registry登録作業のタイミング（PRの実施時期）に依存してしまい、story自体の性質（いつ配信されたイベント/レイドか）を公開ID自体から読み取れない
- v2では、`YYMMDD`部分を「Registry登録日」ではなく「**sourceKeyの日付接頭辞**（実データ由来、当該story/eventの実際の日付）」に変更し、`seq`部分を「story全体を通した連番」ではなく「**カテゴリ別の昇格（Registry登録）順**の通し連番」に変更する。これにより、公開ID自体がカテゴリと概ねの時系列を表すようになる
- この変更はユーザー決定（2026-07-14）であり、Fableが設計を確定した。本ドキュメントはその決定を記録するものであり、設計判断そのものの再検討は行わない

## 16.2 新形式（v2、決定）

```text
{CATEGORY}_{seq:03d}_{YYMMDD}
```

- `CATEGORY`: `EVENT`/`RAID`（将来`MAIN`/`OTHER`等への拡張はopen question、§16.6）
- `seq`: カテゴリ別の**昇格（Registry登録）順**の通し連番、1始まり、3桁zero padding
- `YYMMDD`: **sourceKeyの日付接頭辞**（実データ由来の日付、ユーザーが「公開ID構成要素としての使用」を明示的に許可済み。§16.5で匿名化方針の改定として記録する）

例（形式のみ、実値は含まない）:

```text
EVENT_001_YYMMDD
EVENT_002_YYMMDD
RAID_001_YYMMDD
```

`publicEpisodeId`の形式`{publicStoryId}_E{NN}`（`Public_ID_Registry_Design.md` §3.1）、`publicEvidenceId`の形式`{publicEpisodeId}_{PREFIX}{sequence:04d}`（§6.4）はいずれも**不変**。v2で変わるのは`publicStoryId`本体の内部構造のみであり、それを参照する派生ID（episode/evidence）の組み立てロジック自体は変更しない。

## 16.3 移行対象3件の新旧mapping

既公開3 storyのpublicStoryIdをv1からv2へ移行する（移行の実行は次PRのスコープ、本PRでは実施しない）。

| # | カテゴリ | 旧publicStoryId（v1、割当日ベース、廃止） | 新publicStoryId（v2、形式のみ） |
|---|---|---|---|
| 1 | EVENT | `EVT_260707_001` | `EVENT_001_{YYMMDD}`（sourceKeyの日付接頭辞、実値は移行実行PRで確定） |
| 2 | EVENT | `EVT_260712_001` | `EVENT_002_{YYMMDD}` |
| 3 | RAID | `RAID_260712_001` | `RAID_001_{YYMMDD}` |

- 旧publicStoryId 3件は、いずれもRegistry登録日ベースのID（`Public_ID_Registry_Design.md` §5.2の既存運用）であり、sourceKey由来の実データ断片を含まない（§16.5参照）。そのため本表にそのまま記載してよいと判断した
- 新publicStoryIdの実値（`YYMMDD`部分、sourceKeyの日付接頭辞由来）は、**`knowledge/public_ids/story_public_ids.yaml`へ正式登録されるまではdocsに書かない**（§4のRegistry連動許可リスト方式に従う、移行実行PRで確定・記載する）
- seq番号（`001`/`002`）は、カテゴリ別のRegistry登録順（＝現行3 storyの登録順）をそのまま踏襲する。EVENTカテゴリは登録順どおり`001`→`002`、RAIDカテゴリは1件のみのため`001`とする

## 16.4 旧ID廃止と再利用禁止

- v1形式（`EVT_YYYYMMDD_NNN`/`RAID_YYYYMMDD_NNN`、割当日ベース）は**廃止**する。以後、新規Registry entryの追加にv1形式を使わない
- §16.3の旧publicStoryId 3件（`EVT_260707_001`/`EVT_260712_001`/`RAID_260712_001`）は、移行実行後は`knowledge/public_ids/story_public_ids.yaml`から削除される。**削除後もこれらのID値は将来にわたって再利用しない**（`Public_ID_Registry_Design.md` §2「一度公開したら原則変更しない」安定性原則の系譜、および`Evidence_Index_Batch_Promotion_Policy.md` §10 Rollback policyの「一度公開した`publicStoryId`/`publicEpisodeId`は再利用しない」方針と同じ扱いとする）
- 旧IDの廃止・再利用禁止は、移行実行PRの更新記録（`TASKS.md`・関連runbook）に明記する運用とする（`Evidence_Index_Batch_Promotion_Policy.md` §11.2.1の「削除される公開IDを更新記録に列挙し以後再利用しない」の記録パターンを踏襲する）

## 16.5 匿名化方針の改定

**旧方針**（`Public_ID_Registry_Design.md` §5.3、`Evidence_Index_Batch_Promotion_Policy.md` §5の既存Registry entry review条件等で前提としてきたもの）: 「公開IDはsourceKey由来にしない」。

**新方針（v2、本PRで確定）**: 「**sourceKeyの日付部分のみ**、正式に割当済みの公開IDの構成要素として使用してよい。**イベント名部分（sourceKeyのslug、例: 実イベント名の略称等）は引き続き使用禁止**」。

- 改定理由: v2の`YYMMDD`はsourceKeyの日付接頭辞そのものだが、日付単体は特定のイベント内容・タイトルを一意に明かす情報ではなく、ユーザーが公開して問題ないと判断した（2026-07-14決定）
- sourceKeyのイベント名/slug部分（実イベント名の略称等）は、この改定後も**引き続き公開ID・docs双方で使用禁止**のまま変更しない。v2は「日付部分の可否」のみを変更するものであり、匿名化方針全体を緩めるものではない
- この改定は、`AI_PR_Playbook.md` §5「匿名化ルール」・`Public_ID_Registry_Design.md` §5.3「含めないもの」・`Evidence_Index_Batch_Promotion_Policy.md` §5「Registry entry review条件」の前提を部分的に更新するが、**これらのdocs本文自体の書き換えは本PRでは行わない**（次PR以降、必要に応じて表現を追随させる。矛盾する場合は本節を優先する）
- 本改定は`knowledge/public_ids/story_public_ids.yaml`に**正式登録済み**のpublicStoryId/publicEpisodeId/publicEvidenceIdの構成要素としての日付断片にのみ適用される。Registry未登録の日付断片（sourceKeyそのものの断片・ローカルworkspace生成物内の値等）は、引き続き匿名化ルールの対象として扱う

## 16.6 Open questions（未確定事項、据え置き）

- 日付接頭辞を持たない旧番号体系のsourceKey（連番_名前_年 形式）への対応は未確定のまま据え置く（今回の移行対象3件はいずれも日付接頭辞つきのため当面影響しない）
- MAINカテゴリ（日付なし・章番号体系、`Story_ID_Policy_Decision.md` §6.1）の命名は将来の検討事項として据え置く。v2形式`{CATEGORY}_{seq:03d}_{YYMMDD}`をそのまま適用できるかは未確定
- `OTHER`カテゴリへのv2適用可否も未確定のまま据え置く
- Registry追加順（＝昇格順）を`seq`の根拠とする運用は、将来batch promotionの粒度（`Evidence_Index_Batch_Promotion_Policy.md` §4）が変わった場合でも一貫して維持できるかは、実際のbatch運用を重ねてから確認する
