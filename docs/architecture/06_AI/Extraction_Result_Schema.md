# Extraction Result Schema（抽出結果スキーマ設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Extraction_Result_Schema.md`

---

# 1. 目的

この文書は、`Extraction_Pipeline.md` で定義したExtraction Phaseの出力（Extracted Knowledge JSON）について、フィールド単位の構造を確定させることを目的とする。

`Extraction_Pipeline.md` は抽出対象・処理単位・保存方針という「パイプライン全体の設計」を扱う文書であり、各抽出候補オブジェクトの構造は例示レベルにとどめていた。
本文書はその続きとして、`schemas/extraction.schema.json` をはじめとするJSON Schema群を実装する **直前** に固めるべきフィールド定義を扱う。

前提として以下を踏まえる。

- `AI_CONTEXT.md` 4.3: Raw Scriptを直接AIへ渡さない
- `AI_CONTEXT.md` 4.4: Evidence First。抽出結果には必ず根拠IDを持たせる
- `AI_CONTEXT.md` 4.5: 公式情報・AI Summary・AI考察を分離する
- `AI_CONTEXT.md` 4.7: Local First AI
- `Identifier_Specification.md`: Story/Episode/Scene/Block ID体系、Entity ID（`CHAR_`/`ORG_`/`LOC_`/`ITEM_`/`EVENT_`/`LORE_`）、Evidence ID
- `Normalized_Story_JSON.md`: Extraction Pipelineの入力となるBlock構造（`dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`）
- `Extraction_Pipeline.md`: Extraction Phase全体の設計（§4 抽出対象、§6 Evidenceの扱い、§7 fact/inference分離、§8 LLM providerの使い分け・Structured JSON必須・失敗時の扱い、§9 data/extracted/ の保存方針）

本文書はスキーマの **設計** のみを対象とする。
JSON Schema・Pythonコードの実装は別文書・別作業とする（本文書作成時点では未着手）。

---

# 2. 入力: Normalized Story JSON

Extraction Result Schemaが前提とする入力は `Extraction_Pipeline.md` §2 と同一であり、変更はない。

- 入力単位: `schemas/story.schema.json` 準拠のエピソード単位JSON（`data/normalized/**/{episodeId}.json`）
- 処理単位: 1エピソードJSON = 1回の抽出実行（`Extraction_Pipeline.md` §2.2）
- 除外条件: `compatibilityReport.parserCompatibility` が `blocked`、またはスキーマ検証失敗（`Extraction_Pipeline.md` §2.3）

本文書が新たに定義するのは、この入力から生成される **出力側** の各オブジェクトのフィールドである。

---

# 3. 出力: Extracted Knowledge JSON

## 3.1 対象ドキュメント

本文書がフィールドを定義する対象は、`Extraction_Pipeline.md` §3.1 の二段階構成のうち、主にStage A（`data/extracted/_raw/{episodeId}.extraction.json`）に格納される候補オブジェクト群である。
Stage B（マージ済みエンティティ）のフィールド構造は、Stage Aの候補オブジェクトが持つ `fields`（§4.3 FieldValue）をそのまま引き継ぐため、本文書ではStage A側の定義を正とし、Stage B固有のフィールド（`mergedFrom`/`lastMergedAt` 等）は `Extraction_Pipeline.md` §3.3 を参照する。

## 3.2 episode_extraction ドキュメント構造の確定

`Extraction_Pipeline.md` §3.2 のStage A基本構造に、Evidenceの正規化格納先として `evidenceIndex`、失敗記録の即時参照先として `extractionErrors` を追加する。

```json
{
  "schemaVersion": "0.1",
  "documentType": "episode_extraction",
  "episodeId": "MAIN_S01_C02_E01",
  "storyId": "MAIN_S01_C02",
  "storyCategory": "MAIN",
  "extractionRun": {
    "extractionVersion": "0.1.0",
    "extractionMethod": "llm",
    "modelProvider": "ollama",
    "modelName": "qwen3:8b",
    "promptVersion": "episode_extraction_v0.1",
    "extractedAt": null,
    "parserCompatibilityAtExtraction": "compatible"
  },
  "evidenceIndex": {},
  "characters": [],
  "organizations": [],
  "locations": [],
  "items": [],
  "lore": [],
  "events": [],
  "relationships": [],
  "timelineCandidates": [],
  "extractionErrors": []
}
```

`evidenceIndex` はこのエピソードの抽出で参照された全EvidenceRefを `sourceId` をキーに保持するオブジェクトとする（§5.2）。
各候補オブジェクトは、EvidenceRef全体を埋め込まず、`evidenceIds`（§4.1）としてキーだけを持つ。
埋め込み方式ではなくインデックス方式を採る理由は§5.3で述べる。

`extractionErrors` は§14で定義するExtractionErrorの配列。
エピソード単位の抽出が部分的に成功した場合（一部の候補は抽出できたが特定タスクだけ失敗した場合など）に、成功分と失敗分を同一ドキュメント内で両立させるために置く。
エピソード全体が失敗した場合の扱いは§14.3で扱う。

---

# 4. 共通フィールド

§6〜§13で定義するCandidateオブジェクト（CharacterCandidate / LocationCandidate / OrganizationCandidate / ItemCandidate / LoreCandidate / EventCandidate / RelationshipCandidate / TimelineCandidate）は、すべて以下の共通フィールドを持つ。
これを **CandidateEnvelope** と呼ぶ。

## 4.1 フィールド定義

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `id` | Yes | string | 候補ID。Stage Aでは§4.2の暫定候補ID形式、Stage Bへ昇格後は確定Canonical ID（`CHAR_*`等、`Identifier_Specification.md` §6）に置き換わる |
| `type` | Yes | string | 候補種別のdiscriminator。enum: `character_candidate` / `location_candidate` / `organization_candidate` / `item_candidate` / `lore_candidate` / `event_candidate` / `relationship_candidate` / `timeline_candidate` |
| `sourceType` | Yes | string | 候補全体を代表する情報源区分。enum: `official` / `script` / `ai_extracted` / `ai_inferred` / `manual` / `unknown`（`Extraction_Pipeline.md` §7.1と同一語彙） |
| `confidence` | Yes | number | 0.0〜1.0。候補全体を代表するconfidence |
| `evidenceIds` | Yes | string[] | この候補の根拠となる`EvidenceRef.sourceId`の配列。最低1件必須（§6.1で定義するEvidence必須ルールに従う） |
| `extractionRun` | Yes | object | `Extraction_Pipeline.md` §3.2と同一構造。候補単体を切り出して扱っても出自を追跡できるよう、ドキュメント側の`extractionRun`をそのまま複製して埋め込む |

## 4.2 `id` の形式（Stage A: 候補ID）

Stage Aの時点では、候補はまだcanonical IDへ解決されていない（`existing*Id` が`null`の候補も多い、§6〜§13参照）。
そのため、`id` にはエピソード・種別スコープの暫定IDを割り当てる。

形式:

```text
{episodeId}_CAND_{TYPE}{number}
```

`TYPE` は種別ごとに固定の短縮語を使う。
`number` は1始まり、3桁ゼロ埋め、種別ごとに独立採番する（`Identifier_Specification.md` §5のBlock ID採番方式に準拠）。

| type | TYPE短縮語 | 例 |
|---|---|---|
| `character_candidate` | `CHAR` | `MAIN_S01_C02_E01_CAND_CHAR001` |
| `location_candidate` | `LOC` | `MAIN_S01_C02_E01_CAND_LOC001` |
| `organization_candidate` | `ORG` | `MAIN_S01_C02_E01_CAND_ORG001` |
| `item_candidate` | `ITEM` | `MAIN_S01_C02_E01_CAND_ITEM001` |
| `lore_candidate` | `LORE` | `MAIN_S01_C02_E01_CAND_LORE001` |
| `event_candidate` | `EVENT` | `MAIN_S01_C02_E01_CAND_EVENT001` |
| `relationship_candidate` | `REL` | `MAIN_S01_C02_E01_CAND_REL001` |
| `timeline_candidate` | `TL` | `MAIN_S01_C02_E01_CAND_TL001` |

この暫定ID形式は `Identifier_Specification.md` にはまだ存在しないため、本文書で新規定義する。
将来同文書へ統合する場合は、Evidence ID（§8同文書）と同様に「最小単位を参照する」思想を踏襲する。

Stage Bへ昇格した時点で、`id` は `existing*Id` に設定されていたcanonical ID、または手動補正で新規採番されたcanonical IDに置き換わる（`Extraction_Pipeline.md` §8.4 手動補正）。
暫定IDは `mergedFrom` の実体を辿るための参照情報としてのみ残る。

## 4.3 FieldValue（候補内の属性値）

CandidateEnvelopeの`sourceType`/`confidence`は候補全体を代表する値であり、属性（フィールド）ごとの粒度は表さない。
属性ごとにfact/inferenceを分離する必要がある場合（`Extraction_Pipeline.md` §7.1）、各Candidateは`fields`オブジェクトを持ち、その値として以下の **FieldValue** 構造を使う。

```json
{
  "value": "異形生物対策班の作戦参謀。",
  "sourceType": "ai_extracted",
  "confidence": 0.9,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0007"]
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `value` | Yes | any | 属性値（`null`可） |
| `sourceType` | Yes | string | CandidateEnvelopeと同一語彙 |
| `confidence` | Yes | number | 0.0〜1.0 |
| `evidenceIds` | No | string[] | この属性値固有の根拠。省略時は候補全体の`evidenceIds`を根拠とみなす |

`sourceType`テーブルの意味・運用（`ai_inferred`をWikiの「AI考察」セクションへ振り分ける等）は`Extraction_Pipeline.md` §7.1〜§7.3を正とし、本文書では重複記載しない。

## 4.4 Evidenceなし推定情報の扱い

`sourceType: "ai_inferred"` は、本文に直接明記されていない推測情報を表す（`Extraction_Pipeline.md` §7.1）。
ここでいう「Evidenceなし」とは、推測内容そのものを一字一句引用できるBlockが存在しないことを指すのであって、根拠となる文脈Blockまで不要という意味ではない。

- `ai_inferred` な値であっても、`evidenceIds`（候補全体またはFieldValue単位）は必ず1件以上持つ。推測の元になった文脈Blockを根拠として記録する
- 推測の根拠となるBlockが1件も特定できない場合、その推測は出力しない（`Extraction_Pipeline.md` §6.1「Evidenceを1件も持たない抽出結果は出力しない」を`ai_inferred`にも同様に適用する）
- `ai_extracted`（本文に明記）と`ai_inferred`（本文からの推測）の違いは、Evidenceの有無ではなく、Evidence本文と出力値が **直接一致するか・解釈を挟むか** の違いである

---

# 5. EvidenceRef

## 5.1 構造

`Identifier_Specification.md` §8の形式をそのまま踏襲する。

```json
{
  "sourceId": "MAIN_S01_C02_E01_DLG0007",
  "storyId": "MAIN_S01_C02",
  "episodeId": "MAIN_S01_C02_E01",
  "sceneId": "MAIN_S01_C02_E01_SC001",
  "confidence": 0.94
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `sourceId` | Yes | string | 根拠Block ID（`_DLG`/`_MONO`/`_NAR`/`_CHOICE`優先。粗い場合はScene/Episode/Story ID） |
| `storyId` | Yes | string | Story ID |
| `episodeId` | Yes | string | Episode ID |
| `sceneId` | No | string | Scene ID。`sourceId`がScene単位以上に粗い場合は省略可 |
| `confidence` | Yes | number | この根拠自体の確からしさ（Parser側の`source.confidence`とは別軸。Extraction時点でLLMがこのBlockを根拠として選んだ確からしさ） |

## 5.2 evidenceIndexへの格納

Stage Aドキュメントでは、EvidenceRefを候補ごとに埋め込まず、ドキュメント直下の`evidenceIndex`に`sourceId`をキーとして格納する。

```json
{
  "evidenceIndex": {
    "MAIN_S01_C02_E01_DLG0007": {
      "sourceId": "MAIN_S01_C02_E01_DLG0007",
      "storyId": "MAIN_S01_C02",
      "episodeId": "MAIN_S01_C02_E01",
      "sceneId": "MAIN_S01_C02_E01_SC001",
      "confidence": 0.94
    }
  }
}
```

各候補（§4）は`evidenceIds: ["MAIN_S01_C02_E01_DLG0007"]`のようにキーの配列だけを持ち、`evidenceIndex`を引くことでEvidenceRef全体を取得する。

## 5.3 埋め込み方式ではなくインデックス方式を採る理由

`Extraction_Pipeline.md` §3.2〜§4の例示では、各候補が`evidence: []`としてEvidenceRefそのものを直接埋め込んでいた。
本文書ではこれを`evidenceIndex` + `evidenceIds`参照方式に変更する。

- 1エピソードの抽出では、複数の候補が同一Blockを根拠に引用することが多い（例: 同一Dialogueが Character・Organization・Relationship 全ての根拠になる）。EvidenceRefをそのつど埋め込むと、`storyId`/`episodeId`など同一エピソード内でほぼ不変な値が候補数だけ重複する
- Evidence Viewer（`Normalized_Story_JSON.md` §1で将来利用者として想定されているコンポーネント）が「このBlockはどの候補から参照されているか」という逆引きを行う際、`evidenceIndex`のキー集合を起点に候補側の`evidenceIds`をスキャンする形で実装しやすい
- Stage Bへのマージ時、同一Evidenceを複数候補が共有しているケースの重複排除が、インデックス方式の方がシンプルになる

Stage B（マージ済みエンティティ、`Extraction_Pipeline.md` §3.3）は複数エピソードを横断するため、`evidenceIndex`をエピソード単位で持つ前提が崩れる。
Stage Bのエンティティファイルでは、`evidence`フィールドとしてEvidenceRefそのものを配列で埋め込む方式（`Extraction_Pipeline.md` §3.3の例のまま）を維持し、インデックス方式はStage A限定とする。

---

# 6. CharacterCandidate

`Extraction_Pipeline.md` §4.1を、CandidateEnvelope（§4）を継承する形で確定させる。

```json
{
  "id": "MAIN_S01_C02_E01_CAND_CHAR001",
  "type": "character_candidate",
  "sourceType": "ai_extracted",
  "confidence": 0.9,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0007"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingCharacterId": "CHAR_RAIN",
  "sourceCharacterId": "26",
  "nameCandidates": ["レイン"],
  "fields": {
    "description": {
      "value": "異形生物対策班の作戦参謀。",
      "sourceType": "ai_extracted",
      "confidence": 0.9
    },
    "personality": {
      "value": "冷静沈着だが仲間思い。",
      "sourceType": "ai_inferred",
      "confidence": 0.55
    }
  }
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingCharacterId` | No | string \| null | 既知キャラクター辞書と`sourceCharacterId`を突き合わせて解決できた場合のcanonical ID |
| `sourceCharacterId` | No | string \| null | 元スクリプト上のキャラクター番号（`Normalized Story JSON`の`speaker.sourceCharacterId`由来） |
| `nameCandidates` | Yes | string[] | 本文中に現れた名前表記の候補（表記揺れを含みうる） |
| `fields` | No | object\<string, FieldValue\> | `description`/`personality`等、属性ごとのfact/inference分離値。キー集合は固定しない（拡張可能） |

`existingCharacterId`が`null`の場合、Stage Bでは`data/extracted/_unresolved/characters.json`へ置かれる（§15）。
Character IDのローマ字化ルールは`Identifier_Specification.md` OD-001が未確定のため、AIには確定させない（同文書の方針を踏襲）。

---

# 7. LocationCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_LOC001",
  "type": "location_candidate",
  "sourceType": "script",
  "confidence": 0.95,
  "evidenceIds": ["MAIN_S01_C02_E01_NAR0001"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingLocationId": null,
  "nameCandidates": ["異形生物対策班　本部"],
  "sceneRefs": ["MAIN_S01_C02_E01_SC001"],
  "fields": {}
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingLocationId` | No | string \| null | 解決済みcanonical Location ID（`LOC_*`） |
| `nameCandidates` | Yes | string[] | 場所名の候補 |
| `sceneRefs` | Yes | string[] | この場所と紐づくScene IDの配列 |
| `fields` | No | object\<string, FieldValue\> | 場所の説明等（現時点では未使用でも空オブジェクトを許容） |

主な手がかりは`Scene.location.locationName`（`narrationType: location_label`）と背景系Stage Direction（`Normalized_Story_JSON.md` §21.1 `directionType: background`）。
背景コマンドからのLocation推定（Phase 1 Could項目）が実装され次第、根拠として`evidenceIds`に`stage_direction` BlockのIDも加わる。

---

# 8. OrganizationCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_ORG001",
  "type": "organization_candidate",
  "sourceType": "script",
  "confidence": 0.9,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0001"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingOrganizationId": null,
  "nameCandidates": ["異形生物対策班"],
  "memberCandidates": ["CHAR_RAIN"],
  "fields": {}
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingOrganizationId` | No | string \| null | 解決済みcanonical Organization ID（`ORG_*`） |
| `nameCandidates` | Yes | string[] | 組織名の候補 |
| `memberCandidates` | No | string[] | 所属メンバー候補（Character IDまたはCharacterCandidate `id`） |
| `fields` | No | object\<string, FieldValue\> | 組織の説明等 |

`memberCandidates`はAI推定であり、確定Relationshipへの自動昇格は行わない（`Extraction_Pipeline.md` §4.3）。
この制約を反映し、`memberCandidates`に列挙されたメンバーシップは、独立した`RelationshipCandidate`（`relationshipType: "MEMBER_OF"`等、§12）としても別途生成してよいが、`sourceType: "ai_inferred"`を付与する。

---

# 9. ItemCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_ITEM001",
  "type": "item_candidate",
  "sourceType": "script",
  "confidence": 0.85,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0003"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingItemId": null,
  "nameCandidates": ["デタリキ"],
  "fields": {}
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingItemId` | No | string \| null | 解決済みcanonical Item ID（`ITEM_*`） |
| `nameCandidates` | Yes | string[] | アイテム名の候補 |
| `fields` | No | object\<string, FieldValue\> | アイテムの説明等 |

---

# 10. LoreCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_LORE001",
  "type": "lore_candidate",
  "sourceType": "script",
  "confidence": 0.8,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0001"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingLoreId": null,
  "termCandidates": ["デタリキZ"],
  "fields": {
    "description": {
      "value": null,
      "sourceType": "unknown",
      "confidence": 0.0
    }
  }
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingLoreId` | No | string \| null | 解決済みcanonical Lore ID（`LORE_*`） |
| `termCandidates` | Yes | string[] | 用語表記の候補 |
| `fields` | No | object\<string, FieldValue\> | `description`等。`Extraction_Pipeline.md` §4.5の`descriptionCandidate`は本文書で`fields.description`（FieldValue）へ統合し、fact/inference分離を可能にする |

Character/Organization/Location/Itemのいずれにも分類できない固有名詞・設定用語が対象（`Identifier_Specification.md` §6.7）。

---

# 11. EventCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_EVENT001",
  "type": "event_candidate",
  "sourceType": "ai_extracted",
  "confidence": 0.75,
  "evidenceIds": ["MAIN_S01_C02_E01_NAR0003"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingEventId": null,
  "nameCandidates": ["ジャマー初出現"],
  "participantCandidates": ["CHAR_RAIN"],
  "locationCandidates": [],
  "fields": {}
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingEventId` | No | string \| null | 解決済みcanonical Event ID（`EVENT_*`。`Identifier_Specification.md` §6.6、イベントストーリー種別`EVT`とは別概念） |
| `nameCandidates` | Yes | string[] | 出来事名の候補 |
| `participantCandidates` | No | string[] | 関与したCharacter ID/candidate `id`の配列 |
| `locationCandidates` | No | string[] | 発生場所のLocation ID/candidate `id`の配列 |
| `fields` | No | object\<string, FieldValue\> | 出来事の詳細説明等 |

---

# 12. RelationshipCandidate

```json
{
  "id": "MAIN_S01_C02_E01_CAND_REL001",
  "type": "relationship_candidate",
  "sourceType": "ai_inferred",
  "confidence": 0.6,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0012"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "existingRelationshipId": null,
  "sourceCandidate": "CHAR_AKAGI_HINA",
  "targetCandidate": "CHAR_RAIN",
  "relationshipType": "TRUSTS",
  "direction": "source_to_target",
  "temporalNote": null,
  "fields": {
    "basis": {
      "value": null,
      "sourceType": "unknown",
      "confidence": 0.0
    }
  }
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `existingRelationshipId` | No | string \| null | 解決済みcanonical Relationship ID（`REL_*`、`Identifier_Specification.md` §7） |
| `sourceCandidate` | Yes | string | 関係の起点（Entity IDまたは対応するCandidate `id`） |
| `targetCandidate` | Yes | string | 関係の終点 |
| `relationshipType` | Yes | string | 語彙は`docs/architecture/04_Knowledge_Graph/Relationships.md`を正とする（本文書作成時点では未確定。§16.4参照） |
| `direction` | Yes | string | `source_to_target` / `target_to_source` / `bidirectional` |
| `temporalNote` | No | string \| null | 関係が変化した場合の変化契機。連番Relationship ID（`REL_..._0001`）と対応させる |
| `fields` | No | object\<string, FieldValue\> | `basis`（関係の根拠となる説明）等 |

`relationshipType`のenum値は未確定のため、本文書ではフィールド型を`string`とし、`schemas/extraction.schema.json`実装時点でも暫定的に自由文字列を許容し、`Relationships.md`確定後にenum制約へ切り替える方針とする（§16.4）。

---

# 13. TimelineCandidate

`Extraction_Pipeline.md` §4.8の構造は、他のCandidate型と異なりEpisode単位のコンテナに複数の候補をまとめる形だった。
本文書では、コンテナ内の各エントリもCandidateEnvelope（§4）に揃え、他のCandidate型との扱いを統一する。

```json
{
  "id": "MAIN_S01_C02_E01_CAND_TL001",
  "type": "timeline_candidate",
  "sourceType": "ai_inferred",
  "confidence": 0.7,
  "evidenceIds": ["MAIN_S01_C02_E01_DLG0002"],
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "kind": "relative_order",
  "relativeTo": "MAIN_S01_C01_E01",
  "relation": "after",
  "fields": {
    "basis": {
      "value": "本文中で前章の出来事に言及",
      "sourceType": "ai_extracted",
      "confidence": 0.7
    }
  }
}
```

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `kind` | Yes | string | 候補の種類。現時点では`relative_order`のみ定義（将来`absolute_date`等を追加しうる） |
| `relativeTo` | No | string \| null | `kind: "relative_order"`のとき、比較対象のEpisode ID |
| `relation` | No | string | `before` / `after` / `same_time`等 |
| `fields` | No | object\<string, FieldValue\> | `basis`（推定根拠の説明） |

TimelineCandidateはエンティティを持たないため、Stage Bのマージ対象外とし、`data/extracted/timeline_candidates/{episodeId}.json`にエピソード単位の配列としてそのまま保存する（`Extraction_Pipeline.md` §3.3, §4.8）。

---

# 14. ExtractionError

`Extraction_Pipeline.md` §8.5で定義した失敗モードを、構造化されたオブジェクトとして確定させる。

## 14.1 構造

```json
{
  "errorId": "MAIN_S01_C02_E01_ERR001",
  "episodeId": "MAIN_S01_C02_E01",
  "errorType": "schema_validation_failed",
  "message": "characters[2].fields.description.confidence is out of range",
  "extractionRun": {
    "...": "§3.2と同一構造"
  },
  "rawOutput": null,
  "relatedCandidateType": "character_candidate",
  "occurredAt": null,
  "retryable": true
}
```

## 14.2 フィールド定義

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `errorId` | Yes | string | エピソード内連番ID。形式`{episodeId}_ERR{number}`（3桁ゼロ埋め） |
| `episodeId` | Yes | string | 対象Episode ID |
| `errorType` | Yes | string | enum: `llm_call_failed` / `timeout` / `json_parse_failed` / `schema_validation_failed` / `evidence_missing` / `provider_unavailable`（`Extraction_Pipeline.md` §8.5） |
| `message` | Yes | string | 人間可読なエラー内容 |
| `extractionRun` | Yes | object | どの実行・providerで失敗したか（§3.2と同一構造） |
| `rawOutput` | No | string \| null | LLMの生出力（`json_parse_failed`等、デバッグに必要な場合のみ保持。機密性の高いスクリプト全文を含みうるため取り扱いに注意） |
| `relatedCandidateType` | No | string \| null | 失敗が特定のCandidate型に紐づく場合のtype値 |
| `occurredAt` | No | string \| null | ISO8601タイムスタンプ |
| `retryable` | Yes | boolean | 再実行で解消しうるか（`timeout`/`provider_unavailable`は`true`、`schema_validation_failed`はプロンプト修正が必要なため`false`を既定とする、等の目安） |

## 14.3 保存先とドキュメント内での扱い

失敗レポートは`data/reports/extraction_errors/{episodeId}.json`に保存する方針（`Extraction_Pipeline.md` §8.5）を、以下のように確定させる。

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "errors": [
    {
      "...": "§14.1のExtractionError"
    }
  ]
}
```

- エピソード全体の抽出が失敗した場合（LLM呼び出し自体が失敗、JSONが1件もパースできない等）: Stage A側の`data/extracted/_raw/{episodeId}.extraction.json`は生成せず、`data/reports/extraction_errors/{episodeId}.json`のみを出力する
- 一部の候補だけが失敗した場合（例: schema検証で`characters[2]`だけが弾かれた）: 成功した候補群は通常通りStage A出力に含め、失敗分は`extractionErrors`（§3.2のドキュメント直下フィールド）と`data/reports/extraction_errors/{episodeId}.json`の両方に記録する（ドキュメント内は実行直後の即時参照用、`data/reports/`側は横断集計・再実行対象の抽出用）

---

# 15. data/extracted/ 配置方針

`Extraction_Pipeline.md` §9のディレクトリ構成を、本文書で定義したオブジェクトに対応づける。

```text
data/extracted/
  _raw/
    {episodeId}.extraction.json        # §3.2 episode_extractionドキュメント一式
                                        # （evidenceIndex, CharacterCandidate[] 等 §6〜§13, extractionErrors[]）
  _unresolved/
    characters.json                    # existingCharacterId=null のCharacterCandidate集約
    organizations.json
    locations.json
    items.json
    lore.json
    events.json
  characters/
    {characterId}.json                 # Stage B: マージ済みエンティティ（Extraction_Pipeline.md §3.3）
  organizations/
    {organizationId}.json
  locations/
    {locationId}.json
  items/
    {itemId}.json
  lore/
    {loreId}.json
  events/
    {eventId}.json
  relationships/
    {relationshipId}.json
  timeline_candidates/
    {episodeId}.json                   # §13 TimelineCandidate配列（マージ対象外）

data/reports/
  extraction_errors/
    {episodeId}.json                   # §14.3 ExtractionError集約
```

`RelationshipCandidate`用の`_unresolved/`ディレクトリは設けない。
理由: Relationshipは`sourceCandidate`/`targetCandidate`双方が解決されて初めて意味を持つため、いずれかが未解決の間はStage Aの`relationships`配列内に留め置き、Stage Bマージ処理側で「両端が解決済みのRelationshipCandidateのみ`relationships/`へ昇格させる」というゲート条件を設ける（`Extraction_Pipeline.md` §9.2の`_unresolved/`方針を拡張）。

`data/extracted/`・`data/reports/extraction_errors/`はいずれも生成物であり、`.gitignore`の対象とする（`Extraction_Pipeline.md` §9.3と同じ方針）。

---

# 16. schemas/extraction.schema.json への接続方針

## 16.1 スキーマファイル構成

`Extraction_Pipeline.md` §10で列挙したschema一覧に対し、本文書のフィールド定義を反映した接続方針を確定させる（実装はまだ行わない）。

```text
schemas/
  extraction.schema.json               # 新規: episode_extraction ドキュメント全体のルートschema（§3.2に対応）
  evidence.schema.json                 # §5 EvidenceRef（$refで共有）
  extraction_error.schema.json         # §14 ExtractionError
  candidates/
    candidate_envelope.schema.json     # §4.1 CandidateEnvelope（$defsとして共有、他schemaからallOfで継承）
    field_value.schema.json            # §4.3 FieldValue（$refで共有）
    character_candidate.schema.json    # §6
    location_candidate.schema.json     # §7
    organization_candidate.schema.json # §8
    item_candidate.schema.json         # §9
    lore_candidate.schema.json         # §10
    event_candidate.schema.json        # §11
    relationship_candidate.schema.json # §12
    timeline_candidate.schema.json     # §13
```

`Extraction_Pipeline.md` §10.1で列挙していた`schemas/character.schema.json`等（Stage B確定エンティティ用）は、本文書のCandidate schemaとは別物として維持する。
Candidate schemaはStage A（未確定候補）、既存列挙のschemaはStage B（確定エンティティ）を検証する。

## 16.2 `extraction.schema.json`の構成方針

- ルートは§3.2のepisode_extraction構造をそのまま`properties`化する
- `characters`/`organizations`/`locations`/`items`/`lore`/`events`は、それぞれ対応するCandidate schemaへの配列参照（`items: { "$ref": ".../character_candidate.schema.json" }`等）とする
- `relationships`は`relationship_candidate.schema.json`への配列参照
- `timelineCandidates`は`timeline_candidate.schema.json`への配列参照
- `evidenceIndex`は`additionalProperties`として`evidence.schema.json`への参照を持つオブジェクトとする（キー=`sourceId`はフォーマット検証しない。Block ID命名規則の変更に追従しやすくするため）
- `extractionErrors`は`extraction_error.schema.json`への配列参照
- 各Candidate schemaは`candidate_envelope.schema.json`の必須プロパティ（§4.1）を`allOf`で継承し、型固有プロパティ（§6〜§13）を追加する形にする

## 16.3 バリデーションのタイミング

`Extraction_Pipeline.md` §8.1「LLM出力はStructured JSON必須」の運用として、`extraction.schema.json`（および子schema群）による検証は、LLM出力を受け取った直後、`data/extracted/_raw/`へ書き込む前に行う。
検証失敗時は§14 ExtractionError（`errorType: "schema_validation_failed"`）として記録し、不正なJSONを`data/extracted/`へ書き込まない。

## 16.4 未確定のまま残す点

- `relationshipType`（§12）のenum化は`Relationships.md`確定後に行う。それまでは`extraction.schema.json`側も自由文字列を許容する
- Candidate IDの暫定形式（§4.2）は、実運用でぶつかる問題（同一Blockから同種の候補が複数出るケースの採番順など）を見てから、必要なら本文書を改訂する
- `fields`（FieldValue辞書）のキー集合をCandidate型ごとに固定enumにするか、自由キーのまま運用するかは、実装・プロンプト設計と合わせて決定する

---

# 17. 採用方針

- 本文書は`Extraction_Pipeline.md`のフィールドレベル設計を継承・確定させるものであり、パイプライン全体の方針（LLM providerの使い分け、Structured JSON必須、失敗時の扱い等）は`Extraction_Pipeline.md`を正とする
- すべてのCandidateオブジェクトはCandidateEnvelope（§4.1: `id`/`type`/`sourceType`/`confidence`/`evidenceIds`/`extractionRun`）を共有し、`evidenceIds`（最低1件）でEvidenceRefを参照する
- EvidenceRefはStage Aでは`evidenceIndex`に正規化して格納し、候補側は`sourceId`参照のみ持つ（§5.3）
- 属性単位のfact/inference分離はFieldValue（§4.3）で行い、`ai_inferred`はEvidenceなし（本文に非明記）の推定情報を分離するために使う。ただし推測の根拠Blockそのものは省略しない（§4.4）
- ExtractionErrorは`data/reports/extraction_errors/{episodeId}.json`に保存し、成功分の出力とは独立して追跡する
- 実装（JSON Schema・Pythonコード）は本文書の対象外とし、`schemas/extraction.schema.json`実装時の接続方針（§16）のみを示す
