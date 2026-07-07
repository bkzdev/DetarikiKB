# Evidence Index Design（Evidence indexの設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Evidence_Index_Design.md`

---

# 1. Background

`feature/story-summary-renderer-integration`（PR #80）でStory Summary/Episode SummaryをStory pageに表示できるようになり、`feature/story-summary-evidence-display`（PR #81）でその本文の下に`evidenceRefs`をIDのみ短く表示できるようになった（`Evidence refs: `ID1`, `ID2`` 形式、`agents/wiki_generator/renderer.py`の`_render_evidence_refs_line`）。

現時点（PR #81時点）の状態:

- Story Summary本文の下に`Evidence refs: ID1, ID2`を表示できる
- Episode Summary本文の下にも同様に表示できる
- `evidenceRefs`が無い場合は何も表示しない
- 非表示status（unreviewed/rejected/needs_revision/draft/deprecated）のSummaryではevidenceRefsも非表示
- **evidenceRefsはまだリンク化していない**（テキスト表示のみ）
- **Evidence index本体は未実装**
- Episode pageにはまだsummary/evidenceRefsを表示していない
- raw text/raw DEC command/元セリフ全文は表示していない

本文書は、`evidenceRefs`が将来リンク化される先となる**Evidence index**を、何のために作り、どの情報を公開Wikiに出し、どの情報を内部review用途に留めるかを設計する。**本PRではEvidence index rendererの実装・schema実装・ページ生成・リンク化・Normalized Story JSONからの自動抽出はいずれも行わない**（設計のみ、§10・§15参照）。

---

# 2. Goals（本PRのゴール）

- Evidence indexの役割を定義する
- Evidence indexを公開Wikiに出す範囲と、内部review用途に留める範囲を分ける
- `evidenceRefs`を将来リンク化する場合の方針を決める
- Evidence indexにraw dialogue text・raw DEC commandを出さない方針を明記する
- Evidence indexが参照するsource of truthを決める
- Story page / Episode page / Summary / Unresolved reportとの関係を設計する
- Evidence IDの粒度と表示内容を整理する
- 次PRでschemaまたはrenderer実装に進められるようにする

---

# 3. Non-goals（本PRで行わないこと）

- Evidence index schema実装（`schemas/evidence_index.schema.json`等）
- Evidence index renderer実装
- Evidence page生成
- `evidenceRefs`のリンク化
- Evidence index自動生成（Normalized Story JSON / Extraction Resultからの抽出処理）
- raw textを含むreview packet生成
- Story page / Episode page rendererの変更
- Story Summary schema変更
- AI Analysis / Speculation schema実装
- AI要約生成実装（LLM provider/prompt/batch処理）

---

# 4. Evidence indexの役割（What is it for）

Evidence indexは、SummaryやCandidate/Merged Knowledgeが参照している`evidenceRefs`を、人間が追跡・検証しやすくするための**索引**である。

## 4.1 役割

- Summaryの根拠IDを追跡する（「このSummary文はどのBlockから来たか」を辿れるようにする）
- Story / Episode / Block / Dialogueなどの参照関係を整理する
- AI要約やAI抽出結果の検証に使う（人間レビューア・将来のAI Analysisいずれからも参照される索引）
- 将来のEvidence link先になる（`evidenceRefs`テキスト表示からリンク表示への移行先）
- Knowledge GraphやReview toolingの土台になる
- **raw textを公開するページではない**

## 4.2 非目的（Explicitly not）

- raw DEC本文の公開
- 元セリフ全文の公開
- script command dumpの公開
- extraction JSONの生dump
- AI考察の表示（AI Analysis/Speculationとは別物、§9参照）
- 公開Wiki上での全文検索用raw corpus化

Evidence indexは「このIDはどこから来たどんな種類の参照か」を示す索引であり、「元の文章を読むためのページ」ではない。この区別が、既存の「raw textを出さない」プロジェクト横断ルール（`AI_CONTEXT.md` §3.11、`Wiki_Output_Design.md` §4・§7）とEvidence indexを両立させる鍵になる。

---

# 5. Public Evidence Index / Internal Review Evidence Packet の分離

Evidence indexには2種類の用途があり得るため、明確に分離する。

## 5.1 A. Public Evidence Index

公開Wikiに出してよい最低限の索引。**本PR以降、schema化・実装の対象とするのはこちらのみ**（§10参照）。

含めてよい情報:

- `evidenceId`
- `storyId` / `publicStoryId`
- `episodeId` / `publicEpisodeId`
- `blockId` / `sceneId`
- evidence type（§8）
- speaker canonicalId（解決できている場合のみ）
- related entity IDs
- source document reference（`storyId`/`episodeId`単位、ローカル絶対パスは含めない）
- summaryから参照されているかどうか（`referencedBy`）
- **raw textなし**
- **raw commandなし**
- **local pathなし**

## 5.2 B. Internal Review Evidence Packet

内部review用の詳細情報。**将来別設計に分離する**（本PRのスコープ外、§10 Phase 5）。

含みうる情報（将来検討）:

- Normalized Story JSON内の該当block
- speaker label詳細
- parser command詳細
- extraction candidate詳細
- validation/debug metadata
- 場合によっては短いcontext snippet（採否は将来設計で慎重に判断する）

Internal Review Evidence Packetは`workspace/review_packets/evidence/`のようなローカル専用領域に置き、**commit禁止**とする（既存の`workspace/review_packets/`（`.gitignore`済み）と同じ扱い方針を踏襲する）。

## 5.3 採用方針

- まずはPublic Evidence Indexのみを設計対象にする
- Internal Review Evidence Packetは将来別設計に分離する（本文書では大枠の位置づけのみ示す）
- 公開Wikiではraw textを出さない
- review用にraw textを扱う場合も`workspace/`配下・commit禁止にする

---

# 6. Raw text非表示方針

Public Evidence Indexでは以下を**表示しない**（既存の横断ルール、`AI_CONTEXT.md` §3.11・`Wiki_Output_Design.md` §4を踏襲）。

- raw DEC text
- 元セリフ全文
- raw command（`@ChTalk`等）
- local absolute path
- raw source file nameの過度な露出（既存の`_sanitize_source_path`と同じ縮約方針を踏襲する）
- `$num`等のscript変数
- extraction JSONの生dump
- promptやLLM出力の生dump

Summary `evidenceRefs`から将来リンクされるEvidence page/entryでも、初期段階では**ID・種別・Story/Episode情報・関連entityだけ**を表示する方針とする。本文・抜粋（`textExcerpt`相当）は表示しない。

raw textを使った詳細検証が必要な場合は、§5.2のInternal Review Evidence Packetとして`workspace/review_packets/evidence/`配下に分離する（commit禁止）。

---

# 7. Source of truth比較と採用方針

Evidence indexの生成元（source of truth）を4案比較する。

## 7.1 候補A: Normalized Story JSON

- 長所: dialogue/block/scene/evidenceIdの元に最も近い、parser由来IDと相性がよい
- 短所: raw textに近い構造のため、公開時にraw textを誤って含めないよう注意が必要

## 7.2 候補B: Extraction Result

- 長所: AI抽出candidateが参照する`evidenceIndex`/`evidenceIds`と相性がよい、candidate単位の検証に向く
- 短所: Summary `evidenceRefs`だけでなくEntity candidateの根拠にも使われるため、Evidence index自体の責務がやや広がる

## 7.3 候補C: Merged Knowledge Collection

- 長所: Wiki rendererがすでに読み込んでいる、public wiki出力に最も近い
- 短所: `evidence`配列（EvidenceRef埋め込み）はentity単位に閉じており、Summary側の`evidenceRefs`（Story/Episode単位）を横断的に索引化する構造を持たない

## 7.4 候補D: Dedicated Evidence Index file（専用の中間成果物）

- 長所: Normalized Story JSON / Extraction Resultから安全な情報だけを抽出して作る専用ファイルにできる。公開用にraw textを除外しやすい。将来のリンク先として安定させやすい（生成元が変わってもEvidence index自体のURLは変えずに済む）
- 短所: 新しい中間生成物・生成パイプラインが1段階増える

## 7.5 採用方針

**Public Evidence Indexは候補D（Dedicated Evidence Index file）をsourceにする。**

- 生成元は候補A（Normalized Story JSON）と候補B（Extraction Result）の両方とする。Block/Scene/Episode/Story IDと種別（evidence type）はNormalized Story JSON由来、Summary/Candidateからの参照関係（`referencedBy`）はExtraction Result/Merged Knowledge Collection/Story Summary側から逆引きして組み立てる
- raw textを含めない安全な中間成果物として扱う（Normalized Story JSONの`source.raw`相当のフィールドは生成時点で除外する）
- Merged CollectionやSummaryは、Evidence indexを**参照する側**（consumer）であり、Evidence index自体の生成元にはしない
- 候補C（Merged Knowledge Collection）は将来`referencedBy`の一部情報源として使うが、単独のsource of truthにはしない

---

# 8. Evidence type方針

Normalized Story JSONのblock typeと整合させる（`Normalized_Story_JSON.md`の`type`フィールド、`Identifier_Specification.md` §5・§8）。

| evidenceType | 対応するBlock/粒度 | 備考 |
|---|---|---|
| `dialogue` | Dialogue Block（`_DLG{number}`） | |
| `monologue` | Monologue Block（`_MONO{number}`） | |
| `narration` | Narration Block（`_NAR{number}`） | |
| `choice` | Choice Block（`_CHOICE{number}`） | Choice Optionまで下げるかは次PRで検討（§14 未確定事項） |
| `stage_direction` | Stage Direction Block（`_STAGE{number}`） | 演出情報のみ、raw command名は出さない |
| `speaker_label` | Special Speaker Label（`agents/parser/speaker_labels.py`由来） | `name`コマンド/`@ChTalkName`由来のspeaker group等（`Extraction_Result_Schema.md` §13.5）。通常のCharacter evidenceとは区別する |
| `scene` | Scene単位（`_SC{number}`） | Block単位で特定できない場合の粗い粒度（`Identifier_Specification.md` §8のfallback） |
| `episode` | Episode単位 | さらに粗い粒度 |
| `story` | Story単位 | 最も粗い粒度 |
| `unknown` | Parser側`type: "unknown"`のBlock | 破棄しない原則（`AI_CONTEXT.md` §3.2）をEvidence indexでも踏襲する |

方針:

- **type enumを増やしすぎない**（上記10種で当面固定し、raw command名をそのままtypeとして露出しない）
- `unknown`を許容する（Parser側の`unknown`ブロック方針と一貫させる）
- `@ChTalk`等raw commandは公開indexのtype/どのフィールドにも出さない

---

# 9. Evidence ID link方針（次PR以降、本PRでは未実装）

PR #81では`evidenceRefs`をテキスト表示した。将来リンク化する場合の方針を3案比較する。

## 9.1 候補A: Evidence indexの単一ページ内anchor

```text
evidence/index.md#EVT_SAMPLE_E01_DLG0001
```

- 長所: 実装が簡単、初期段階に向く
- 短所: indexが巨大化しやすい（全story・全episodeのevidenceが1ページに集まる）

## 9.2 候補B: Story別Evidence page

```text
evidence/{publicStoryId or storyId}.md#EVT_SAMPLE_E01_DLG0001
```

- 長所: Story pageと対応しやすい、巨大化しにくい
- 短所: path helperとgroupingの実装が必要（`story_page_path`/`resolve_story_path_id`と同種のロジック）

## 9.3 候補C: Episode別Evidence page

```text
evidence/{publicEpisodeId or episodeId}.md#EVT_SAMPLE_E01_DLG0001
```

- 長所: `evidenceId`の粒度と近い、Episode単位検証に向く
- 短所: ページ数が増える（story 1件につきepisode数分のEvidence page）

## 9.4 推奨

**初期はStory別Evidence page（候補B）がバランス良い。**

- Story Summaryのリンク元がStory pageであり、同じStoryのEpisode群のevidenceを1ページにまとめる方が、Story page→Evidence pageの導線が自然（Story pageは既にstoryId単位でグルーピングされている、`Story_Page_Design.md` §6）
- 候補A（単一ページ）は初期実装は簡単だが、story数・episode数の増加でページが際限なく巨大化し、`Wiki_Output_Design.md`で繰り返し指摘されてきた「表が横長すぎる」問題と同種のスケーラビリティ問題を招く
- 候補C（Episode別）はEpisode pageとの対応は良いが、Story Summary側のevidenceRefs（story横断の場合がある）とEpisode単位ページの対応がやや複雑になる
- `publicStoryId`優先→`storyId`へのfallback方針（`resolve_story_path_id`と同じパターン）をEvidence page pathにもそのまま適用できる想定
- Episode pageからも、同じStory Evidence pageの該当anchorへリンクできる（§11.2）

**本PRではURL構造・path helper実装は行わない。** 次PR（`evidence-index-renderer-integration`）で実装する。

---

# 10. Implementation phases（実装フェーズ案）

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1: Design only | Evidence indexの役割・データモデル・公開範囲を設計。docs/tests/TASKS更新 | **本PR** |
| Phase 2: `evidence-index-schema-implementation` | `schemas/evidence_index.schema.json`、`docs/templates/evidence_index_template.yaml`、synthetic fixture、validator script、loader | 未着手 |
| Phase 3: `evidence-index-renderer-integration` | Evidence page生成、Story Summary/Episode Summary evidenceRefsのリンク化、Story pageからEvidence pageへの導線、raw text非表示の維持 | 未着手 |
| Phase 4: `evidence-index-generation-dry-run` | Normalized Story JSON/Extraction ResultからEvidence index候補を生成、workspace配下でのdry-run、review後にpublic-safe evidence indexへ昇格 | 未着手 |
| Phase 5: Internal review packets | raw textや詳細contextを含むreview packetをworkspace配下に生成（commit禁止）、public wikiとは分離 | 未着手 |

---

# 11. Story page / Episode page / Summary / Unresolved reportとの関係

## 11.1 Story page

- Story Summary / Episode SummariesのevidenceRefsを表示する（実装済み、PR #81）
- 将来、`evidenceRefs`をEvidence pageへリンクする（§9、次PR以降）
- Story単位Evidence pageへの導線を持つ可能性がある（Story page内に「Evidence一覧」的なリンクを追加する案、次PR以降で検討）

## 11.2 Episode page

- 現時点ではsummary/evidenceRefsを表示していない（`Story_Page_Design.md`のNon-goalsの通り、本PRでも変更しない）
- 将来Episode Summaryを表示する場合、同じStory単位のEvidence page（該当anchor）へリンクできる
- Episode pageは詳細確認・review用途としてEvidence indexとの相性が良い（既存のCandidate Counts/Related Charactersと同じ「詳細確認ページ」という役割、`Story_Page_Design.md` §7）

## 11.3 Summary（Story Summary / Episode Summary）

- `evidenceRefs`はEvidence index entryを参照する（`evidenceId`をキーに引く）
- Summary textにraw textは持たない（既存方針、`Story_Summary_Design.md` §7.3）
- Evidence indexにもraw textは出さない（本文書§6）
- 表示対象条件（`review.status`がreviewed/approved・`generationStatus`がgenerated）はSummary側の既存方針をそのまま踏襲し、Evidence index側で独自の表示条件は持たない

## 11.4 Unresolved report

- unresolved entityがどのevidenceに出現したかの逆引きを、将来Evidence index経由で提供できる可能性がある
- ただし初期実装（Phase 2〜4）では必須ではない。Unresolved reportは既に`evidenceRefs`/`sourceCandidates`の件数を独自に集計しており（`agents/wiki_generator/renderer.py`の`_render_entity_type_sections`）、Evidence indexとの統合は将来の改善候補とする

---

# 12. Evidence indexとAI Analysis / Speculationの関係

- Evidence indexは**根拠索引**であり、考察本文を持たない
- AI Analysis / SpeculationはEvidence indexを参照してよい（`ai_inferred`なFieldValue/Relationshipの根拠として`evidenceId`を引用する用途）
- AI Analysis / Speculation用のevidenceRefsも、将来同じEvidence indexを使える（evidence typeの追加は不要、既存の`dialogue`/`narration`等をそのまま参照する）
- **Evidence indexには「これは伏線である」等の解釈を持たせない**。解釈はAI Analysis側（`Wiki_Output_Design.md` §9.17）に置く
- この分離は、Story Summary/Episode Summaryと同様に`AI_CONTEXT.md` §4.5「Official / AI Summary / AI Analysisを分離する」の具体化である

---

# 13. Data model draft（次PR以降のschema実装案）

## 13.1 ドキュメント構造案

```yaml
evidenceIndexVersion: 1
generatedFrom:
  normalizedStoryRefs:
    - storyId: EVT_SAMPLE
      episodeId: EVT_SAMPLE_E01
  extractionRefs: []
entries:
  - evidenceId: EVT_SAMPLE_E01_DLG0001
    evidenceType: dialogue
    storyId: EVT_SAMPLE
    publicStoryId: EVT_260101_001
    episodeId: EVT_SAMPLE_E01
    publicEpisodeId: EVT_260101_001_E01
    sceneId: EVT_SAMPLE_E01_SC001
    blockId: EVT_SAMPLE_E01_BLK0001
    speaker:
      speakerId: CHAR_TEST_001
      displayName: Synthetic Speaker
      resolutionStatus: resolved
    relatedEntities:
      - entityType: character
        id: CHAR_TEST_001
        displayName: Synthetic Speaker
    referencedBy:
      summaries:
        - storyId: EVT_SAMPLE
          summaryType: episode
          episodeId: EVT_SAMPLE_E01
      candidates: []
    visibility:
      public: true
      rawTextIncluded: false
    notes: null
```

これは設計案であり、既存のID体系・既存schema（`schemas/story_summary.schema.json`のEvidenceRefパターン等）に合わせて次PR（Phase 2）で調整する。

## 13.2 Required / optional fields（草案）

### 必須候補

| Field | 説明 |
|---|---|
| `evidenceId` | Block ID優先、粗い場合はScene/Episode/Story ID（`Identifier_Specification.md` §8） |
| `evidenceType` | §8の10種いずれか |
| `storyId` | 対象Story ID |
| `episodeId` | 対象Episode ID（story単位のevidenceの場合は省略可、次PRで検討） |
| `visibility.rawTextIncluded` | 常に`false`固定（公開Evidence indexである保証） |

### 任意候補

| Field | 説明 |
|---|---|
| `publicStoryId` / `publicEpisodeId` | 公開Wiki URL用ID（`story_manifest.yaml`と対応） |
| `sceneId` / `blockId` | より詳細な参照情報 |
| `speaker` | 解決できた場合のspeaker情報（`speakerId`/`displayName`/`resolutionStatus`） |
| `relatedEntities` | このevidenceに関連するentity一覧（Character等） |
| `referencedBy` | このevidenceIdを参照しているSummary/Candidateの一覧（逆引き用） |
| `notes` | 自由記述の補足（実データ本文の転記はしない） |

`visibility.public`は将来的にInternal Review Evidence Packet側の情報を混在させる可能性を見据えた予約フィールドとし、Public Evidence Indexでは常に`true`のエントリのみを対象とする（`false`のエントリを混在させる設計は採用しない。混在させると「公開Wikiに何を出しているか」の境界が曖昧になるため、Public Evidence IndexとInternal Review Evidence Packetは完全に別ファイル・別ディレクトリとして分離する、§5参照）。

---

# 14. Validation plan（次PR以降、本PRでは未実装）

- `schemas/evidence_index.schema.json`（未作成）でstructural validationを行う
- `evidenceId`が実在のNormalized Story JSON/Extraction Result側と一致するかのcross-reference検証（既存の「semantic validationの範囲が限定的」という既知課題、`TASKS.md` Known Issuesと同様の性質）
- raw text禁止文字列検出は、`agents/wiki_generator/story_summaries.py`の`FORBIDDEN_TEXT_PATTERNS`と同種のvalidatorを、Evidence index生成パイプライン側にも適用する想定（自由記述フィールド`notes`等が対象）

---

# 15. 未確定事項（Open questions）

- Choice Block由来のevidenceIdを、Choice単位（`_CHOICE{number}`）とChoice Option単位（`_CHOICE{number}_OPT{number}`）のどちらで扱うか（`Identifier_Specification.md` §5.6・§5.7の両方が存在するため、Phase 2で決定する）
- `referencedBy.candidates`（Extraction Candidate側からの逆引き）の具体的なデータ構造（Stage A candidate IDは再生成で変わりうるため、安定した参照キーの設計が必要、`Merged_Knowledge_Design.md` §10.4と同じ制約）
- Story単位のevidence（`episodeId`を持たない、story全体を指すevidence）をどう表現するか
- Internal Review Evidence Packetの詳細設計（§5.2、本文書では大枠のみ）
- Evidence indexとKnowledge Graphの連携方式（本文書では「土台になる」とだけ位置づけ、詳細設計は別途）
- Unresolved reportとの統合要否（§11.4、初期実装では必須ではないと整理したが、実際の運用で必要性を再評価する）

---

# 16. 参照

- `docs/architecture/06_AI/Story_Summary_Design.md`（Story/Episode Summaryのデータ構造・evidenceRefs方針、§9で本文書へのリンクを追加）
- `docs/architecture/07_Wiki/Story_Page_Design.md`（Story page設計、evidenceRefs表示実装状況）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§4 evidenceRefsの扱い、§9.16 Source/evidence index page、§9.17 AI analysis page）
- `docs/architecture/05_Parser/Identifier_Specification.md`（§5 Episode/Scene/Content ID、§8 Evidence ID）
- `docs/architecture/05_Parser/Normalized_Story_JSON.md`（Block構造・`type`フィールド）
- `docs/architecture/06_AI/Extraction_Result_Schema.md`（EvidenceRef構造、§13.5 SpecialSpeakerLabelCandidate）
- `docs/architecture/06_AI/Merged_Knowledge_Design.md`（§10 Provenance/Evidence、§10.4 candidate ID安定性の制約）
- `docs/architecture/06_AI/Extraction_Pipeline.md`（§6 Evidenceの扱い）
- `agents/wiki_generator/renderer.py`（`_render_evidence_refs_line`、現行evidenceRefsテキスト表示実装）
- `TASKS.md`（次PR候補の追跡）
