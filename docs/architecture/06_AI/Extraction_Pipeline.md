# Extraction Pipeline（AI抽出パイプライン設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Extraction_Pipeline.md`

---

# 1. 目的

この文書は、Detariki Knowledge Base（DKB）における **Extraction Phase**（Normalized Story JSONからKnowledge要素を抽出する工程）の設計を定義する。

Parser Phase 1により、Raw Scriptは以下の形へ正規化されるようになった。

```text
Raw Script
  ↓
Story Parser
  ↓
Normalized Story JSON
```

Extraction Phaseは、この続きを担う。

```text
Normalized Story JSON
  ↓
Extraction Pipeline（本文書の対象）
  ↓
Extracted Knowledge JSON
  ↓
Knowledge Graph Builder / Wiki Generator / AI Analysis Generator
```

前提として以下を踏まえる。

- `AI_CONTEXT.md` 4.3: Raw Scriptを直接AIへ渡さない。Extraction PhaseもNormalized Story JSONのみを入力とする。
- `AI_CONTEXT.md` 4.4: Evidence First。抽出結果には必ず根拠IDを持たせる。
- `AI_CONTEXT.md` 4.5: 公式情報・AI Summary・AI考察を分離する。
- `AI_CONTEXT.md` 4.7: Local First AI。ローカルLLM利用を前提とする。
- `Identifier_Specification.md`: Character / Organization / Location / Item / Event / Lore / Relationship のID体系。
- `Story_Metadata.md`: `sourceType` / `confidence` によるメタデータの情報源管理パターン。
- `Normalized_Story_JSON.md`: 入力となるStoryDocument構造（Episode / Scene / Block）。
- `Script_Compatibility_Check.md`: 不明情報を破棄せず段階的に扱うという方針。
- `Parser_Implementation_Plan.md`: Phase単位で設計書→schema→実装→テストの順に進めるという開発フロー。

この文書はExtraction Phaseの **設計** のみを対象とする。JSON Schema・Pythonコードの実装は別文書・別作業とする（本文書作成時点では未着手）。

---

# 2. 入力: Normalized Story JSON

## 2.1 入力ファイル

Extraction Pipelineの入力は、`schemas/story.schema.json` に準拠した正規化済みストーリーJSONとする。

```text
data/normalized/main/MAIN_S01_C02_E01.json
data/normalized/event/EVT_0162_E01.json
data/normalized/character/CHAR_MAIN_AKAGI_HINA_E01.json
```

## 2.2 処理単位としての入力粒度

現状の `scripts/normalize_story.py` はエピソード単位でファイルを出力する（`Parser_Implementation_Plan.md` Phase 9）。Extraction Pipelineもこれに合わせ、**1エピソードJSON = 1回の抽出実行の最小入力単位** とする。

理由:

- LLMのコンテキスト長に収まりやすい
- エピソード単体でのdiff・再実行がしやすい（スクリプト差し替え時の再抽出コストを局所化する）
- `compatibilityReport` がエピソード単位で付与されているため、`parserCompatibility` が `needs_update` / `blocked` のエピソードを抽出対象から機械的に除外しやすい

複数エピソード・複数ストーリーにまたがる情報（同一キャラクターが複数章に登場する等）は、エピソード単位の抽出結果を後段でマージすることで扱う（§9参照）。章単位のNormalized Story JSONが将来追加された場合も、同じ扱いとする。

## 2.3 抽出対象から除外する入力状態

以下のエピソードは、Extraction Pipelineの入力から自動的に除外する（後述の互換性ゲートで弾く）。

- `compatibilityReport.parserCompatibility` が `blocked`
- スキーマ検証（`story.schema.json`）に失敗するファイル

`needs_update` / `warning` のエピソードは抽出自体は実行するが、抽出結果に `parserCompatibilityAtExtraction` を記録し、後で再抽出が必要な候補として追跡できるようにする。

---

# 3. 出力: Extracted Knowledge JSON

## 3.1 二段階構成

Extraction Pipelineの出力は2段階に分ける。

```text
Stage A: Raw Extraction（エピソード単位の抽出結果）
  data/extracted/_raw/{episodeId}.extraction.json

Stage B: Merged Knowledge（エンティティ単位に統合された結果）
  data/extracted/characters/{characterId}.json
  data/extracted/organizations/{organizationId}.json
  data/extracted/locations/{locationId}.json
  data/extracted/items/{itemId}.json
  data/extracted/lore/{loreId}.json
  data/extracted/events/{eventId}.json
  data/extracted/relationships/{relationshipId}.json
  data/extracted/timeline_candidates/{episodeId}.json
```

理由:

- 1エピソードの抽出だけでは、あるキャラクターの全体像（初登場・別名・所属変遷など）は分からない
- Stage Aはエピソード単体の「観測結果」、Stage Bはストーリー横断で統合した「現時点のKnowledge」という役割分担にする
- Stage Aは常に再生成可能な中間生成物として扱い、Stage Bのマージロジックを後から改善しても、Stage Aを再利用して再マージできるようにする

## 3.2 Stage A: Raw Extraction 基本構造

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
    "modelProvider": null,
    "modelName": null,
    "promptVersion": null,
    "extractedAt": null,
    "parserCompatibilityAtExtraction": "compatible"
  },
  "characters": [],
  "organizations": [],
  "locations": [],
  "items": [],
  "lore": [],
  "events": [],
  "relationships": [],
  "timelineCandidates": []
}
```

各配列要素は §4 で定義する抽出対象ごとの候補オブジェクトとし、必ず `evidence` を持つ（§6）。

## 3.3 Stage B: Merged Knowledge 基本構造

エンティティ単位ファイルは、複数エピソードから集まった候補をマージした結果を保持する。

```json
{
  "schemaVersion": "0.1",
  "documentType": "extracted_character",
  "id": "CHAR_AKAGI_HINA",
  "canonicalName": "赤城陽菜",
  "aliases": [],
  "fields": {},
  "evidence": [],
  "mergedFrom": [
    "MAIN_S01_C02_E01",
    "CHAR_MAIN_AKAGI_HINA_E01"
  ],
  "lastMergedAt": null
}
```

`fields` の中身は §4 / §7 で定義するfact / inference分離構造に従う。`documentType` はエンティティ種別ごとに変える（`extracted_character` / `extracted_organization` / `extracted_location` / `extracted_item` / `extracted_lore` / `extracted_event` / `extracted_relationship`）。

`timelineCandidates` はエンティティではないため、Stage Bではマージせずエピソード単位のまま `data/extracted/timeline_candidates/` に保持する（§4.8）。

---

# 4. 抽出対象

Extraction Pipelineは以下8種類を抽出する。

## 4.1 Character

対象: 作中に登場する人物。

```json
{
  "candidateId": null,
  "existingCharacterId": "CHAR_RAIN",
  "sourceCharacterId": "26",
  "nameCandidates": ["レイン"],
  "fields": {
    "description": { "value": null, "sourceType": "unknown", "confidence": 0.0 }
  },
  "evidence": []
}
```

- `existingCharacterId` は既知キャラクター辞書（`reference/parser/characters_reference.json` 相当、将来は `knowledge/dictionaries/characters.yaml`）と `sourceCharacterId` を突き合わせて解決できた場合のみ設定する
- 解決できない場合は `existingCharacterId: null` とし、`nameCandidates` を手動レビュー・canonical ID割り当ての材料として残す（§8.3）
- Character IDの正規化ルールは `Identifier_Specification.md` 6.1 に従う（`CHAR_{ROMANIZED_NAME}`）。ローマ字化・canonical ID確定はAIに任せない（同文書 OD-001の未確定事項を踏襲し、手動確定を必須とする）

## 4.2 Location

対象: 場面が発生する場所。

```json
{
  "candidateId": null,
  "existingLocationId": null,
  "nameCandidates": ["異形生物対策班　本部"],
  "sceneRefs": ["MAIN_S01_C02_E01_SC001"],
  "evidence": []
}
```

主な手がかりは `Scene.location.locationName`（`narrationType: location_label` のNarration Block）と、背景系Stage Direction（`bg` コマンド等）。Phase 1 Parserの `Could` 項目（背景コマンドからLocationを推定）が実装され次第、Stage Directionもソースに加える。

## 4.3 Organization

対象: 作中の組織・チーム・勢力。

```json
{
  "candidateId": null,
  "existingOrganizationId": null,
  "nameCandidates": ["異形生物対策班"],
  "memberCandidates": ["CHAR_RAIN"],
  "evidence": []
}
```

`memberCandidates` はAI推定（`ai_inferred`）として扱い、確定Relationshipには自動昇格しない（§7）。

## 4.4 Item

対象: 作中に登場する固有名詞のアイテム・装備・概念的道具。

```json
{
  "candidateId": null,
  "existingItemId": null,
  "nameCandidates": ["デタリキ"],
  "evidence": []
}
```

## 4.5 Lore

対象: 世界観・用語・固有概念（`Identifier_Specification.md` 6.7 の `LORE_` に対応）。Character / Organization / Location / Item のいずれにも分類できない固有名詞・設定用語をここに収める。

```json
{
  "candidateId": null,
  "existingLoreId": null,
  "termCandidates": ["デタリキZ"],
  "descriptionCandidate": null,
  "evidence": []
}
```

## 4.6 Event（作中出来事）

対象: 作中で発生した出来事（`Identifier_Specification.md` 6.6 の `EVENT_`。イベントストーリー種別 `EVT` とは別概念）。

```json
{
  "candidateId": null,
  "existingEventId": null,
  "nameCandidates": ["ジャマー初出現"],
  "participantCandidates": ["CHAR_RAIN"],
  "locationCandidates": [],
  "evidence": []
}
```

## 4.7 Relationship

対象: エンティティ間の関係（人物間・人物と組織・人物と場所など）。

```json
{
  "candidateId": null,
  "existingRelationshipId": null,
  "sourceCandidate": "CHAR_AKAGI_HINA",
  "targetCandidate": "CHAR_RAIN",
  "relationshipType": "TRUSTS",
  "direction": "source_to_target",
  "temporalNote": null,
  "fields": {
    "basis": { "value": null, "sourceType": "unknown", "confidence": 0.0 }
  },
  "evidence": []
}
```

- `relationshipType` の語彙は `docs/architecture/04_Knowledge_Graph/Relationships.md` を正とする（本文書作成時点では空プレースホルダーのため、Extraction Phase着手時に合わせて定義する）
- 時間経過で変化する関係は `Identifier_Specification.md` §7 の連番ID（`REL_..._0001`）に対応させ、`temporalNote` に変化のきっかけとなったEvidenceを記録する

## 4.8 Timeline candidate

対象: 作中時系列（`canonicalOrder`）を推定するための手がかり。確定Timelineそのものではなく、あくまで **候補** として保持する（`Story_Metadata.md` OD-002）。

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "candidates": [
    {
      "kind": "relative_order",
      "relativeTo": "MAIN_S01_C01_E01",
      "relation": "after",
      "basis": "本文中で前章の出来事に言及",
      "evidence": [],
      "confidence": 0.7
    }
  ]
}
```

Timeline candidateはエンティティを持たないため、Stage Bでのマージ対象外とし、エピソード単位のまま `data/extracted/timeline_candidates/` に保存する（§3.3）。将来のTimeline Builder（`AI_CONTEXT.md` §19 次フェーズ候補）が、複数エピソードのcandidateを統合して確定Timelineを構築する。

---

# 5. 処理単位

Extraction PipelineはNormalized Story JSONの階層（`Normalized_Story_JSON.md` §4）に沿って、以下の単位で処理する。

## 5.1 Story

- 複数エピソードにまたがる情報（Character/Organization/Locationなど）を統合する単位
- Extraction Pipeline自体はStory単位で一括実行するのではなく、Episode単位の実行結果をStory単位で束ねてマージする（§9）

## 5.2 Episode

- Extraction実行（LLM呼び出し）の基本単位（§2.2）
- 1回の実行で `characters` / `organizations` / `locations` / `items` / `lore` / `events` / `relationships` / `timelineCandidates` をまとめて抽出する（Block走査は1回で済ませ、LLM呼び出し回数を抑える）

## 5.3 Scene

- Location推定の単位
- Scene内の全Blockを、そのSceneの `location` 候補の根拠として扱える

## 5.4 Block

- Evidenceの最小単位（`Identifier_Specification.md` §8の優先順位: Dialogue > Monologue > Narration > Choice Option > Scene > Episode > Story）
- 抽出対象として直接読むのは `dialogue` / `monologue` / `narration` / `choice` の4種
- `stage_direction` は本文抽出の対象ではないが、Location（背景コマンド）やItem（演出上の小道具言及）の補助的手がかりとして参照してよい
- `unknown` はExtraction Pipelineの入力としては無視する（Parser側で `unknown` のまま残っている時点で、本文境界が不確実であるため）。ただし `unknownCommands` / `unknownCharacterIds` が多いエピソードは §2.3 の互換性ゲートで弾かれる想定

---

# 6. Evidenceの扱い

## 6.1 共通ルール

Extraction Pipelineが生成するすべての候補オブジェクト（Character/Organization/Location/Item/Lore/Event/Relationship/Timeline candidate）は、`evidence` 配列を最低1件持つ。Evidenceを1件も持たない抽出結果は出力しない（Evidenceなしの推測は捨てる）。

## 6.2 Evidence構造

`Identifier_Specification.md` §8 の形式をそのまま踏襲する。

```json
{
  "sourceId": "MAIN_S01_C02_E01_DLG0007",
  "storyId": "MAIN_S01_C02",
  "episodeId": "MAIN_S01_C02_E01",
  "sceneId": "MAIN_S01_C02_E01_SC001",
  "confidence": 0.94
}
```

- `sourceId` はBlock ID（`_DLG`/`_MONO`/`_NAR`/`_CHOICE`）を優先する。Block単位で根拠を特定できない場合のみ、Scene ID → Episode ID → Story IDへ段階的に粗くする
- 複数Blockにまたがる根拠は `evidence` 配列に複数エントリを追加する（1エントリに複数sourceIdを詰め込まない）

## 6.3 Evidenceと `source.raw` の関係

Normalized Story JSONの各BlockはすでにEvidence用の `source`（sourceFile/lineStart/lineEnd/raw）を持つ（`Normalized_Story_JSON.md` §23）。Extraction Pipelineは新たに行番号を再計算せず、参照先BlockのIDのみを保持する。元テキストへ遡る必要がある場合は、Block IDからNormalized Story JSONを引き直せばよい（Evidence情報の二重管理を避ける）。

---

# 7. AI推定と本文根拠の分離

## 7.1 fact / inference の分離

`Story_Metadata.md` §9 の `metadataSources` パターンを、抽出結果のフィールド単位に適用する。

```json
{
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

| `sourceType` | 意味 | Extraction Pipelineでの扱い |
|---|---|---|
| `official` | 公式資料由来 | Extraction Pipelineでは基本的に生成しない（手動投入専用） |
| `script` | スクリプト本文に明記 | 本文中の直接的な記述から抽出したフィールドに使う |
| `ai_extracted` | AIが本文から抽出（本文に書かれている内容の要約） | 通常の抽出結果の既定値 |
| `ai_inferred` | AIが本文から推測（本文に明記されていない） | 性格・関係性の解釈など、推測を含むフィールドに使う |
| `manual` | 人間が手動補正 | §8.3のレビュー後に上書きされた値 |
| `unknown` | 未確定 | 値がまだ得られていないプレースホルダー |

## 7.2 分離の目的

`AI_CONTEXT.md` 4.5「公式情報とAI Summary/AI考察を分離する」をExtraction Phaseの時点から満たすため、次の2種類を必ず別フィールドとして保持する。

- **fact系フィールド**（`script` / `ai_extracted`）: 本文に書かれている内容の要約。Wikiの「本編内での言及」セクションの元データになる
- **inference系フィールド**（`ai_inferred`）: 本文に明記されていない考察・解釈。Wikiの「AI考察」セクションの元データになる

Wiki Generator（後続フェーズ）は、この `sourceType` を見てセクションを振り分ける前提とする。Extraction Pipeline側でfact/inferenceを混在させると、後段で分離できなくなるため、ここでの分離が必須となる。

## 7.3 confidence

`confidence` は0.0〜1.0の実数とする。閾値の絶対的な基準はモデル・プロンプトに依存するため本文書では固定しないが、次の運用を推奨する。

- `confidence < 0.4` の候補はStage Bへのマージ時に「要レビュー」として隔離し、自動採用しない
- 同一フィールドに対して複数エピソードから矛盾する値が得られた場合、`confidence` が高い方を暫定採用しつつ、両方をEvidenceとして保持する（矛盾自体もWikiの「矛盾点」ページの入力になり得るため、破棄しない）

---

# 8. ローカルLLM / 外部LLM Provider / 手動補正の使い分け

`AI_CONTEXT.md` 4.7「Local First AI」を、Extraction Pipelineの処理系列ごとに具体化する。

## 8.1 出力形式: Structured JSON必須（共通ルール）

ローカルLLM・外部LLM Providerのどちらを使う場合でも、LLM呼び出しの最終出力は **Structured JSON** とする。

- 自由文（説明文・Markdown・コードフェンス付きJSONなど）は最終出力として受け付けない。プロンプト側でJSON以外の出力形式を許容しない
- 得られたJSONは §10 で定義予定の各schema（`episode_extraction.schema.json` 等）で検証し、検証に通ったものだけを `data/extracted/` へ書き込む
- 検証に失敗したレスポンスは破棄せず、§8.5の失敗レポートとして保存する

## 8.2 ローカルLLM（既定 / デフォルトprovider）

対象:

- Character / Organization / Location / Item / Lore / Event の抽出（§4.1〜4.6）
- Relationship候補の抽出（§4.7）
- Timeline candidateの抽出（§4.8）

理由（`AI_CONTEXT.md` 4.7）:

- 全ストーリーを繰り返し再抽出する前提のため、従量課金APIでは処理コストが積み上がる
- 手元のGPUを活用できる
- スクリプト全文をローカル完結で処理でき、外部送信の懸念を避けられる

Extraction Pipelineの **既定（デフォルト）provider** はローカルLLM providerとする。想定するローカルprovider例:

- `ollama`
- `lmstudio`

`extractionRun.extractionMethod: "llm"`、`extractionRun.modelProvider` にローカルprovider名を記録する。

```json
{
  "extractionVersion": "0.1.0",
  "extractionMethod": "llm",
  "modelProvider": "ollama",
  "modelName": "qwen3:8b",
  "promptVersion": "episode_extraction_v0.1",
  "extractedAt": null,
  "parserCompatibilityAtExtraction": "compatible"
}
```

## 8.3 外部LLM Provider（補助用途のみ）

対象:

- ローカルLLMで精度不足が確認された特定タスク（複雑な関係性推論、長距離文脈が必要な矛盾検出など）
- 品質検証用のサンプル比較（同一エピソードをローカルLLMと外部LLM Providerの両方で抽出し、精度差を確認する用途）

想定する外部LLM Provider例（特定ベンダー固定ではなく、設定で切り替え可能なprovider抽象の一例として扱う）:

- `openai`
- `anthropic`
- `gemini`
- `openrouter`

`extractionRun.extractionMethod: "llm"`、`extractionRun.modelProvider` に上記いずれかのprovider名を記録し、通常運用のデフォルトにはしない。APIキーは `AI_CONTEXT.md` 13.5 の通り `.env` / 環境変数で管理し、リポジトリに含めない。

**Raw ScriptやNormalized Story JSONの全文データを外部LLM Providerへ送信するのは、利用者が明示的に外部Providerを設定した場合に限る。** 既定（ローカルLLM）運用では、本文データが外部へ送信されることはない。

## 8.4 手動補正

AIに任せず、必ず人間が確定させる項目:

- Character / Organization / Location / Item / Lore / Event のcanonical ID割り当て（`Identifier_Specification.md` OD-001「ローマ字表記ルール」を踏まえ、主要エンティティは手動でcanonical IDを管理する方針を採用済み）
- 表記揺れ・別名のエンティティ統合（同一人物と判定するかどうかの最終判断）
- `confidence` が低い、または競合するRelationshipの採否
- Stage Bマージ時に「要レビュー」隔離された候補の採否（§7.3）

手動補正の結果は `sourceType: "manual"`、`confidence: 1.0` として記録し、以後の自動マージで上書きされないようにする（`fields.<name>.sourceType` が `manual` のフィールドは、再抽出時に自動更新の対象から除外する）。

## 8.5 失敗時の扱い

LLM呼び出し（ローカル・外部いずれのproviderでも）は以下の失敗モードを想定し、失敗を握りつぶさずレポートとして残す。

- `llm_call_failed`: provider呼び出し自体がエラーを返した
- `timeout`: 呼び出しが規定時間内に完了しなかった
- `json_parse_failed`: 出力がJSONとしてパースできなかった
- `schema_validation_failed`: パースはできたが§8.1のschema検証に通らなかった
- `evidence_missing`: `evidence` を1件も持たない候補のみが返り、§6.1のルールにより出力から除外された
- `provider_unavailable`: ローカルprovider未起動・外部provider APIキー未設定など、provider自体に到達できなかった

失敗レポートは `data/reports/extraction_errors/{episodeId}.json` に保存する。成功した候補（あれば）はStage Aの通常出力に書き込み、失敗分のみを失敗レポート側に切り分ける。

---

# 9. data/extracted/ の保存方針

## 9.1 ディレクトリ構成

```text
data/extracted/
  _raw/
    {episodeId}.extraction.json        # Stage A: エピソード単位の生抽出結果
  characters/
    {characterId}.json                 # Stage B
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
    {episodeId}.json                   # マージ対象外（§4.8）
```

## 9.2 未解決候補の置き場所

`existingCharacterId` 等が `null` のまま、まだcanonical IDへ解決されていない候補は、確定エンティティのディレクトリには置かない。

```text
data/extracted/_unresolved/
  characters.json
  organizations.json
  locations.json
  items.json
  lore.json
  events.json
```

手動補正（§8.3）でcanonical IDが確定した時点で、対応するディレクトリ（`characters/` 等）へ昇格させる。

## 9.3 Gitでの扱い

`data/extracted/` は生成物であり、`.gitignore` の既存ルール（`data/extracted/**/*.json`）に従いリポジトリへコミットしない。この方針は `feature/parser-phase1` で確立した「生成物・実スクリプトはコミットしない」というルール（§13.5 APIキー、および実運用で実際に事故が起きた `tests/fixtures/parser/` の教訓）と同じ理由による。

## 9.4 再実行と冪等性

- Stage A（`_raw/{episodeId}.extraction.json`）は、対応するNormalized Story JSONまたは抽出ロジック・プロンプトが変わるたびに再生成してよい使い捨てファイルとする
- Stage B（エンティティ単位ファイル）は `mergedFrom` にどのエピソードから統合されたかを記録し、特定エピソードの再抽出時に該当分だけ再マージできるようにする
- `sourceType: "manual"` のフィールドは再マージ時も保持する（§8.3）

---

# 10. 次に作るべきschema一覧

本文書の設計をJSON Schema化する際の対象一覧。現時点ではいずれも未着手（実装はしない）。

## 10.1 既存の空プレースホルダーを実装するもの

```text
schemas/character.schema.json
schemas/location.schema.json
schemas/organization.schema.json
schemas/item.schema.json
schemas/relationship.schema.json
schemas/timeline.schema.json
schemas/event.schema.json
```

これらは現在すべて0バイトのプレースホルダーであることを確認済み。§4のCharacter/Location/Organization/Item/Relationship/Timeline candidate/Eventの構造を、Stage B（`extracted_*`）の確定エンティティ形式として定義する。

## 10.2 新規追加が必要なもの

```text
schemas/lore.schema.json                  # §4.5 Lore（既存placeholderに存在しない）
schemas/episode_extraction.schema.json    # §3.2 Stage A: エピソード単位の生抽出結果
schemas/evidence.schema.json              # §6.2 Evidence共通構造（他schemaから$refで共有）
```

## 10.3 前提として先に固めるべき語彙定義

schema化より前に、以下の語彙・分類を確定させる必要がある（未確定のままschemaのenumを固定すると後で壊れやすいため）。

- `docs/architecture/04_Knowledge_Graph/Relationships.md`: `relationshipType` の語彙（現在空プレースホルダー）
- `docs/architecture/04_Knowledge_Graph/Node_Definitions.md`: Knowledge Graphのノードラベルとの対応関係（現在空プレースホルダー）
- キャラクター・組織・場所のcanonical ID辞書（`Identifier_Specification.md` OD-001/OD-003の未確定事項）

---

# 11. 採用方針

- Extraction Pipelineの入力はNormalized Story JSONのみとし、Raw Scriptを直接AIへ渡さない
- 抽出実行はEpisode単位、統合（マージ）はEntity単位（Story横断）で行う
- すべての抽出結果はEvidenceを最低1件持ち、Evidenceのない推測は出力しない
- fact（`script`/`ai_extracted`）とinference（`ai_inferred`）を必ず別フィールドとして分離する
- 通常の抽出処理はローカルLLM providerを既定とし、外部LLM Provider（openai / anthropic / gemini / openrouter 等）は補助用途に限定する
- LLM出力はStructured JSON必須とし、schema検証を通過したもののみ`data/extracted/`へ書き込む
- Raw Scriptや全文データを外部LLM Providerへ送信するのは、利用者が明示的に外部Providerを設定した場合に限る
- LLM呼び出しの失敗（呼び出し失敗・timeout・JSONパース失敗・schema検証失敗・evidence欠如・provider unavailable）は`data/reports/extraction_errors/{episodeId}.json`に記録する
- Canonical IDの確定・表記揺れの統合・低confidence候補の採否は人間が行う
- `data/extracted/` は生成物としてGit管理対象外とする
- Story/Episode Summary（Wikiのあらすじ表示用、AI考察とは別物）は本文書のExtraction Candidate群（Character/Location/...）とは別のデータ種別として扱う。データ構造・保存場所は`docs/architecture/06_AI/Story_Summary_Design.md`を参照
- Evidence index（Summary `evidenceRefs`の将来リンク先、§6のEvidence構造を再利用する公開用索引）の設計は`docs/architecture/06_AI/Evidence_Index_Design.md`を参照。生成元はNormalized Story JSON/Extraction Result、公開Wikiにはraw textを一切含めない方針
