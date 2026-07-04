# Wiki Output Design（Wiki出力設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/07_Wiki/Wiki_Output_Design.md`

---

# 1. 目的

この文書は、Stage B（`agents/merger/`、`docs/architecture/06_AI/Merged_Knowledge_Design.md`）が出力する merged knowledge collection から、将来どのようなWikiページを生成するかを設計する。

**このPRではWiki生成パイプラインの実装は行わない。** ページ種別・責務・front matter方針・出力ディレクトリ案・テンプレート方針・merged collectionとの対応表を整理し、実装PR分割案（§12）を示すことがゴールである。

---

# 2. Knowledge BaseとWikiの関係

```text
Raw Script (.dec)
  → Story Parser → Normalized Story JSON
  → Extractor (Stage A: episode_extraction, Candidate単位)
  → Merger (Stage B: merged knowledge collection, Entity単位)
  → Wiki Generation（本文書の対象）
```

- **Source of Truth は merged knowledge collection である。** `schemas/merged_knowledge.schema.json` / `schemas/merged_knowledge_collection.schema.json` に準拠したデータが、Wikiページの内容を決定する唯一の情報源になる。
- **Wikiページは生成物であり、原則として手編集しない。** Merged Knowledge Design（`Merged_Knowledge_Design.md` §11.1）が「生成物（`data/extracted/`）と手動管理ソース（`knowledge/`）を分離する」方針を採っているのと同じ原則を、Wiki層でも踏襲する。人間が加えたい情報は、Wikiページを直接編集するのではなく、`knowledge/overrides/`（manual override）を通じて merged knowledge collection 側に反映し、そこから再生成する。
- 例外として、`docs/`配下の設計文書・ランブック（本文書を含む）は人間が直接管理する。これらはWiki生成物ではなく、プロジェクトの設計・運用ドキュメントである。

---

# 3. 情報の分離方針（公式情報 / AI要約 / AI考察 / manual override）

`AI_CONTEXT.md` §4.5「Official / AI Summary / AI Analysisを分離する」を、Wikiページの構成原則としてここで具体化する。

| 区分 | 由来（`sourceType`） | ページ上の扱い |
|---|---|---|
| 公式情報 | `official`（ゲーム公式設定資料等、将来入力） | 「公式情報」セクションにそのまま掲載。confidence表示は不要（公式情報は確度100%として扱う） |
| 本文抽出（fact） | `script` / `ai_extracted`（Normalized Story JSONから機械的に抽出した情報） | 「抽出情報」セクション。evidenceRefsと合わせて表示し、rule-based抽出であることが分かるようにする |
| AI推定（inference） | `ai_inferred`（将来のLLM抽出。「〜らしい」等の推定） | **公式情報・抽出情報とは必ず別セクション、または別ページに分離する。** 見出しに `AI-generated analysis` 等の明示ラベルを付け、confidenceとevidenceRefsを必ず併記する |
| manual override | `manual`（人間が明示的に確定した値。`confidence: 1.0`） | 通常セクション内に反映してよいが、「人間により確認済み」であることが分かるバッジ・注記を付ける（`manualOverridesApplied`を参照） |

この分離は`Merged_Knowledge_Design.md` §4.1原則4（fact/inferenceをマージで混ぜない）がStage Bのデータ構造レベルで既に担保しているため、Wiki生成側は`fieldValues`/`sourceTypes`の`sourceType`を見てセクションを振り分けるだけでよい（Wiki側で新たな判定ロジックを作る必要はない）。

---

# 4. evidenceRefs の扱い

**方針: 元セリフ全文を大量転載しない。参照情報を残し、AI要約と元データ参照を分離する。**

- ページ上には evidenceの**要約**（どのエピソード・どのシーンで言及されたか）と、`evidenceId` / `episodeId` / `sceneId` / `blockId` の参照情報のみを表示する。
- `MergedEvidenceRef.textExcerpt`（`schemas/merged_knowledge.schema.json`で任意フィールドとして定義済み）は、表示する場合も**短い抜粋**にとどめる。全文転載はしない（著作権・引用量への配慮、`AI_CONTEXT.md` §4.6 静的サイト公開前提と合わせて特に注意する）。
- 将来的にローカル・内部ツールからは、`evidenceId`から Normalized Story JSON の該当Blockまで遡れる（`Merged_Knowledge_Design.md` §10.1の遡及チェーンをそのまま使う）。公開Wiki側ではこの遡及リンクを外部公開しない（Raw Scriptを公開する意図は無いため）。
- 表示形式の例:

  ```markdown
  ### 登場エピソード
  - MAIN_S01_C02_E01（seq: 3件の言及）
  - MAIN_S01_C03_E01（seq: 1件の言及）
  ```

  のように、evidence件数の要約＋episodeIdのリンクにとどめ、本文そのものは載せない。

---

# 5. unresolved entity / canonicalId なし entity の表示方針

`docs/architecture/06_AI/Canonical_ID_Policy.md` の「canonicalIdが無いentityのURLは不安定」という原則（§2「`mergedId`は再マージで変わりうるため外部から参照しない」）を、Wiki生成の可否判定にそのまま適用する。

| 状態 | 判定 | 理由 |
|---|---|---|
| `status: merged`かつ`canonicalId`あり | 通常ページを生成する | URLが安定（canonicalIdは一度確定したら原則変更しない） |
| `status: unresolved`（`canonicalId: null`） | **通常ページは生成しない。** `reports/unresolved/`配下にのみ一覧掲載する | `id`（`mergedId`）は再マージで変わりうるため、外部から参照可能なURLを持たせるべきではない |
| `status: conflict` | 通常ページは生成するが、warning boxを表示する | canonicalIdは確定しているため生成してよいが、未解決の衝突があることを読者に明示する必要がある |
| `status: deprecated` | ページを生成しない、または「統合済み」として新IDへのリダイレクト情報のみ残す | 打ち消し・統合済みのエンティティを独立ページとして残す意味が薄い |

- unresolved entityは「まだ確定していないが観測されている」情報であり、破棄はしない（`AI_CONTEXT.md` §13.3 unknown/unresolvedを破棄しない原則と同じ思想）。個別ページの代わりに、Unresolved Report（§7 Phase 1）へ集約する。
- `report.unresolvedEntityCounts`（`schemas/merged_knowledge_collection.schema.json`）をそのままレポートの数値サマリーとして使える。

---

# 6. hidden / excluded entity の扱い

以下に該当するentityは、Wiki生成対象から明示的に除外する（生成しない、または非公開扱いにする）。

- `confidence < 0.4`（`Merged_Knowledge_Design.md` §4.5「低confidence candidateの隔離」対象。そもそも`_unresolved/`へ隔離されているため、通常は§5の「unresolved」扱いに自然と合流する）
- `evidenceRefs`が0件のentity（`Merged_Knowledge_Design.md` §10.1「Evidenceを持たないmerged entityは出力しない」により、Stage B時点で既にこの状態のentityは出力されない設計だが、Wiki生成側でも同じ条件を防御的に確認する）
- `status: deprecated`（`suppressed: true`相当のmanual overrideで打ち消されたentity。§8.2 `suppress` action）
- 将来、`manual override`で明示的に「非公開」フラグが立てられたentity（現時点の`manual_overrides.schema.json`にはそのようなoperationは無いため、必要になった時点で別途設計する）

これらは「存在しないもの」として扱うのではなく、`report`（merge report）側の集計には含め続ける（破棄しない原則）。Wikiページとしての独立公開のみを保留する。

---

# 7. 実データ由来生成物をcommitしない方針

`docs/runbooks/Real_Data_Dry_Run.md` / `docs/runbooks/Character_Dictionary_Review.md` と同じ既存ルールを、Wiki生成物にもそのまま適用する。

- 実データ（実際の`.dec`スクリプト由来のセリフ・キャラクター名・merged knowledge collection）から生成したWikiページ・Markdownファイルは、**commitしない**。
- 合成データ（`CHAR_TEST_*`等）から作った**サンプル**のみ、`docs/examples/wiki_output/`または`tests/fixtures/`に置いてよい（本PRで追加するものは§13参照）。
- 将来、実データからのローカルdry-run render（§12 実装PR案6）を行う場合も、出力先は`.gitignore`済みの領域（`workspace/dry_runs/`等）を使う。
- 公開時（GitHub Pages / Cloudflare Pages等）の運用方針は、本文書のスコープ外とし、別PRで決める（Non-goals参照）。

---

# 8. ページ種別と優先順位

以下のページ種別を設計する。全てを最初から実装する必要はないため、Phase分けする。

## Phase 1（最優先）

| ページ種別 | 概要 |
|---|---|
| Top page | Wikiサイトのトップ。ストーリー一覧・統計サマリーへの入口 |
| Story index | ストーリー（`storyId`）一覧。カテゴリ（MAIN/EVENT/CHARACTER等）別に整理 |
| Episode page | エピソード単位のページ。登場人物・場所・あらすじ相当の抽出情報 |
| Character page | キャラクター単位のページ（§9で詳細） |
| Unresolved report page | `status: unresolved`のentity一覧。canonicalId未確定のため個別ページを持たない代わりに、ここに集約する |

## Phase 2

| ページ種別 | 概要 |
|---|---|
| Location page | 場所単位のページ |
| Organization page | 組織単位のページ |
| Item page | アイテム単位のページ |
| Lore page | 用語・設定単位のページ |
| Event page | 作中出来事単位のページ |
| Relationship section | 独立ページではなく、Character/Organizationページ内の関係セクションとして表示（§9） |
| Timeline page | エピソード横断の時系列情報一覧（`timeline_entries.json`由来。§7参照の通り順序確定はしない） |

## Phase 3

| ページ種別 | 概要 |
|---|---|
| AI analysis / speculation page | AI推定（`ai_inferred`）のみで構成される考察ページ。公式情報と混在させない（§3） |
| Evidence / source index page | `sourceDocuments`一覧。どのepisode_extractionがマージに使われたかの索引 |
| Knowledge Graph view | Neo4jベースのグラフビュー（`docs/architecture/04_Knowledge_Graph/`との連携。本文書のスコープ外に近いため最終フェーズ） |

Relationship page（独立ページ）は現時点では見送り、Character/Organizationページ内のセクションとする方針を推奨する。理由: 現状のRelationshipは「2つのエンティティ間の1つながり」であり、独立ページにするほどの内容量（本文・evidence以外の固有情報）が無いため。将来、Relationshipに付随する情報（変化の経緯`temporalNote`等）が増えた場合に独立ページ化を再検討する。

---

# 9. ページ責務

各ページについて、入力source・表示フィールド・非表示情報・evidenceRefs表示方法・unresolved時の表示・manual override反映方針・AI由来情報のラベル付け・将来のテンプレート名を整理する。

## 9.1 Top page

- source: `report`（merge report全体）のサマリー、`sourceDocuments`件数
- 表示: ストーリー数・キャラクター数・場所数等の統計、Story indexへのリンク、Unresolved reportへのリンク
- 表示しないもの: 個別entityの詳細、AI考察
- テンプレート名（案）: `templates/wiki/index.md.j2`

## 9.2 Story index

- source: `sourceDocuments`（`storyId`でグルーピング）
- 表示: ストーリーID・カテゴリ（MAIN/EVENT/CHARACTER/COLLABORATION/OTHER）・エピソード一覧
- 表示しないもの: エピソード本文
- テンプレート名（案）: `templates/wiki/story_index.md.j2`

## 9.3 Episode page

- source: 個別`entities.*`のうち、`sourceCandidates[].episodeId`がこのエピソードに一致するもの（登場キャラクター・場所等の索引として）
- 表示: `episodeId`、登場キャラクター一覧（Character pageへのリンク）、登場場所一覧、`unresolvedEntityCounts`のうちこのエピソード由来分
- 表示しないもの: 本文セリフ全文（§4 evidence方針と同じ理由）
- unresolved時の表示: このエピソード由来のunresolvedエンティティは名前のみ列挙し、リンクは張らない（個別ページが無いため）
- テンプレート名（案）: `templates/wiki/episode.md.j2`

## 9.4 Character page

- source: `entities.characters`（`status: merged`のみ。§5参照）
- 表示する主なフィールド:
  - `displayName`（`canonicalName`）
  - `aliases`
  - `status`
  - `sourceTypes`
  - `confidence`
  - 関連するRelationship（Character/Organizationへの所属等、§8 Relationship section）
  - 登場エピソード一覧（evidence由来、§4の要約形式）
  - evidence概要（件数・エピソード別内訳、本文なし）
  - `conflicts`（存在する場合、warning box）
  - `manualOversidesApplied`（人間確認済みフィールドがあれば明示）
- 表示してはいけないもの: 本文セリフ全文、`sourceCandidateId`等の内部処理用ID（provenance情報として保持はするが、ページ本文には出さない。デバッグ用途のfront matterまたは別セクションに留める）
- evidenceRefsの表示方法: §4の通り、要約＋エピソードリンクのみ
- unresolved時の表示方法: このページ自体を生成しない（§5）。名前のみの言及はUnresolved reportに掲載
- manual override反映後の表示方針: `manualOverridesApplied`が非空なら「人間により確認済み」の注記を表示
- AI由来情報のラベル付け: `sourceTypes`に`ai_inferred`が含まれるフィールドは「AI推定」ラベルを付けるか、AI analysis pageへ分離する
- テンプレート名（案）: `templates/wiki/character.md.j2`

## 9.5 Location page

- source: `entities.locations`
- 表示: `displayName`、`aliases`、`sceneRefs`件数、登場エピソード
- テンプレート名（案）: `templates/wiki/location.md.j2`

## 9.6 Organization page

- source: `entities.organizations`
- 表示: `displayName`、`aliases`、所属キャラクター（Relationship `MEMBER_OF`/`AFFILIATED_WITH`経由）
- Relationship sectionをここに埋め込む（§8参照）
- テンプレート名（案）: `templates/wiki/organization.md.j2`

## 9.7 Item page

- source: `entities.items`
- 表示: `displayName`、`aliases`、登場エピソード
- テンプレート名（案）: `templates/wiki/item.md.j2`

## 9.8 Lore page

- source: `entities.lore`
- 表示: 用語表記（`termCandidates`相当）、`aliases`、関連エピソード
- 注意: Loreは「同じ語が別概念を指すリスクが最も高い」種別（`Merged_Knowledge_Design.md` §5.5）。ページ上でも、複数の意味が疑われるentity（`conflicts`が`merge_suggestion`を含む場合）はwarningを強めに出す
- テンプレート名（案）: `templates/wiki/lore.md.j2`

## 9.9 Event page

- source: `entities.events`
- 表示: `displayName`、参加キャラクター（`participantEntityIds`）、発生場所（`locationEntityIds`）、関連エピソード
- テンプレート名（案）: `templates/wiki/event.md.j2`

## 9.10 Relationship section（独立ページではない、§8参照）

- source: `entities.relationships`。`sourceEntityId`/`targetEntityId`のいずれかが該当ページの主体と一致するものを抽出
- 表示: `relationshipType`、方向（`direction`）、`temporalNote`（変化があれば）、evidence概要
- AI由来情報のラベル付け: `sourceType: ai_inferred`のRelationshipは「AI推定の関係」ラベルを付ける（`Merged_Knowledge_Design.md` §6.4がfact/inferenceを別レコードで保持する設計のため、Wiki側は`sourceType`で振り分けるだけでよい）

## 9.11 Timeline page

- source: `entities.timeline`（`timeline_entries.json`相当）
- 表示: `kind`別（`explicit_order`/`temporal_marker`）にセクション分割、`scope`（episode/block）ごとの一覧
- 表示してはいけないもの: 順序の「確定」表現。`Merged_Knowledge_Design.md` §7.1の通りStage Bでは順序を確定しないため、Wikiページ上も「観測された順序情報の一覧」であることを明示し、確定した年表のように見せない
- テンプレート名（案）: `templates/wiki/timeline.md.j2`

## 9.12 Unresolved report page

- source: `report.unresolvedEntityCounts`、および`_unresolved/`相当のentity一覧（`status: unresolved`）
- 表示: entity種別ごとの件数、代表的なdisplayName（あれば）、`mergedId`（内部参照用、外部リンクにはしない）
- テンプレート名（案）: `templates/wiki/unresolved_report.md.j2`

## 9.13 Conflict report page

- source: `report.conflictCounts`
- 表示: `conflictType`別・`severity`別・entity type別の件数。個別conflictの詳細は該当entityページのwarning boxで確認する形とし、このページはサマリーに留める

## 9.14 Relationship type report page

- source: `report.relationshipTypeSummary`
- 表示: `knownTypes`/`unknownTypes`の内訳。taxonomy確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`）前の暫定状況の可視化用

## 9.15 Canonical ID report page

- source: `report.canonicalIdSummary`
- 表示: `totalAssigned`/`duplicateCount`/`invalidCount`と`warnings`

## 9.16 Source / evidence index page

- source: `sourceDocuments`
- 表示: マージに使われたepisode_extractionドキュメントの一覧（`documentId`/`episodeId`/`candidateCounts`）
- Phase 3。実データのepisode一覧をそのまま公開する意味があるかは、公開方針決定時に再検討する

## 9.17 AI analysis / speculation page

- source: `sourceType: ai_inferred`のFieldValue/Relationshipのみ
- 表示: 「AI-generated analysis」の明示ラベル、confidence、evidenceRefs
- 表示してはいけないもの: 公式情報・抽出情報との混在（§3）
- Phase 3。LLM抽出自体が未実装のため、当面は空またはページ自体を生成しない

---

# 10. Markdown front matter 方針

MkDocs Material等での利用を見据え、以下のfront matter方針を設計する。**実データページはまだ生成しない。以下は合成例のみ。**

```markdown
---
title: "Example Character"
entity_type: "character"
entity_id: "CHAR_EXAMPLE"
canonical_id: "CHAR_EXAMPLE"
status: "merged"
confidence: 0.9
source_types: ["script"]
generated_from: "merged_knowledge_collection"
generated_at: "2026-07-04T00:00:00Z"
schema_version: "0.1"
---
```

フィールド方針:

- `entity_id` / `canonical_id`: 両方持たせる。`entity_id`は`MergedEntityBase.id`（現時点で権威的な識別子）、`canonical_id`は`MergedEntityBase.canonicalId`（確定済みのみ、`null`なら生成しない §5）。将来`id`と`canonicalId`が分離運用される場合に備え、あえて両方残す
- `status`: `schemas/merged_knowledge.schema.json`の`Status`列挙値（`merged`/`unresolved`/`conflict`/`deprecated`）をそのまま使う。ページを生成するのは実質`merged`/`conflict`のみ（§5）
- `generated_from`: 常に`"merged_knowledge_collection"`固定。手編集ではなく生成物であることをfront matterレベルでも明示する（§2）
- `generated_at`: 生成日時（実データ生成時にのみ入る。合成例では固定値でよい）
- `ai_generated` / `ai_confidence`: AI analysis page（§9.17）でのみ使う追加フィールド案。Phase 3実装時に確定する

---

# 11. 出力ディレクトリ案

```text
site_src/
  index.md
  stories/
    index.md
    {storyId}/
      index.md
      {episodeId}.md
  characters/
    index.md
    {canonicalId}.md
  locations/
    {canonicalId}.md
  organizations/
    {canonicalId}.md
  items/
    {canonicalId}.md
  lore/
    {canonicalId}.md
  events/
    {canonicalId}.md
  timelines/
    index.md
  reports/
    unresolved.md
    conflicts.md
    relationship_types.md
    canonical_ids.md
    sources.md
```

- `docs/wiki_generated/`案も検討したが、`docs/`配下は既に設計文書・ランブックというGit管理対象の手書きドキュメント置き場として使われている（`docs/architecture/`、`docs/runbooks/`）。生成物を同じ`docs/`配下に混在させると、`Merged_Knowledge_Design.md` §11.1が生成物ディレクトリで既に解決した「生成物と手書きソースの混在問題」を、Wiki層で再発させることになる。そのため**`site_src/`（リポジトリ直下、生成物専用）を推奨**する。
- **現時点の推奨: 実データ由来の生成物は当面commitしない。** `site_src/`は`.gitignore`対象とし、ローカル・CI内での生成→静的サイトビルド→デプロイのパイプライン内でのみ実体化する（公開時の運用は別PRで決める、§14 Non-goals）。
- 合成fixtureから作ったサンプルは`docs/examples/wiki_output/`（本PRで追加、§13）または`tests/fixtures/`に置く。

---

# 12. テンプレート方針

## 12.1 候補

| 方式 | メリット | デメリット |
|---|---|---|
| Jinja2 templates | 表現力が高い、MkDocs等のエコシステムと相性が良い、条件分岐・ループが書きやすい | 新規依存追加が必要（`pyproject.toml`変更） |
| Python string builder | 依存追加不要、既存の`agents/parser/normalizer.py`等と同じ手続き的スタイル | ページ数が増えるとテンプレートロジックが肥大化しやすい |
| Markdown renderer module（自作の小さな関数群） | 依存追加不要、テストしやすい単位に分割できる | Jinja2ほどの表現力・保守性は無い |

## 12.2 推奨

**このPRではテンプレート方式を確定しない。設計のみ行い、依存追加の要否は実装PR（§14 実装PR案 1. wiki renderer skeleton）で判断する。**

理由: Jinja2導入は将来的に便利だが、依存追加は実装が具体化してから判断すべきであり、設計段階で決め打ちしない（Non-goals「Wiki生成パイプライン実装」に該当するため、このPRのスコープ外）。

## 12.3 テンプレート名候補（実装時の参考）

```text
templates/wiki/index.md.j2
templates/wiki/story_index.md.j2
templates/wiki/episode.md.j2
templates/wiki/character.md.j2
templates/wiki/location.md.j2
templates/wiki/organization.md.j2
templates/wiki/item.md.j2
templates/wiki/lore.md.j2
templates/wiki/event.md.j2
templates/wiki/timeline.md.j2
templates/wiki/unresolved_report.md.j2
```

このPRでは`.j2`ファイル本体は追加しない（テンプレートエンジン未確定のため）。

---

# 13. merged collection との対応表

| merged knowledge collection側 | Wiki側 |
|---|---|
| `entities.characters` | Character pages（§9.4） |
| `entities.locations` | Location pages（§9.5） |
| `entities.organizations` | Organization pages（§9.6） |
| `entities.items` | Item pages（§9.7） |
| `entities.lore` | Lore pages（§9.8） |
| `entities.events` | Event pages（§9.9） |
| `entities.relationships` | Relationship sections（独立ページではない、§9.10） |
| `entities.timeline` | Timeline page（§9.11） |
| `report.unresolvedEntityCounts` | Unresolved report（§9.12） |
| `report.conflictCounts` | Conflict report（§9.13） |
| `report.relationshipTypeSummary` | Relationship type report（§9.14） |
| `report.canonicalIdSummary` | Canonical ID report（§9.15） |
| `sourceDocuments` | Source / evidence index（§9.16） |

---

# 14. URL / slug 方針

**名前ベースslugは原則避ける。** `displayName`は変更されうる（表記揺れの統合、manual overrideによる`canonicalName`変更等）ため、URLの安定性をdisplayNameに依存させない。

| 種別 | URL方針 | 例 |
|---|---|---|
| Character/Location/Organization/Item/Lore/Event（canonicalIdあり） | `{type}/{canonicalId}.md` | `characters/CHAR_RAIN.md` |
| 同上（canonicalIdなし = unresolved） | ページを生成しない。`reports/unresolved.md`にのみ一覧掲載 | （URLなし） |
| Story/Episode | `stories/{storyId}/{episodeId}.md` | `stories/MAIN_S01_C02/MAIN_S01_C02_E01.md` |
| index系 | `{type}/index.md` | `characters/index.md` |
| Timeline | `timelines/index.md`（単一集約ファイル、`Merged_Knowledge_Design.md` §7が「エンティティ統合しない」方針のため個別ページを持たない） | |

`canonicalId`自体が`Identifier_Specification.md`の規則で安定運用される前提（`Canonical_ID_Policy.md` §2「一度確定したら原則変更しない」）に、Wiki URLの安定性を委ねる。

---

# 15. 将来の実装PR案

1. **wiki renderer skeleton**: `agents/wiki_generator/`（現在は空placeholder package）に、merged knowledge collectionの読み込み・検証・空のページ構造出力までの骨格を作る。個別ページ生成ロジックはまだ実装しない（`agents/merger/`のmerge engine skeleton PRと同じ進め方）
2. **character page renderer with synthetic fixture**: Character pageのみ実装。合成fixtureで検証
3. **episode page renderer with synthetic fixture**: Episode pageを実装
4. **unresolved report renderer**: Unresolved report pageを実装（Phase 1完了）
5. **MkDocs Material minimal site**: 生成したMarkdown群を実際にMkDocs Materialでビルドできることを確認する最小構成（本文書のNon-goals「MkDocs本格導入」とは異なり、ビルド可否の疎通確認のみ）
6. **real data local render dry-run**: ローカルignored領域で、実データ由来のmerged knowledge collectionから実際にレンダリングしてみる（`docs/runbooks/Real_Data_Dry_Run.md`と同じ運用: 生成物はcommitしない）
7. **public publishing workflow**: GitHub Pages / Cloudflare Pages等への公開ワークフロー（Non-goals、別PRで検討）

各PRは小さく、`uv run pytest`の全通過と、実データを使わない自作fixtureによる検証を維持する（`Merged_Knowledge_Design.md` §13と同じ進め方）。

---

# 16. Non-goals

本設計書では以下を**スコープ外**とする。

- Wiki生成パイプラインの実装（Python。§15のPR群で別途行う）
- 実データ由来Wikiページ・生成Markdownのcommit
- MkDocs Materialの本格導入・サイト構築
- GitHub Pages / Cloudflare Pages設定
- Knowledge Graph生成（Neo4j投入処理。`docs/architecture/04_Knowledge_Graph/`は別文書群）
- LLM/provider/prompt実装、AI考察本文の生成
- canonical ID自動割り当て
- キャラクター辞書の推測confirmed化
- Parser大規模再設計
- Jinja2等テンプレートエンジンの依存追加可否の確定（§12.2の通り実装PRで判断）

---

# 17. 採用方針（サマリ）

- Wikiのsource of truthはmerged knowledge collectionであり、Wikiページは常に再生成可能な生成物として扱う（手編集しない）
- 公式情報・抽出情報（fact）・AI推定（inference）・manual overrideは、`sourceType`を軸に必ず分離して表示する
- evidenceRefsは要約と参照情報（evidenceId/episodeId/sceneId/blockId）のみを表示し、元セリフ全文は転載しない
- `canonicalId`が未確定（`status: unresolved`）のentityは通常ページを生成せず、Unresolved reportへ集約する。URLの安定性を`canonicalId`にのみ依存させる
- Phase 1（Top/Story index/Episode/Character/Unresolved report）→ Phase 2（Location/Organization/Item/Lore/Event/Relationship section/Timeline）→ Phase 3（AI analysis/Evidence index/Knowledge Graph view）の順で実装する
- テンプレート方式（Jinja2 / 自作builder）はこのPRでは確定せず、実装PRで判断する
- 実データ由来の生成物は当面commitしない。合成fixtureのサンプルのみ`docs/examples/`等に置く
