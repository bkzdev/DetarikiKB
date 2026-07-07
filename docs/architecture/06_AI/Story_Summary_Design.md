# Story Summary Design（Story Summary / Episode Summary データ構造設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Story_Summary_Design.md`

---

# 1. Background

`Story_Page_Design.md`（PR #75）でStory page中心のWiki構造を設計し、`wiki-story-page-renderer`（PR #76）でStory pageを実装した。実データ小規模サンプルによる`story-page-manual-review`（PR #77）でStory index → Story page → Episode pageの導線に問題ないことを確認済みである。

現在のStory pageは以下の状態にある。

- Story Summary: 「未生成」固定のplaceholder（`_render_story_summary_section`）
- Episode Summaries: Episodeごとに「未生成」固定のplaceholder（`_render_episode_summaries_section`）
- Episode list / Related Characters / Unresolved reportへの導線: 実装済み

ユーザー方針（`Story_Page_Design.md` §2背景を踏襲）:

- Story pageには将来的に要約を付けたい
- Story全体の要約だけでなく、Episodeごとに区切った要約も必要
- `evidenceId`/`episodeId`/`blockId`管理は従来通りEpisode単位で維持する
- AI考察・推測は通常要約とは分離する
- 元セリフ全文・raw DEC textは出さない

本文書は、この「未生成」placeholderを実際のSummaryデータで置き換える**前段の設計**として、Story Summary / Episode Summaryのデータモデル・保存場所・renderer連携方針を定義する。

---

# 2. Summary types（Summaryの種類）

少なくとも以下3種類を区別する。

## 2.1 A. Story Summary

- Story全体の要約
- Story page上部（Overview直下）に表示する
- 1 storyにつき0〜1個
- Episode Summariesを統合した短い全体要約という位置づけ

## 2.2 B. Episode Summary

- Episodeごとの要約
- Story pageの Episode Summaries section（`### {episode見出し}`単位）に表示する
- 1 episodeにつき0〜1個。将来的に複数版（表記違い・改訂履歴）を持たせるかは§14未確定事項とする
- Episode pageへの表示可否は本文書では決定しない（§10 Non-goals、後続PRで検討）

## 2.3 C. AI Analysis / Speculation

- 考察・推測・矛盾点・伏線・キャラ関係考察など
- Story Summary / Episode Summaryとは**必ず分離**する（別section、または別page）
- 本文書のSummary schemaには一切含めない
- `Wiki_Output_Design.md` §9.17（AI analysis / speculation page、Phase 3・未実装）が受け皿になる想定

| | Story Summary (A) | Episode Summary (B) | AI Analysis / Speculation (C) |
|---|---|---|---|
| 単位 | Story | Episode | Story/Episode/Character等、対象は将来決める |
| 内容 | 明示された事実の簡潔なあらすじ | 同左（Episode単位） | 考察・推測・矛盾点・伏線・関係性解釈 |
| 本文書のschema対象か | Yes | Yes | **No**（別設計） |
| raw text/AI考察混在 | 禁止 | 禁止 | Summaryとは別物として扱う（本文書では設計しない） |

---

# 3. Data ownership（データの位置づけ）

Story/Episode Summaryは、他の既存データ種別のどれとも役割が異なる。

| データ種別 | 由来 | Git管理 | 参考 |
|---|---|---|---|
| Normalized Story JSON / Extraction / Merged Knowledge Collection / Wiki Markdown | 実データ（`.dec`）から機械的に生成 | **commitしない**（`AI_CONTEXT.md` §3.11） | `Extraction_Pipeline.md`, `Merged_Knowledge_Design.md` |
| `knowledge/dictionaries/character_profiles.yaml` | 公式外部資料（Wiki等）由来、人間確認済みのみ登録 | **commitする** | `Character_Profile_Dictionary_Design.md` |
| `knowledge/overrides/*.yaml`（設計のみ、未実装） | 人間が明示的に記述する短い補正指示（ID割り当て等） | **commitする** | `Merged_Knowledge_Design.md` §8 |
| **Story/Episode Summary（本文書）** | 実データ（`.dec`由来のNormalized Story JSON / Extraction Result）を要約したプレーンテキスト。AI生成 or 人間執筆 | **レビュー状態による（§6参照）** | 本文書 |

Story/Episode Summaryは、Normalized Story JSON/Extraction/Merged Knowledge/Wiki Markdownと同じ「実データ由来」ではあるが、それらと違い**短いプレーンテキストの要約**であり、`character_profiles.yaml`の自己紹介文と同様に「レビュー済みなら知識ベースとして保持してよい」性質を持つ。したがって単純に「commitしない」既存ルールをそのまま適用するのではなく、**レビュー状態に応じてGit管理するかどうかを分ける**方針を採る（§6・§7）。

---

# 4. Non-goals（本PRで行わないこと）

- AI要約生成の実装（LLM呼び出し・prompt・batch処理）
- 実データを使ったSummary生成・投入
- `schemas/story_summary.schema.json`等のJSON Schema実装（原則。§9参照）
- renderer統合の実装（`render_wiki.py --story-summaries`等）
- Story page / Episode page rendererの変更
- Evidence index実装
- AI Analysis / Speculation自体のschema設計（§2.3の通り別設計とする）

---

# 5. Storage options（保存場所の比較）

## 5.1 候補A: 単一YAML

```text
knowledge/summaries/story_summaries.yaml
```

- 長所: 初期実装が簡単、まとめてvalidateしやすい、少数データで扱いやすい
- 短所: story件数が増えると1ファイルが巨大化する、review差分（PRの差分表示）が見づらくなる（1PRで無関係な複数storyの変更が混ざりやすい）

## 5.2 候補B: 1 story 1 file（推奨）

```text
knowledge/summaries/stories/{storyId}.yaml
```

- 長所: story単位でreviewしやすい、差分が小さくPRが読みやすい、将来件数が増えても線形にスケールする
- 短所: loaderが複数ファイルを走査する分やや複雑になる、ファイル数が増える

## 5.3 候補C: 生成物ディレクトリ

```text
data/generated/summaries/
```

- 長所: AI生成物として`data/extracted/`等と同じ扱いにでき、既存の「生成物はcommitしない」ルールにそのまま従える
- 短所: review済みsummaryと未reviewの生成物が同じ場所に混在しやすく、「このsummaryはWikiに表示してよい状態か」が場所だけでは判別できない。レビュー状態を跨いだ管理には不向き

## 5.4 採用: 候補B + draft置き場の併用

**`knowledge/summaries/stories/{storyId}.yaml`を正式な保存場所として採用する。** ただし候補Cの弱点（未reviewの生成物が紛れ込む）を避けるため、`character_profiles.yaml`の運用（`Character_Profile_Dictionary_Design.md` §8、`wiki_member_profiles_batch_*.yaml`等のcandidateはcommitせず、人間確認済みの投入のみ`character_profiles.yaml`へ反映する）と同じ二段構成を採る。

```text
[生成/下書き] workspace/summary_drafts/{storyId}.yaml    ← commitしない (draft/generated段階)
      ↓ 人間レビュー (review.status: reviewed/approved)
[確定]        knowledge/summaries/stories/{storyId}.yaml ← commitする (§6のreview状態に従う)
```

- `workspace/summary_drafts/`は既存の`workspace/`ディレクトリ配下であり、`.gitignore`に個別パターンを追加してignore対象とする
- `knowledge/summaries/stories/{storyId}.yaml`にコミットしてよいのは、`review.status`が`reviewed`または`approved`のSummaryのみとする（§6・§7）。`unreviewed`/`needs_revision`/`rejected`のエントリを`knowledge/summaries/`側にcommitしない

候補Aと候補Bの比較では長期的な件数増加を見込みBを推奨するが、初期PR（`story-summary-schema-implementation`）ではローダー実装の負荷を考慮し、まず候補Bのシンプルな実装（1ファイル1story、YAML読み込みのみ）から始めることを推奨する。

**実装状況（`feature/story-summary-schema-implementation`で実施）**: `.gitignore`へ`workspace/summary_drafts/`を追加した（実データ由来のdraft summaryをcommitしないため）。`knowledge/summaries/stories/`・`knowledge/summaries/`には空ディレクトリ維持用の`.gitkeep`のみを追加し、実データsummaryは追加していない。`scripts/validate_story_summaries.py --require-reviewed`で、`review.status`が`reviewed`/`approved`以外のファイルをエラーにできるようにした（§10.3実装状況参照）。

---

# 6. Status and review workflow（status/review方針）

「生成の進み具合」と「人間レビューの状態」は別軸であるため、2つのstatusに分離する（本文書で確定）。

## 6.1 生成ステータス（`status`、ドキュメント/Summary単位）

| 値 | 意味 |
|---|---|
| `missing` | Summary未生成。**通常は永続化しない**（該当エントリが存在しないこと自体が`missing`を表す）。loader/renderer側が「該当エントリなし」を`missing`として解釈するための値であり、生成パイプラインが明示的に書き込む値ではない |
| `draft` | 生成されたが下書き段階（人間レビュー前提、Wiki表示はまだしない） |
| `generated` | AI生成 or 人間執筆が完了した状態（レビュー未着手〜レビュー中を含む） |
| `deprecated` | 過去に生成されたが、内容が古くなった・re-generateが必要と判断された |

## 6.2 レビューステータス（`review.status`）

| 値 | 意味 |
|---|---|
| `unreviewed` | 人間による確認が行われていない |
| `reviewed` | 人間が内容を確認した（正確性は確認したが、公開判断は別） |
| `approved` | 人間が確認し、Wiki表示・Git commitを承認した |
| `rejected` | 内容に問題がある、または再生成が必要と判断された |
| `needs_revision` | 部分的に修正が必要（全面却下ではない） |

## 6.3 renderer表示条件（本文書で方針のみ決定、実装は次PR）

- Story page/Episode Summaries sectionで実テキストを表示してよいのは、`review.status`が`reviewed`または`approved`のSummaryのみとする
- `unreviewed`/`needs_revision`/`rejected`のSummaryは、実装時点では従来通り「未生成」のまま表示する（人間の確認前にAI生成テキストをそのままWikiへ出さない）
- この条件により、§5.4の「`knowledge/summaries/`にcommitするのは`reviewed`/`approved`のみ」という保存方針と、rendererの表示条件が一致する（`knowledge/summaries/`に存在する時点で表示可能、という単純な判定にできる）

---

# 7. Separation from AI analysis/speculation（AI考察との分離）

## 7.1 Summaryに含める

- そのStory/Episodeで起きたこと
- 主要登場人物
- 主要イベント
- 明示された事実
- 簡潔なあらすじ

## 7.2 Summaryに含めない

- 伏線考察
- 矛盾点考察
- キャラ関係の推測
- 未確定推測
- AIの独自解釈
- fan theory

上記(7.2)に該当する内容は、将来的にAI Analysis / Speculation / Theory / Contradiction notesなどの**別section・別page**に分離する（`Wiki_Output_Design.md` §3・§9.17の分離方針をそのまま踏襲）。本文書で定義するSummary schemaにこれらのフィールドは存在しない。

## 7.3 rawテキスト非保存方針

- Summary textにraw dialogueを大量引用しない（短い一文引用程度に留める運用を推奨するが、本文書では文字数上限等の詳細は次PRのschema実装時に確定する）
- raw DEC textを含めない（コマンド文字列・`$num`等の変数を含めない）
- 元セリフ全文を保存・表示しない（`Wiki_Output_Design.md` §4のevidenceRefs方針と同じ）

---

# 8. Data model（データモデル）

## 8.1 ドキュメント構造（1 story = 1 file、`knowledge/summaries/stories/{storyId}.yaml`）

```yaml
schemaVersion: 0.1.0
documentType: story_summary
storyId: EVT_SAMPLE
publicStoryId: EVT_260101_001
language: ja
generationStatus: generated
storySummary:
  text: "..."
  confidence: 0.7
  evidenceRefs:
    - EVT_SAMPLE_E01_DLG0001
episodeSummaries:
  - episodeId: EVT_SAMPLE_E01
    publicEpisodeId: EVT_260101_001_E01
    episodeNumber: 1
    text: "..."
    confidence: 0.6
    evidenceRefs:
      - EVT_SAMPLE_E01_DLG0001
source:
  sourceType: ai_generated
  model: local_or_manual
  promptVersion: null
  generatedAt: null
  inputRefs: []
review:
  status: reviewed
  reviewer: bkzdev
  reviewedAt: "2026-07-08"
  notes: null
notes: null
```

**実装状況（`feature/story-summary-schema-implementation`で実施）**: ドキュメント直下の生成ステータスフィールドは、`review.status`との混同を避けるため`status`から`generationStatus`へ改名して実装した（`schemas/story_summary.schema.json`）。`storySummary`/`episodeSummaries[]`個別の`status`継承フィールドは実装しない（スコープを単純化し、ドキュメント直下の`generationStatus`のみを単一のソースとする）。

## 8.2 Required / optional fields

### Story-level（ドキュメント直下）

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `schemaVersion` | Yes | string | schema version |
| `documentType` | Yes | string | 固定値 `story_summary` |
| `storyId` | Yes | string | 対象Story ID |
| `publicStoryId` | No | string \| null | 公開Wiki URL用ID。`story_manifest.yaml`の`publicStoryId`と対応させる |
| `generationStatus` | Yes | string | ドキュメント全体の生成ステータス（§6.1） |
| `language` | Yes | string | 既定 `ja` |
| `storySummary` | No | object \| null | §8.3。未生成なら省略またはnull |
| `episodeSummaries` | Yes | array | §8.4。要素0件も許容（Story Summaryのみ先に生成されるケース） |
| `source` | Yes | object | §8.5 |
| `review` | Yes | object | §8.6 |
| `notes` | No | string \| null | 自由記述 |

### 8.3 Story Summary

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `text` | Yes | string | 要約本文 |
| `confidence` | No | number | 0.0〜1.0 |
| `evidenceRefs` | No | string[] | §9 |

### 8.4 Episode Summary（`episodeSummaries[]`の各要素）

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `episodeId` | Yes | string | 対象Episode ID |
| `publicEpisodeId` | No | string \| null | `story_manifest.yaml`の`publicEpisodeId`と対応 |
| `episodeNumber` | No | integer | story内の並び順（`Story_Page_Design.md` §8のEpisode Summaries見出し解決と同じ考え方） |
| `text` | Yes | string | 要約本文 |
| `confidence` | No | number | 0.0〜1.0 |
| `evidenceRefs` | No | string[] | §9 |

### 8.5 Source

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `sourceType` | Yes | string | `manual` / `ai_generated` / `imported` / `unknown` |
| `model` | No | string \| null | AI生成時のモデル名・provider識別子 |
| `promptVersion` | No | string \| null | プロンプトのバージョン識別子 |
| `generatedAt` | No | string \| null | ISO8601タイムスタンプ |
| `inputRefs` | No | string[] | 生成時に参照したepisodeId等（監査用） |

### 8.6 Review

| Field | 必須 | 型 | 説明 |
|---|---:|---|---|
| `status` | Yes | string | §6.2 |
| `reviewer` | No | string \| null | レビュー実施者 |
| `reviewedAt` | No | string \| null | ISO8601タイムスタンプまたは日付文字列 |
| `notes` | No | string \| null | レビューコメント |

---

# 9. Evidence references（evidenceRefs方針）

- Story Summary / Episode Summaryともに`evidenceRefs`を持てるようにする。**必須にはしない**（初期のAI生成・人間執筆いずれも、evidenceRefsが無くても保存自体は許容する）
- `evidenceRefs`はNormalized Story JSON / Extraction Resultの`evidenceId`（Block ID、`Identifier_Specification.md` §8の形式、例: `EVT_SAMPLE_E01_DLG0007`）を参照する。**Episode単位のID体系をそのまま維持する**（新たなID体系は作らない）
- `evidenceRefs`を持たせても、元セリフ全文は保存しない（`evidenceRefs`は根拠の**参照**であり、根拠テキストの**引用**ではない）
- `evidenceRefs`はSummaryの根拠確認用であり、将来のEvidence index（`Wiki_Output_Design.md` §9.16、未実装）との連携を見込む。連携方式（Evidence indexからSummaryへの逆引き等）は本文書では設計しない

**実装状況（`feature/story-summary-schema-implementation`で実施）**: `schemas/story_summary.schema.json`の`EvidenceRef`定義で形式検証（`^[A-Z][A-Z0-9_]*$`）を実装した。Block/Scene/Episode/Story IDいずれの粒度も許可する（`Identifier_Specification.md` §8の段階的fallbackを妨げないよう、suffix別のenum制約はかけない）。

**Story pageへの表示方針・実装状況（`feature/story-summary-evidence-display`で実施）**:

- 表示対象はPR #80と同じ表示可能条件（`review.status`が`reviewed`/`approved`・`generationStatus`が`generated`）を満たすSummaryのみ。それ以外（unreviewed/rejected/needs_revision/draft/deprecated/未登録/textが空）は`evidenceRefs`も一切表示しない
- 表示形式は「`Evidence refs: `ID1`, `ID2``」のようにIDのみをbacktickで囲んだ1行のインライン表示とする（実装の単純さ・読みやすさを優先、`_render_evidence_refs_line`）。件数が多い場合のbullet list化・Evidence indexへのリンク化は本PRでは行わず、将来（`story-summary-evidence-index-design`等）の検討課題とする
- **evidenceRefsが空の場合は「案A」を採用し、Evidence refs行自体を何も表示しない**（Summary本文の邪魔にならないことを優先。`evidenceRefs`は任意項目でありempty自体はエラーではないため）
- renderer側でも安全性を確認する: `list`以外の値は無視、非文字列・空文字列・whitespaceのみの要素は無視、重複は除去（元の順序は維持）
- Story Summary/Episode Summaryいずれも同じ`_render_evidence_refs_line`ヘルパーを共有する
- **Episode pageへのevidenceRefs表示は行っていない**（Story pageのみ対象、Non-goals）
- raw dialogue text・raw DEC command・raw pathはevidenceRefs表示に一切含まれない（IDのみ表示のため）

**Evidence index設計（`feature/story-summary-evidence-index-design`で実施）**: `evidenceRefs`テキスト表示の次段階として、将来のリンク先となるEvidence indexの役割・データモデル・公開範囲（Public Evidence Index / Internal Review Evidence Packet）を`docs/architecture/06_AI/Evidence_Index_Design.md`で設計した。初期推奨はStory別Evidence page（`evidence/{publicStoryId or storyId}.md`）、Evidence indexはAI Analysis/Speculationとは分離する。**本PRではschema実装・renderer統合・リンク化は行っていない**（設計のみ、次PR`evidence-index-schema-implementation`）。

**Evidence index schema実装（`feature/evidence-index-schema-implementation`で実施）**: `schemas/evidence_index.schema.json`・`agents/wiki_generator/evidence_index.py`（loader/validator）・`scripts/validate_evidence_index.py`（CLI）を実装した。保存場所は`knowledge/evidence/stories/{storyId}.yaml`（`.gitkeep`のみ、実データ未投入）。**Story Summary/Episode SummaryのevidenceRefsをEvidence indexへリンク化する統合はまだ行っていない**（次PR`evidence-index-renderer-integration`）。

---

# 10. Renderer integration plan（次PR以降の統合方針、本PRでは未実装）

`agents/wiki_generator/renderer.py`の`_render_story_summary_section` / `_render_episode_summaries_section`（現状「未生成」固定を返す）を、以下の方針でSummaryデータへ差し替える。**本PRではrenderer実装を行わない。**

1. `scripts/render_wiki.py`に任意引数`--story-summaries <path>`を追加する（`--character-profiles`と同じ任意引数パターン、未指定時は既存動作を維持）
2. `agents/wiki_generator/`（または`agents/parser/`）にsummary loaderを追加し、`knowledge/summaries/stories/{storyId}.yaml`群を読み込んで`storyId`をキーにした索引を構築する（`character_profiles.py`の`build_character_profile_index`と同じパターン）
3. `storyId`（無ければ`publicStoryId`）でStory Summaryを、`episodeId`（無ければ`publicEpisodeId`）でEpisode Summaryを照合する
4. `review.status`が`reviewed`/`approved`のSummaryのみ、Story pageのplaceholderを実テキストへ置き換える（§6.3）。それ以外は従来通り「未生成」のまま表示する
5. Episode pageへのEpisode Summary表示可否は本文書では決定しない（後続PRで判断、§4 Non-goals）

**実装状況（`feature/story-summary-schema-implementation`で実施）**: 上記1〜4の土台となるloader（`load_story_summary`/`load_story_summaries`/`build_story_summary_index`/`build_public_story_summary_index`/`find_episode_summary`/`find_episode_summary_by_public_id`/`is_displayable_summary`）を`agents/wiki_generator/story_summaries.py`に実装した。**`render_wiki.py`/`renderer.py`への統合自体は行っていない**（次PR`story-summary-renderer-integration`のスコープ）。

**実装状況（`feature/story-summary-renderer-integration`で実施）**: 上記1〜4をすべて実装した。

- `scripts/render_wiki.py`に`--story-summaries <path>`（file/directory両対応）を追加した。未指定時は既存動作を維持する
- `agents/wiki_generator/story_summaries.py`に`StorySummaryLookup`（`storyId`/`publicStoryId`両方の索引をまとめたコンテナ）・`build_story_summary_lookup`・`resolve_story_summary`・`resolve_episode_summary`・`get_displayable_story_summary`・`get_displayable_episode_summary`・`is_document_displayable`を追加した
- `storyId`優先→`publicStoryId`で照合し、両方が異なるドキュメントを指す場合は矛盾として安全側に倒しNoneを返す（表示しない）。Episode側も`episodeId`優先→`publicEpisodeId`で同じ方針
- `is_displayable_summary`を拡張し、`review.status`（`reviewed`/`approved`）に加え`generationStatus`（`generated`のみ表示、`draft`/`deprecated`/`missing`は非表示）も判定できるようにした。既存呼び出し（`generation_status`省略）は後方互換のまま
- `agents/wiki_generator/renderer.py`の`_render_story_summary_section`/`_render_episode_summaries_section`/`render_story_page`/`build_pages`に`story_summary_lookup`（任意引数、デフォルトNone）を追加し、表示可能なSummaryが見つかった場合のみ本文を表示、それ以外は従来通り「未生成」を表示するようにした
- **Episode pageへのSummary表示は行っていない**（§4 Non-goalsのまま、Character page/Characters index/Unresolved reportにも影響なし）
- evidenceRefsの表示は行っていない（summary textのみ表示、§9末尾の通り次PR候補`story-summary-evidence-display`に持ち越し）

---

# 11. Validation plan（次PR以降、本PRでは未実装）

`story_summary`の検証方針（実装は次PR）。

- `schemas/story_summary.schema.json`（未作成）でstructural validationを行う
- `storyId`/`episodeId`が実在のNormalized Story JSON/Merged Knowledge Collection側と一致するかは、schema単体では検証できないため、CLI側（`scripts/validate_story_summaries.py`相当、未作成）でのcross-reference検証を別途検討する
- `evidenceRefs`が実在の`evidenceId`かどうかの検証は、既存の「semantic validationの範囲が限定的」という既知課題（`TASKS.md` Known Issues）と同様、初期実装では必須にしない

**実装状況（`feature/story-summary-schema-implementation`で実施）**: `schemas/story_summary.schema.json`によるstructural validationと、`scripts/validate_story_summaries.py`によるPython側validation（duplicate storyId/publicStoryId/episodeId/publicEpisodeId検出、raw/source text禁止文字列検出、`--require-reviewed`指定時のreview status enforcement）を実装した。実在のNormalized Story JSON/Merged Knowledge Collectionとのcross-reference検証（storyId/episodeIdが実在するか）は、上記記載の通り本PRでも未実装のまま次PR以降の課題とする。

---

# 12. Implementation phases（実装フェーズ案）

| フェーズ | 内容 | 状態 |
|---|---|---|
| `story-summary-schema-design` | データモデル・保存場所・status/review方針・evidenceRefs方針・AI考察分離方針・renderer連携方針の設計のみ | 完了 |
| `story-summary-schema-implementation` | `schemas/story_summary.schema.json`実装、`agents/wiki_generator/story_summaries.py`（loader/validator）実装、`scripts/validate_story_summaries.py`（CLI）実装、`docs/templates/story_summary_template.yaml`・合成fixture・テスト追加、`workspace/summary_drafts/`のgitignoreパターン追加 | 完了 |
| `story-summary-renderer-integration` | `render_wiki.py --story-summaries`実装、`_render_story_summary_section`/`_render_episode_summaries_section`の実データ連携、合成fixtureでの確認 | 完了 |
| `story-summary-evidence-display` | Story pageのStory/Episode Summary本文下にevidenceRefsをIDのみ短く表示（`_render_evidence_refs_line`） | **完了（本PR）** |
| 将来 `story-summary-generation-planning` | AI要約生成パイプライン（LLM provider/prompt実装）の着手時期・方式検討 | 未着手 |
| 将来 `story-summary-evidence-index-design` | Evidence index本体の設計、evidenceRefsのリンク化・Evidence detail page | 未着手 |
| 将来 | Episode pageへのSummary/evidenceRefs表示可否判断、実データでの表示確認（manual review） | 未着手 |

---

# 13. Non-goals（再掲）

§4と重複するが、レビュー観点で明示的に再掲する。

- AI要約生成実装
- LLM provider実装
- prompt実装
- batch要約処理
- 実データ要約生成
- `schemas/story_summary.schema.json`実装（原則）
- renderer integration実装
- Story page renderer変更
- Episode page変更
- Evidence index実装
- AI Analysis / Speculation schema実装

上記は本文書の初版（`story-summary-schema-design`）時点でのNon-goalsの記録である。schema/loader/validator/template/fixtureの実装は`story-summary-schema-implementation`で、Story page renderer統合は`story-summary-renderer-integration`で完了済み。AI要約生成・evidenceRefs表示・Episode pageへのSummary表示は引き続きNon-goalsのまま（§12 Implementation phasesの状態列を参照）。

---

# 14. Open questions（未確定事項）

- Episode Summaryの複数版（改訂履歴）を持たせるかどうか（現状は1 episodeにつき0〜1個のみ設計）
- Episode pageにもEpisode Summaryを表示するかどうか（§10.5、後続PRで判断）
- Summary text自体の文字数上限（`character_profiles.yaml`の`selfIntroduction`同様、著作権・引用量の観点は本文書のスコープ外）
- Evidence indexとの具体的な連携方式（`Wiki_Output_Design.md` §9.16が未実装のため）
- `knowledge/summaries/`へのcommit可否判定を、人間の目視確認以外の方法（CIチェック等）でも担保すべきか。`scripts/validate_story_summaries.py --require-reviewed`は実装したが、CIへの組み込み自体はまだ行っていない

---

# 15. 参照

- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page設計、§8 Summary placement）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（evidenceRefsの将来リンク先となるEvidence indexの設計）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§3 情報分離方針、§4 evidenceRefs方針、§9.17 AI analysis page）
- `docs/architecture/06_AI/Extraction_Pipeline.md`（Evidence構造・fact/inference分離の元設計）
- `docs/architecture/06_AI/Extraction_Result_Schema.md`（EvidenceRef構造、`Identifier_Specification.md` §8）
- `docs/architecture/06_AI/Merged_Knowledge_Design.md`（§11 生成物/手動管理ソースの分離パターン、本文書の保存場所方針が踏襲する先例）
- `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`（committedな公式データ辞書の先例、draft→confirmed昇格運用の踏襲元）
- `agents/wiki_generator/renderer.py`（`_render_story_summary_section`/`_render_episode_summaries_section`、置き換え対象）
- `schemas/story_summary.schema.json`（本設計のJSON Schema実装）
- `agents/wiki_generator/story_summaries.py`（loader/validator/index構築のPython実装）
- `scripts/validate_story_summaries.py`（CLI validator）
- `docs/templates/story_summary_template.yaml`（合成データのみのテンプレート見本）
- `TASKS.md`（次PR候補の追跡）
