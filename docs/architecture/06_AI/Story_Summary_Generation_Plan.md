# Story Summary Generation Plan（Story/Episode Summary AI生成パイプライン実装計画）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Story_Summary_Generation_Plan.md`

---

# 1. Background

`Story_Summary_Design.md`（`story-summary-schema-design`〜`story-summary-evidence-index-design`系PR）で、Story Summary/Episode Summaryのデータモデル・保存場所（`knowledge/summaries/stories/{storyId}.yaml`）・status/review workflow・renderer統合・evidenceRefsのEvidence Indexへのリンク化までを実装済みである。しかし、**実際に要約テキストを生成するAI生成パイプライン自体の設計・着手時期は`Story_Summary_Design.md` §12で「将来 `story-summary-generation-planning`」として未着手のまま残されていた**。

一方、`Evidence_Index_Public_ID_Policy.md`・`Public_ID_Registry_Design.md`は、Public Evidence Indexの初回実データ昇格試行（`evidence-index-promotion-first-reviewed-sample`）で「保存先ファイル名・主キーがsourceKey由来の内部`storyId`をそのまま使う設計であり、commitするとGit履歴に永続混入する」という問題を発見し、これを解決するために

- 内部trace ID（`storyId`/`episodeId`/`evidenceId`等）と公開ID（`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`）の分離（案C）
- Public-safe projection（内部IDを公開ID値へ置換・除去する変換）
- Public ID Registry（`knowledge/public_ids/story_public_ids.yaml`、`publicEpisodeId`の永続化場所）

という一連の解決策を段階的に実装し、昇格済み3 story・392 entriesの実運用（`evidence-index-promotion-first-real-batch`）まで到達した。

**`schemas/story_summary.schema.json`は、現状`storyId`必須・保存ファイル名`{storyId}.yaml`という設計になっており、これはEvidence Indexが最初にぶつかった問題と完全に同型である**（§4で詳述）。AI生成パイプラインを設計するにあたり、この問題を素通りしたまま実装計画を立てると、Evidence Indexで一度見送った「sourceKey由来IDのGit履歴永続混入」を今度はSummary側で繰り返すことになる。

本文書は、AI要約生成パイプラインの実装計画を、この公開ID問題への対応方針を含めて確定する。**本PRはdocs-only PRであり、LLM呼び出し本体・prompt実装・provider実装・実要約生成・schema変更の実施はいずれも行わない**（`AI_CONTEXT.md` §4「`agents/extractor/`のLLM呼び出し本体・provider連携実装は、ユーザーの明示的な指示があるまで着手しない」と同じ制約を、新設予定の`agents/summarizer/`にも適用する）。

---

# 2. Scope（本文書の対象範囲）

対象:

- AI要約生成パイプラインの実装フェーズ分割（各フェーズを将来1 PRに対応させる粒度）
- Summary fileの公開ID問題への対応方針（Evidence Indexとの一貫性）
- パイプライン段階設計（PoC→small batch→通常運用）
- prompt設計の方針レベルの整理（実promptは書かない）
- provider抽象の配置方針（`agents/summarizer/` vs `agents/extractor/`）
- 品質ゲート（機械的検証と人間レビューの分担）

対象外（Non-goals、詳細は§10）:

- LLM呼び出し本体・provider実装・prompt実装
- 実データSummary生成
- schema変更の実施（提案の整理まで）
- summary fixtureのmigration
- `agents/`・`scripts/`配下の実装変更

---

# 3. Fixed premises（確定事項、本PRでは変更しない）

ユーザー指示により、以下は本PRの前提として固定する。実装PR側で覆す場合は、その時点で明示的な設計変更として扱う。

| 項目 | 内容 |
|---|---|
| LLM provider方針 | ローカルLLM（Ollama、devcontainerに既設。`docker-compose.yml`の`ollama`サービス、`OLLAMA_HOST`環境変数）をデフォルトとする。外部provider（API系）はopt-in。APIキーはcommit禁止（既存方針`TASKS.md` Rules・`AI_CONTEXT.md` §3.11どおり） |
| 生成単位 | Episode Summaryを先に生成し、Story SummaryはEpisode Summary群から合成する2段構成 |
| 入力 | Normalized Story JSON（parser経由の正規化済みテキスト）。raw `.dec`を直接LLMに渡さない（`AI_CONTEXT.md` §3.1） |
| 出力先 | draftは`workspace/summary_drafts/`（`.gitignore`済み）→人間review→reviewed/approvedのみ`knowledge/summaries/stories/`へ昇格（`Story_Summary_Design.md` §5.4の既存workflowどおり） |
| Summary/Analysis分離 | 要約はAI Analysis/Speculation（考察）と混ぜない（`Story_Summary_Design.md` §2.3・§7方針） |
| language | `ja` |
| evidenceRefs変換 | LLMには内部blockId付きの正規化テキストを与え、引用させた内部IDを後処理で`publicEvidenceId`へ変換してdraftに格納する。変換にはEvidence Index public-safe projectionのmapping CSV（workspace限定）を使う設計とする。Evidence Index未昇格のstoryは`evidenceRefs`無しで生成可 |

---

# 4. Summary fileの公開ID問題（最重要論点）

## 4.1 現状の構造と問題の確認

`schemas/story_summary.schema.json`は以下の構造になっている（§1参照、実装済み）。

- ドキュメント直下の`storyId`が**required**（内部Story ID、sourceKey由来を含みうる、`pattern: ^[A-Z][A-Z0-9_]*$`）
- `publicStoryId`は**optional**（`oneOf: [pattern string, null]`）
- 保存ファイル名は`knowledge/summaries/stories/{storyId}.yaml`（`Story_Summary_Design.md` §5.2、内部`storyId`をファイル名にそのまま使う設計）
- `episodeSummaries[].episodeId`が**required**（内部Episode ID）、`publicEpisodeId`は**optional**
- `evidenceRefs`は`EvidenceRef`パターン（`^[A-Z][A-Z0-9_]*$`）で、現状は内部`evidenceId`（Block ID）を参照する設計（`Story_Summary_Design.md` §9）

これは、Evidence Indexが`evidence-index-promotion-first-reviewed-sample`で発見した問題（`Evidence_Index_Public_ID_Policy.md` §2）と**完全に同型**である。

| | Evidence Index（解決済み） | Story Summary（本PR時点） |
|---|---|---|
| 保存ファイル名 | 当初`{storyId}.yaml`（内部ID由来） | 現状`{storyId}.yaml`（内部ID由来） |
| ドキュメント直下の必須ID | `entries[].storyId`/`episodeId`/`evidenceId`が必須 | `storyId`が必須、`episodeSummaries[].episodeId`が必須 |
| 公開ID | `publicStoryId`/`publicEpisodeId`/`publicEvidenceId`はoptional追加のみ（当初） | `publicStoryId`/`publicEpisodeId`はoptional（現状のまま） |
| 参照先ID | `evidenceRefs`相当が内部IDのまま | `evidenceRefs`が内部`evidenceId`を参照（現状） |
| 発見された問題 | commitするとsourceKey由来`storyId`がファイル名・全entryのフィールドにGit履歴永続混入 | **同じ経路でstoryId/episodeIdがGit履歴に永続混入しうる（未着手のため未発生だが、構造上のリスクは同一）** |

**したがって、AI生成パイプラインの実装計画は、Evidence Indexが到達した解決策（案C: Public-safe projection）と一貫させることを最優先方針とする。** Evidence Indexとは別の解決策を新たに検討する必要はない。むしろ、Evidence Indexとは異なる方針を採ると、両者の`{publicStoryId}.yaml`という命名規則がちぐはぐになり、Wiki生成・promotion運用が複雑化する。

## 4.2 Evidence Indexの解決策の要約（本文書が踏襲するもの）

`Evidence_Index_Public_ID_Policy.md`・`Public_ID_Registry_Design.md`で確定・実装済みの要素:

1. **ID分類**: 内部trace ID（`storyId`/`episodeId`/`sceneId`/`blockId`/`evidenceId`/sourceKey）と公開ID（`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`）を分離する（§3.1・§3.2）
2. **案C（Public-safe projection）**: 公開repoに保存するデータは、`publicStoryId`/`publicEpisodeId`/`publicEvidenceId`を中心にしたprojectionとして保存する。内部trace IDは必要最小限のreview-only metadataに分離するか、Internal Review Evidence Packet（未実装）側に置く
3. **保存先・ファイル名**: `{publicStoryId}.yaml`（1 file = 1 publicStoryId）
4. **Public ID Registry**: `knowledge/public_ids/story_public_ids.yaml`（`schemas/public_id_registry.schema.json`、`additionalProperties: false`で内部ID混入を構造的に防止）を、`publicStoryId`/`publicEpisodeId`の正式な永続化場所として使う。source of truthは引き続き`story_manifest.yaml`側（人間が個別に確定）で、Registryは公開してよい部分だけを転記した副次的な記録という位置づけ
5. **projection段階**: Compatible projection（案A、内部IDを維持したまま公開IDを追加、migration/debugging用）→Public-safe projection（案B、内部IDを公開ID値へ置換・除去、Public promotion対象）という2段階を経る
6. **exposure scan**: 出力の直列化文字列に対し、内部ID値（公開IDと異なり4文字以上のもの）が残っていないかをヒューリスティックscanし、検出時はblocking errorにする
7. **mapping CSV**: 内部ID⇔公開IDのmapping table（`--mapping-output`相当）はworkspace限定・commit禁止（Internal Review Evidence Packet候補データ）
8. **renderer切替**: 見出し・anchor・リンクは`publicEvidenceId`/`publicStoryId`中心にする（`display_evidence_id`/`resolve_evidence_entry`パターン）

## 4.3 Story Summaryへの適用方針（提案、本PRでは実施しない）

上記1〜8を、Story Summaryに以下のように対応させることを提案する。

### 4.3.1 保存先・ファイル名

```text
[現状の設計]     knowledge/summaries/stories/{storyId}.yaml
[提案する将来形]  knowledge/summaries/stories/{publicStoryId}.yaml
```

Evidence Indexと**全く同じ命名規則**を採用する。1 file = 1 publicStoryIdとし、複数の異なる`storyId`が同じ`publicStoryId`に解決される場合や、逆に1つの`storyId`から複数の`publicStoryId`が生じるケースはblocking errorとする（Evidence Indexの`--projection-mode public-safe`のファイル名衝突判定と同じ方針）。

### 4.3.2 IDフィールドのpublic-safe化

| フィールド（現状） | projection後の扱い（提案） |
|---|---|
| `storyId`（required） | 値を`publicStoryId`へ置換する。fieldそのものは互換性のためrequiredのまま維持する案（Evidence Indexの`public-safe`モードと同じ、§6.8踏襲） |
| `publicStoryId`（optional） | 引き続き元の値を保持する（projectionされたことの機械的な確認用） |
| `episodeSummaries[].episodeId`（required） | 値を`publicEpisodeId`へ置換する |
| `episodeSummaries[].publicEpisodeId`（optional） | 引き続き元の値を保持する |
| `evidenceRefs`（内部evidenceId参照） | `publicEvidenceId`参照へ変換する（§4.3.3） |

### 4.3.3 evidenceRefsの変換

`Evidence_Index_Public_ID_Policy.md` §8.3で既に「Summary `evidenceRefs`は最終的に`publicEvidenceId`を参照する方針とする（dual-field化は複雑さが増すため採用しない）」と決定済みである。本文書はこの既存方針をそのまま踏襲し、AI生成パイプラインの後処理ステップとして具体化する（§6.4「hallucination対策」参照）。

- LLM生成時点では、入力に内部blockId付きの正規化テキストを渡すため、LLMが引用するのは内部blockIdになる
- draft保存段階（`workspace/summary_drafts/`）では、内部blockId参照のまま保持してよい（Evidence Indexのworkspace dry-run生成物と同様、workspace限定である間はcommit対象外のため内部ID混在を許容する）
- `knowledge/summaries/stories/{publicStoryId}.yaml`への昇格時（projection）に、Evidence Index public-safe projectionが持つ内部`evidenceId`⇔`publicEvidenceId`のmapping（`project_evidence_index_public_ids.py --mapping-output`相当、workspace限定CSV）を使って、`evidenceRefs`内の内部blockId参照を`publicEvidenceId`参照へ変換する
- Evidence Index側がその内部blockIdをまだ`publicEvidenceId`に変換していない（＝該当storyがEvidence Index未昇格）場合は、`evidenceRefs`を空にして昇格する（§3の確定事項どおり、evidenceRefs無しでの生成・昇格を許容する。既存のEvidence_Index_Design.md §10の「未解決は従来通りID表示のまま、非エラー」という安全側フォールバックとも整合する）
- 変換元のmapping CSV自体は、Evidence Index側の運用と同じくworkspace限定・commit禁止とする

### 4.3.4 Public ID Registryの共有

Story Summary専用の新しいRegistryは作らない。**既存の`knowledge/public_ids/story_public_ids.yaml`（`schemas/public_id_registry.schema.json`）をそのまま共有インフラとして再利用する。** `publicStoryId`/`publicEpisodeId`の値はEvidence IndexとStory Summaryで同一である必要があり（同じstory/episodeを指す公開ID体系は1つに統一する）、別々のRegistryを持つと不整合のリスクが生じる。

### 4.3.5 必要なschema変更の整理（提案のみ、本PRでは実施しない）

Evidence Indexの段階的アプローチ（`publicEvidenceId`のoptional追加→projection実装→required化は先送り）をそのまま踏襲する。

1. **現状**: `publicStoryId`/`publicEpisodeId`は既にoptionalとして実装済み（`story-summary-schema-implementation`で対応済み、追加のschema変更は不要）
2. **Compatible projection相当**: 既存schemaのまま、`storyId`/`episodeId`は維持しつつ`publicStoryId`/`publicEpisodeId`を確実に埋める運用（schema変更なし、実装のみで対応可能）
3. **Public-safe projection相当**: `storyId`/`episodeId`の**値**を公開ID値へ置換する運用（Evidence Indexと同様、fieldの必須性自体は変更しない設計を軸に検討する。schema上の破壊的変更を避けるため）
4. **evidenceRefsのpattern**: `EvidenceRef`定義（`^[A-Z][A-Z0-9_]*$`）は`publicEvidenceId`の形式（`{publicEpisodeId}_{PREFIX}{sequence:04d}`）とも互換であるため、**pattern自体の変更は不要と見込まれる**（実装PR側で最終確認する）
5. **required化のタイミング**: `publicStoryId`/`publicEpisodeId`のrequired化は、Evidence Indexと同様「Public promotion-readyな運用上の期待値」に留め、schema上のrequired制約への格上げは、Public版schemaを分離するタイミング（Evidence Index `Evidence_Index_Public_ID_Policy.md` §10.2と同じ判断軸）まで見送ることを提案する

**本PRでは上記のいずれのschema変更も実施しない**（§10 Non-goals）。実装が必要になった時点で、対応する実装フェーズ（§9）のPRで判断する。

## 4.4 Evidence Indexフェーズとの対応表

将来の実装フェーズを、Evidence Indexが辿った実装フェーズ（`Evidence_Index_Public_ID_Policy.md` §12）と対応させて整理する。

| Evidence Index側フェーズ | 対応するStory Summary側フェーズ（本文書§9で詳細） |
|---|---|
| Phase 1: `publicEvidenceId`のschema設計・optional追加 | 既に`publicStoryId`/`publicEpisodeId`はoptionalとして実装済み（追加作業不要） |
| Phase 2: Compatible projection実装 | `summary-generation-public-safe-projection`のCompatible相当部分 |
| Phase 2.5: Public-safe projection実装 | 同上、Public-safe相当部分 |
| Phase 2.6: `publicEpisodeId`未確定検出・Registry設計 | 新設不要。既存の`scripts/check_public_episode_ids.py`・Registryをそのまま再利用する |
| Phase 2.7: Registry統合 | Summary側projectionでも同じRegistry読み込みロジックを共有importする方針 |
| Phase 3: renderer切替 | Story page Summary section表示の`publicStoryId`/`publicEpisodeId`優先切替（既存の`resolve_story_summary`は`storyId`優先→`publicStoryId`fallbackの照合ロジックを既に持つため、影響は限定的） |
| Phase 4: promotion script対応 | Summary昇格スクリプト（新設、`promote_evidence_index.py`に類似した安全策）のtarget filename `publicStoryId`必須化 |
| Phase 5: 初回実データ昇格 | 実データ1 storyでのAI要約生成→レビュー→projection→昇格の試行 |

---

# 5. Pipeline stage design（PoC→small batch→通常運用）

Evidence Indexのbatch promotion運用（`Evidence_Index_Batch_Promotion_Policy.md`）と同じ「段階的に規模を広げる」アプローチを採用する。

| Stage | 内容 | 対象規模 | 前提条件 |
|---|---|---|---|
| **Stage 0: PoC** | 昇格済み3 storyのうち1 story（Evidence Index昇格済み＝evidenceRefs変換可能なもの）を選び、ローカルLLM（Ollama）でEpisode Summary→Story Summary生成を試行する。人間reviewを経て、`workspace/summary_drafts/`での生成確認、または最小限の初回commit（1 story）まで | 1 story | 本文書の実装フェーズ（§9）がPoCに必要な最小実装まで完了していること。ユーザーの明示的なLLM呼び出し着手指示（`AI_CONTEXT.md` §4） |
| **Stage 1: small batch** | 複数story（Evidence Index batch promotion policyと同じ最大3〜5 story目安）で生成→review→projection→限定commitを行う | 最大3〜5 story | Stage 0での問題（hallucination傾向、prompt調整要否、public ID projectionの実運用確認）が解消済み |
| **Stage 2: 通常運用** | 昇格済みstory全体を対象にした継続的な生成運用。CI組み込み・自動化の要否は別途検討（`evidence-index-promotion-batch-tooling`と同様、機械的checkの拡充は別PR） | 段階的拡大 | Stage 1で品質・運用フローが安定していることを人間が確認済み |

Evidence Indexの`Evidence_Index_Batch_Promotion_Policy.md` §9（Failed story handling）・§10（Rollback policy）と同様の考え方を、Story Summary側でも将来採用することを想定する（詳細設計は各Stageの実装PRに委ねる、本PRでは確定しない）。

---

# 6. Prompt design policy level（方針レベルの整理。実promptは書かない）

**本PRでは実際のprompt文面は一切書かない。** 以下は将来のprompt実装PRが従うべき方針の整理である。

## 6.1 入力構造

- Episode単位のNormalized Story JSONから、`dialogue`/`monologue`/`narration`/`choice`（Evidence Indexの`--policy public-default`と同じ対象type、`stage_direction`は既定で対象外）のBlockを抽出し、各Blockに内部`blockId`を付与したテキスト表現をLLMへ渡す
- Raw `.dec`由来の演出コマンド・変数・rawテキストはLLMに渡さない（`AI_CONTEXT.md` §3.1どおり、既に正規化済みのテキストのみを渡す）
- 1 episode分のテキストが長すぎる場合の分割方針は§6.5参照

## 6.2 出力構造

- summary本文（プレーンテキスト、`Story_Summary_Design.md` §7.1「Summaryに含める」範囲に限定）
- 引用したblockId list（後処理でのevidenceRefs変換・実在性検証に使う、§6.3・§6.4）
- 出力formatはJSON（`{"text": "...", "evidenceRefs": ["...", "..."]}`相当）を想定するが、具体的なJSON schemaやfunction calling方式の選定は実装PR側で決定する（本PRでは確定しない）

## 6.3 hallucination対策

- **引用強制**: LLMに対し、要約本文の各文（または段落）につき最低1つの`blockId`引用を求めるプロンプト設計を検討する（強制の厳密さは実装PR側で調整）
- **実在blockId検証**: 後処理で、LLMが引用した`blockId`がそのepisodeのNormalized Story JSON中に実在するかを機械的に検証する。実在しないIDが含まれる場合は、そのentryを`draft`のまま留め、`generationStatus: generated`への昇格や人間レビュー待ちのフラグを立てる（自動的にrejectはしない。人間が内容自体は妥当だがID紐付けミスと判断するケースを考慮）
- **禁止文字列scan**: 既存の`FORBIDDEN_TEXT_PATTERNS`相当（`validate_story_summaries.py`・`check_evidence_index_promotion.py`が使うraw text/rawコマンド禁止パターン）を、生成directのdraftにも適用する
- **長文verbatim引用の検出**: 生成text中に、参照元Blockの本文と一定文字数（閾値は実装PR側で確定、目安として`Story_Summary_Design.md` §7.3の「短い一文引用程度」を超える連続一致）以上一致する部分列がないかをチェックする。検出時は「rawテキストの大量引用」として`draft`のまま留める

## 6.4 長文episodeの分割方針

- episode本文がLLMのcontext長を超える場合、Scene単位またはBlock群単位でchunk分割し、chunkごとに部分要約→部分要約群を再統合してEpisode Summaryにする2段階要約を想定する
- 分割・再統合ロジックの具体的な実装（chunk境界の決め方、再統合prompt）は実装PR側で設計する。本PRでは「分割が必要になりうる」という方針と、分割してもBlockId引用の実在性検証は変わらず機能するという設計要件のみを明記する

---

# 7. Provider抽象の配置

## 7.1 現状確認

- `agents/summarizer/`は**現時点で存在しない**（`agents/`配下は`analysis`/`consistency_checker`/`extractor`/`graph_builder`/`merger`/`orchestrator`/`parser`/`wiki_generator`のみ。`analysis`/`consistency_checker`/`graph_builder`/`orchestrator`は`__init__.py`のみの空placeholder）
- `agents/extractor/`には、LLM呼び出し本体はまだ実装されていない。`agents/extractor/models.py`の`ExtractionProvenance`相当のdataclassに`model_provider`/`model_name`/`prompt_version`という**文字列フィールドのみ**が存在し、既定値は`extraction_method: "rule_based"`（LLM呼び出し前提のフィールドを持つが、実際のprovider抽象クラス・API呼び出しロジックは未実装）
- devcontainer側にはOllamaサービスが既設（`docker-compose.yml`の`ollama`サービス・`OLLAMA_HOST`環境変数）。ローカルLLM運用の基盤自体は用意済み

## 7.2 配置方針（確定）

- **`agents/summarizer/`を新設する**（`summary-generation-skeleton`で新設済み）。Story/Episode Summary生成は、Extraction（Stage A candidate抽出）とは責務が異なる独立したパイプラインであるため、`agents/extractor/`に混在させない
- **provider抽象の配置は`summary-generation-provider-implementation`で確定した**: ユーザーが2026-07-13にsummarizer系のLLM provider実装を明示的に解禁したことを受け、`agents/common/`のような共有レイヤーは新設せず、**`agents/summarizer/provider.py`にsummarizer固有として実装した**（`SummaryLLMProvider`/`OllamaProvider`/`LLMCompletion`/`LLMProviderError`）。`agents/extractor/`のLLM呼び出しは引き続き未解禁のままであり（`AI_CONTEXT.md` §4）、共有レイヤーへの昇格が必要かどうかは、実際に`agents/extractor/`側のLLM呼び出しが解禁されるPRで再判断する（§11 Open questionsを解消）
- 共有レイヤーへ昇格する場合の候補配置は引き続き`agents/common/llm_provider.py`のような両者から参照可能な共通モジュールを想定するが、現時点では新設しない
- いずれの場合も、外部provider（API系）はopt-in、ローカルLLM（Ollama）がデフォルトという方針（`TASKS.md` Rules）は共通で適用する。`summary-generation-provider-implementation`で実装した`OllamaProvider`はAPIキー・認証を扱わないローカルOllama専用実装であり、外部provider実装は引き続き将来PRのスコープ

---

# 8. Quality gate（品質ゲート）

生成draftの機械的検証と人間レビューの分担を整理する。

## 8.1 機械的検証（自動化対象）

| 検証項目 | 内容 | 既存の類似実装 |
|---|---|---|
| schema検証 | `schemas/story_summary.schema.json`によるstructural validation | `scripts/validate_story_summaries.py` |
| evidenceRefs実在性 | 引用blockIdがNormalized Story JSON中に実在するか（§6.3） | `Story_Summary_Design.md` §11で既知課題として明記済みの「evidenceRefs実在確認は初期実装では必須にしない」を、AI生成時点では強化する方針 |
| 禁止文字列scan | raw text/rawコマンド禁止パターン | `validate_story_summaries.py`の既存raw/source text禁止文字列検出、`FORBIDDEN_TEXT_PATTERNS`相当 |
| 長文verbatim引用検出 | 参照元本文との連続一致検出（§6.3） | 新規実装が必要（既存scriptには無い） |
| public ID projection検証 | `publicStoryId`/`publicEpisodeId`欠落・exposure scan（§4.3） | Evidence Indexの`project_evidence_index_public_ids.py`のsourceKey由来ID exposure scanと同じヒューリスティック |

## 8.2 人間レビュー（人手対応）

- 内容の正確性（明示された事実のみか、AI考察が混入していないか、`Story_Summary_Design.md` §7.2該当項目が混入していないか）
- 文体・簡潔さ
- `review.status`の判定（`reviewed`/`approved`/`rejected`/`needs_revision`）
- Public ID projection後の内容確認（機械的scanをすり抜けた内部ID断片が無いかの最終目視、Evidence Indexのvisual review方針と同じ）

## 8.3 分担の原則

機械的検証で1つでもblocking issueが検出された場合、そのdraftは`knowledge/summaries/stories/`へ昇格しない（Evidence Indexの`check_evidence_index_promotion.py`のgatekeeperパターンと同じ「check-onlyで昇格を止める」設計を踏襲する）。人間レビューは機械的検証をすべて通過したdraftのみを対象にする（無駄な人手レビューを減らす）。

---

# 9. Implementation phases（実装フェーズ分割案）

各フェーズは将来1 PRに対応する粒度を想定する。フェーズ名は次PR候補名の草案であり、着手順序・粒度は実装PR着手時に見直してよい。

| フェーズ（候補PR名） | 内容 | Non-goals（そのPRで行わないこと） |
|---|---|---|
| `story-summary-generation-planning`（本PR） | 本文書の作成。公開ID問題への対応方針・パイプライン段階設計・prompt設計方針・provider抽象配置・品質ゲート整理・実装フェーズ分割 | LLM呼び出し・prompt・provider実装、schema変更の実施、実要約生成、fixture migration |
| `summary-generation-skeleton` | `agents/summarizer/`パッケージの新設（`__init__.py`のみ、または最小限のdataclass定義）。実際のLLM呼び出しは含めない。§7の配置方針に基づく最小限の骨格のみ | LLM呼び出し本体・provider実装 |
| `summary-public-id-projection-design` | §4.3の提案を実装レベルで詳細化する設計PR（schema変更案の確定、projection scriptの入出力仕様確定）。Evidence Indexの`evidence-index-public-id-schema-design`相当。**完了**（`docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`として確定。projection scriptを独立scriptとして`scripts/project_story_summary_public_ids.py`に新設する方針、CLI引数・exit code・blocking条件・field変換表・evidenceRefs変換仕様・Registry共有設計（`check_public_episode_ids.py`の`_resolve_registry_lookup`/`_group_entries_by_internal_story`を再利用）を確定した） | schema実装、projection実装 |
| `summary-public-id-schema-implementation` | `schemas/story_summary.schema.json`への必要最小限の変更実装（optionalフィールドの追加等、破壊的変更なし）。**`summary-public-id-projection-design`の結論によりスキップ可能**（`Summary_Public_ID_Projection_Design.md` §8で、既存schemaの構造（required/optional/pattern）を一切変更せずcompatible/public-safe両projection modeを実現できることを確認した） | projection実装、renderer変更 |
| `summary-generation-public-safe-projection` | Evidence Indexの`project_evidence_index_public_ids.py`に相当する、Summary用public-safe projection scriptの実装（Compatible→Public-safeの2段階） | LLM呼び出し実装、実データprojection実行 |
| `summary-generation-provider-implementation` | **完了**（ユーザーが2026-07-13にsummarizer系のLLM provider実装を明示的に解禁したことを受けて実装。`AI_CONTEXT.md` §4）。Ollama provider呼び出し本体（`agents/summarizer/provider.py`、`POST {host}/api/generate`・`stream: false`固定、`urllib.request`のみ使用・新規ランタイム依存無し、HTTP transportはconstructor injection可能）を実装した | prompt実装・要約生成ロジック（次フェーズ）、外部provider実装（opt-in部分は別フェーズ）、実Ollama呼び出し・実データSummary生成 |
| `summary-generation-prompt-implementation`（ユーザー明示指示後） | Episode Summary生成prompt・hallucination対策の後処理実装 | Story Summary合成ロジック（次フェーズ） |
| `summary-generation-story-synthesis`（ユーザー明示指示後） | Episode Summary群からStory Summaryを合成するロジック実装 | - |
| `summary-generation-quality-gate` | §8の機械的検証（evidenceRefs実在性・禁止文字列scan・verbatim引用検出）を実装するCLI（`check_evidence_index_promotion.py`類似のgatekeeper） | 自動promotion実行 |
| `summary-generation-poc`（ユーザー明示指示後） | §5 Stage 0の実施。昇格済み1 storyでの実際のローカルLLM生成→人間review→初回commit試行 | 複数storyへの拡大 |

**次PR候補（直近）**: 本PR完了後、優先度の高い候補は`summary-generation-skeleton`（実装を伴わない骨格新設、低リスク）または`summary-public-id-projection-design`（公開ID問題の実装詳細確定、Evidence Indexとの一貫性を早期に固める）のいずれか。どちらを先にするかはユーザー判断を仰ぐ。

---

# 10. Non-goals（本PR固有の再掲）

- LLM呼び出し・prompt・provider実装
- schema変更の実施（提案の整理まで）
- 実要約生成
- summary fixtureのmigration
- `agents/`・`scripts/`配下の変更
- `agents/summarizer/`パッケージの新設自体（次PR候補、§9）
- Evidence Index側（`agents/wiki_generator/evidence_index.py`・`scripts/project_evidence_index_public_ids.py`等）の変更
- `knowledge/public_ids/story_public_ids.yaml`への実データ追加
- AI Analysis / Speculation schemaの実装

---

# 11. Open questions（未確定事項）

- ~~provider抽象を`agents/summarizer/`固有にするか、`agents/extractor/`と共有する共通レイヤーにするか（§7.2）~~ → **`summary-generation-provider-implementation`で確定**: `agents/summarizer/provider.py`にsummarizer固有として実装し、`agents/common/`共有レイヤーは新設しないことを確定した。`agents/extractor/`側のLLM呼び出しが解禁されるタイミングで、共通レイヤーへの昇格要否を再判断する（§7.2参照）
- ~~Summary用public-safe projectionを、Evidence Indexと同じ`project_evidence_index_public_ids.py`を拡張して対応するか、独立した新規scriptにするか~~ → **`summary-public-id-projection-design`で確定**: `scripts/project_story_summary_public_ids.py`という独立scriptとして新設する方針を確定した（Evidence Indexの文書構造との違いを踏まえた判断、`Summary_Public_ID_Projection_Design.md` §4参照）
- ~~`evidenceRefs`のEvidence Index mapping CSVへの依存を、Summary側のprojection scriptがどう読み込むか~~ → **`summary-public-id-projection-design`で確定**: Evidence Index public-safe projectionの`--mapping-output`CSVをそのまま`--evidence-mapping`として入力し、Summary側で独自のmapping生成は行わない方針を確定した（`Summary_Public_ID_Projection_Design.md` §6参照）
- 長文verbatim引用検出の具体的な閾値・アルゴリズム（§6.3）
- Episode Summary複数版（改訂履歴）を持たせるかどうか（`Story_Summary_Design.md` §14で既に未確定のまま持ち越されている論点、AI生成が始まると再生成のたびに複数版が必要になる可能性があるため、本PRでも未確定のまま据え置く）
- Story Summary合成（Episode Summary群→Story Summary）の具体的なロジック（単純な要約結合か、再度LLMに要約させるか）
- CI組み込み（`validate_story_summaries.py --require-reviewed`のCI化）の要否・タイミング（`Story_Summary_Design.md` §14で既存の未確定事項）

---

# 12. 参照

- `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`（本文書§4.3の提案を実装レベルまで詳細化した設計PR。projection scriptのCLI仕様・field変換表・evidenceRefs変換仕様・Registry共有設計・schema変更不要の結論を確定）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Summaryのデータモデル・保存場所・status/review workflow・renderer統合の既存設計、本文書はその「AI要約生成パイプライン」部分を具体化する）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（本文書§4が踏襲する内部ID/公開ID分離方針・publicEvidenceId方針・Public-safe projection方針）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（本文書§4.3.4が共有する既存Public ID Registry設計）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・データモデル、evidenceRefsのリンク先）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria、Public promotion対象entry typeの考え方）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（本文書§5が踏襲するbatch size段階・Registry review条件・failed story/rollback方針）
- `docs/architecture/06_AI/Extraction_Result_Schema.md`（`ExtractionProvenance`の`model_provider`等フィールド、§7.1で確認した既存LLM関連フィールドの現状）
- `agents/extractor/models.py`（`model_provider`/`model_name`/`prompt_version`フィールドの現状実装）
- `schemas/story_summary.schema.json`（本文書§4で問題を確認した現行schema）
- `schemas/evidence_index.schema.json` / `schemas/public_id_registry.schema.json`（本文書が参照するEvidence Index側の既存schema）
- `scripts/project_evidence_index_public_ids.py` / `scripts/check_public_episode_ids.py`（本文書が踏襲するprojection/registry実装パターン）
- `AI_CONTEXT.md` §4（LLM呼び出し本体着手の制約方針）
- `TASKS.md`（次PR候補の追跡）
