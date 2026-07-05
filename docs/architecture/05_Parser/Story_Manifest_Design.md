# Story Manifest Design（DEC配置 ⇔ storyId/episodeId対応表の設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/05_Parser/Story_Manifest_Design.md`

---

# 1. 目的

本格運用時、ユーザーのローカル環境には多数の`.dec`ファイルが、ゲームデータのエクスポート構造に近い形で配置される見込みである。例えば以下のような配置になる。

```text
EVENT\csl_script_event_250626_dancer_export\CAB-csl_script_event_250626_dancer-episode1.dec
EVENT\csl_script_event_250626_dancer_export\CAB-csl_script_event_250626_dancer-episode2.dec
```

この配置はDKBの正規ID体系（`storyId`/`episodeId`、`Identifier_Specification.md`）とは無関係な、ゲーム側のエクスポート都合の名前である。`scripts/normalize_story.py`は現状`--story-id`/`--episode-id`/`--category`を毎回人間が指定する必要があり（`--story-title`/`--episode-title`も同様）、大量の`.dec`ファイルを扱う本格運用では非効率になる。

本文書は、**raw DECファイルのローカル配置とDKB正規IDの対応を管理する`story_manifest.yaml`**の設計を行う。`knowledge/dictionaries/characters.yaml`（ID解決用辞書）・`knowledge/dictionaries/character_profiles.yaml`（公式プロフィール辞書）と同じ位置づけの、**人手管理・人間確認済みの対応表**である。

**本PRでは設計・schema案・runbook相当の説明・合成template・候補生成script skeletonまでを行う。実DECファイル・実データ由来manifest・実データのnormalize/merge/renderは一切行わない。**

---

# 2. story_manifest.yaml の位置づけ

| ファイル | 役割 | ID解決・merge処理への関与 |
|---|---|---|
| `knowledge/dictionaries/characters.yaml` | キャラクターID解決用辞書（`sourceCharacterId` → `characterId`） | あり（`agents/parser/resolver.py`） |
| `knowledge/dictionaries/character_profiles.yaml` | 公式プロフィール辞書（`characterId`に紐づく読み仮名/所属等） | なし（Wiki表示専用） |
| **`story_manifest.yaml`（本文書で設計）** | **raw DECファイル配置 ⇔ `storyId`/`episodeId`/`title`/`subtitle`/`rawPath`対応表** | 将来的にあり（`scripts/normalize_story.py`の入力補完、§14） |

`story_manifest.yaml`の実体（人間確認済みの対応表そのもの）は本PRでは作成しない。将来の`story manifest candidate builder`・`story title/subtitle import`タスクで、候補生成→人間確認→確定という流れを経て作成する（`character_profiles.yaml`のbatch importと同じ運用パターン、`docs/runbooks/Character_Profile_Wiki_Import.md`参照）。

---

# 3. DECファイル配置とDKB正規IDの分離方針

`Identifier_Specification.md` §2.4は「タイトルをIDに含めない」方針を定めている。本設計はこれをさらに一段階手前まで拡張し、**ファイル配置そのものもDKB正規IDに直接反映させない**方針を取る。

- raw DECファイルのディレクトリ名・ファイル名は、ゲーム側のエクスポート命名規則に従う（DKBが制御できない）
- `storyId`/`episodeId`は、raw配置から**機械的に導出可能な部分のみ**を使い、人間が読みやすい正規形に変換する
- 表示用タイトル・サブタイトルはraw配置にもDEC本文にも含まれていない可能性が高いため、`story_manifest.yaml`側で別途保持し、DECファイルからは推測しない（§11）

---

# 4. raw DEC layout supported pattern

以下の配置を正式にsupported patternとして記録する。

**ユーザーのローカル配置（Windows、バックスラッシュ区切り）:**

```text
EVENT\csl_script_event_250626_dancer_export\CAB-csl_script_event_250626_dancer-episode1.dec
EVENT\csl_script_event_250626_dancer_export\CAB-csl_script_event_250626_dancer-episode2.dec
```

**DKB内部での正規化後（スラッシュ区切り、§5）:**

```text
EVENT/csl_script_event_250626_dancer_export/CAB-csl_script_event_250626_dancer-episode1.dec
EVENT/csl_script_event_250626_dancer_export/CAB-csl_script_event_250626_dancer-episode2.dec
```

**この配置から自動推定してよいもの:**

| 項目 | 値 | 由来 |
|---|---|---|
| category（正規化前） | `EVENT`（先頭ディレクトリ名） | パス構造 |
| category（正規化後） | `event` | `EVENT` → 小文字化（§6） |
| sourceKey | `250626_dancer` | `csl_script_event_{sourceKey}_export`ディレクトリ名から抽出（§7） |
| storyId | `EVT_250626_DANCER` | `EVT_{sourceKeyを大文字化}`（§8） |
| episodeNumber | `1` / `2` | ファイル名末尾`-episode{N}.dec`から抽出（§10） |
| episodeId | `EVT_250626_DANCER_E01` / `EVT_250626_DANCER_E02` | `{storyId}_E{episodeNumber:02d}`（§9） |
| sourceFileName | `CAB-csl_script_event_250626_dancer-episode1.dec` | ファイル名そのまま |
| rawPath | `EVENT/csl_script_event_250626_dancer_export/CAB-csl_script_event_250626_dancer-episode1.dec` | 正規化済み相対パス |

**この配置から自動推定しないもの（§11で詳述）:**

- 公式イベントタイトル
- エピソードごとのサブタイトル
- 表示用タイトル
- 章タイトル
- AI要約タイトル

---

# 5. パス正規化方針

- Windows上のバックスラッシュ区切り（`\`）は、DKB内部（`story_manifest.yaml`の`rawDirectory`/`rawPath`、および将来の`scripts/normalize_story.py`連携）では常にスラッシュ区切り（`/`）へ正規化する
- `rawDirectory`/`rawPath`は、DECファイル群のraw rootディレクトリ（例: `--raw-root`で指定したローカルパス）からの**相対パス**として保持する。ローカル絶対パス（`C:\Users\...`等）は保持しない（既存の「ローカル絶対パスを含む結果ファイルはcommitしない」ルール、`docs/runbooks/Real_Data_Dry_Run.md` §3と同じ方針）
- パス比較・マッチングは、正規化後のスラッシュ区切り文字列に対して行う

---

# 6. category正規化方針

raw配置の先頭ディレクトリ名（ユーザー環境での慣習、大文字）と、DKB内部の正規化カテゴリ（`agents/parser/exporter.py`の`_category_to_subdir`が使う語彙、小文字）の対応は以下の通りとする。

| raw先頭ディレクトリ名（想定） | 正規化category | storyId prefix | このPRでの自動推定対応状況 |
|---|---|---|---|
| `EVENT` | `event` | `EVT` | **対応（§4で確認済みのパターン）** |
| `MAIN` | `main` | `MAIN` | 未対応。`docs/runbooks/Real_Data_Dry_Run.md`のサンプルでは`MAIN_S01_C02_E01.dec`のようにDECファイル名自体が既に最終storyId形式であり、`EVENT`と同じ`_export`ディレクトリ規約に従うかは未確認（§18 OD-002） |
| `RAID` | `raid` | `RAID` | 未対応。`EVENT`と同じゲームエクスポート由来なら同型の可能性が高いが、実際のraw配置未確認のため今回は決め打ちしない（§18 OD-002） |
| `OTHER` | `other` | `OTHER` | 未対応（同上） |
| `CHARACTER`（想定） | `character` | `CHAR_MAIN`/`CHAR_EXTRA`/`CHAR_DATE`のいずれか | **未対応。** キャラクターストーリーは3種類のstoryId prefixに分かれる（`Identifier_Specification.md` §4.6-4.8）ため、raw配置だけからどのprefixかを機械的に判定する方法が未確認（§18 OD-003） |

**このPR（`story manifest design`）で候補生成scriptが実際に対応するのは`EVENT`カテゴリのみ**である。他カテゴリは、実際のraw配置を確認してから対応を追加する（Non-goals、§19）。

---

# 7. sourceKey抽出方針

`sourceKey`は、`_export`ディレクトリ名から`csl_script_{category}_`プレフィックスと`_export`サフィックスを除いた部分とする。

```text
csl_script_event_250626_dancer_export
         └────────┬────────┘
                sourceKey = "250626_dancer"
```

`sourceKey`はDKB正規ID（`storyId`）の材料であり、それ自体はタイトルではない（`Identifier_Specification.md` §2.4「タイトルをIDに含めない」の精神を踏襲）。ファイル名側（`CAB-csl_script_event_250626_dancer-episode1.dec`）にも同じ`sourceKey`が含まれるため、両者が一致することをscript側で確認する（一致しないファイルは「認識できないファイル」として候補生成対象外とし、無視も含め報告する。§16）。

---

# 8. storyId生成方針

`storyId`は`EVT_{sourceKeyを大文字化}`とする。

```text
sourceKey: 250626_dancer
storyId:   EVT_250626_DANCER
```

## 8.1 `Identifier_Specification.md` §4.3との関係（重要な相違点）

`Identifier_Specification.md` §4.3は、イベントストーリーIDを`EVT_{eventNumber}`（例: `EVT_0162`、数値の管理番号）と定義している。本設計が導出する`EVT_{SOURCE_KEY}`（例: `EVT_250626_DANCER`）は、**数値の`eventNumber`ではなくraw配置由来の`sourceKey`をそのまま使う点で異なる**。

これは意図的な設計判断であり、以下の理由による。

- `Identifier_Specification.md` §10 OD-002は「イベント番号の基準」自体が未確定事項として残っている（推奨: 初期段階では手動管理の安定したイベント順を使用する）
- `sourceKey`はraw配置から機械的かつ安定して導出できる（`Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」の「安定性」に資する）のに対し、`eventNumber`（連番）は人間が採番方針を決めるまで存在しない
- `story_manifest.yaml`の`metadataStatus: pending`は、このstoryIdが**まだ人間確認前の候補**であることを明示する（`Canonical_ID_Policy.md`の「名前一致だけでcanonicalIdを自動確定しない」という既存の慎重な運用方針を、Story ID領域でも踏襲したもの）

**本PRはこの相違を解消しない。** `EVT_{sourceKey}`形式を候補IDとしてそのまま採用し続けるか、人間確認時に`EVT_{eventNumber}`形式へ改めて採番し直すかは、`docs/runbooks/Character_Dictionary_Review.md`のconfirmed化運用に相当する将来の人間レビュー時に判断する未確定事項として残す（§18 OD-001）。

---

# 9. episodeId生成方針

`episodeId`は`{storyId}_E{episodeNumber:02d}`とする（`Identifier_Specification.md` §5.1のEpisode ID形式に準拠、2桁ゼロ埋め）。

```text
storyId:       EVT_250626_DANCER
episodeNumber: 1
episodeId:     EVT_250626_DANCER_E01
```

---

# 10. episodeNumber数値ソート方針

ファイル名末尾の`-episode{N}.dec`から`N`を**整数として**抽出する。文字列としての辞書順ソートではなく、数値としてソートする。

```text
episode1.dec, episode2.dec, episode10.dec
→ 数値ソート: 1, 2, 10 (正しい順序)
→ 文字列ソート: 1, 10, 2 (誤った順序、採用しない)
```

`episodeNumber`は1始まりの整数（schema上`minimum: 1`）。ゼロ埋めはID生成時（`E{episodeNumber:02d}`）にのみ行い、`episodeNumber`フィールド自体は整数値のまま保持する。

---

# 11. title / subtitle / displayTitle の扱い

## 11.1 DECから自動推測しない方針

`title`（ストーリータイトル）・`subtitle`（エピソードサブタイトル）は、**raw配置（ディレクトリ名・ファイル名）からもDEC本文からも自動推測しない**。

理由:

- raw配置由来の`sourceKey`（例: `250626_dancer`）は識別用の材料であり、公式タイトルの表記そのものではない（略称・コードネームである可能性が高い）
- サブタイトルはDECファイル内に含まれていない可能性が高い（ユーザーからの既知情報）
- AIによる本文推測タイトルを公式情報と混同すると、`Character_Profile_Dictionary_Design.md` §3で確立した「公式情報とAI推定情報を分離する」既存方針に反する

## 11.2 null許容

`story_manifest.yaml`の`title`/`displayTitle`（ストーリー単位）、`subtitle`/`displayTitle`（エピソード単位）は、すべて`null`を許容する（schema上`oneOf: [string, null]`）。人間入力または将来の外部一覧import（`story title/subtitle import`タスク）でのみ値を設定する。

## 11.3 displayTitleの組み立て

`displayTitle`が`null`の場合、Wiki側は`storyId`/`episodeId`、または「第{episodeNumber}話」のような機械的な表記でfallback表示する（§15）。`displayTitle`が設定されている場合はそれを優先する。`title`/`subtitle`から`displayTitle`を自動組み立てするロジックは、このPRでは実装しない（設計のみ）。

---

# 12. metadataStatus方針

`story_manifest.yaml`の各エントリ（ストーリー単位・エピソード単位ともに）は、`metadataStatus`を持つ。

| 値 | 意味 |
|---|---|
| `pending` | 候補生成スクリプトが機械的に導出した状態。人間未確認 |
| `confirmed` | 人間がtitle/subtitle等を確認・入力済み |
| `title_unknown` | 人間が確認した結果、公式タイトル自体が不明・非公開と判断された（`pending`のまま放置されている状態と区別するための明示的な状態） |
| `deprecated` | 廃止・重複等により無効化されたエントリ |

`character_profiles.yaml`の`status`（`draft`/`confirmed`/`deprecated`）と役割は近いが、「タイトル不明であることが判明済み」という状態（`title_unknown`）を独自に持つ点が異なる（raw配置からの機械的な候補生成が前提のため、`pending`のまま長期間残ることが多く、それと「調べたが本当に分からない」を区別する必要があるため）。

---

# 13. schema

`schemas/story_manifest.schema.json`（本PRで追加）を参照。ルート構造は以下の通り。

```yaml
schemaVersion: "0.1.0"
documentType: "story_manifest"
stories:
  - storyId: "EVT_250626_DANCER"
    category: "event"
    sourceKey: "250626_dancer"
    title: null
    displayTitle: null
    metadataStatus: "pending"
    rawDirectory: "EVENT/csl_script_event_250626_dancer_export"
    notes: null
    episodes:
      - episodeId: "EVT_250626_DANCER_E01"
        episodeNumber: 1
        subtitle: null
        displayTitle: null
        rawPath: "EVENT/csl_script_event_250626_dancer_export/CAB-csl_script_event_250626_dancer-episode1.dec"
        sourceFileName: "CAB-csl_script_event_250626_dancer-episode1.dec"
        metadataStatus: "pending"
        notes: null
```

合成データのみの完全なテンプレート例は`docs/templates/story_manifest_template.yaml`を参照（§16、実イベント名は使わない）。

---

# 14. parser/normalizerとの連携方針（将来方針、このPRでは未実装）

- 将来的に`scripts/normalize_story.py`は、`--story-id`/`--episode-id`/`--category`/`--story-title`/`--episode-title`を**手動指定する代わりに**、`story_manifest.yaml`と`--input`のrawPathを突き合わせて自動解決できるようにする（例: `--manifest story_manifest.yaml`のような任意引数を将来追加する）
- **manifestが提供する責務**: `storyId`/`episodeId`/`category`/`title`/`subtitle`/`rawPath`の対応
- **parserが担う責務**: DEC本文を読み、Block/Scene/Dialogue等の構造化（変更なし）
- **優先順位**: rawPathがmanifestに存在する場合はmanifest側の値を優先する。manifestに無い、またはmanifest自体が指定されない場合は、既存の手動`--story-id`/`--category`指定、またはファイル名からの推定ロジック（未実装、将来検討）をfallbackとして使う
- **`subtitle`はparserがDEC本文から推測しない**（§11.1の方針をparser側にも適用する）。parserはmanifestが持つ`subtitle`値をそのまま`episodeSubtitle`（`Story_Metadata.md` §4.1）へ転記するだけに留める

**本PRでは`agents/parser/`・`scripts/normalize_story.py`のコード変更は一切行わない。** 上記は将来PR（`normalize_story manifest integration`）のための設計メモである。

---

# 15. Wiki出力との連携方針

`docs/architecture/07_Wiki/Wiki_Output_Design.md`に以下を軽微追記する（本PRでの追記内容）。

- Episode pageのtitle/subtitleは、将来的に`story_manifest.yaml`由来の値（Normalized Story JSONの`metadata.episodeTitle`/`episodeSubtitle`経由、`Story_Metadata.md`参照）を使う
- `subtitle`が設定されている場合は表示する
- `subtitle`が無い場合（`null`）は、`episodeId`または「第{episodeNumber}話」のような機械的表記でfallback表示する
- AI-generated titleは、公式`title`/`subtitle`とは明確に別扱いとする（`Wiki_Output_Design.md` §3の情報分離方針、既存のAI analysis page区分をそのまま踏襲）
- `metadataStatus: pending`のエントリ由来のページでは、必要に応じて「タイトル未確認」等の注意表示を検討してよい（このPRでは表示ロジック自体は実装しない）

**本PRでは`agents/wiki_generator/renderer.py`の大改修は行わない。**

---

# 16. 候補生成script

`scripts/build_story_manifest_candidates.py`（本PRで追加）は、ローカルのraw DEC配置（`EVENT`カテゴリのみ、§6）から`story_manifest.yaml`候補を機械的に生成するCLIである。

- `--raw-root <path>`: raw DECファイル群のルートディレクトリ（例: `EVENT/`の親ディレクトリ）
- `--output <path>`: 生成したmanifest候補（YAML）の書き出し先（省略時は件数サマリーのみ表示し書き出さない）
- `--quiet`: 進捗メッセージを抑制する

動作:

1. `--raw-root`直下の`EVENT`ディレクトリ（大文字小文字を区別しない）を探す
2. `EVENT`直下の各サブディレクトリ名が`csl_script_event_{sourceKey}_export`パターンに一致するか確認する
3. 一致するディレクトリ内の`.dec`ファイルのうち、`CAB-csl_script_event_{sourceKey}-episode{N}.dec`パターン（ディレクトリ名と同じ`sourceKey`を持つもの）に一致するファイルを収集する
4. `episodeNumber`を数値としてソートする（§10）
5. `storyId`/`episodeId`を機械的に組み立てる（§8-9）
6. `title`/`subtitle`/`displayTitle`は常に`null`、`metadataStatus`は常に`pending`とする
7. `rawDirectory`/`rawPath`は`--raw-root`からの相対パスとし、スラッシュ区切りへ正規化する（§5）

**このscriptはDEC本文を一切読まない**（ファイル名・ディレクトリ名の文字列処理のみ）。合成fixture（テスト内で`tmp_path`に空の`.dec`ファイルを作成）のみでテストする（§17）。

---

# 17. 実DEC・実manifestはcommitしない方針

- 実DECファイル自体（`data/raw/**/*.dec`）は既存の`.gitignore`ルールでcommit対象外（`docs/runbooks/Real_Data_Dry_Run.md` §3と同じ）
- `scripts/build_story_manifest_candidates.py --output`で生成した実データ由来のmanifest候補は、本PRで`.gitignore`に追加する`workspace/story_manifest/`・`story_manifest_candidates_*.yaml`・`story_manifest_candidates_*.json`パターンでcommit対象外にする（§19）
- `docs/templates/story_manifest_template.yaml`は完全な合成データのみで構成し、実イベント名・実ファイル名・実storyIdは一切使わない

---

# 18. 未確定事項

## OD-001: `EVT_{sourceKey}`と`EVT_{eventNumber}`の関係

§8.1で述べた通り、raw配置から機械的に導出する`EVT_{sourceKey}`（候補ID、`metadataStatus: pending`）と、`Identifier_Specification.md` §4.3が定める`EVT_{eventNumber}`（連番の管理ID）の関係を、人間が最終的にどう確定するかは未確定。

候補:

- `EVT_{sourceKey}`をそのままconfirmed後のcanonical storyIdとして採用する（`sourceKey`が既に十分安定しているため）
- confirmed時に`EVT_{eventNumber}`へ改めて採番し直し、`sourceKey`は`notes`または将来の`aliases`相当のフィールドへ退避する

推奨: 初期段階では前者（`EVT_{sourceKey}`をそのまま採用）を仮運用し、実際に複数イベントのmanifestが揃った時点で改めて判断する。

## OD-002: MAIN/RAID/OTHERカテゴリのraw配置規約

`EVENT`と同じ`csl_script_{category}_{sourceKey}_export`規約に従うかどうかが未確認（§6）。実際のraw配置サンプルが得られ次第、本文書と候補生成scriptを拡張する。

## OD-003: CHARACTERカテゴリのstoryId prefix判定

`CHAR_MAIN`/`CHAR_EXTRA`/`CHAR_DATE`のうちどれに該当するかを、raw配置だけから機械的に判定する方法が未確認（§6）。実際のraw配置サンプルが得られ次第、判定ロジックを設計する。

## OD-004: displayTitle自動組み立てロジック

`title`/`subtitle`から`displayTitle`を自動組み立てするフォーマット（`Story_Metadata.md`の`displayTitle`例「第1期 第2章「異形生物対策班、始動！」」に相当するイベント版の表記）は未確定。人間確認時にmanifest側で直接指定する運用を当面継続する。

---

# 19. Non-goals

本PRでは以下を**スコープ外**とする。

- 実DECファイルのcommit
- 実データ由来`story_manifest.yaml`のcommit
- rawPath実一覧のcommit
- 実タイトル・実サブタイトルのcommit
- DEC本文からsubtitleを推測する処理の実装
- AIによるタイトル生成
- `agents/parser/`・`scripts/normalize_story.py`の大改修（`--manifest`引数の実装含む、将来PR）
- `agents/wiki_generator/renderer.py`の大改修（title/subtitle表示ロジックの実装含む、将来PR）
- 実データのnormalize/merge/render実行
- GitHub Pages / Cloudflare Pages公開
- Knowledge Graph生成
- LLM/provider/prompt実装
- MAIN/RAID/OTHER/CHARACTERカテゴリのraw配置規約確定（OD-002/OD-003）

---

# 20. 参照

- `docs/architecture/05_Parser/Identifier_Specification.md`（Story ID/Episode ID形式の基本定義、§4.3のEVT形式との相違点は§8.1参照）
- `docs/architecture/05_Parser/Story_Metadata.md`（storyTitle/episodeTitle/subtitle等のメタデータ定義、Normalized Story JSON側の既存スキーマ）
- `docs/architecture/06_AI/Canonical_ID_Policy.md`（「名前一致だけでcanonicalIdを自動確定しない」という慎重な運用方針、本設計の`metadataStatus: pending`の考え方の元）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Episode pageのtitle/subtitle表示方針、§15で軽微更新）
- `schemas/story_manifest.schema.json`（本PRで追加したschema実装）
- `docs/templates/story_manifest_template.yaml`（合成データのみのテンプレート例）
- `scripts/build_story_manifest_candidates.py`（本PRで追加した候補生成script）
- `docs/runbooks/Real_Data_Dry_Run.md`（実DECファイルの既存commit禁止ルール）
