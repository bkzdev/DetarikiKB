# Summary Public ID Projection Design（Story Summary公開ID projectionの実装設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Summary_Public_ID_Projection_Design.md`

---

# 1. Background

`story-summary-generation-planning`（`Story_Summary_Generation_Plan.md`）§4で、`schemas/story_summary.schema.json`の現行設計（`storyId`必須・保存ファイル名`{storyId}.yaml`）が、Evidence Indexが`evidence-index-promotion-first-reviewed-sample`（PR #91）で発見した「sourceKey由来IDのGit履歴永続混入」問題（`Evidence_Index_Public_ID_Policy.md` §2）と完全に同型であることを確認し、Evidence Indexが到達した解決策（案C: Public-safe projection）をそのまま踏襲する方針を確定した。同文書§4.3では、この方針をStory Summaryへ適用する提案（保存先・ファイル名、IDフィールドのpublic-safe化、evidenceRefs変換、Registry共有、schema変更要否）を整理したが、いずれも「提案、本PRでは実施しない」レベルに留まっていた。

本文書は、`Evidence_Index_Public_ID_Policy.md` §6.7〜§6.9で実装済みの`scripts/project_evidence_index_public_ids.py`の設計・実装パターンを踏襲し、`Story_Summary_Generation_Plan.md` §4.3の提案を実装レベルまで詳細化する。Evidence Indexの`evidence-index-public-id-schema-design`（PR #93、`publicEvidenceId`のschema/形式/prefix mapping確定）に相当する設計PRである。

本PRはdocs-only PRである。projection scriptの実装・実データprojection実行・Evidence Index側docs/scriptsの変更はいずれも行わない（§11 Non-goals）。

---

# 2. Scope（対象範囲）

対象:

- projection script（`scripts/project_story_summary_public_ids.py`、新設予定）のCLI引数・exit code・blocking条件・report/mapping CSV内容の確定
- compatible/public-safe両modeのfield変換表の確定
- evidenceRefs変換仕様（Evidence Index public-safe projectionのmapping CSVとの対応）の確定
- Public ID Registry共有設計（import再利用する関数名の確定）
- `schemas/story_summary.schema.json`の変更要否の最終確認・結論
- sourceKey由来ID exposure scan仕様の確定
- 実装フェーズ（`Story_Summary_Generation_Plan.md` §9）との対応関係の確定

対象外（Non-goals、詳細は§11）:

- `scripts/project_story_summary_public_ids.py`本体の実装
- 実データprojection実行
- `schemas/`配下の変更（§8で変更不要という結論に達するため、そもそも変更が発生しない）
- Evidence Index側docs/scriptsの実装変更（リンク追加のみ可）

---

# 3. ID categories（IDのSummaryへの適用）

`Evidence_Index_Public_ID_Policy.md` §3のID分類を、Story Summaryの文脈にそのまま対応させる。

## 3.1 A. 内部trace ID（Internal trace ID）

| フィールド（`schemas/story_summary.schema.json`） | 説明 |
|---|---|
| `storyId`（document直下、required） | sourceKey由来を含みうる内部Story ID |
| `episodeSummaries[].episodeId`（required） | 内部Episode ID |
| `storySummary.evidenceRefs[]` / `episodeSummaries[].evidenceRefs[]` | 内部`evidenceId`（Block ID）を参照しうる（Evidence Index側が未projectionの場合） |
| `source.inputRefs[]` | 生成時に参照した内部episodeId等（監査用、自由記述） |

## 3.2 B. 公開ID（Public-facing ID）

| フィールド | 説明 |
|---|---|
| `publicStoryId`（document直下、optional、既に実装済み） | `story_manifest.yaml`/`knowledge/public_ids/story_public_ids.yaml`の`publicStoryId`と対応 |
| `episodeSummaries[].publicEpisodeId`（optional、既に実装済み） | 同Registryの`publicEpisodeId`と対応 |
| `evidenceRefs[]`が指す`publicEvidenceId` | Evidence Index public-safe projectionが生成した公開Evidence ID（本文書§6） |

## 3.3 C. 表示用label・その他保持フィールド

| フィールド | 扱い |
|---|---|
| `storySummary.text` / `episodeSummaries[].text` | 要約本文そのもの（IDではないが、sourceKey由来語がAI生成テキストへ混入していないかは§9のexposure scanが最終防波堤として機能する） |
| `review.*` / `source.model` / `source.promptVersion` / `source.generatedAt` | Summary固有の運用metadata。sourceKey由来IDではないため、内部ID分類には含めない（§5で変換表として扱う） |

方針: `Evidence_Index_Public_ID_Policy.md` §3.3と同じく、タイトル由来のURL/IDは採用しない（Story Summaryにはそもそもタイトル由来フィールドは存在しない）。

---

# 4. Projection script design（`scripts/project_story_summary_public_ids.py`）

`scripts/project_evidence_index_public_ids.py`のCLI形状・安全方針をそのまま踏襲する独立scriptとして設計する（`Story_Summary_Generation_Plan.md` §11のopen questionを本PRで確定：独立scriptとする。Evidence Index自身も`build_evidence_index_candidates.py`拡張ではなく独立scriptとして`project_evidence_index_public_ids.py`を新設した前例があり、Story Summaryは入出力の文書構造（Evidence Indexの「flatなentries配列」に対しStory Summaryは「1 story 1ドキュメント、episodeSummariesはnested配列」）が異なるため、既存scriptへ分岐追加するより、独立scriptとして構造の違いを素直に表現する方が明快と判断した）。

## 4.1 CLI引数

```text
uv run python scripts/project_story_summary_public_ids.py \
    --input knowledge/summaries/stories/ \
    --output workspace/summary_drafts/public_id_projection/ \
    --mapping-output workspace/summary_drafts/public_id_map.csv \
    --report workspace/summary_drafts/public_id_report.md \
    --projection-mode compatible \
    --clean

uv run python scripts/project_story_summary_public_ids.py \
    --input knowledge/summaries/stories/ \
    --output workspace/summary_drafts/public_safe/stories/ \
    --mapping-output workspace/summary_drafts/public_safe/mapping.csv \
    --report workspace/summary_drafts/public_safe/report.md \
    --projection-mode public-safe \
    --evidence-mapping workspace/evidence_index_dry_runs/public_safe/mapping.csv \
    --registry knowledge/public_ids/story_public_ids.yaml \
    --clean
```

| 引数 | 必須 | 既定値 | 説明 |
|---|---|---|---|
| `--input` / `-i` | Yes | - | Story Summary YAMLファイル、またはdirectory（直下の`*.yaml`/`*.yml`を収集、`project_evidence_index_public_ids.py`と同じ収集ロジックを踏襲） |
| `--output` / `-o` | Yes | - | projection結果を書き出すdirectory（workspace配下のみ。`knowledge/summaries/`・`knowledge/public_ids/`配下は指定不可、§4.4） |
| `--mapping-output` | Yes | - | 内部ID⇔公開IDのmapping CSVを書き出すファイルパス（workspace配下のみ。内部IDを含むためcommit禁止） |
| `--report` | Yes | - | projection結果をMarkdownで書き出すファイルパス（workspace配下のみ） |
| `--schema` | No | `schemas/story_summary.schema.json` | 入力・projected出力のschema検証に使うファイルパス |
| `--registry` | No | None | Public ID Registry YAMLのパス（`scripts/check_public_episode_ids.py`/`project_evidence_index_public_ids.py`と同じschema/lookup方針、§7） |
| `--registry-schema` | No | `schemas/public_id_registry.schema.json` | Registry schemaのパス |
| `--evidence-mapping` | No | None | Evidence Index public-safe projectionが生成した`--mapping-output`のCSV（複数storyがある場合はfile/directory両対応、workspace配下想定）。指定時、`evidenceRefs`内の内部blockId参照を`publicEvidenceId`参照へ変換する（§6）。未指定時、`evidenceRefs`はcompatible modeでは無変換、public-safe modeでは常に空へ変換される（§6.4） |
| `--projection-mode` | No | `compatible` | `{compatible, public-safe}`。`project_evidence_index_public_ids.py`と同じ二段構成（§5） |
| `--clean` | No | False | `--output`出力先ディレクトリを書き込み前に削除する |
| `--quiet` / `-q` | No | False | 進捗メッセージを抑制する |

## 4.2 Exit codes

`project_evidence_index_public_ids.py`と同じ3値方式を踏襲する。

| exit code | 意味 |
|---|---|
| `0` | projection成功（blocking issueなし） |
| `1` | projection validation失敗（§4.3のいずれかに該当） |
| `2` | `--input`/`--schema`/`--registry`/`--registry-schema`/`--evidence-mapping`パスが見つからない、または`--output`/`--mapping-output`/`--report`が`knowledge/summaries/`・`knowledge/public_ids/`配下を指しているなどのconfig error（§4.4） |

## 4.3 Blocking条件（exit code 1）

1. documentに`publicStoryId`が無く、`--registry`からも解決できない
2. `episodeSummaries[]`のいずれかの要素に`publicEpisodeId`が無く、`--registry`からも解決できない
3. 既存`publicStoryId`/`publicEpisodeId`がRegistry値と矛盾する
4. public-safe modeで、1つの入力ファイル内で`storyId`と異なる複数の`publicStoryId`が混在する、または複数の入力ファイルが同じ`publicStoryId`（＝同じ出力ファイル名）へ解決される（1 file = 1 publicStoryId方針）
5. projected出力（compatible/public-safe いずれのmodeでも）が`schemas/story_summary.schema.json`によるschema検証に失敗する
6. public-safe modeで、sourceKey由来ID exposure scan（§9）が1件でも検出する

含めない条件（意図的にblockingにしないもの）:

- `review.status`が`reviewed`/`approved`以外であること（projection scriptはID安全性のみを扱い、内容レビュー状態のenforcementは既存の`scripts/validate_story_summaries.py --require-reviewed`の責務のまま分離する。§12 Open questionsで運用上の推奨順序を補足する）
- `evidenceRefs`が`--evidence-mapping`で解決できないこと（`Story_Summary_Generation_Plan.md` §4.3.3どおり、`evidenceRefs`を空にして昇格可、reportにwarningとして記録するのみ。§6.4）

## 4.4 安全策（出力先制限）

`project_evidence_index_public_ids.py`の出力先安全確認と同じパターンを踏襲する。`--output`/`--mapping-output`/`--report`は、以下いずれかの配下を指す場合exit code 2で拒否する。

- `knowledge/summaries/`（projection結果を誤って正式commit場所へ直接書いてしまう事故を防ぐ）
- `knowledge/public_ids/`（Registry本体を誤って上書きする事故を防ぐ）

`--input`ファイル自体は読み込みのみで変更しない（書き込み先は常に`--output`）。

## 4.5 Report / mapping CSVの内容

### 4.5.1 `--mapping-output`（CSV、commit禁止）

`project_evidence_index_public_ids.py`の`MAPPING_FIELDNAMES`と同じ発想で、1 episode 1行（story-level summaryのみのdocumentは1 story 1行を追加）とする。

```text
storyId,publicStoryId,episodeId,publicEpisodeId,publicEpisodeIdSource,
registryMatched,registryConflict,registryPublicEpisodeId,episodeOrder,
evidenceRefsInputCount,evidenceRefsConvertedCount,evidenceRefsClearedCount
```

- `publicEpisodeIdSource`: `input` / `registry` / `missing`（`project_evidence_index_public_ids.py`の同名列と同じ語彙）
- `evidenceRefsInputCount`/`evidenceRefsConvertedCount`/`evidenceRefsClearedCount`: そのepisode（またはstory-level summary）の`evidenceRefs`について、入力件数・`--evidence-mapping`で変換できた件数・変換できず空にした件数（§6.4）

内部ID（`storyId`/`episodeId`）と公開IDを1行に並べて記録するため、Evidence Index側`--mapping-output`と同様に常にworkspace限定・commit禁止とする（Internal Review Evidence Packet候補データ、未実装のまま据え置き）。

### 4.5.2 `--report`（Markdown）

`project_evidence_index_public_ids.py`と同じ節構成を踏襲する。

```text
# Story Summary Public ID Projection Report

- Input / Output / Mapping output / Evidence mapping / Projection mode / File count / Story count / Episode count

## Projection Result
- Missing publicStoryId count / Missing publicEpisodeId count / Conflicts count

## Registry
- Registry path / stories count / episodes count / entries from input・registry / missing after registry / conflicts

## Evidence Refs Conversion
- Evidence mapping path (or "(none)")
- Converted count / Cleared count (no evidence mapping match) / Stories promoted without evidenceRefs

## Public-safe Projection   (public-safe modeのみ)
- Output filename policy: publicStoryId-based ({publicStoryId}.yaml)
- Rewritten ID fields count / Removed internal fields count (source.inputRefs)
- Internal ID exposure scan result
- Promotion readiness (promotion-candidate / not-promotion-ready)

## Issues
## Warnings
## Final Decision
## Note
```

「evidenceRefsが空で昇格されたstory」の一覧はwarningとして`## Warnings`に記録する（`Story_Summary_Generation_Plan.md` §4.3.3の運用どおり、blockingにはしない）。

---

# 5. Field rewrite table（compatible / public-safe）

`Evidence_Index_Public_ID_Policy.md` §6.7・§6.8の「compatible modeは内部IDを一切削除しない migration/debugging用、public-safe modeが実際のPublic promotion対象」という二段構成をそのまま踏襲する。`Story_Summary_Generation_Plan.md` §4.3.2の表を、document全fieldに対して詳細化する。

| フィールド | compatible mode | public-safe mode |
|---|---|---|
| `schemaVersion` / `documentType` | 無変更 | 無変更 |
| `storyId`（required） | 無変更（内部IDのまま） | 値を`publicStoryId`の値へ置換する。field自体はrequiredのまま維持（schema互換、Evidence Index public-safe modeの書き換え方針§6.8を踏襲） |
| `publicStoryId`（optional） | Registry補完があれば書き込む（§7） | 元の値をそのまま保持する（rewriteされた`storyId`と重複するが、projection済みであることの機械的確認用、Evidence Index §6.8と同じ理由） |
| `language` | 無変更 | 無変更 |
| `generationStatus` | 無変更 | 無変更（projection scriptはreview/generation statusを書き換えない、§4.3の意図的除外条件） |
| `storySummary.text` | 無変更 | 無変更（§9のexposure scanでsourceKey由来語混入をscan） |
| `storySummary.confidence` | 無変更 | 無変更 |
| `storySummary.evidenceRefs[]` | 無変換（内部blockId参照のまま） | `--evidence-mapping`で`publicEvidenceId`へ変換、解決不可なら空配列へ（§6.4） |
| `episodeSummaries[].episodeId`（required） | 無変更 | 値を`publicEpisodeId`の値へ置換する |
| `episodeSummaries[].publicEpisodeId`（optional） | Registry補完があれば書き込む | 元の値をそのまま保持する |
| `episodeSummaries[].episodeNumber` | 無変更 | 無変更 |
| `episodeSummaries[].text` | 無変更 | 無変更（exposure scan対象） |
| `episodeSummaries[].confidence` | 無変更 | 無変更 |
| `episodeSummaries[].evidenceRefs[]` | 無変換 | `--evidence-mapping`で`publicEvidenceId`へ変換、解決不可なら空配列へ |
| `source.sourceType` / `source.model` / `source.promptVersion` / `source.generatedAt` | 無変更 | 無変更 |
| `source.inputRefs[]` | 無変更 | 除去する |
| `review.status` / `review.reviewer` / `review.reviewedAt` / `review.notes` | 無変更 | 無変更 |
| `notes` | 無変更 | 無変更 |

出力ファイル名:

```text
compatible mode:   {output_dir}/{storyId}.yaml         （入力ファイル名を維持）
public-safe mode:  {output_dir}/{publicStoryId}.yaml   （1 file = 1 publicStoryId）
```

---

# 6. evidenceRefs conversion（Evidence Index mapping CSVとの対応）

`Evidence_Index_Public_ID_Policy.md` §8.3で既に確定済みの「Summary `evidenceRefs`は最終的に`publicEvidenceId`を参照する（dual-field化は不採用）」方針を、具体的な変換手順として定義する。

## 6.1 入力: `--evidence-mapping`

Evidence Index public-safe projection（`scripts/project_evidence_index_public_ids.py --projection-mode public-safe --mapping-output <path>`）が生成するmapping CSV（`MAPPING_FIELDNAMES`、`Evidence_Index_Public_ID_Policy.md` §6.7参照）をそのまま入力として受け取る。新たなmapping生成ロジックはSummary側で持たない（`Story_Summary_Generation_Plan.md` §11のopen question「同じCSVを共有するか、Summary側でも独自にmapping生成が必要か」を本PRで共有する方向に確定する）。

使用する列は`evidenceId`（内部blockId、Evidence Index側の内部ID）と`publicEvidenceId`（変換先）の2列のみ。他の列（`storyId`/`publicStoryId`/`episodeId`/`publicEpisodeId`/`evidenceType`/`sceneId`/`blockId`/`episodeOrder`/`publicEpisodeIdSource`/`registryMatched`/`registryConflict`/`registryPublicEpisodeId`）は無視する。

`--evidence-mapping`にはfile（1 story分のCSV）またはdirectory（複数story分のCSVをまとめて読み込む）を指定できる。directory指定時は、内部で全CSVの`evidenceId -> publicEvidenceId`行を1つのlookup dictへマージする（`publicEvidenceId`が重複する場合は後勝ちとし、他scriptの索引構築と同じ「後勝ち」方針を踏襲、警告はreportに記録しない軽微な仕様とする。将来複数storyのmapping CSVを1つのlookupへ安全にマージする必要が生じた場合は別途検討、§12）。

## 6.2 変換ロジック

`storySummary.evidenceRefs[]`・`episodeSummaries[].evidenceRefs[]`それぞれの各値`ref`について:

1. `ref`が`--evidence-mapping`のlookupに`evidenceId`として存在すれば、対応する`publicEvidenceId`へ置換する
2. `ref`が既に`publicEvidenceId`形式（lookupの値側と一致、またはlookupの`evidenceId`列に存在しない）である場合は、そのまま保持する（Evidence Index側の解決ロジックが内部ID/公開IDどちらでも解決できるfallback方針と同じ「両方許容」の考え方を、変換前チェックとして先取りする）
3. `ref`がlookupのどちらにも見つからない場合、そのstory/episode全体の`evidenceRefs`を空配列にする（1件でも未解決参照があれば、そのSummary単位でevidenceRefs全体を空にする。部分的に変換済み・部分的に内部IDのまま、という中途半端な状態を出力に残さないための安全側の判断）

## 6.3 `--evidence-mapping`未指定時

- compatible mode: `evidenceRefs`は無変換のまま出力する（内部blockId参照が残ることは許容、migration/debugging用のためpromotion対象ではない）
- public-safe mode: 変換元が無いため、全document・全episodeの`evidenceRefs`を空配列にする（§6.4のフォールバックと同じ扱い）

## 6.4 Evidence Index未昇格storyの扱い

`Story_Summary_Generation_Plan.md` §4.3.3で既に確定済みの方針をそのまま実装レベルへ落とす。

- 該当storyがEvidence Index未昇格（`--evidence-mapping`に該当`storyId`のentryが1件も無い）の場合、そのstoryの`evidenceRefs`（story-level・episode-levelとも）を空配列にしてprojectionを継続する（blockingにしない）
- reportの`## Evidence Refs Conversion`section・`## Warnings`sectionに、`evidenceRefs`無しで昇格したstory/episodeの一覧をwarningとして記録する
- `Evidence_Index_Design.md` §10の既存の安全側フォールバック（「未解決は従来通りID表示のまま、非エラー」）とも整合する設計

---

# 7. Registry sharing design（Public ID Registry共有設計）

`Story_Summary_Generation_Plan.md` §4.3.4で確定済みの「新しいRegistryは作らず既存`knowledge/public_ids/story_public_ids.yaml`を再利用する」方針を、具体的なimport設計として確定する。

## 7.1 共有元

`scripts/project_evidence_index_public_ids.py --registry`統合（`feature/evidence-index-public-id-registry-integration`）と同じパターンで、以下2関数を`scripts/check_public_episode_ids.py`からそのままimportして再利用する。

```python
from check_public_episode_ids import (
    DEFAULT_REGISTRY_SCHEMA_PATH,
    _group_entries_by_internal_story,
    _resolve_registry_lookup,
)
```

- `_resolve_registry_lookup(args)`: `--registry`/`--registry-schema`引数からRegistry lookup（`dict[(publicStoryId, episodeOrder), publicEpisodeId]`）を組み立てる。`argparse.Namespace`を受け取る関数のため、`project_story_summary_public_ids.py`側の`parse_args()`も`--registry`/`--registry-schema`を同名で持たせ、そのまま渡せるようにする
- `_group_entries_by_internal_story(raw_documents)`: `raw_documents: list[tuple[Path, dict]]`（各`dict`は`entries: list[dict]`キーを持つ）を受け取り、内部`storyId`単位でentryをグルーピングする

## 7.2 データ構造の違いに対するアダプタ

Evidence Indexは「1ファイルに複数storyのflatな`entries`配列」を扱うのに対し、Story Summaryは「1ファイル1 story、`episodeSummaries[]`という入れ子配列」という構造を持つ。`_group_entries_by_internal_story`/`_resolve_registry_lookup`のシグネチャを変更せずに再利用するため、`project_story_summary_public_ids.py`側でEvidence Index entry形状を模した一時的なadapterレコードを組み立ててから渡す。

```text
Story Summary document (1 file)
  storyId, publicStoryId,
  episodeSummaries: [
    { episodeId, publicEpisodeId, ... },
    ...
  ]

  -> adapter (project_story_summary_public_ids.py内、Registry lookup専用、出力には含めない)

synthetic "entries" list:
  [
    { "storyId": storyId, "episodeId": ep.episodeId,
      "publicStoryId": publicStoryId, "publicEpisodeId": ep.publicEpisodeId },
    ...  # episodeSummaries[]の要素数分
  ]
```

このsynthetic entriesを`raw_documents = [(path, {"entries": synthetic_entries})]`の形に包んで`_group_entries_by_internal_story`/`_resolve_registry_lookup`へ渡すことで、episodeOrder計算（内部`episodeId`の出現順、1始まり）・Registry補完・conflict検出のロジックをEvidence Index側と完全に一致させる。adapterレコード自体は変換専用の内部データであり、`--output`のprojected documentには含めない（実際のStory Summary schema構造へ書き戻す）。

## 7.3 補完ルール

`Public_ID_Registry_Design.md` §6.3・`Evidence_Index_Public_ID_Policy.md` §6.10と同じルールをそのまま適用する。

- 既存`publicEpisodeId`（または`publicStoryId`）がある場合: Registry値と一致すればそのまま、不一致ならblocking、Registryに該当が無ければwarning（PASSは維持）
- 既存の値が無い場合: Registryに該当があれば補完（documentへ直接書き込み）、無ければ引き続きblocking（自動採番はしない）
- Story Summaryは`publicStoryId`自体もdocument直下のoptional fieldとして持つため、Evidence Indexには無い「`publicStoryId`自体のRegistry補完」も同じ考え方で行いたくなるが、Registry構造上`publicStoryId`自体をキーにstoryを逆引きする仕組みは提供されない（Registryの主キーは`publicStoryId`そのものであり、内部`storyId`からの逆引きインデックスを持たない）。したがって`publicStoryId`が欠落しているdocumentは、Registry未指定時と同じ扱い（§4.3項目1でblocking）になる。Registryは`publicEpisodeId`の補完にのみ有効であり、`publicStoryId`自体の補完手段ではないという制約を明記しておく（Evidence Index側`project_evidence_index_public_ids.py`も同じ制約を持つ、「documentにpublicStoryIdを持つentryが1件も無い」チェックが独立して存在する理由と同じ）

---

# 8. Schema変更要否の結論

`Story_Summary_Generation_Plan.md` §4.3.5で「実装PR側で最終確認する」としていた4項目を、本PRで確認・確定する。

| 項目 | 確認結果 |
|---|---|
| `publicStoryId`/`publicEpisodeId`のoptional実装 | `story-summary-schema-implementation`で既に実装済み（`schemas/story_summary.schema.json`の`properties.publicStoryId`・`definitions.EpisodeSummaryEntry.properties.publicEpisodeId`、いずれも`oneOf: [pattern string, null]`）。追加のschema変更は不要 |
| Compatible projection相当 | 既存fieldをそのまま使う運用のみで実現できる（`storyId`/`episodeId`は維持、`publicStoryId`/`publicEpisodeId`を確実に埋めるだけ）。schema変更不要 |
| Public-safe projection相当（`storyId`/`episodeId`の値の置換） | `storyId`のpattern（`^[A-Z][A-Z0-9_]*$`）・`episodeSummaries[].episodeId`のpattern（同一）は、`publicStoryId`/`publicEpisodeId`のpattern（同じく`^[A-Z][A-Z0-9_]*$`）と完全に一致する。`publicStoryId`/`publicEpisodeId`の実際の値（例: `{publicStoryId}`形式・`{publicStoryId}_E01`形式、`EVT_YYYYMMDD_NNN`のような匿名化表記）は元々このpatternに適合する形式で採番されている（`Public_ID_Registry_Design.md` §3.1）ため、値を置換してもschema検証は変更なしで通過する。field自体のrequired性を変える必要も無く、schema変更不要 |
| `EvidenceRef` pattern（`^[A-Z][A-Z0-9_]*$`）と`publicEvidenceId`形式の互換性 | `publicEvidenceId`形式`{publicEpisodeId}_{PREFIX}{sequence:04d}`（`Evidence_Index_Public_ID_Policy.md` §6.4）を展開すると、`publicEpisodeId`自体が`^[A-Z][A-Z0-9_]*$`に適合する文字列（例: `{publicStoryId}_E01`形式）、`PREFIX`は大文字英字のみ（`DLG`/`MONO`/`NAR`/`CHO`/`UNK`等、§6.5 evidenceType prefix mapping）、`sequence:04d`は数字4桁である。したがって`publicEvidenceId`全体は常に大文字英数字とアンダースコアのみで構成され、`^[A-Z][A-Z0-9_]*$`に完全に適合する。pattern変更は不要と確認できた（`Story_Summary_Generation_Plan.md` §4.3.5項目4で「実装PR側で最終確認する」としていた点を、本PRで確定） |

結論: `schemas/story_summary.schema.json`に対する変更は一切不要である。compatible/public-safe両projection modeとも、既存schemaの構造（required/optional/pattern）を変更せずに実現できる。

この結論により、`Story_Summary_Generation_Plan.md` §9の実装フェーズ表にあった`summary-public-id-schema-implementation`フェーズはスキップ可能となる（§10で詳述）。

---

# 9. sourceKey由来ID exposure scan仕様

`Evidence_Index_Public_ID_Policy.md` §6.9のscan仕様を、Story Summary documentの構造に合わせて適用する。

- 収集対象: projection前（rewrite前）のdocumentが持つ`storyId`・`episodeSummaries[].episodeId`の値
- 除外対象: 収集した値のうち、対応する`publicStoryId`・対応する`episodeSummaries[].publicEpisodeId`と一致する値（偶然の一致は安全と判断、Evidence Index §6.9と同じ理由）
- 閾値: 4文字未満の値は誤検出防止のため対象外（Evidence Index側の閾値と同じ値を再利用する設計とする）
- scan対象: public-safe出力document（field rewrite後）を直列化した文字列全体。`storySummary.text`/`episodeSummaries[].text`/`review.notes`/`notes`等、rewrite対象外として保持したfield経由の内部ID混入（LLM生成テキストへのsourceKey由来語の偶発的混入等）も検出できるようにするため
- 検出時の扱い: 1件でも検出すればblocking error（exit code 1）とし、reportに検出件数・該当内部ID一覧を記録する（`Evidence_Index_Public_ID_Policy.md` §6.9と同じ）
- 本scanもヒューリスティックであり、実sourceKeyの一覧と突き合わせる方式ではない（Evidence Index側と同じ既知の限界。将来的な精度向上は別PRで検討、§12）

---

# 10. Implementation phases（実装フェーズとの対応）

`Story_Summary_Generation_Plan.md` §9のフェーズ表を、本PRの結論を踏まえて更新する。

| フェーズ（候補PR名） | 本PRでの扱い |
|---|---|
| `summary-public-id-projection-design`（本PR） | 完了。本文書として設計を確定した |
| `summary-public-id-schema-implementation` | スキップ可能（§8の結論により、`schemas/story_summary.schema.json`の変更は不要と判明したため、このフェーズ自体が不要になった。`Story_Summary_Generation_Plan.md` §9の該当行にも本PRでその旨を追記する） |
| `summary-generation-public-safe-projection` | 本文書の設計（§4〜§9）を実装するフェーズ。`scripts/project_story_summary_public_ids.py`（新規script）を実装し、Compatible→Public-safeの2段階projectionを実現する。Evidence Indexの`evidence-index-public-id-projection`＋`evidence-index-public-id-public-safe-projection`に相当する内容を1フェーズに統合する（Story Summary側はEvidence Indexほど段階を細分化する必要性が低いと判断: publicEvidenceId自動採番のような複雑な連番ロジックが無く、公開IDは既にRegistry側で確定済みの値を参照するだけであるため） |

---

# 11. Non-goals

`summary-public-id-projection-design`（本PR）で以下は行っていない:

- `scripts/project_story_summary_public_ids.py`本体の実装
- 実データprojection実行
- `agents/`・`scripts/`・`schemas/`配下の一切の変更
- Evidence Index側docs（`Evidence_Index_Public_ID_Policy.md`等）・scripts（`project_evidence_index_public_ids.py`/`check_public_episode_ids.py`等）の実装変更（本文書からのリンク追加のみ）
- `knowledge/public_ids/story_public_ids.yaml`への実データ追加
- LLM呼び出し・prompt・provider実装（`Story_Summary_Generation_Plan.md` §10のNon-goalsをそのまま継承）
- 実要約生成
- `agents/summarizer/`パッケージの変更（`summary-generation-skeleton`で新設済みの骨格を維持、本PRでは触れない）

---

# 12. Open questions（未確定事項）

- projection scriptによる`review.status`/`generationStatus`のenforcement要否: 本PRでは「projection scriptはID安全性のみを扱い、内容レビュー状態は既存の`validate_story_summaries.py --require-reviewed`に委ねる」設計としたが、運用上は「`--require-reviewed`通過後にのみprojectionを実行する」という手順順序をrunbook等で明記する必要がある（`summary-generation-public-safe-projection`実装時、またはその運用手順を定めるPRで確定）
- `review.reviewer`実名の扱い: public-safe modeでも`review.reviewer`はrewriteせず保持する設計としたが、これはsourceKey由来の内部traceではないためEvidence Indexの`notes`/`relatedEntities`保持方針と同列に扱った結果である。実際の運用でreviewer個人名を公開Wiki相当のprojection出力に残してよいかは、Evidence Index側にも先例が無い論点であり、本PRでは確定しない（`summary-generation-public-safe-projection`実装時、または別途プライバシー方針PRで検討）
- `--evidence-mapping`が複数storyのCSVをまとめたdirectoryである場合のマージ挙動: 本PRでは「`publicEvidenceId`重複時は後勝ち」という軽量な仕様としたが、実運用でのCSVファイル構成（1 story 1 CSVを想定）次第では厳密な重複検出が必要になる可能性がある（`summary-generation-public-safe-projection`実装時に確認）
- Story Summary合成（Episode Summary群→Story Summary）ロジックとprojectionの実行順序: `Story_Summary_Generation_Plan.md` §11で未確定のまま持ち越されている論点（本文書のスコープ外）だが、projection scriptはStory Summary合成が完了した後の最終document単位で動作する前提である点は明記しておく
- CI組み込み: `Story_Summary_Generation_Plan.md` §11・`Story_Summary_Design.md` §14で既存の未確定事項（`validate_story_summaries.py --require-reviewed`のCI化）と同様、本projection scriptのCI組み込み要否・タイミングも未確定のまま据え置く

---

# 13. 参照

- `docs/architecture/06_AI/Story_Summary_Generation_Plan.md`（§4.3の元提案・§9実装フェーズ分割・§11 open questions、本文書はその実装レベル詳細化）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（§6.4-§6.10 publicEvidenceId形式・Compatible/Public-safe projection実装・exposure scan仕様、本文書が踏襲する設計・実装パターンの元）
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`（Public ID Registry設計、§6.3 Registry統合実装が本文書§7の踏襲元）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Summaryのデータモデル・保存場所・evidenceRefs方針の既存設計）
- `scripts/project_evidence_index_public_ids.py`（CLI形状・safety策・field rewrite・exposure scanの実装パターンの踏襲元、読むだけで変更しない）
- `scripts/check_public_episode_ids.py`（`_resolve_registry_lookup`/`_group_entries_by_internal_story`のimport元、読むだけで変更しない）
- `schemas/story_summary.schema.json`（本文書§8で変更不要と確認した既存schema）
- `schemas/evidence_index.schema.json` / `schemas/public_id_registry.schema.json`（本文書が参照する既存schema）
- `TASKS.md`（次PR候補の追跡）
