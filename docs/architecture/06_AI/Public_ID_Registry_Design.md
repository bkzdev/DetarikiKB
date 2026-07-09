# Public ID Registry Design（publicEpisodeId未確定問題の整理とPublic ID Registry設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Public_ID_Registry_Design.md`

---

# 1. Background

`evidence-index-public-id-public-safe-projection`（PR #95）で、`scripts/project_evidence_index_public_ids.py --projection-mode public-safe`を実装した。匿名化実データサンプル（1 story・187 entries）に対してdry-run実行したところ、以下の結果になった。

- Episode 1相当（92 entries）: `publicEpisodeId`が確定済みだったため、Public-safe projectionが正しく成功し、`validate_evidence_index.py`・`check_evidence_index_promotion.py`ともPASS、internal ID exposure scanも0件だった
- Episode 2相当（95 entries）: `publicEpisodeId`が未確定だったため、`publicEpisodeId`欠落のblocking errorが正しく発火し、projectionが失敗した

**この結果自体は安全策として正しい**（`Evidence_Index_Public_ID_Policy.md` §6.7.1が定めた「`publicEpisodeId`欠落は自動補完せずblocking error」という方針通り）。しかし、実promotion再開（`knowledge/evidence/stories/`への実データ昇格の再試行）には、対象storyの**全episode**で`publicEpisodeId`が確定している必要がある。未確定IDを推測で埋めるのは危険であり、`publicEpisodeId`をどこに永続化し、どう割り当てるかの運用を整理する必要がある。

本文書は、この問題を整理し、`publicEpisodeId`の役割・採番方針・永続化場所（Public ID Registry）を設計する。実イベント名・実sourceKey・実storyIdは本文書に記載しない（匿名化した例で説明する）。

---

# 2. publicEpisodeIdの役割

`publicEpisodeId`は以下の役割を持つ（`Evidence_Index_Public_ID_Policy.md` §3.2・§6の踏襲）。

- Public Evidence Index内のepisode識別子（`storyId`/`episodeId`に代わる公開向けID）
- `publicEvidenceId`のprefix（`{publicEpisodeId}_{TYPE_PREFIX}{sequence:04d}`、`Evidence_Index_Public_ID_Policy.md` §6.4）になる
- 将来のEvidence page anchor / Summary `evidenceRefs`リンクの基盤になる（`evidence-index-public-id-renderer-switch`、未着手）
- sourceKey由来の内部`episodeId`をPublic repoに出さないための、公開してよいID
- story内のepisode順（`episodeOrder`）と対応する必要がある（採番方針、§3）
- **一度公開したら原則変更しない**（`Identifier_Specification.md` §2.1の安定性原則を`publicEpisodeId`にも適用する）

---

# 3. 採番方針

## 3.1 採用形式

```text
{publicStoryId}_E{episodeOrder:02d}
```

例:

```text
EVT_260707_001_E01
EVT_260707_001_E02
EVT_260707_001_E03
```

- story内のepisode順（`episodeOrder`）で採番する
- 1始まり、2桁zero padding（`Story_Manifest_Design.md` §9の既存`episodeId`採番と同じ2桁ゼロ埋め規則を踏襲）
- episode titleやsourceKey由来の語は含めない（`Story_ID_Policy_Decision.md` §8.1の「タイトル由来URLを避ける理由」と同じ原則）
- 一度公開した後は原則変更不可。episode追加・順序変更が起きる場合はmigration policyが別途必要（本文書では未確定、§8 Open Questionsに記録）

## 3.2 既存publicEvidenceId形式との関係

`Evidence_Index_Public_ID_Policy.md` §6.4で決定した`publicEvidenceId`形式は、`publicEpisodeId`をそのままprefixとして使う。

```text
{publicEpisodeId}_{TYPE_PREFIX}{sequence:04d}
```

つまり`publicEpisodeId`が未確定・不安定な間は、そのepisodeに属する全entryの`publicEvidenceId`も採番できない（PR #95のEpisode 2 blocking FAILがこの依存関係をそのまま体現している）。`publicEpisodeId`の安定性が、`publicEvidenceId`の安定性の前提になる。

---

# 4. 永続化場所

## 4.1 候補比較

### 候補A: `story_manifest.yaml`に保存

`story_manifest.yaml`は既に`publicStoryId`/`publicEpisodeId`フィールドを持つ（`Story_Manifest_Design.md` §13.2、`feature/story-manifest-public-id-fields-design`で実装済み）。renderer側もこの値を実際に使っている（`feature/story-manifest-public-id-renderer-switch`）。

- 長所: story/episodeの公開IDを一元管理できる、`build_evidence_index_candidates.py`の入力元（Normalized Story JSON経由）として既に機能している、既存フローと完全に一致する
- 短所: `story_manifest.yaml`自体は`sourceKey`/`rawPath`/`title`/`subtitle`等の内部情報を含む可能性が高く、**実データ由来の`story_manifest.yaml`はcommitしない運用**（`Story_Manifest_Design.md` §17・§19のNon-goals）と衝突する。公開してよいID情報だけを取り出してcommitしたい場合に分離しづらい

### 候補B: `knowledge/public_ids/story_public_ids.yaml`のようなPublic ID Registryに保存

- 長所: 公開IDだけをcommitできる、sourceKeyや実タイトルを一切含めずに管理できる（schema上`additionalProperties: false`で構造的に混入不可能にできる）、Public-safe projectionの入力として扱いやすい
- 短所: `story_manifest.yaml`とのjoinが別途必要、generator/projection scriptに追加入力が必要

### 候補C: workspace assignment fileのみ

- 長所: commitリスクが低い（`workspace/`配下は既存の`.gitignore`保護をそのまま使える）
- 短所: 再現性が落ちる、CI/将来のbuildに乗せにくい、長期運用（複数story・複数episodeの蓄積）に不向き

## 4.2 採用方針

- **長期方針として候補B（Public ID Registry）を採用する**。`story_manifest.yaml`は内部情報（`sourceKey`/`rawPath`/`title`/`subtitle`等）を含む可能性があるため、公開repoに置く場合はPublic IDだけを別ファイルへ分離する
- **ただし本PRでは大きく実装しすぎない**。Registryのschema・簡易validator・assignment候補提案scriptまでを実装し、実registryへの実データ追加・`project_evidence_index_public_ids.py`側でのregistry入力への本格対応は後続PRに委ねる（§6・§9）
- `story_manifest.yaml`自体の役割・スコープ・commit禁止方針は変更しない（`Story_Manifest_Design.md`のまま）。Registryは`story_manifest.yaml`の代替ではなく、「公開してよい部分集合を安全にcommitできる形で持つ」ための補完的な仕組みである
- internal storyId/episodeIdとの対応関係（mapping）は、Registry側には持たせない。必要な場合は`workspace/`側・Internal Review Evidence Packet側（`internal-review-evidence-packet-design`、未実装）で扱う方針とする

---

# 5. Public ID Registry設計

## 5.1 ファイル

`knowledge/public_ids/story_public_ids.yaml`（案。実装時のファイル名・配置は`schemas/public_id_registry.schema.json`のロードパスと合わせて確定する）

## 5.2 スキーマ（実装済み、`schemas/public_id_registry.schema.json`）

```yaml
registryVersion: 1
stories:
  - publicStoryId: EVT_260707_001
    category: event
    episodes:
      - publicEpisodeId: EVT_260707_001_E01
        episodeOrder: 1
      - publicEpisodeId: EVT_260707_001_E02
        episodeOrder: 2
```

## 5.3 含めないもの（重要）

- sourceKey由来の内部`storyId`
- 内部`episodeId`
- raw title / raw subtitle
- raw path / raw file name
- 実イベント名

schema自体が`additionalProperties: false`を全階層で指定しているため、上記フィールドは**構造的に追加できない**（新しいプロパティを足そうとするとschema検証エラーになる）。これは`schemas/evidence_index.schema.json`の`visibility.rawTextIncluded: const false`と同じ「機械的な保証」パターンを踏襲したものである。

## 5.4 story_manifest.yamlとの関係

- `publicStoryId`/`publicEpisodeId`という値そのものは、引き続き人間が`story_manifest.yaml`側で個別に確定する運用を継続する（`Story_Manifest_Design.md` §13.2の既存運用は変更しない）
- Public ID Registryは、`story_manifest.yaml`で確定した値のうち**公開してよい部分だけを転記した副次的な記録**という位置づけにする（source of truthは引き続き`story_manifest.yaml`側）
- internal storyId ⇔ publicStoryIdの対応そのもの（mapping）は、Registry側ではなくInternal Review Evidence Packet側またはworkspace限定のmapping（`project_evidence_index_public_ids.py`の`--mapping-output`と同じ位置づけ）で扱う

---

# 6. 実装方針（本PRのスコープ）

## 6.1 実装したもの

- `schemas/public_id_registry.schema.json`（§5.2のschema、`registryVersion`/`stories[].publicStoryId`/`category`/`episodes[].publicEpisodeId`/`episodeOrder`）
- `scripts/check_public_episode_ids.py`（assignment候補提案script、§7）
- `tests/scripts/test_check_public_episode_ids.py`（16件）

## 6.2 実装しなかったもの

- 実Registryファイルへの実データ追加（`knowledge/public_ids/`は本PRでは作成しない。作成する場合も`.gitkeep`のみに留める運用を次PR以降で検討する）
- `scripts/project_evidence_index_public_ids.py`本体の変更（`--projection-mode public-safe`の`publicEpisodeId`欠落blocking挙動はPR #95のまま維持する）
- Registryを`project_evidence_index_public_ids.py`の入力として直接使う統合（次PR候補`evidence-index-public-id-registry-integration`、§9）
- `story_manifest.yaml`の実データ変更・自動生成

---

# 7. Assignment check script（`scripts/check_public_episode_ids.py`）

## 7.1 役割

- Public Evidence Index候補（`schemas/evidence_index.schema.json`準拠のYAML）を入力とする
- `publicStoryId`を持つentryが検出できるstory群について、episodeごとに`publicEpisodeId`が割り当て済みかを確認する
- 欠落しているepisodeについて、`{publicStoryId}_E{episodeOrder:02d}`形式の割当候補（suggestion）をworkspace限定で提案する
- **`story_manifest.yaml`・Evidence Index・Public ID Registryのいずれも自動で書き換えない**

## 7.2 CLI

```powershell
uv run python scripts/check_public_episode_ids.py `
  --input workspace/evidence_index_dry_runs/first_reviewed_sample/default/stories `
  --report workspace/public_episode_ids/report.md `
  --suggestions-output workspace/public_episode_ids/suggestions.yaml
```

任意引数: `--registry <path>`（Public ID Registryを併用し、既存登録済みの`(publicStoryId, episodeOrder)`があればその値を再利用する）、`--registry-schema`、`--strict`（episode内でのpublicEpisodeId conflictをblocking errorにする。既定では警告のみ）、`--quiet`。

## 7.3 Exit codes

- `0`: 全episodeに`publicEpisodeId`が割り当て済み
- `1`: `publicEpisodeId`欠落、`publicStoryId`欠落、duplicate `publicEpisodeId`のいずれかを検出（`--strict`指定時はconflictも含む）
- `2`: 入力/schema/registryパスが見つからない、registryのschema検証失敗、`--report`/`--suggestions-output`が`knowledge/evidence/`・`knowledge/public_ids/`配下を指しているなどのconfig error

## 7.4 suggestions出力形式

```yaml
suggestions:
  - publicStoryId: EVT_260707_001
    missingEpisodeOrder: 2
    suggestedPublicEpisodeId: EVT_260707_001_E02
    reason: "Next sequential episode order inferred from candidate order."
    reviewRequired: true
```

`reviewRequired`は常に`true`（§7.6）。

## 7.5 source text exposure対策

`--report`/`--suggestions-output`には、`publicStoryId`/`publicEpisodeId`候補・`episodeOrder`（整数）以外を一切出力しない。内部`storyId`/`episodeId`/`evidenceId`、raw title、raw pathはいずれも出力対象に含めない。`publicStoryId`が1件も無いstory groupは、内部IDの代わりに`unidentified-story-group-{N}`という匿名ラベル（Nは検出順の連番）で報告する。

## 7.6 Assignment方針: 人間review必須

- scriptは候補を提案するだけであり、実際の永続化（`story_manifest.yaml`への書き込み、Public ID Registryへの追加）は**常に人間レビュー後**に行う
- 推測結果を自動で本番反映しない（`reviewRequired: true`固定）
- `episodeOrder`の根拠（「入力entriesの出現順から推定した1始まりの連番」であり、正式なepisode順の保証ではない）を`reason`に明記する
- `publicEpisodeId`の衝突（同一値が複数episodeに割り当てられている）はduplicate errorとして必ず検出する
- 一度publishされた`publicEpisodeId`は変更しない（§2）。`--registry`併用時は、Registryに既存の割当がある場合はその値をそのまま再提案し、勝手に別の値へ採番し直さない

---

# 8. Open Questions（未確定事項）

- `episodeOrder`の正式な根拠をどう確定するか（本scriptは「入力entriesの出現順」というヒューリスティックのみを使う。`story_manifest.yaml`の`episodeNumber`と必ず一致する保証はまだ無い）
- episode追加・既存episode順序変更が起きた場合のmigration policy（`publicEpisodeId`の安定性原則との両立）
- Public ID Registryの実ファイル配置・commitタイミング（`knowledge/public_ids/`を新設するか、既存`knowledge/`配下の別位置にするか）
- `project_evidence_index_public_ids.py`とRegistryの本格統合方法（`evidence-index-public-id-registry-integration`、§9）
- Registry自体の更新運用（人間が直接編集するか、`story_manifest.yaml`から半自動生成するcopy scriptを用意するか）

---

# 9. Non-goals（本PRで行わないこと）

- 実Evidence Indexのcommit・`knowledge/evidence/stories/`への実データ昇格
- `promote_evidence_index.py --execute`の実行、実promotion retry
- renderer/paths.pyの変更（Evidence page見出し・anchor・Summary evidenceRefsリンクの切替）
- `publicEpisodeId`の自動補完・本番反映
- `story_manifest.yaml`の実データ変更
- 実Public ID Registryへの実データ追加
- `scripts/project_evidence_index_public_ids.py`/`scripts/promote_evidence_index.py`/`scripts/check_evidence_index_promotion.py`/`scripts/build_evidence_index_candidates.py`の変更
- `schemas/evidence_index.schema.json`の破壊的変更
- Internal Review Evidence Packet生成

後続PR候補（`evidence-index-public-id-registry-integration`）:

- Public ID Registryを`project_evidence_index_public_ids.py`へ入力として渡す
- 欠落`publicEpisodeId`をRegistryから補う（自動反映ではなく、projection時の参照のみ）
- 補えない場合は引き続きblocking
- mapping reportにregistry sourceを記録する

---

# 10. 参照

- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（`publicEvidenceId`形式・prefix mapping・Public-safe projection方針、§6.4-§6.9）
- `docs/architecture/06_AI/Evidence_Index_Design.md`（Evidence Indexの役割・実装フェーズ）
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`（promotion criteria/exclusion criteria）
- `docs/architecture/05_Parser/Story_ID_Policy_Decision.md`（`publicStoryId`/`publicEpisodeId`のfield naming採用決定、§7）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（`story_manifest.yaml`の`publicStoryId`/`publicEpisodeId`実装、§13.2）
- `docs/architecture/05_Parser/Identifier_Specification.md`（§2.1安定性原則）
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`（§13.4 Public-safe projection実データdry-run結果）
- `scripts/check_public_episode_ids.py`（本PRで追加したassignment候補提案script）
- `schemas/public_id_registry.schema.json`（本PRで追加したPublic ID Registry schema）
- `TASKS.md`（次PR候補の追跡）
