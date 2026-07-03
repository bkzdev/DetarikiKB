# Merged Knowledge Design（Stage B 統合知識設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Merged_Knowledge_Design.md`

---

# 1. 目的

この文書は、Extraction Phase の **Stage B: Merged Knowledge**（エピソード単位の抽出候補をエンティティ単位に統合した知識）の設計を定義する。

`Extraction_Pipeline.md` §3.1 で定義した二段階構成の後段にあたる。

```text
Stage A: Raw Extraction（エピソード単位の抽出結果、実装済み）
  data/extracted/_raw/{episodeId}.extraction.json
    ↓
Stage B: Merged Knowledge（本文書の対象）
  エンティティ単位に統合された知識
    ↓
Canonical Knowledge / Knowledge Graph / Wiki Generation（後続フェーズ）
```

## 1.1 Candidate と Merged Knowledge の違い

| | Stage A: Candidate | Stage B: Merged Knowledge |
|---|---|---|
| 単位 | エピソード単位の**観測結果** | エンティティ単位の**統合された知識** |
| 状態 | 未確定候補。同一エンティティが複数エピソードに別candidateとして重複して存在する | 重複解決済み。1エンティティ = 1ドキュメント |
| ID | エピソードスコープの暫定candidate ID（`{episodeId}_CAND_CHAR001`） | canonical Entity ID（`CHAR_AKAGI_HINA`）、未解決なら暫定merge ID（§4.4） |
| 確定度 | rule-based/LLMの出力そのまま | 手動補正（manual override）適用後の「現時点の知識」 |
| 再生成 | 対応するNormalized Story JSONからいつでも再生成できる使い捨て中間生成物 | Stage A全体 + override群から再マージで再生成できる生成物 |

Stage Aは「このエピソードで何が観測されたか」、Stage Bは「ストーリー全体を通して現時点で何が分かっているか」を表す。

## 1.2 後続フェーズとの関係

Merged Knowledgeは以下の**前段データ**であり、それ自体が最終成果物ではない。

- **Canonical Knowledge**: Merged Knowledgeのうち、canonical IDが確定し手動レビューを通過したエンティティの確定版（将来フェーズ）
- **Knowledge Graph**: Merged/Canonicalのエンティティをノード、Relationshipをエッジとして構築する（将来フェーズ）
- **Wiki Generation**: Merged/Canonicalの`fields`（fact/inference分離済み）からページを生成する（将来フェーズ）

本文書はStage Bの設計のみを対象とする。JSON Schema・Pythonコードの実装は別作業とする（§13）。

---

# 2. 入力

## 2.1 Stage A episode_extraction

主入力は `schemas/extraction.schema.json` に準拠したStage A出力の全ファイルとする。

```text
data/extracted/_raw/{episodeId}.extraction.json
```

各ファイルから利用する情報:

- 8種のCandidate配列（`characters` / `locations` / `organizations` / `items` / `lore` / `events` / `relationships` / `timelineCandidates`）
- `evidenceIndex`（candidateの`evidenceIds`を解決するためのEvidenceRef辞書）
- `extractionRun`（どのバージョン・どの方式で抽出されたかの実行情報。§10.3）
- `episodeId` / `storyId` / `storyCategory`（provenanceとして保持）
- `extractionRun.parserCompatibilityAtExtraction`（`needs_update`のエピソード由来のcandidateを「再抽出待ち」として印付けするため）

## 2.2 入力の検証

マージ実行前に、各入力ファイルが以下を満たすことを確認する。

- `extraction.schema.json` によるJSON Schema検証に通ること
- `agents/extractor/validator.py` のsemantic validationでerrorが無いこと（warningは許容し、マージレポートへ転記する）

検証に落ちたファイルはマージ対象から除外し、レポート（§11）に記録する。壊れた入力を黙って取り込まない。

## 2.3 Manual override / correction file（将来入力）

手動補正ファイル（§8）を第二の入力とする。Stage B初期実装ではローダーが無くてもよいが、マージ結果のデータ構造は最初からoverride適用を前提に設計する（後からoverrideを差し込める形にしておく）。

```text
knowledge/overrides/*.yaml (または *.json)
```

## 2.4 Canonical ID辞書（将来入力）

`Extraction_Pipeline.md` §4.1 が想定する既知エンティティ辞書（`knowledge/dictionaries/characters.yaml` 等）が整備され次第、名前・sourceCharacterIdからcanonical IDへの解決に使う。辞書が無い間は、Stage Aの`existing*Id`（Parserの解決結果）だけを信頼する。

---

# 3. 出力

## 3.1 出力ドキュメント種別

Stage Bは8種のmergedドキュメントを出力する。`documentType` は `Extraction_Pipeline.md` §3.3 の語彙を踏襲する。

| Stage A candidate | Stage B document | documentType |
|---|---|---|
| CharacterCandidate | merged character | `extracted_character` |
| LocationCandidate | merged location | `extracted_location` |
| OrganizationCandidate | merged organization | `extracted_organization` |
| ItemCandidate | merged item | `extracted_item` |
| LoreCandidate | merged lore entry | `extracted_lore` |
| EventCandidate | merged event | `extracted_event` |
| RelationshipCandidate | merged relationship | `extracted_relationship` |
| TimelineCandidate | merged timeline entries | `extracted_timeline`（§7。エンティティ統合ではなく集約。1ファイル = 全エピソード横断の順序情報一覧） |

## 3.2 配置

生成物は `data/extracted/merged/` 配下に置く（比較検討は§11）。

```text
data/extracted/
  _raw/                                  # Stage A（既存）
    {episodeId}.extraction.json
  merged/                                # Stage B（本文書）
    characters/{characterId}.json        # canonical ID確定分
    locations/{locationId}.json
    organizations/{organizationId}.json
    items/{itemId}.json
    lore/{loreId}.json
    events/{eventId}.json
    relationships/{relationshipId}.json
    timeline/timeline_entries.json       # §7（エンティティ単位ファイルを持たない）
    _unresolved/                         # canonical ID未確定分（§4.4）
      characters.json
      locations.json
      organizations.json
      items.json
      lore.json
      events.json
      relationships.json                 # 両端未解決のRelationship置き場（§6.5、既存設計からの変更点）
  reports/
    merge_report.json                    # §11 マージレポート
```

`Extraction_Pipeline.md` §9.1 では Stage B を `data/extracted/characters/` のように `_raw/` と同階層に置く案だったが、本文書で `data/extracted/merged/` 配下へまとめる形に変更する。理由: Stage A（`_raw/`）とStage B（`merged/`）が生成物ディレクトリとして対で見え、`.gitignore` 管理・一括削除・再生成の単位が明確になるため。

## 3.3 Merged entity 基本構造

`Extraction_Pipeline.md` §3.3 の基本構造を継承し、provenance（§10）を加えて確定させる。

```json
{
  "schemaVersion": "0.1",
  "documentType": "extracted_character",
  "id": "CHAR_RAIN",
  "idStatus": "canonical",
  "canonicalName": "レイン",
  "aliases": [],
  "fields": {},
  "evidence": [],
  "sourceCandidates": [
    {
      "candidateId": "MAIN_S01_C02_E01_CAND_CHAR001",
      "episodeId": "MAIN_S01_C02_E01",
      "sourceType": "script",
      "confidence": 0.9,
      "extractionRunRef": "MAIN_S01_C02_E01"
    }
  ],
  "extractionRuns": {
    "MAIN_S01_C02_E01": {
      "extractionVersion": "0.1.0",
      "extractionMethod": "rule_based",
      "modelProvider": null,
      "modelName": null,
      "promptVersion": null,
      "extractedAt": null,
      "parserCompatibilityAtExtraction": "compatible"
    }
  },
  "confidence": 0.9,
  "mergedFrom": ["MAIN_S01_C02_E01"],
  "lastMergedAt": null,
  "manualOverridesApplied": []
}
```

- `id`: canonical Entity ID（`Identifier_Specification.md` §6）。未確定の場合は§4.4の暫定merge ID
- `idStatus`: `canonical`（手動確定済み） / `provisional`（未確定。`_unresolved/`に置かれる）
- `evidence`: EvidenceRefの**埋め込み配列**。Stage Aのインデックス参照方式はエピソード単位の前提が崩れるため、Stage Bでは埋め込みに戻す（`Extraction_Result_Schema.md` §5.3で決定済み）
- `sourceCandidates` / `extractionRuns`: provenance（§10）
- `confidence`: 統合後のエンティティ全体を代表する値（§4.3）
- `fields`: FieldValue辞書（`Extraction_Result_Schema.md` §4.3と同一構造）。fact/inference分離をStage Bでも維持する
- `manualOverridesApplied`: 適用済みoverrideのID一覧（§8.4 audit trail）

---

# 4. CandidateからMergedへの基本方針

## 4.1 マージの4原則

1. **既存IDを最優先する。** `existingCharacterId` / `existingOrganizationId` 等、Stage Aの時点で構造的に解決済みのcanonical IDがあるcandidate同士だけを自動マージする。
2. **名前一致だけで自動マージしない。** 名前のみのcandidate（`existing*Id: null`）は、表記が完全一致していてもエピソードをまたいだ自動統合の**確定**はしない。同名の別人・別組織がありうるため、名前一致は「マージ候補の提案」（§9.4）に留め、確定は手動補正（§8）に委ねる。
3. **Stage Aの情報を失わない。** `sourceType` / `confidence` / `evidenceIds`（解決済みEvidenceRef） / candidate ID / extractionRun は、マージ後もprovenance（§10）として全て追跡できる形で保持する。マージは情報の集約であって破棄ではない。
4. **fact と inference を混ぜない。** `sourceType: script` / `ai_extracted`（fact系）と `ai_inferred`（inference系）の値は、同一フィールドであってもマージで相互に上書きしない。FieldValue単位で`sourceType`を保持し、Wiki Generatorが後段でセクションを分離できる状態を維持する（`Extraction_Pipeline.md` §7.2）。

## 4.2 マージ単位（merge key）

エンティティ種別ごとのmerge keyは§5で定義する。共通ルール:

- merge keyが一致するcandidate群を1つのmergedドキュメントへ統合する
- keyの優先順位は「構造化ID > それ以外」。構造化IDを持つcandidateと名前のみのcandidateは、同名でも自動では同一視しない
- Stage A内（同一エピソード内）の重複統合は実装済みのため、Stage Bは**エピソード横断**の統合だけを担う

## 4.3 confidence集約

- merged entityの代表`confidence`は、構成candidateのconfidenceの**最大値**とする（観測が増えて確からしさが下がることはない、という単純なモデル）
- 平均・加重平均は採らない。エピソード数に依存して値が動き、閾値運用（§4.5）が不安定になるため
- candidate個別のconfidenceは`sourceCandidates[].confidence`にそのまま残す
- 手動補正で確定した値は`confidence: 1.0`（`Extraction_Pipeline.md` §8.4）

## 4.4 未解決candidateの扱い

canonical IDへ解決できていないcandidate（`existing*Id: null`）は、確定エンティティディレクトリに置かず `merged/_unresolved/{type}.json` へ集約する（`Extraction_Pipeline.md` §9.2の方針を踏襲）。

- `_unresolved/` 内の各エントリには暫定merge IDを割り当てる。形式: `UNRESOLVED_{TYPE}_{number}`（例: `UNRESOLVED_CHAR_0001`）。この暫定IDは再マージで変わりうるため、外部から参照しない（Wiki・Graphは`canonical`のみ参照する）
- 名前完全一致のcandidate群は`_unresolved/`内で1エントリに**仮グルーピング**してよい（提案として）。ただし`idStatus: provisional`のまま、canonical昇格は手動補正で行う
- 手動補正でcanonical IDが割り当てられた時点で、`merged/{type}/{canonicalId}.json` へ昇格する

## 4.5 低confidence candidateの隔離

`confidence < 0.4` のcandidateは自動採用せず「要レビュー」として`_unresolved/`側へ隔離する（`Extraction_Pipeline.md` §7.3）。現行のrule-based抽出は0.5/0.7/0.9のみを出すため当面該当しないが、LLM抽出の導入後に効く閾値として最初から実装する。

## 4.6 再マージと冪等性

- Stage Bは「Stage A全ファイル + override群」から**全再生成できる**ことを保証する（入力が同じなら出力も同じ）
- 特定エピソードの再抽出時は、`mergedFrom`にそのepisodeIdを含むエンティティだけを再マージ対象にできる（増分マージ）。ただし正しさの基準は常に全再生成とし、増分は最適化として扱う
- `sourceType: manual`のフィールドとoverride適用結果は、再マージしても保持される（§8.3）

---

# 5. Entity別merge方針

## 5.1 Character

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingCharacterId`。第2: `sourceCharacterId`（ゲーム内キャラ番号。全ストーリーで安定と仮定できるため、`existingCharacterId`が無くても同一`sourceCharacterId`同士は自動マージしてよい）。第3: 名前のみ → 自動マージしない（§4.1原則2） |
| confidence集約 | max（§4.3） |
| evidence集約 | 全candidateの`evidenceIds`をEvidenceRefへ解決して`evidence`配列に統合。重複sourceIdは1件化 |
| conflict handling | 同一keyで`nameCandidates`が異なる → 全表記を`aliases`に保持し、`canonicalName`は最頻出表記を暫定採用。矛盾として破棄しない |
| unresolved | `existingCharacterId`も`sourceCharacterId`も無いもの（speakerNameのみ）は`_unresolved/characters.json`へ |
| manual correction | canonical ID割り当て（ローマ字化はOD-001未確定のためAIに確定させない）、同一人物判定（別名統合）、canonicalName選択 |

## 5.2 Location

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingLocationId`。第2: 名前のみ → 自動マージしない。ただしstage_direction由来の背景コマンド文字列（`bg_school`等）は名前ではなく識別子に近いため、**完全一致なら自動マージしてよい**（同一コマンド = 同一背景アセットとみなせる） |
| confidence集約 | max |
| evidence集約 | Scene ID evidence / stage_direction Block evidenceを統合。`sceneRefs`も全candidateの和集合を保持 |
| conflict handling | 同一locationIdに異なるlocationName → aliasesへ |
| unresolved | locationId無しの表示名系（「本部」等）は`_unresolved/locations.json`へ |
| manual correction | canonical LOC_ID割り当て、背景コマンド→場所名の対応付け（`bg_school`→「学園」） |

## 5.3 Organization

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingOrganizationId`。第2: 名前のみ → 自動マージしない |
| confidence集約 | max |
| evidence集約 | Block evidence / Episode-level evidence（speakerAssignments由来）を統合。Episode-level evidenceも粒度情報として残す（Blockに「格上げ」しない） |
| conflict handling | 同一組織の正式名称・略称の揺れ → aliasesへ |
| unresolved | affiliation文字列のみ由来（「異形生物対策班」等）は`_unresolved/organizations.json`へ |
| manual correction | canonical ORG_ID割り当て、正式名称の選択、略称のalias登録 |

## 5.4 Item

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingItemId`。第2: 名前のみ → 自動マージしない |
| confidence集約 | max |
| evidence集約 | Block evidence（stage_direction含む）を統合 |
| conflict handling | 名称揺れ → aliasesへ |
| unresolved | itemName のみは`_unresolved/items.json`へ |
| manual correction | canonical ITEM_ID割り当て |

## 5.5 Lore

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingLoreId`。第2: 用語表記のみ → 自動マージしない。Loreは特に「同じ語が別概念を指す」リスクが高いため、8種の中で最も保守的に扱う |
| confidence集約 | max |
| evidence集約 | Block evidenceを統合。`termCandidates`は和集合 |
| conflict handling | 用語の表記揺れ（「デタリキZ」「デタリキ・Z」）→ termCandidates/aliasesに全保持 |
| unresolved | loreId無しは`_unresolved/lore.json`へ |
| manual correction | canonical LORE_ID割り当て、Character/Org/Location/Itemへの再分類（Loreは受け皿カテゴリのため、レビューで他種別へ移すことがある） |

## 5.6 Event（作中出来事）

| 項目 | 方針 |
|---|---|
| merge key | 第1: `existingEventId`。第2: 名前のみ → 自動マージしない。出来事は「ジャマー出現」のような汎用名が複数の別出来事を指しやすい |
| confidence集約 | max |
| evidence集約 | Block evidence（stage_direction含む）を統合。`participantCandidates` / `locationCandidates`は和集合（candidate IDが混ざる場合は§10.2の対応表でcanonical IDへ引き直す） |
| conflict handling | 同名別出来事の疑い → 自動マージしないため原則発生しない。同一eventIdで参加者リストが異なる場合は和集合（出来事の観測が増えただけとみなす） |
| unresolved | eventName のみは`_unresolved/events.json`へ |
| manual correction | canonical EVENT_ID割り当て、同一出来事判定、EPISODEをまたぐ出来事の統合 |

## 5.7 Relationship

§6で個別に定義する。

## 5.8 Timeline

§7で個別に定義する。

---

# 6. Relationship merge方針

Relationshipは「両端のエンティティ解決」に依存するため、他の種別より一段複雑になる。

## 6.1 merge key

```text
(resolved sourceId, resolved targetId, relationshipType)
```

- `sourceCandidate` / `targetCandidate` はEntity IDまたはcandidate IDを取りうる（`Extraction_Result_Schema.md` §12）。マージ前に§10.2の対応表（candidate ID → merged entity ID）でcanonical IDへ解決する
- **両端がcanonical IDへ解決できたRelationshipだけを`merged/relationships/`へ昇格させる**（`Extraction_Result_Schema.md` §15のゲート条件を踏襲）
- 片端でも未解決のものは`merged/_unresolved/relationships.json`に置く。`Extraction_Result_Schema.md` §15は「Stage Aの`relationships`配列内に留め置く」としていたが、本文書で`_unresolved/`へ集約する形に変更する。理由: Stage Aファイルは使い捨て・再生成対象であり、「未解決だが観測済みのRelationship一覧」を横断的にレビューする置き場が別途必要になるため
- merged relationshipのIDは`Identifier_Specification.md` §7の形式（`REL_{sourceId}_{relationshipType}_{targetId}`、変化する関係は連番付き）

## 6.2 directionの扱い

- 同一merge keyで全candidateのdirectionが一致 → その値を採用
- 矛盾（`source_to_target`と`bidirectional`が混在等） → **broadな方（`bidirectional`）を暫定採用**し、conflictとしてレポートに記録する（§9.7）。狭い方向を勝手に選んで情報を落とすより、広い方を取って人間が絞る方が安全
- `MEMBER_OF` / `AFFILIATED_WITH` は意味的に方向が固定（Character → Organization）のため、逆向きが観測されたらconflictではなく入力エラーとしてレポートする

## 6.3 relationshipType の暫定扱い

- taxonomyは未確定のまま自由文字列を維持する（`Extraction_Result_Schema.md` §16.4。本文書でも確定させない）
- `MEMBER_OF` / `AFFILIATED_WITH` / `RELATED_TO` / `APPEARS_WITH` は暫定語彙として使用を継続する
- `MEMBER_OF`（構造化ID由来）と`AFFILIATED_WITH`（名前のみ由来）は**別merge keyのまま統合しない**。同一(source, target)ペアに両方が存在する場合、格上げ（AFFILIATED_WITH → MEMBER_OF）はマージレポートで提案し、確定は手動補正で行う
- taxonomy確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`）後に、既存merged relationshipのtype移行手順を別途設計する

## 6.4 evidence集約と明示/推定の分離

- 同一merge keyのcandidate群のevidenceを全て統合する
- `sourceType`がfact系（`script`）とinference系（`ai_inferred`、将来のLLM抽出）のRelationshipは、**同一merge keyでも別レコードとして保持する**（マージしない）。「本文に明示された所属」と「AIが推定した所属」を1つに潰すと、後段のWiki（公式情報とAI考察の分離、`AI_CONTEXT.md` 4.5）が成立しなくなるため
- merged relationshipドキュメントに`sourceType`を持たせ、fact系レコードとinference系レコードをGraph/Wiki側でフィルタできるようにする

## 6.5 unresolved / manual correction

- unresolved: 片端未解決（§6.1）。手動補正で両端が解決された時点で昇格
- manual correction: relationshipTypeの修正・格上げ、方向の確定、自己参照や誤検出の無効化（削除ではなく`suppressed: true`のような打ち消しoverride。§8.2）

---

# 7. Timeline merge方針

Timelineは**エンティティを持たない**ため、他の7種と同じ「エンティティ統合」は行わない。Stage Bでの扱いは「エピソード横断の集約・一覧化」に留める。

## 7.1 既存設計からの位置づけ調整

`Extraction_Pipeline.md` §4.8 / §3.3はTimeline candidateを「Stage Bのマージ対象外とし、エピソード単位のまま保持する」としていた。本文書では、**エンティティ統合はしない**という原則を維持したまま、エピソード横断で順序情報を1ファイルに集約した`timeline_entries.json`（`documentType: extracted_timeline`）を追加する。理由: 将来のTimeline Builderや矛盾検出は「全エピソードの順序情報の一覧」を入力とするため、その一覧化までをStage Bの責務とするのが自然なため。順序の**確定**（canonicalOrderの決定）はStage Bではしない。

## 7.2 集約ルール

- **kindごとに分離して集約する。** `explicit_order`（明示順序値）と`temporal_marker`（flashback等の構造マーカー）は意味が異なるため、混ぜて1つの順序列にしない
- `explicit_order` / scope: `episode`（`canonicalOrder` / `releaseOrder` / `displayOrder`由来）: orderFieldごとに「episodeId → orderValue」の対応表として集約する。**orderField間の優先順位付けはしない**（`displayOrder`の正式計算式・`canonicalOrder`の扱いはOD未確定のため。`AI_CONTEXT.md` §16）
- `explicit_order` / scope: `block`（`timelineId` / `timelineLabel` / `timePosition`由来）: `sourceTimelineId`またはラベルごとにグルーピングし、evidence付きで一覧化する
- `temporal_marker`: markerTypeごとに「episodeId + evidence」の観測一覧として保持する。「flashbackがあった」という事実だけを集約し、**どの時点への回想かは解釈しない**
- 自然文推定由来の時系列情報（将来LLMが生成する`relative_order`, `sourceType: ai_inferred`）は、rule-based由来（`script`）と**別セクションで保持**し、混ぜない

## 7.3 conflict / 今後の課題

- 同一episodeIdに矛盾する順序値が観測された場合（例: 再抽出前後で`canonicalOrder`が変わった等）はconflictとしてレポートに記録し、新しいextractionRun由来を暫定採用する
- **timeline ordering conflict の本格検出（順序グラフの循環検出等）は今後の課題**とし、Stage Bでは実装しない。Stage Bは材料の集約までを担い、順序の整合性判定はTimeline Builder（将来フェーズ）に委ねる

---

# 8. Manual correction / override

## 8.1 基本方針

- rule-based / LLM抽出の結果は**完全自動では確定しない**。canonical ID割り当て・同一エンティティ判定・低confidence候補の採否は必ず人間が行う（`Extraction_Pipeline.md` §8.4）
- 手動補正は「マージ済みファイルを直接編集する」のではなく、**独立したoverrideファイルとして記述し、マージ実行時に適用する**。merged/配下は常に再生成可能な生成物に保つため
- overrideファイルは手書きソースであり、Git管理する（§11）

## 8.2 override の種別（設計案）

```yaml
# knowledge/overrides/characters.yaml の例（形式はschema設計時に確定）
- overrideId: OVR_0001
  targetType: character
  action: assign_canonical_id        # 暫定merge ID → canonical ID割り当て
  match:
    unresolvedKey: "speakerName:ノイズ"
  set:
    id: CHAR_NOISE
  note: "未登録キャラのcanonical ID手動割り当て"
  author: bkzdev
  createdAt: "2026-07-03"
```

想定するaction:

| action | 用途 |
|---|---|
| `assign_canonical_id` | 未解決エントリへのcanonical ID割り当て（`_unresolved/` → 昇格） |
| `merge_entities` | 同一エンティティ判定（表記揺れの統合） |
| `set_field` | フィールド値の手動確定（`sourceType: manual` / `confidence: 1.0`で記録） |
| `set_canonical_name` | canonicalName / aliasesの整理 |
| `suppress` | 誤検出candidateの打ち消し（削除ではなく抑制。provenanceは残る） |
| `promote_relationship` | AFFILIATED_WITH → MEMBER_OF 格上げ等のrelationship補正 |

## 8.3 適用ルール

- override適用結果のフィールドは `sourceType: "manual"` / `confidence: 1.0` とする
- `sourceType: manual` のフィールドは、以後の再マージ・再抽出で自動上書きされない（`Extraction_Pipeline.md` §8.4）
- overrideが参照する対象が再マージで消えた場合（例: 対象candidateが再抽出で出なくなった）、そのoverrideは「適用先なし」としてレポートに記録し、黙って無視しない

## 8.4 correction log / audit trail

- merged entityの`manualOverridesApplied`に、適用したoverrideIdの一覧を残す
- マージレポート（§11）に「適用されたoverride」「適用先が見つからなかったoverride」を毎回記録する
- overrideファイル自体がGit管理されるため、いつ誰が何を補正したかの履歴はGitのログでも追跡できる。`author` / `createdAt` / `note` はファイル内にも残す（Gitを見なくても文脈が分かるように）

---

# 9. Conflict handling

マージ中に検出しうる衝突と対応を一覧化する。共通原則: **conflictは黙って解決しない。** 暫定採用ルールで処理を続行しつつ、必ずマージレポート（§11）へ記録し、手動補正の入力材料にする。

| # | conflict | 暫定処理 | レポート |
|---|---|---|---|
| 9.1 | conflicting names（同一IDに複数表記） | 全表記をaliasesに保持、最頻出をcanonicalName暫定採用 | name_conflict |
| 9.2 | duplicate IDs（別種別で同一canonical IDを主張） | 先着を採用、後続は`_unresolved/`へ隔離 | duplicate_canonical_id（error級） |
| 9.3 | low confidence（< 0.4） | 自動採用せず`_unresolved/`へ（§4.5） | low_confidence_quarantined |
| 9.4 | same name, different entity の疑い | 名前のみは自動マージしないため誤統合は起きない。名前一致グループは「マージ候補の提案」としてレポートに出すだけ | merge_suggestion |
| 9.5 | same entity, different names | 構造化IDが同じなら自動統合し表記はaliasesへ（9.1と同処理）。IDが無い場合は9.4と同様に提案止まり | merge_suggestion |
| 9.6 | sourceType conflict（同一フィールドにscript値とai_inferred値） | 相互上書きしない。fact系とinference系を別FieldValueとして併記（§4.1原則4）。fact系同士の値矛盾はconfidence高い方を暫定採用し、両方をevidence付きで保持（`Extraction_Pipeline.md` §7.3。矛盾自体がWiki「矛盾点」ページの入力になる） | field_value_conflict |
| 9.7 | relationship conflict（direction矛盾・type揺れ） | directionはbroad側を暫定採用（§6.2）。MEMBER_OF/AFFILIATED_WITH併存は格上げ提案（§6.3） | relationship_conflict |
| 9.8 | timeline order conflict | 新しいextractionRun由来を暫定採用し記録（§7.3）。本格的な順序整合性判定はしない | timeline_conflict |

---

# 10. Provenance / Evidence

## 10.1 原則

**merged entityから、元のRaw Scriptの行まで一直線に遡れること。** 遡及チェーンは以下の通り。

```text
merged entity
  → sourceCandidates[].candidateId（Stage A candidate）
  → evidence[].sourceId（Block ID）
  → Normalized Story JSON の Block.source（sourceFile / lineStart / lineEnd / raw）
  → Raw Script の該当行
```

- merged entityにも`evidence`（EvidenceRef埋め込み配列）を必ず残す。Evidenceを1件も持たないmerged entityは出力しない（Stage Aと同じ原則）
- Wiki Generatorはこの`evidence`から「本編内での言及」の根拠リンクを表示できる

## 10.2 candidate対応表

マージ実行時に「Stage A candidate ID → merged entity ID」の対応表を生成し、レポートと一緒に保存する。

```text
data/extracted/reports/candidate_mapping.json
```

用途:

- EventCandidateの`participantCandidates`やRelationshipCandidateの両端に含まれるcandidate IDを、merged entity IDへ解決する（§5.6 / §6.1）
- 「このcandidateはどのmerged entityに取り込まれたか」の逆引き
- 増分マージ時の差分計算

## 10.3 extractionRunの保持方式

Stage Aでは全candidateにextractionRunが複製埋め込みされている。Stage Bで同じことをすると、数十エピソード分のrunが1エンティティに重複して埋まり肥大化する。

採用方針: **runRefs参照方式**。

- merged entityの`sourceCandidates[].extractionRunRef`にはepisodeIdのみを持たせる
- merged entityドキュメント直下の`extractionRuns`辞書（episodeId → extractionRun）に実体を1回だけ格納する（§3.3の構造例）
- これによりcandidate単位の出自（どの実行・どの方式で抽出されたか）は失わずに、重複を排除する

## 10.4 original candidate id の保持

- `sourceCandidates[].candidateId`にStage Aの暫定candidate IDをそのまま残す
- Stage Aファイルは再生成でcandidate IDが変わりうるため、candidate IDの安定性には依存しない（provenanceの記録としてのみ使い、参照キーには使わない）。安定な参照はcanonical Entity IDとBlock ID（Evidence）が担う

---

# 11. Directory layout

## 11.1 比較

**A案: `data/extracted/` 一本**

```text
data/extracted/
  _raw/          # Stage A
  merged/        # Stage B
  overrides/     # 手動補正
  reports/
```

- 利点: Extraction関連が1箇所に集まり、把握しやすい
- 欠点: `data/extracted/`は`.gitignore`で生成物として除外済み。手書きのoverrideファイルを生成物ディレクトリに同居させると、「commitしないルール」（`TASKS.md` §5）と「overrideはGit管理すべき」が衝突する。gitignoreの例外指定で回避はできるが、事故（override消失・誤コミット）の温床になる

**B案: `data/knowledge/` 新設に全移動**

```text
data/knowledge/
  merged/
  canonical/
  overrides/
```

- 利点: 「knowledge」という名前が最終成果物に近い語感で分かりやすい
- 欠点: 生成物（merged）と手書きソース（overrides）が同居する問題はA案と同じ。さらに既存の`data/extracted/_raw/`（Stage A）と場所が分かれ、`Extraction_Pipeline.md` §9の既存設計からの変更量が大きい

**C案（推奨）: 生成物と手動管理ソースを分離するハイブリッド**

```text
data/extracted/          # 生成物。Git管理外（現状の.gitignoreのまま）
  _raw/                  # Stage A（既存）
  merged/                # Stage B出力（§3.2）
  reports/               # マージレポート・candidate対応表

knowledge/               # 手動管理ソース。Git管理対象（リポジトリ直下）
  overrides/             # §8 手動補正ファイル
  dictionaries/          # canonical ID辞書（Extraction_Pipeline.md §4.1が既に想定済み）
```

- 「生成物はcommitしない・手書きはcommitする」という既存ルールとディレクトリ境界が一致する
- `Extraction_Pipeline.md` §4.1が既に`knowledge/dictionaries/characters.yaml`という配置を想定しており、既存設計と整合する
- Canonical Knowledge（確定版）を将来どこに置くか（`knowledge/canonical/`としてGit管理し成果物をレビュー可能にする案が有力）は、Canonical化フェーズの設計時に確定する

## 11.2 マージレポート

マージ実行のたびに以下を出力する（生成物。Git管理外）。

```text
data/extracted/reports/merge_report.json
```

内容: 処理したepisode_extraction数 / 生成・更新されたmerged entity数 / `_unresolved/`件数 / §9のconflict一覧 / 適用override・適用先なしoverride / semantic validation warningの転記。

---

# 12. Future schema

次に作るべきJSON Schema（**本ブランチでは作成しない**。設計のみ）。

```text
schemas/
  merged_knowledge.schema.json       # §3.3のmerged entity共通構造 + 種別ごとの固有フィールド
                                     # （documentType判別のoneOf構成。extracted_character /
                                     #   extracted_location / ... / extracted_relationship /
                                     #   extracted_timeline）
  manual_overrides.schema.json       # §8.2のoverrideファイル形式
                                     # （overrideId / targetType / action / match / set /
                                     #   note / author / createdAt）
  canonical_knowledge.schema.json    # Canonical化フェーズ用。merged_knowledgeの
                                     # idStatus: canonical + レビュー済みフラグを持つ確定版。
                                     # 設計はCanonicalフェーズで詰める（今は名前の予約のみ）
```

補足:

- `Extraction_Pipeline.md` §10.1が挙げていた`schemas/character.schema.json`等の空プレースホルダー群は、`merged_knowledge.schema.json`に統合する形とし、個別ファイルとしては実装しない方針を推奨する（8ファイルに分けると共通CandidateEnvelope相当の重複が増えるため）。採否はschema実装PRで最終判断する
- マージレポート（§11.2）のschema化は任意（内部レポートのため、初期はschemaなしでよい）

---

# 13. Future implementation plan

Stage B実装のPR分割案（各PRは小さく、テスト付きで）。

1. **Stage B schema作成**: `merged_knowledge.schema.json` + `manual_overrides.schema.json` + fixture + schema tests（Parser Phase 1と同じ「schemaを実体より先に作る」進め方）
2. **merge engine skeleton**: `agents/merger/`（仮）に、Stage Aファイル群の読み込み・検証ゲート（§2.2）・空のmerged構造出力・merge_report骨格まで。candidate統合ロジックはまだ空
3. **character/location/organization merge**: §5.1〜5.3のmerge key実装（existing*Id / sourceCharacterId / 背景コマンド一致）。`_unresolved/`集約と暫定merge ID採番を含む
4. **item/lore/event merge**: §5.4〜5.6（3.の仕組みの横展開）
5. **relationship merge**: §6（candidate対応表による両端解決、昇格ゲート、direction矛盾処理）
6. **timeline aggregation**: §7（kind別集約、timeline_entries.json出力）
7. **manual override loader**: §8（override読み込み・適用・audit trail・適用先なし検出）
8. **report generator**: §11.2（conflict一覧・merge_suggestion・candidate_mapping出力の充実）

各段階で `uv run pytest` の全通過と、実データを使わない自作fixtureによる検証を維持する。

---

# 14. Non-goals

本設計書では以下を**スコープ外**とする。

- Stage Bの実装（Python / schema。§13のPR群で別途行う）
- Knowledge Graph実装（Neo4jモデル・投入処理）
- Wiki生成
- LLMによる推定merge（「この2つは同一人物らしい」のようなAI判断でのエンティティ統合）
- 自然文からの追加抽出（Stage Aの責務。Stage Bは新しい情報を抽出しない）
- relationshipType taxonomyの最終確定（`Relationships.md`の作業として別途）
- timeline contradiction detection（順序矛盾の本格検出。Timeline Builderフェーズへ）
- Canonical Knowledgeフェーズの詳細設計（`canonical_knowledge.schema.json`は名前の予約のみ）

---

# 15. 採用方針（サマリ）

- Stage Bは「エピソード単位の観測（Candidate）」を「エンティティ単位の統合知識（Merged Knowledge）」へ変換する。Canonical Knowledge / Knowledge Graph / Wikiの前段である
- 構造化ID（existing*Id / sourceCharacterId / 背景コマンド）が一致するものだけを自動マージし、名前一致だけでは自動マージしない。名前一致はマージ候補の提案に留める
- 未解決candidateは`merged/_unresolved/`へ集約し、canonical昇格は手動補正で行う。Relationshipは両端解決済みのみ昇格する
- fact（script / ai_extracted）とinference（ai_inferred）はマージで混ぜない。FieldValue単位でsourceTypeを維持する
- Timelineはエンティティ統合せず、kind別のエピソード横断集約（timeline_entries.json）までをStage Bの責務とする。順序の確定・矛盾検出はしない
- 手動補正は独立したoverrideファイル（`knowledge/overrides/`、Git管理）で行い、merged/配下は常に再生成可能な生成物に保つ。`sourceType: manual`は再マージで上書きされない
- conflictは黙って解決せず、暫定採用ルールで続行しつつ必ずマージレポートへ記録する
- provenance（sourceCandidates / extractionRuns参照 / evidence埋め込み）により、merged entityからRaw Scriptの行まで遡れる状態を維持する
- 生成物は`data/extracted/`（Git管理外）、手動管理ソースは`knowledge/`（Git管理）に分離する
