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
| Phase 4: promotion script対応 | **完了**（`summary-promotion-copy-script`）。`scripts/promote_story_summaries.py`（新設、`promote_evidence_index.py`と同じ安全パターン）を実装した。target filename `{publicStoryId}.yaml`必須化に加え、前提条件5項目（1. public-safe projection済み: `storyId==publicStoryId`・全`episodeSummaries[].episodeId==publicEpisodeId`・ファイル名一致、2. schema検証+`review.status`（approved/reviewed）+`generationStatus`（generated）、3. 禁止文字列scan、4. `--registry`指定時のPublic ID Registry実在確認、5. `--evidence-index`指定時のevidenceRefs解決確認）をすべて1ファイル単位で検証し、1つでも満たさなければそのファイルをcopyしない設計とした。Evidence Index側と異なり別ファイルのreview noteは要求せず（Story Summaryのin-file `review`セクション自体が人間レビュー記録であるため）、`--overwrite`もSummaryの再生成・改訂という正当なユースケースを想定した設計とした（詳細は同scriptのdocstring参照） |
| Phase 5: 初回実データ昇格 | 実データ1 storyでのAI要約生成→レビュー→projection→昇格の試行 |

---

# 5. Pipeline stage design（PoC→small batch→通常運用）

Evidence Indexのbatch promotion運用（`Evidence_Index_Batch_Promotion_Policy.md`）と同じ「段階的に規模を広げる」アプローチを採用する。

| Stage | 内容 | 対象規模 | 前提条件 |
|---|---|---|---|
| **Stage 0: PoC** | 昇格済み3 storyのうち1 story（Evidence Index昇格済み＝evidenceRefs変換可能なもの）を選び、ローカルLLM（Ollama）でEpisode Summary→Story Summary生成を試行する。人間reviewを経て、`workspace/summary_drafts/`での生成確認、または最小限の初回commit（1 story）まで | 1 story | 本文書の実装フェーズ（§9）がPoCに必要な最小実装まで完了していること。ユーザーの明示的なLLM呼び出し着手指示（`AI_CONTEXT.md` §4） |
| **Stage 1: small batch** | 複数story（Evidence Index batch promotion policyと同じ最大3〜5 story目安）で生成→review→projection→限定commitを行う。**初回small batch（2 story）実施済み**（`summary-generation-small-batch-001`、`promote_story_summaries.py --execute`の初回実運用。人間レビューで情報源の取り違え・未解決話者プレースホルダー混入を検出し人手修正した） | 最大3〜5 story | Stage 0での問題（hallucination傾向、prompt調整要否、public ID projectionの実運用確認）が解消済み |
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

## 6.5 Domain context注入（`summary-domain-context-injection`で確定）

**背景**: `summary-generation-quality-v2`のRAID small batch人間レビューを経てもなお、2026-07-19のユーザーレビューで3世代のdraftに共通する系統的な帰属誤りが確認された。「半裸になったのは班長」のように話者が明示されないモノローグ（このゲームの主人公＝プレイヤー本人を指す「班長」の内心描写）を、LLMがその都度異なる近くの名前付きキャラクターへ誤帰属する、というパターンである。原因は、ゲーム固有の前提（主人公＝プレイヤー＝「班長」という呼称）をLLMが知らないことにあり、`episode-summary-v3`の「登場人物」リスト注入（解決済みspeaker displayNameのみ）だけでは対策できない種類の誤りだった。

**設計方針（確定）**:

- ユーザーが事実として確認済みの前提知識を、`knowledge/dictionaries/summary_domain_context.yaml`（**commit対象**）としてYAML管理する。ファイルヘッダに「人間確認済みの事実のみを記載する」運用ルールを明記し、AIが単独で新しい事実を追加することを禁止する（`docs/runbooks/Story_Summary_Generation_Runbook.md`の編集手順参照）
- `agents/summarizer/domain_context.py`の`load_domain_context`がこのYAMLを読み込み、`entries[].text`のlistを返す。ファイルが存在しない、または`entries`が空の場合は空listを返し、呼び出し側はこれを「注入なし・従来動作」として扱う（**後方互換**）
- `agents/summarizer/prompt.py`の`build_episode_summary_system_prompt`/`build_story_summary_system_prompt`/`build_story_summary_system_prompt_v2`/`build_refine_system_prompt`が、domain contextのlistを各system prompt固定値の末尾へ追記する（`build_domain_context_block`）。episode要約・story合成（v1/v2いずれも）・自己推敲パスの全system promptが対象
- `PROMPT_VERSION`（`episode-summary-v4`）・`STORY_SUMMARY_PROMPT_VERSION`（`story-summary-v3`）・`REFINE_PROMPT_VERSION_SUFFIX`（`refine-v2`）は、domain context注入に対応したprompt実装のversionを表す（ファイルの有無に関わらず同じ値）。実際にdomain contextが注入されたかどうかは、`agents/summarizer/generator.py`の`_build_provenance`が非空のdomain_context受領時のみ追記する`DOMAIN_CONTEXT_PROMPT_VERSION_SUFFIX`（`domain-context-v1`）の有無でprovenanceから判別できる
- 初期entryは2件のみ: (a) 主人公＝プレイヤー＝「班長」という呼称の説明、(b) 話者不明モノローグは班長のものである可能性が高いという帰属ヒント。いずれも2026-07-19にユーザー本人が確認済みの事実であり、AI推測の設定・実データ由来の固有名詞は含まない
- 汎用的な用語間関係（glossary）の注入自体（`TASKS.md` Backlog `summary-generation-glossary-injection`）は、本項目の初の具体化として実装されたのみで、今後運用でentryを追加していく方針とする

**quality gateの盲点修正（同PRで併せて対処）**: `summary-generation-poc-first-commit`のRAID batchレビューで、summary本文中に括弧書きのblockId引用がそのまま残るケースを`check_story_summary_drafts.py`が検出できていないことが判明した（§8.1「本文中evidence/block ID引用検出」項目を参照）。`agents/summarizer/generator.py`側でも、LLM出力から括弧書きのblockId引用を機械的に除去する後処理（`strip_evidence_id_citations`）を追加し、quality gateの検出を「最終防衛線」とする二重防御構成にした。

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
| 本文中evidence/block ID引用検出（`summary-domain-context-injection`で追加） | `storySummary.text`/`episodeSummaries[].text`本文中への括弧書きblockId引用の検出（§6.5参照、前回batchレビューで判明したquality gateの盲点） | 新規実装（`scripts/check_story_summary_drafts.py`、既存の禁止文字列scanとは独立したパターン） |

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
| `summary-generation-prompt-implementation`（ユーザー明示指示後） | **完了**（ユーザーが2026-07-13にsummarizer系のprompt実装を明示的に解禁したことを受けて実装。`AI_CONTEXT.md` §4）。Episode Summary生成prompt（`agents/summarizer/prompt.py`、`PROMPT_VERSION = "episode-summary-v1"`、`dialogue`/`monologue`/`narration`/`choice`Blockのみ再帰抽出・blockId付きテキスト表現埋め込み・JSON出力形式指示）と入力構築・LLM呼び出し・hallucination対策の後処理・draft組み立て（`agents/summarizer/generator.py`、実在blockId検証・禁止文字列scan（`FORBIDDEN_TEXT_PATTERNS`再利用）・長文verbatim引用検出（既定閾値30文字、`--verbatim-threshold`で変更可）はいずれも非blockingでdraftは`generationStatus: draft`のまま生成、LLM呼び出し失敗・応答parse失敗・必須キー欠落・入力Block無し・入力長超過のみ生成をskip）を実装した。workspace限定のdraft生成CLI（`scripts/generate_story_summaries.py`、`--output`/`--report`は`knowledge/`配下を拒否）も新設した | Story Summary合成ロジック（次フェーズ）、実Ollama呼び出し・実データSummary生成・実データでのCLI実行、chunk分割2段階要約の実装（§6.4参照） |
| `summary-generation-story-synthesis`（ユーザー明示指示後） | **完了**（ユーザーが2026-07-13にsummarizer系のLLM実装を明示的に解禁したことを受けて実装。`AI_CONTEXT.md` §4）。Episode Summary群からStory Summaryを合成するロジック（`agents/summarizer/generator.py`の`synthesize_story_summary`、prompt構築は`agents/summarizer/prompt.py`の`build_story_summary_prompt`・`STORY_SUMMARY_PROMPT_VERSION = "story-summary-v1"`）を実装した。合成方式はLLM再要約（§11で確定）: 生成済みEpisode Summary群のtext（episodeNumber順、`[Episode {episodeNumber}] {text}`形式）を入力に`{"text": "..."}`のみをLLMへ生成させ（story-level textにblockId引用は求めない）、story-level evidenceRefsはepisode-level evidenceRefsの重複排除union（episodeNumber順→episode内出現順の安定ソート）を後処理で機械的に設定する。後処理はJSON parse失敗・`text`キー欠落・空text（いずれもblocking、合成skip）・禁止文字列scan（`FORBIDDEN_TEXT_PATTERNS`再利用、非blocking）のみで、**verbatim引用検出はstory合成では行わない**（入力が既にsafeなepisode summaryであり生のセリフ本文ではないため）。入力Episode Summary群の合計文字数が上限（episode側と同じ`DEFAULT_MAX_INPUT_CHARACTERS`）を超える場合はissueを立てて合成をskipする（episode側と同じ安全弁パターン）。issueを持つepisodeが1つでもある場合でも合成自体は行い、非blocking issue `source-episode-has-issues`として記録する（人間レビューで判断）。`scripts/generate_story_summaries.py`は「episode群生成→story合成→draft YAML書き出し」フローへ拡張し、story合成は既定で有効・`--no-story-synthesis`でopt-out（既存CLI引数・`knowledge/`配下拒否の出力先安全策は不変）。reportにstory合成結果・issuesを追記する | quality gate CLI（次PR `summary-generation-quality-gate`のスコープ）、実Ollama呼び出し・実データSummary生成・実データでのCLI実行、chunk分割2段階要約の実装、projection script・Evidence Index側の変更 |
| `summary-generation-quality-gate` | **完了**。§8.1の機械的検証4項目（schema検証・evidenceRefs実在性・禁止文字列scan・長文verbatim引用検出。「public ID projection検証」は`scripts/project_story_summary_public_ids.py`の既存責務のため対象外）を実装するcheck-onlyのgatekeeper CLI `scripts/check_story_summary_drafts.py`（`check_evidence_index_promotion.py`と同じパターン、LLM呼び出しなし）を新設した。schema検証は`schemas/story_summary.schema.json`へのDraft7Validator適用（`agents.wiki_generator.story_summaries.parse_story_summary_document`をimport再利用）。evidenceRefs実在性は`--normalized`（Normalized Story JSON file/directory）指定時のみ、`agents.summarizer.extract_episode_blocks`で抽出したstory/episode単位のblockId集合に対してstorySummary/episodeSummariesのevidenceRefsを照合し、実在しないIDはblocking、対応するstory/episodeが`--normalized`に見つからない場合はwarning（非blocking）、`--normalized`未指定時は検証全体をskipしreportに明記（非blocking）とした。禁止文字列scanは`agents.wiki_generator.story_summaries.FORBIDDEN_TEXT_PATTERNS`を再利用し、`storySummary.text`/`episodeSummaries[].text`/`notes`/`review.notes`を対象に検出時blockingとした。長文verbatim引用検出は`--normalized`指定時のみ、`episodeSummaries[].text`と対応episodeのBlock本文との連続一致を検出する。検出ロジックは`agents/summarizer/generator.py`の非公開関数`_check_verbatim_quotes`を公開関数`check_verbatim_quotes`へ最小限リファクタして再利用した（挙動・既定閾値30文字は変更していない、既存テストも維持）。**`storySummary.text`（story-level）はverbatim検出の対象外とした**（`synthesize_story_summary`がstory合成でverbatim検出を行わない設計（入力が既にsafeなepisode summaryのため）と同じ判断をquality gate側にも適用し、docstring・reportの両方に明記した）。機械的検証で1つでもblocking issueがあれば昇格不可（exit code 1）とするgatekeeperパターン（Plan §8.3）をそのまま実装し、人間レビュー項目（内容正確性・文体・`review.status`判定）は対象外であることをscript docstring・report双方（`## Out of Scope`節）に明記した。`--input`はworkspace配下限定にせず`knowledge/summaries/stories/`配下の既存fileの再検証にも使える。`--report`は`knowledge/`配下を拒否（exit code 2）。exit code: 0=全PASS、1=blocking issueあり、2=config error（入力パス不在・`--report`がknowledge/配下等）。`tests/scripts/test_check_story_summary_drafts.py`（23件、全PASS/schema violation/evidenceRefs実在・不在・episode未検出warning・`--normalized`未指定skip/禁止文字列4フィールド分/verbatim閾値境界・story-level除外確認/`--normalized`未指定時のverbatim skip/file・directory入力/`--report`のknowledge/配下拒否/report内容各節・Final Decision/check-only（入力ファイルbyte不変）を合成fixtureのみで検証した。`Story_Summary_Generation_Plan.md`（本行）・`TASKS.md`を更新した。**自動promotion・copy scriptの実装、LLM呼び出し、実データdraftの生成・検証実行、projection script・Evidence Index側scripts・`validate_story_summaries.py`のCLI挙動変更、PoC実施はいずれも行っていない**（次候補`summary-generation-poc`、ユーザー明示指示待ち・ローカルOllama必要） | 自動promotion実行、LLM呼び出し、実データdraft生成・検証実行、projection script/Evidence Index側scripts/`validate_story_summaries.py`のCLI挙動変更、PoC実施 |
| `summary-generation-poc`（ユーザー明示指示後） | **完了。** §5 Stage 0を実施した。昇格済み1 story（Evidence Index昇格済み、2 episodes）でローカルLLM生成→quality gate全PASS→人間review（内容誤り2点を人手修正）→Public-safe projection（evidenceRefs全変換・exposure 0）→`knowledge/summaries/stories/{publicStoryId}.yaml`の初回commitまで到達した。PoCで発見された実装バグ2件はPR #115/#116で修正済み | 複数storyへの拡大 |
| `summary-generation-quality-v2`（ユーザー明示指示後、2026-07-18承認） | **完了。** RAID small batch（`workspace/summary_drafts/raid_batch_001/`、4件）の人間レビューで確認された品質問題2点（①story summaryの情報欠落=Episode Summary群の再要約という二段圧縮方式が原因、②主語の曖昧さ・指示語の多用）を解消する生成品質改善を実装した。**story-summary-v2**: Story Summary合成の入力を、Episode Summary群の再要約(v1)から全episode本文の直接入力(v2、`build_story_summary_prompt_v2`/`render_story_full_text`)へ変更した。story-level evidenceRefsは引き続き機械的union方式のまま。入力の概算トークン数（`estimate_token_count`、実tokenizerは使わない単純な文字数概算）が`DEFAULT_MAX_CONTEXT_TOKENS`（CLI `--story-synthesis-max-context-tokens`で変更可）を超える場合はv1方式へ自動フォールバックする（失敗にしない、非blocking issue `story-synthesis-context-fallback`をreportへ記録）。**episode-summary-v3**: episode要約promptへ、(a) 各文の主語（人物名）明示・曖昧な指示語回避の指示、(b) 解決済みspeaker displayNameから機械抽出した「登場人物」一覧の注入（`extract_speaker_names`、未解決話者は含めない）、(c) 本文中にblockIdや括弧書きの参照を書かない指示、の3点を追加した。**自己推敲パス**: CLIフラグ`--refine`（既定OFF）指定時、生成済みの各summary（episode/story両方）に対し同モデルで推敲パスを1周実行する（`_refine_episode_draft`/`_refine_story_text`、失敗時は元のtextを維持し非blocking issueのみ記録）。使用時はprovenanceの`promptVersion`へ`refine-v1`を追記する。実際に使われたprompt方式はいずれも`source.promptVersion`から判別できる（`episode-summary-v3`固定、story側は`story-summary-v2`または`story-summary-v1-fallback`、refine使用時は`,refine-v1`を追記）。既存の`--no-story-synthesis`・quality gate・schema・draft出力形式（`promptVersion`文字列と生成方式以外）は変更していない。テストは合成fixture+mock providerのみ（v2の入力整形・contextガードのフォールバック分岐、v3のprompt構築、refineフラグのplumbingを検証）。**4 draftの再生成・commit、glossary（用語関係）注入の実装、外部API provider実装、モデル変更はいずれも行っていない**（glossary注入は`TASKS.md` Backlogの`summary-generation-glossary-injection`のまま） | 4 draftの再生成・commit、glossary注入、外部API provider実装、モデル変更 |

**次PR候補（直近）**: `summary-generation-quality-gate`完了により、§9の実装フェーズはすべて完了した。残る次候補は`summary-generation-poc`（§5 Stage 0の実施、**着手にはユーザーの明示的許可が必要**、実行にはローカルOllamaが必要）のみである。

**追記（`summary-generation-poc-first-commit`、2026-07-18）**: `summary-generation-poc`で確立した生成〜昇格の全手順（`docs/runbooks/Story_Summary_Generation_Runbook.md`が文書化）を、EVENTカテゴリとは別のカテゴリ（RAID、Evidence Index昇格済み1 story・2 episodes）に対しても実行し、ユーザーが人間レビュー・draft内容を事前承認した上で初回commitまで到達した。生成（Ollamaローカル実行）は約24秒、quality gate（`check_story_summary_drafts.py`）は初回・レビュー後修正後の両方でPASS、人間レビューで2点（Episode 1本文の文体統一・係り受け誤読の修正）を修正、Public-safe projection（`internal_id_exposure=0`・`promotion_readiness=promotion-candidate`）を経て`promote_story_summaries.py --execute`で昇格した。これにより、カテゴリを跨いだ生成〜昇格パイプラインの再現性を確認した。公開Summaryは3→4 storyに拡大した。件数・所要時間のみ記録し、実sourceKey・要約本文はここに記載しない。

**追記（`summary-generation-quality-v2`、2026-07-18）**: 上記4 storyのうちRAID small batch（4件、workspace限定・非commit）の人間レビューで確認された品質問題2点（story summaryの情報欠落・主語の曖昧さ）を受け、`summary-generation-quality-v2`でstory-summary-v2/episode-summary-v3/自己推敲パスを実装した（詳細は上表参照）。本PRでは既存4 draftの再生成・再commitは行っていない（次回以降のsummary生成batchから新方式が適用される）。

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
- ~~Story Summary合成（Episode Summary群→Story Summary）の具体的なロジック（単純な要約結合か、再度LLMに要約させるか）~~ → **`summary-generation-story-synthesis`で確定**: 合成方式はLLM再要約とする。生成済みEpisode Summary群のtext（episodeNumber順）を入力とし、story全体の簡潔なあらすじを再度LLMに生成させる（`format_json=True`、出力は`{"text": "..."}`のみ。story-level textにblockId引用は求めない）。story-level evidenceRefsはLLM出力からではなく、episode-level evidenceRefsの重複排除union（episodeNumber順→episode内出現順で安定ソート）を後処理で機械的に設定する（監査可能性を保ちつつLLM引用の不確実性を避ける）。長文verbatim引用検出はstory合成では行わない（入力が既にsafeなepisode summaryであり、生のセリフ本文ではないため。episode生成側の検出はそのまま維持）。promptVersionはepisode用`episode-summary-v1`とは別定数`story-summary-v1`とする（§9該当行参照）
- CI組み込み（`validate_story_summaries.py --require-reviewed`のCI化）の要否・タイミング（`Story_Summary_Design.md` §14で既存の未確定事項）

---

# 12. 参照

- `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`（本文書§4.3の提案を実装レベルまで詳細化した設計PR。projection scriptのCLI仕様・field変換表・evidenceRefs変換仕様・Registry共有設計・schema変更不要の結論を確定）
- `docs/runbooks/Story_Summary_Generation_Runbook.md`（PoC（Stage 0）で確立した生成〜昇格の全8ステップ実行手順、CLIコマンド例、人間レビューチェックリスト、生成物のcommit可否表、既知の制約）
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
