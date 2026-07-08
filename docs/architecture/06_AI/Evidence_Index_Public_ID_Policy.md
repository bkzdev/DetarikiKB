# Evidence Index Public ID Policy（Public Evidence Indexの内部ID/公開ID分離方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`

---

# 1. Background

`evidence-index-promotion-first-reviewed-sample`（PR #91）で、実データ小規模サンプル（EVENTカテゴリ1story・episode2件）を`knowledge/evidence/stories/`へ初めて昇格しようと試みた。`build_evidence_index_candidates.py`によるfiltered候補生成・`validate_evidence_index.py`・`check_evidence_index_promotion.py`（`docs/runbooks/Evidence_Index_Promotion_Check.md`）はいずれも成功/PASSしたが、生成されたEvidence Index YAMLの内容を確認したところ、sourceKey由来の`storyId`がファイル名だけでなくファイル内の主要IDフィールドに大量に繰り返し出現することが判明し、安全側の判断でcommitを見送った（`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.1）。

本文書は、この問題を整理し、Public Evidence Indexにおける内部ID（trace用）と公開ID（Wiki/Git履歴に出してよいID）の分離方針を決定する。**本PRでは実装・schema変更・実Evidence Indexのcommitはいずれも行わない**（設計のみ、§13・§14参照）。

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

## 6.4 publicEvidenceId命名案

```text
{publicEpisodeId}_EVD0001
{publicEpisodeId}_DLG0001
{publicEpisodeId}_NAR0001
{publicEpisodeId}_MONO0001
{publicEpisodeId}_UNK0001
```

- `publicEpisodeId`を接頭辞にすることで、既存の`{episodeId}_DLG{n}`等の連番方式と構造的に一貫させる
- type別prefix（`DLG`/`NAR`/`MONO`/`UNK`等）を維持するか、種別を問わない連番（`EVD0001`）にするかは実装PRで検討する（可読性 vs 一意性のトレードオフ、`choice`のoption入れ子構造との整合も要確認）
- 既存の内部ID体系（`Identifier_Specification.md` §5・§8）との衝突を避けるため、`publicEpisodeId`自体が既存`episodeId`と異なる命名空間であることを前提とする
- 具体的な採番ルール・衝突回避（同一`publicEpisodeId`内での連番管理）は実装PR（`evidence-index-public-id-projection`）で確定する

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
| Phase 0: `evidence-index-promotion-target-filename-policy`（本PR） | 問題整理・ID分類・案A/B/C/D比較・採用方針決定・publicEvidenceId/internalTrace方針の設計 | **完了（本PR、設計のみ）** |
| Phase 1: `evidence-index-public-id-schema-design` | `publicEvidenceId`のschema設計（optional追加案の詳細化、命名規則の確定） | 未着手 |
| Phase 2: `evidence-index-public-id-projection` | `publicEvidenceId`のschema実装（optional追加）・projection/rewrite層の実装（内部ID→公開IDのmapping生成） | 未着手 |
| Phase 3: renderer/paths.py対応 | Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替え | 未着手 |
| Phase 4: `promote_evidence_index.py`/`check_evidence_index_promotion.py`対応 | target filenameの`publicStoryId`必須化、projection済みEvidence Indexのみpromotion対象にする、sourceKey混入scanの追加検討 | 未着手 |
| Phase 5: `evidence-index-promotion-first-reviewed-sample-retry` | Phase 1〜4完了後、実データ1 storyの初回昇格を再試行する | 未着手 |
| Phase 6: `internal-review-evidence-packet-design` | 内部trace ID・mapping tableをInternal Review Evidence Packet側で扱う詳細設計 | 未着手 |

**promotion再開（`knowledge/evidence/stories/`への実データcommit）は、少なくともPhase 2（projection実装）が完了するまで行わない。**

---

# 13. Non-goals（本PRで行わないこと）

- 実Evidence Indexのcommit
- `knowledge/evidence/stories/`への実データ昇格
- `publicEvidenceId`のschema実装
- public ID projection実装（rewrite script等）
- ID rewrite実装
- `scripts/promote_evidence_index.py`の変更
- `scripts/check_evidence_index_promotion.py`の変更
- `scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`の変更
- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の変更
- Evidence page anchorの変更
- `schemas/story_summary.schema.json`（Story Summary schema）の変更
- 既存fixtureの大量変更・migration
- Internal Review Evidence Packet生成
- raw text review packet生成
- Evidence Index batch promotion

---

# 14. Open questions（未確定事項）

- `publicEvidenceId`の具体的な採番ルール（type別prefix維持 vs 種別を問わない連番、choice option入れ子構造との整合）
- `internalTrace`/mapping tableの生成方法（`build_evidence_index_candidates.py`の拡張か、別scriptか）
- mapping tableの保管場所・アクセス制御（`workspace/review_packets/evidence/`が適切か、`internal-review-evidence-packet-design`との統合方法）
- 既存の`evidenceId`（内部ID）を将来的に完全廃止するか、常に保持しつつPublic Evidence Indexでのみ非表示にするか
- `check_evidence_index_promotion.py`のsourceKey混入scanをどう実装するか（`story_manifest.yaml`側の`sourceKey`一覧と突き合わせるか、パターンヒューリスティックにするか）
- MAIN/RAID/OTHER/CHARACTERカテゴリでも同じ問題が起きるか（`Story_ID_Policy_Decision.md` §6の通り、EVENT/RAIDが優先対象、MAINは現行IDが既に短く意味を持つため影響が小さい可能性がある）
- Public Evidence Indexのschema変更（`publicEvidenceId`必須化等）をいつrequired化するか、既存Internal運用（`full`/`review` policy）との互換性をどう保つか

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
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §14（URL/slug方針、`publicStoryId`/`publicEpisodeId`のrenderer反映状況）
- `agents/wiki_generator/paths.py`（`evidence_page_path`、`resolve_story_path_id`）
- `agents/wiki_generator/renderer.py`（`render_evidence_page`、`_evidence_anchor`、`_evidence_ref_link`）
- `scripts/promote_evidence_index.py`（promotion copy script、§11で今後の変更方針を整理）
- `scripts/check_evidence_index_promotion.py`（promotion check script）
- `TASKS.md`（次PR候補の追跡）
