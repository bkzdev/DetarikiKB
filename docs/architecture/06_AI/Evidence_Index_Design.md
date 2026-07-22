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

内部review用の詳細情報。Public Evidence Indexとは別schema・別loader/validator・別CLIで扱う。詳細設計は`docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`へ分離した（§10 Phase 5.1）。

含みうる情報:

- Normalized Story JSON内の該当block
- speaker label詳細
- parser command詳細
- extraction candidate詳細
- validation/debug metadata
- 明示opt-in時だけの短いcontext snippet

Internal Review Evidence Packetは`workspace/review_packets/evidence/`の固定rootに置き、**commit禁止**とする（既存の`workspace/review_packets/`（`.gitignore`済み）と同じ扱い方針を踏襲する）。raw内容はallowlist fieldに限定し、内部ID⇔公開IDのmapping table、保持・削除、human reviewとの境界も専用設計で定義する。

## 5.3 採用方針

- Public Evidence IndexとInternal Review Evidence Packetを完全に別成果物として扱う
- Packetの詳細は`Internal_Review_Evidence_Packet_Design.md`を正とし、本文書では公開側との境界だけを示す
- 公開Wikiではraw textを出さない
- review用にraw textを扱う場合も`workspace/`配下・commit禁止にする

**実装状況（`feature/evidence-index-schema-implementation`で実施）**: Public Evidence Indexの保存場所を`knowledge/evidence/stories/{storyId}.yaml`に確定した（`knowledge/summaries/stories/`と同じ「1 story 1 file」パターン）。`knowledge/evidence/`・`knowledge/evidence/stories/`は`.gitkeep`のみで実データ未投入。Internal Review Evidence Packet（`workspace/review_packets/evidence/`）は既存の`workspace/review_packets/`ignoreパターンでcommit対象外であり、`internal-review-evidence-packet-design`で詳細設計まで完了したが、schema/generatorは未実装である。

**【`feature/evidence-index-promotion-target-filename-policy`で判明・再検討】** 上記の`{storyId}.yaml`という保存場所方針は、`storyId`がsourceKey由来の内部IDであるため、初回実データpromotion試行（PR #91）でGit履歴への永続化リスクが判明した。`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`で、保存先ファイル名を`{publicStoryId}.yaml`へ、Evidence Index内部の主キーを`publicEvidenceId`中心のprojectionへ切り替える方針（案C）を決定した。実装は後続PR。

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

**Public promotion時の初期公開対象entry type（`evidence-index-generation-review`で決定）**: `stage_direction`は実データdry-runでentry数の大半（PR #85実データで約9割）を占めることが判明したため、初期Public Evidence Indexへの昇格時は原則除外する。初期公開対象は`dialogue`/`monologue`/`narration`/`choice`/`unknown`とし、`stage_direction`/`scene`/`episode`/`story`/`speaker_label`は除外または保留とする。詳細な比較・promotion criteria・filter policyは`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`を参照。

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
- ~~Episode pageからも、同じStory Evidence pageの該当anchorへリンクできる（§11.2）~~ → `episode-page-evidence-linking-review`で限定契約を確定した。後続PR `episode-page-summary-evidence-linking`は対象Episodeの表示可能なEpisode Summary本文と直下の`evidenceRefs`のみを追加し、解決済み参照は同じStory別Evidence pageの該当anchorへ公開ID優先でリンクする。未解決時は入力IDのbacktick fallbackを維持する。general Story Evidence index link、Episode別Evidence page/episode絞込anchor、schema/storage/CLI option/path変更は含めず、manual review後に必要性を再判断する

**本PRではURL構造・path helper実装は行わない。** 次PR（`evidence-index-renderer-integration`）で実装する。

---

# 10. Implementation phases（実装フェーズ案）

| フェーズ | 内容 | 状態 |
|---|---|---|
| Phase 1: Design only | Evidence indexの役割・データモデル・公開範囲を設計。docs/tests/TASKS更新 | 完了 |
| Phase 2: `evidence-index-schema-implementation` | `schemas/evidence_index.schema.json`、`docs/templates/evidence_index_template.yaml`、synthetic fixture、validator script、loader | 完了 |
| Phase 3: `evidence-index-renderer-integration` | Evidence page生成、Story Summary/Episode Summary evidenceRefsのリンク化、Story pageからEvidence pageへの導線、raw text非表示の維持 | **完了（本PR）** |
| Phase 4: `evidence-index-generation-dry-run` | Normalized Story JSON/Extraction ResultからEvidence index候補を生成、workspace配下でのdry-run、review後にpublic-safe evidence indexへ昇格 | **完了（本PR、昇格運用のみ未着手）** |
| Phase 4.5: `evidence-index-generation-review` | dry-run結果レビュー、public entry type方針、promotion/exclusion criteria設計（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`） | 完了 |
| Phase 4.6: `evidence-index-generation-filtering` | `build_evidence_index_candidates.py`への`--public-profile`/`--include-types`/`--exclude-types`実装、defaultでstage_direction除外 | 完了 |
| Phase 4.7: `evidence-index-promotion-policy-implementation`（PR #88） | `scripts/check_evidence_index_promotion.py`（promotion check、check-only）・human review template・promotion runbook | 完了（実copyは未実装） |
| Phase 4.8: `evidence-index-promotion-dry-run`（PR #89） | 実データfiltered outputに対するpromotion check/human review templateの実運用dry-run | 完了 |
| Phase 4.9: `evidence-index-promotion-copy-script`（PR #90） | `scripts/promote_evidence_index.py`（promotion checkをPASSした候補のcopy script、dry-run既定・`--execute`必須） | 完了（実データcommitは未実施） |
| Phase 4.10: `evidence-index-promotion-first-reviewed-sample`（PR #91） | 実データ1 storyの初回昇格試行 | 見送り（sourceKey由来ID問題を発見） |
| Phase 4.11: `evidence-index-promotion-target-filename-policy`（PR #92） | 内部ID/公開ID分離方針の設計（`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`） | 完了（設計のみ） |
| Phase 4.12: `evidence-index-public-id-schema-design`（PR #93） | `publicEvidenceId`の形式・prefix mapping確定、`schemas/evidence_index.schema.json`へのoptional追加、loader対応 | 完了（schema/loaderの最小変更のみ） |
| Phase 4.13: `evidence-index-public-id-projection`（PR #94） | Compatible projection（案A）の実装。`scripts/project_evidence_index_public_ids.py`で`publicEvidenceId`を実際に生成・付与する（内部IDは削除しない） | 完了（Public-safe projection・renderer切替・promotion再開は未着手） |
| Phase 4.14: `evidence-index-public-id-public-safe-projection`（PR #95） | Public-safe projection（案B）の実装。`scripts/project_evidence_index_public_ids.py`に`--projection-mode public-safe`を追加し、内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）を公開ID中心へ置換・除去する | 完了（renderer切替・実promotion再開・publicEpisodeId自動補完は未着手） |
| Phase 4.15: `evidence-index-public-episode-id-assignment`（PR #96） | 未確定`publicEpisodeId`の検出・割当候補提案。`docs/architecture/06_AI/Public_ID_Registry_Design.md`（新設）でPublic ID Registry設計、`scripts/check_public_episode_ids.py`を実装 | 完了（実Registry投入・projection scriptとの統合は未着手） |
| Phase 4.16: `evidence-index-public-id-registry-integration`（PR #97） | Public ID Registryを`project_evidence_index_public_ids.py`へ統合し、欠落`publicEpisodeId`をRegistryから補完できるようにする | 完了（実Registry投入・renderer切替・実promotion再開は未着手） |
| Phase 4.17: `evidence-index-public-id-renderer-switch`（PR #98） | Evidence page見出し・anchor・Summary evidenceRefsリンクを`publicEvidenceId`中心に切り替える | 完了（実Registry投入・実promotion再開は未着手） |
| Phase 4.18: `evidence-index-promotion-first-reviewed-sample-retry`（PR #99） | 実Public ID Registry entry追加、実データ1 storyの初回昇格を再試行する | 完了（実Evidence Index 1件を`knowledge/evidence/stories/`へ昇格済み） |
| Phase 4.19: `evidence-index-promotion-first-sample-visual-review`（PR #100） | 昇格済み1 storyについてWiki表示・導線・内部ID/raw text非露出を最終確認する | 完了（実装変更なし） |
| Phase 4.20: `evidence-index-promotion-batch-policy`（PR #101） | 複数storyへ広げる前のbatch promotion運用方針を設計する | 完了（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`新設） |
| Phase 4.21: `evidence-index-promotion-first-batch-dry-run`（PR #102） | 2〜3 storyを対象にworkspace限定でbatch dry-runを実施する | 完了（tooling観点PASS、実commitなし） |
| Phase 4.22: `evidence-index-batch-candidate-selection-policy`（PR #103） | promotion候補storyの機械的選定基準（unknown比率等の閾値・3分類・real batch promotion前提条件）を確定する | 完了（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3新設） |
| Phase 4.23: `script-command-dictionary-expansion-batch-001`（PR #104） | 対象2 storyのunknown比率を下げるparser command辞書拡充 | 完了 |
| Phase 4.24: `story-manifest-public-story-id-real-data-assignment`（PR #105） | 対象2 storyの`publicStoryId`/`publicEpisodeId`確定→再normalize/merge→Story page導線動作確認、second batch dry-run | 完了（tooling・導線ともPASS、実commitなし） |
| Phase 4.25: `evidence-index-promotion-first-real-batch`（本PR） | Phase 3初回実batch promotion。2 story分のPublic ID Registry実データentry追加＋`knowledge/evidence/stories/`への実昇格 | **完了（本PR、2 story昇格）** |
| Phase 5.1: `internal-review-evidence-packet-design` | Packetのbundle/data model、内部ID mapping、raw/context、validation、review/retention/cleanup境界を設計 | **完了（設計のみ）** |
| Phase 5.2: `internal-review-evidence-packet-schema-validator` | Public側とは別のmanifest/story schema、合成fixture、専用validator | 完了 |
| Phase 5.3: `internal-review-evidence-packet-generator` | Normalized Storyと既存mappingからworkspace限定Packetを生成 | 完了 |
| Phase 5.4: `internal-review-evidence-packet-operations` | runbook、inventory、期限warning、dry-run既定cleanup | 完了 |
| Phase 6: `episode-page-evidence-linking-review` | Episode pageへ追加するSummary/evidenceRefs導線を限定レビュー | 完了（docs-only） |
| Phase 6.1: `episode-page-summary-evidence-linking` | 対象Episodeの表示可能なEpisode Summary本文と直下の`evidenceRefs`のみを実装し、その後manual review | 次PR |

**実装状況（`feature/evidence-index-schema-implementation`で実施）**: `schemas/evidence_index.schema.json`（§13データモデル案をそのまま実装。`evidenceType`10種enum・`visibility.rawTextIncluded`を`const: false`で固定）、`agents/wiki_generator/evidence_index.py`（loader/validator、`build_evidence_id_index`/`group_entries_by_story`/`group_entries_by_public_story`/`group_entries_by_episode`/`group_entries_by_public_episode`等のhelper）、`scripts/validate_evidence_index.py`（schema検証・duplicate evidenceId検出・raw text禁止文字列検出・`visibility.public`/`rawTextIncluded`検証）、`docs/templates/evidence_index_template.yaml`、合成fixture（`tests/fixtures/evidence_index/`）を追加した。保存場所は`knowledge/evidence/stories/`を採用し`.gitkeep`のみで実データ未投入。

**実装状況（`feature/evidence-index-renderer-integration`で実施）**: `scripts/render_wiki.py`に`--evidence-index <path>`を追加した。`agents/wiki_generator/paths.py`に`evidence_page_path`（Story別Evidence page、`story_page_path`と同じpublicStoryId優先→storyId fallback方針）、`agents/wiki_generator/evidence_index.py`に`EvidenceIndexLookup`/`build_evidence_index_lookup`/`resolve_group_public_story_id`を追加した。`render_evidence_page`（Evidence Index entryの安全な項目のみ表示、raw text/raw command/local pathは一切出さない）でStory別Evidence pageを生成し、Story page Review Linksに該当storyのEvidence Indexがある場合のみ導線を追加した。Story/Episode SummaryのevidenceRefsは、該当`evidenceId`がEvidence Indexに存在する場合のみEvidence pageの該当anchor（`### {evidenceId}`見出しを小文字化したもの）へリンクし、存在しない場合は従来通りID表示のまま（unresolved扱い、errorにしない）。**Evidence IndexはCLI側で`--validate`指定の有無にかかわらず常にschema検証・raw text禁止文字列検出・`visibility.rawTextIncluded`検証を行う**（安全性を最優先するEvidence Index固有の方針）。**Episode pageへのSummary/evidenceRefs表示・Evidence Index自動生成・Internal Review Evidence Packet生成は行っていない**（次PR`evidence-index-generation-dry-run`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-generation-dry-run`で実施）**: `scripts/build_evidence_index_candidates.py`を追加し、Normalized Story JSON（任意でExtraction Resultも補助的に）からPublic Evidence Index候補YAMLをdry-run生成できるようにした（詳細手順は`docs/runbooks/Evidence_Index_Generation_Dry_Run.md`）。Block単位（`dialogue`/`monologue`/`narration`/`choice`/`stage_direction`/`unknown`の6種、既存Block IDがあるもののみ）でEvidence entryを生成し、`text`/`rawText`/`raw`/`rawCommand`/`args`等の本文系フィールドは値を一切読み取らない。speakerは`isResolved: true`かつ`speakerId`がある場合のみ（`displayName`は常に`null`）、relatedEntitiesはspeaker由来の`character`とScene`location.locationId`由来の`location`のみを出す。`--extractions`指定時はExtraction Resultのcandidate配列`evidenceIds`から`referencedBy.candidates`を逆引きする。生成したcandidateはスクリプト内部で必ずschema検証+Python側整合性検証（raw text禁止文字列含む）を通し、失敗したstoryは書き出さない。出力先は`workspace/evidence_index_dry_runs/`（今回`.gitignore`へ追加）。実データ小規模サンプル（EVENTカテゴリ1story・episode2件、既存の匿名化サンプルを再利用）で生成→`validate_evidence_index.py`→`render_wiki.py --evidence-index`まで確認し、Evidence page（`evidence/{publicStoryId}.md`）の非ASCII文字が「未登録」等の定型プレースホルダーのみであることを確認した（実データ由来のdialogue/narration本文・raw command・local pathの混入なし）。**Scene/Episode/Story単位の粗い粒度のEvidence entry生成、`speaker_label`のevidenceType対応、Story Summaryとの`referencedBy.summaries`連携、Internal Review Evidence Packet生成、`knowledge/evidence/stories/`への自動昇格は行っていない**（次PR候補`evidence-index-generation-review`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-generation-filtering`で実施）**: `evidence-index-generation-review`（PR #86）で決定したPublic entry type方針（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`）を踏まえ、`scripts/build_evidence_index_candidates.py`に`--public-profile default|full|review`（デフォルト`default`）・`--include-types`・`--exclude-types`を追加した。**このスクリプトのdefault挙動をPR #85時点の全type生成からPublic向け（`stage_direction`除外）に変更した**。優先順位は「profile → `--include-types`（置き換え） → `--exclude-types`（常に最後、includeと衝突時はexcludeが勝つ）」、未知のevidenceType指定時はexit code `2`。filterで除外されたentryは`skippedBlockCount`ではなく`filteredEntryCount`/`filteredByTypeCounts`/`filteredReasonCounts`として区別してreportに記録し、`referencedBy.candidates`はfilterで出力対象になったentryにのみ付与する。PR #85と同じ匿名化サンプルで再実行し、default profileでentry数が1793件→187件に縮小すること、`--public-profile full`で1793件（PR #85相当）を再現できることを確認した。**Evidence page renderer変更・promotion script実装・Internal Review Evidence Packet生成は行っていない**（次PR候補`evidence-index-promotion-policy-implementation`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-policy-implementation`で実施）**: `scripts/check_evidence_index_promotion.py`を追加した。schema検証+`agents.wiki_generator.evidence_index.validate_evidence_index_collection`の再利用に加え、Evidence Index YAML全文へのraw/source text禁止文字列scan（`FORBIDDEN_TEXT_PATTERNS`を再利用）、`--policy public-default`（デフォルトかつ現状唯一のpolicy）によるentry type policy check（`stage_direction`は専用メッセージでblocking error）を実装した。`--story-summaries`指定時のみ、reviewed/approvedかつgeneratedなSummaryの`evidenceRefs`がEvidence Indexに存在するかを確認し、missingはwarning（blockingにしない）とする。`--report`でMarkdown reportを出力できる。`docs/templates/evidence_index_promotion_review_template.md`（human review記録テンプレート）・`docs/runbooks/Evidence_Index_Promotion_Check.md`（手順）を追加した。**実際のcopy・commit・自動昇格・Evidence page renderer変更・Internal Review Evidence Packet生成は行っていない**（check-onlyのgatekeeper script、次PR候補`evidence-index-promotion-dry-run`/`evidence-index-promotion-copy-script`/`internal-review-evidence-packet-design`）。

**実装状況（`feature/evidence-index-promotion-copy-script`で実施）**: `scripts/promote_evidence_index.py`を追加した（詳細手順は`docs/runbooks/Evidence_Index_Promotion_Copy.md`）。**デフォルトは常にdry-run**で、`--execute`を明示指定しない限り一切ファイルを書き込まない。`check_evidence_index_promotion.py`の`_build_report`をimportして再利用し、promotion check・`--review-note`のDecision承認判定（`Approved for promotion`のcheck、`Rejected`/`Needs revision`は安全側で非承認扱い）・review note自体のraw/source text禁止文字列scan・1ファイル1story方針（`entries[].storyId`単一）・上書き禁止（既定、`--overwrite`で明示許可）のすべてを満たさない限りcopyしない。copyは`shutil.copy2`によるbyte-for-byte copyとし、copy後は`--target`に対してもschema+整合性検証を再実行する（sanity re-check）。`--target`は既定で`knowledge/evidence/stories`のみ許可（`--allow-nonstandard-target`はtests専用）。合成fixtureで26件のtestsを追加。**実データEvidence Indexの`knowledge/evidence/stories/`への実copy・commitは行っていない**（本scriptはcopyのみでgit操作は行わない。次PR候補`evidence-index-promotion-first-reviewed-sample`/`internal-review-evidence-packet-design`）。

**実施結果（`feature/evidence-index-promotion-first-reviewed-sample`）**: 実データ1 story（EVENTカテゴリ、episode2件）の初回昇格を試行したが、`storyId`（sourceKey由来）がファイル名・全entryの主キーフィールドに大量に出現することが判明し、Git履歴への永続化リスクを理由に安全側で見送った（`knowledge/evidence/stories/`は変更なし）。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.1を参照。

**設計方針決定（`feature/evidence-index-promotion-target-filename-policy`で実施）**: 上記問題を受け、`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`で内部trace ID/公開IDの分離方針を設計した。Public Evidence Indexは`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`中心のprojectionとして保存する方針（案C）を長期方針として採用し、promotion再開はprojection実装完了まで停止することを決定した。**本PRでは実装・schema変更は行っていない。**

**実装状況（`feature/evidence-index-public-id-schema-design`で実施）**: `publicEvidenceId`の形式（`{publicEpisodeId}_{PREFIX}{sequence:04d}`、type別prefix付き連番）・evidenceType prefix mapping（`dialogue`→`DLG`等）・採番方針を確定した（`Evidence_Index_Public_ID_Policy.md` §6.4〜6.6）。`schemas/evidence_index.schema.json`の`EvidenceIndexEntry`に`publicEvidenceId`をoptionalフィールドとして追加し（既存`publicStoryId`/`publicEpisodeId`と同じpattern、`evidenceId`/`storyId`/`episodeId`のrequiredは不変）、`agents/wiki_generator/evidence_index.py`の`EvidenceIndexEntry`dataclass/`_parse_entry`にも対応する`public_evidence_id`フィールドを追加した。schema tests・loader testsを追加し、既存fixtureに合成`publicEvidenceId`を1件追加した。**projection実装（実際の値の付与）・renderer/paths.py変更・promotion script変更・実Evidence Indexのcommitは行っていない**（次PR候補`evidence-index-public-id-projection`）。

**実装状況（`feature/evidence-index-public-id-projection`で実施）**: `scripts/project_evidence_index_public_ids.py`を追加し、`Evidence_Index_Public_ID_Policy.md` §6.4〜6.6で決定した形式・prefix mapping・採番方針の**Compatible projection（案A）**を実装した。`--policy public-default`で許可されたevidenceType（`dialogue`/`monologue`/`narration`/`choice`/`unknown`）のentryのみ、`(publicEpisodeId, evidenceType)`単位で入力entriesの出現順に1始まりの連番を振り、`publicEvidenceId`を新規付与する。`stage_direction`等policy対象外のtypeは既定では採番対象に含めず（`--strict`指定時のみblocking error）、既存の内部ID（`evidenceId`/`storyId`/`episodeId`/`sceneId`/`blockId`）はentryから一切削除しない。documentにpublicStoryIdを持つentryが1件も無い場合、entryにpublicEpisodeIdが欠落している場合（evidenceTypeが`unknown`でも同様に必須）、既存`publicEvidenceId`が再生成結果と一致しない場合、`publicEvidenceId`が重複する場合、projected出力がschema検証に失敗する場合はいずれもblocking errorとしexit code 1にする。`--output`/`--mapping-output`/`--report`は`knowledge/evidence/`配下を指定するとexit code 2で拒否する安全策を実装した。`--mapping-output`（CSV、storyId/publicStoryId/episodeId/publicEpisodeId/evidenceId/publicEvidenceId/evidenceType/sceneId/blockId列）は内部IDを含むため常にworkspace配下・commit禁止とし、`--report`（Markdown）には「compatible projection専用でpromotion対象ではない」ことを明記する。`tests/scripts/test_project_evidence_index_public_ids.py`（28件）で検証した。合成データによる`--input`のsynthetic dry-runおよび既存の匿名化実データサンプルに対する実行結果は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.3を参照。**Public-safe projection（案B、内部ID完全除去）・renderer/paths.pyのpublicEvidenceId中心切替・`promote_evidence_index.py`/`check_evidence_index_promotion.py`の変更・実Evidence Indexのcommit・実promotion再開はいずれも行っていない**（次PR候補`evidence-index-public-id-public-safe-projection`/`evidence-index-public-id-renderer-switch`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-id-public-safe-projection`で実施）**: `scripts/project_evidence_index_public_ids.py`に`--projection-mode {compatible,public-safe}`（デフォルト`compatible`）を追加し、**Public-safe projection（案B）**を実装した。`compatible`モードは既存挙動を完全に維持し（migration/debugging/mapping確認用、Public promotion対象ではない）、`public-safe`モードでは以下を行う: (1) `evidenceId`/`storyId`/`episodeId`の値をそれぞれ`publicEvidenceId`/`publicStoryId`/`publicEpisodeId`へ置換（schema互換のためrequired field自体は維持）、(2) `sceneId`/`blockId`/`referencedBy`/document-level`generatedFrom`は出力しない、(3) `speaker`は`resolutionStatus: resolved`のentryのみ保持、(4) `publicEvidenceId`を持たないentry（`stage_direction`等policy対象外type）はschema上`evidenceId`がrequired・pattern一致必須のため出力から除外、(5) 出力ファイル名を`{publicStoryId}.yaml`にし、1 documentに複数のpublicStoryIdが混在する場合や複数の入力ファイルが同じpublicStoryIdへ解決される場合はblocking error、(6) 出力文字列に対してsourceKey由来ID exposure scanを実行し（内部ID値のうち対応する公開IDと異なり4文字以上のものをforbidden internal IDとして扱う）、検出時はblocking error、(7) `publicEpisodeId`欠落は引き続きblocking error（自動補完は行わない、次PR候補`evidence-index-public-episode-id-assignment`）。`--mapping-output`は両モードで内部IDを含む（commit禁止は不変）。reportに`projection mode`/`public-safe field rewrite summary`/`internal ID exposure scan result`/`promotion readiness`（`compatible`は常に`not-promotion-ready`、`public-safe`はvalidation/exposure scan通過時のみ`promotion-candidate`）を追加した。`tests/scripts/test_project_evidence_index_public_ids.py`に23件のpublic-safe modeテストを追加（既存29件のcompatible modeテストは無変更）。匿名化実データサンプルへのdry-runでは、Episode 2の`publicEpisodeId`未確定によりpublic-safeモードもblocking FAILすることを確認した（想定どおりの安全側挙動）。**renderer/paths.pyの変更・`promote_evidence_index.py`/`check_evidence_index_promotion.py`の変更・実Evidence Indexのcommit・実promotion retry・`publicEpisodeId`自動補完はいずれも行っていない**（次PR候補`evidence-index-public-id-renderer-switch`/`evidence-index-promotion-first-reviewed-sample-retry`/`evidence-index-public-episode-id-assignment`）。

**実装状況（`feature/evidence-index-public-episode-id-assignment`で実施）**: PR #95で実データEpisode 2の`publicEpisodeId`未確定が判明したことを受け、`docs/architecture/06_AI/Public_ID_Registry_Design.md`（新設）で`publicEpisodeId`の役割・採番方針（`{publicStoryId}_E{episodeOrder:02d}`）・永続化場所を整理した。永続化場所は、内部情報を含みうる`story_manifest.yaml`（既存のsource of truth、変更なし）とは別に、公開してよい`publicStoryId`/`publicEpisodeId`のみを保持する**Public ID Registry**（`schemas/public_id_registry.schema.json`、`additionalProperties: false`で内部ID混入を構造的に防止）を長期方針として採用した。`scripts/check_public_episode_ids.py`（新規script）を追加し、Public Evidence Index候補から内部storyId単位でepisodeの`publicEpisodeId`割当状況を集計し、欠落episodeには`{publicStoryId}_E{episodeOrder:02d}`形式の割当候補（`reviewRequired: true`固定）を提案する。`--registry`指定時は既存Registry登録値を優先して再利用し、一度公開したIDを推測で変えないようにする。`--report`/`--suggestions-output`にはsourceKey由来の内部ID・raw title・raw pathを一切出力せず（`publicStoryId`が無いstory groupは`unidentified-story-group-{N}`という匿名ラベルで報告）、`knowledge/evidence/`・`knowledge/public_ids/`配下への書き込みはexit code 2で拒否する。`tests/scripts/test_check_public_episode_ids.py`（16件）で、all-assigned/missing/duplicate/missing publicStoryId/multiple stories/registry入力/`--strict`/internal ID非混入/安全策拒否を検証した。**実Registry・実`story_manifest.yaml`への実データ追加、`project_evidence_index_public_ids.py`との統合、renderer変更、実Evidence Indexのcommitはいずれも行っていない**（次PR候補`evidence-index-public-id-registry-integration`）。

**実装状況（`feature/evidence-index-public-id-registry-integration`で実施）**: `scripts/project_evidence_index_public_ids.py`に`--registry`/`--registry-schema`を追加し、Public ID Registryを実際にprojectionへ統合した。`scripts/check_public_episode_ids.py`の`_resolve_registry_lookup`/`_group_entries_by_internal_story`をimportして再利用し、Registry schema検証・episode grouping/orderロジックを両script間で共有した。欠落`publicEpisodeId`はRegistryに`publicStoryId + episodeOrder`で該当があれば補完（entryへ直接書き込み）し、既存値との不一致はblocking、Registryに該当が無い既存値はwarningとした。Registry補完後に`publicEvidenceId`を生成するため、補完episodeも正しいprefixの`publicEvidenceId`を得る。compatible/public-safe両モードで同じ補完ロジックを共有し、mapping CSVに`episodeOrder`/`publicEpisodeIdSource`/`registryMatched`/`registryConflict`/`registryPublicEpisodeId`列、reportに`## Registry`/`## Warnings`sectionを追加した。`scripts/check_public_episode_ids.py`の`_load_registry`にRegistry内`publicEpisodeId`重複検出も追加した（両script共有）。`tests/scripts/test_project_evidence_index_public_ids.py`に15件のregistry統合テストを追加し、既存67件は無変更のまま全PASSを確認した。匿名化実データサンプルでは、Episode 1（92 entries、input由来）+ Episode 2（95 entries、Registry補完）の**187 entries全件がPublic-safe projectionを通過**し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`ともPASS、internal ID exposureは0件であることを確認した（`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.6）。**実Registryへの実データ追加・renderer変更・実Evidence Indexのcommit・実promotion retryはいずれも行っていない**（次PR候補`evidence-index-public-id-renderer-switch`/`evidence-index-promotion-first-reviewed-sample-retry`）。

**実装状況（`feature/evidence-index-public-id-renderer-switch`で実施）**: `agents/wiki_generator/evidence_index.py`に`display_evidence_id`（`publicEvidenceId`優先、`evidenceId`にfallback）・`build_public_evidence_id_index`・`resolve_evidence_entry`（`publicEvidenceId`索引→内部`evidenceId`索引の順で解決）・`resolve_story_evidence_entries`（内部`storyId`索引→`publicStoryId`索引へのfallback）を追加し、`EvidenceIndexLookup`に`by_public_evidence_id`/`by_public_story_id`を追加した。`agents/wiki_generator/renderer.py`の`_render_evidence_entry`見出し・`_format_evidence_ref_display`（Summary `evidenceRefs`リンクの表示テキスト・anchor）を`display_evidence_id`優先に切り替えた。Public-safe projection output（内部`storyId`自体が`publicStoryId`の値へ置換される）をrenderすると、merged knowledge collection側の内部`storyId`だけではStory pageの「Review Links → Evidence index」導線が解決できなくなる問題を発見し、`resolve_story_evidence_entries`のfallbackで対応した。`evidence_page_path`（`agents/wiki_generator/paths.py`）自体は既に`publicStoryId`優先だったため変更していない。`tests/wiki/test_evidence_index.py`・`tests/wiki/test_wiki_renderer.py`に合成テストを追加し、既存テストは無変更のまま全PASSを確認した。匿名化実データサンプル（Public-safe projection、187 entries）を`render_wiki.py --evidence-index`でrenderし、Evidence page見出し・anchorが`publicEvidenceId`になり内部ID非露出であることを確認した（詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.7）。**実Registryへの実データ追加・実Evidence Index/実rendered outputのcommit・実promotion retryはいずれも行っていない**（次PR候補`evidence-index-promotion-first-reviewed-sample-retry`）。

**実施結果（`feature/evidence-index-promotion-first-reviewed-sample-retry`で実施）**: **`knowledge/evidence/stories/`が.gitkeepのみの状態を脱し、初めて実データ由来のEvidence Index 1件（`EVENT_164_260425.yaml`、匿名化表記、1 story・2 episodes・187 entries）が追加された。** `knowledge/public_ids/story_public_ids.yaml`に対応する1 story分のPublic ID Registry entryを正式commitし、これを使ったPublic-safe projection・promotion check・renderer確認・human review・`promote_evidence_index.py --execute`をすべて実施した。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.8、`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §13を参照。**複数story分の追加・batch promotion・script本体の変更はいずれも行っていない**。

**実施結果（`feature/evidence-index-promotion-first-sample-visual-review`で実施）**: 上記で追加された実Evidence Index 1件について、Wiki表示として公開して問題ないかを最終確認した。**実装変更は行っていない。** `validate_evidence_index.py`・`check_evidence_index_promotion.py`（Story Summary整合性込み）を`knowledge/evidence/stories`に対して再実行しPASS、`render_wiki.py --evidence-index knowledge/evidence/stories`でEvidence pageを再renderし、187 entries全件の見出しが`publicEvidenceId`形式・`stage_direction`が0件であることを確認した。Story pageの「Review Links → Evidence index」リンクが`publicStoryId`ベースで正しく解決されることも実データで確認した。Evidence Index YAML・Evidence page本体に内部ID・raw text露出が無いことをgrep・目視で確認し、`mkdocs build --strict`も成功した。詳細は`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.9を参照。**新規Evidence Index追加・batch promotionはいずれも行っていない**。

**設計方針決定（`feature/evidence-index-promotion-batch-policy`で実施）**: 1 storyのpromotion・visual reviewが実証されたことを踏まえ、複数storyへ広げる際のbatch promotion運用方針を`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（新設）に整理した。段階的batch size方針・Registry entry review条件・promotion前後チェックリスト・visual review方針・failed story handling・rollback方針・PR分割方針を定義し、次PR候補`evidence-index-promotion-first-batch-dry-run`のスコープを明記した。**本PRでは実装変更・実Evidence Index/Registry entryの追加・batch promotion実行はいずれも行っていない**（設計のみ）。

**実施結果（`feature/evidence-index-promotion-first-batch-dry-run`で実施）**: 上記batch policyのPhase 2に基づき、2 story（合計2039 entries）を対象にworkspace限定でbatch dry-runを実施した。Registry候補作成からrender・visual review・exposure checkまでの全工程がPASSし、**tooling自体には問題が無いことを実証した**が、選定storyの`unknown`比率が高いこと・`story_manifest.yaml`未割当の新規storyではStory page導線が機能しないことの2点が新たに判明し、この2 storyでのreal batch promotionは推奨しないと判断した。**実Registry entry・実Evidence Indexのcommitはいずれも行っていない。** 詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.2を参照。

**設計方針決定（`feature/evidence-index-batch-candidate-selection-policy`で実施）**: 上記で判明した品質問題を受け、promotion候補storyの機械的選定基準を`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.3に確定した（unknown比率等の閾値・3分類ラベル・判定手順・real batch promotion前提条件・ロードマップ）。**本PRでは実装変更は行っていない**（設計のみ）。

**実装状況（`feature/script-command-dictionary-expansion-batch-001`で実施）**: 対象2 storyのunknown比率を下げるため、`config/script_commands.yaml`・`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`に演出コマンド1種を追加した。staleなローカル生成物由来の誤った約90%という数値を訂正し、対象2 storyのunknown比率を0%まで低減した。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.4を参照。

**実施結果（`feature/story-manifest-public-story-id-real-data-assignment`で実施）**: 対象2 storyの`publicStoryId`/`publicEpisodeId`をローカルworkspace限定manifest経由で確定し、再normalize/merge後にStory pageの「Review Links → Evidence index」導線が実データで機能することを実証した（`resolve_story_evidence_entries`fallbackの初回実データ確認）。second batch dry-runで両storyとも`promotion-candidate`判定・PASSを確認した。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.5を参照。**Registry実データentry・実Evidence Indexのcommitはいずれも行っていない**。

**実施結果（`feature/evidence-index-promotion-first-real-batch`で実施）**: 上記でPASSした2 storyについて、初回実batch promotion（Phase 3）を実施した。`knowledge/public_ids/story_public_ids.yaml`に2 story分のRegistry entryを追加し（既存1 story分は無変更）、正式Registryを用いたPublic-safe projection（2 story・205 entries、`internal_id_exposure=0`）・validation/promotion check・render・exposure checkをすべてPASSで完走した。human review note（Decision: `Approved for promotion`）を作成した上で`promote_evidence_index.py --execute`を実行し、**`knowledge/evidence/stories/EVENT_168_260624.yaml`・`RAID_027_260504.yaml`の2件のみを正しくcopyした**（既存1 story分には触れていない）。copy後、既存分を含む全3ファイル（392 entries）の再検証・再render・exposure checkもすべてPASSした。詳細は`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.6・`docs/runbooks/Evidence_Index_Promotion_Copy.md` §13.12を参照。**3 story目以降の追加・batch promotion scriptの実装はいずれも行っていない**（次候補`internal-review-evidence-packet-design`/`evidence-index-promotion-batch-tooling`）。

---

# 11. Story page / Episode page / Summary / Unresolved reportとの関係

## 11.1 Story page

- Story Summary / Episode SummariesのevidenceRefsを表示する（実装済み、PR #81）
- `evidenceRefs`をStory別Evidence pageの該当anchorへリンクする（実装済み、`evidence-index-renderer-integration`）
- Story pageのReview Linksから、該当storyのEvidence Indexが存在する場合だけStory別Evidence pageへリンクする（実装済み、`evidence-index-renderer-integration`）

## 11.2 Episode page

- 現時点の実装ではsummary/evidenceRefsを表示していない。この状態は過去PR時点の履歴であり、`episode-page-evidence-linking-review`で後続実装を推奨する決定に更新した
- 後続PR `episode-page-summary-evidence-linking`は、対象EpisodeとID照合できる表示可能なEpisode Summary本文と、その直下の`evidenceRefs`のみを追加する。`generationStatus: generated`、`review.status: reviewed`/`approved`、内部/公開ID矛盾なしを満たさなければ表示しない。欠落・非表示・空本文ならsectionを出さず、Story Summaryは再掲しない
- `evidenceRefs`は空なら行を出さない。解決済みは同じStory別Evidence pageの該当anchorへ公開ID優先でリンクし、未解決時は入力IDのbacktick fallbackを維持する。public-safe projection済みのSummary/Evidence入力を前提とし、既存helperの解決挙動は変更しない
- general Story Evidence index link、Episode別Evidence page/episode絞込anchor、schema/storage/CLI option/path変更は後続実装にも含めず、manual review後に必要性を再判断する
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

# 14. Validation plan（Public実装済み / Packetは別契約）

- Public Evidence Indexは`schemas/evidence_index.schema.json`と`agents/wiki_generator/evidence_index.py`、`scripts/validate_evidence_index.py`でstructural/semantic validationを実装済みである
- Public側では`visibility.public: true`・`rawTextIncluded: false`、raw/source text禁止文字列、duplicate evidence ID等を検査する
- Internal Review Evidence Packetはraw内容が正当に存在し得るため、Public側のraw禁止validatorを流用しない。専用schema/validatorでraw fieldの配置、mapping cross-reference、safe report、output rootを検証する（`Internal_Review_Evidence_Packet_Design.md` §7・§10）
- Public/Packetのどちらも、Normalized Story JSON/Extraction Resultとのcross-referenceは各成果物の専用validatorでfail-closedに扱う

---

# 15. 未確定事項（Open questions）

- Choice Block由来のevidenceIdを、Choice単位（`_CHOICE{number}`）とChoice Option単位（`_CHOICE{number}_OPT{number}`）のどちらで扱うか（`Identifier_Specification.md` §5.6・§5.7の両方が存在するため、Phase 2で決定する）
- `referencedBy.candidates`（Extraction Candidate側からの逆引き）の具体的なデータ構造（Stage A candidate IDは再生成で変わりうるため、安定した参照キーの設計が必要、`Merged_Knowledge_Design.md` §10.4と同じ制約）
- Story単位のevidence（`episodeId`を持たない、story全体を指すevidence）をどう表現するか
- ~~Internal Review Evidence Packetの詳細設計~~ → **`internal-review-evidence-packet-design`で完了**（`docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`）
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
- `docs/runbooks/Evidence_Index_Generation_Dry_Run.md`（`scripts/build_evidence_index_candidates.py`によるEvidence Index候補生成dry-run手順）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（dry-run結果レビュー、Public entry type方針、`knowledge/evidence/stories/`への昇格条件・除外条件・filter policy）
- `docs/runbooks/Evidence_Index_Promotion_Check.md`（`scripts/check_evidence_index_promotion.py`によるpromotion check手順）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（`scripts/promote_evidence_index.py`によるpromotion checkをPASSした候補のcopy手順）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（内部trace ID/公開ID分離方針、保存場所`{storyId}.yaml`をどう扱うかの設計）
- `docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`（内部trace ID mapping、raw/context、bundle、validation、review/retention/cleanupの詳細設計）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（複数storyへ広げる際のbatch size・Registry review条件・promotion前後チェックリスト・visual review・failed story/rollback・PR分割方針）
- `TASKS.md`（次PR候補の追跡）
