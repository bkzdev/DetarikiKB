# Story ID Policy Review（Story ID / Episode ID / URL path方針レビュー）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/05_Parser/Story_ID_Policy_Review.md`

---

# 1. 目的

この文書は、`storyId`/`episodeId`/Wiki URL・ファイル名の**現行方針をレビューし**、公開Wiki化の前に仕様変更が必要かどうかを判断できる材料を整理する。

**本PRではID生成ロジックを変更しない。URL/file pathも変更しない。** 既存schema・既存fixture・既存実装は無変更のまま、実データ小規模サンプルを踏まえた設計レビューのみを行う。

---

# 2. 背景

- `Identifier_Specification.md` §4.3は、イベントストーリーIDを`EVT_{eventNumber}`（数値の管理番号、例: `EVT_0162`）と定義している
- `Story_Manifest_Design.md`（PR #56）は、raw DEC配置から機械的に`storyId`/`episodeId`を導出する`EVT_{sourceKey}`形式（例: `EVT_250626_DANCER`）を採用した。これは`Identifier_Specification.md` §4.3と**意図的に異なる**形式であり、`Story_Manifest_Design.md` §8.1・§18 OD-001で既に「未確定事項」として明記されている
- `feature/wiki-story-index-link-text-improvement`（PR #69）で、Story index/Episode pageの**表示テキスト**はdisplayTitle優先の人間向け表示に改善された
- しかし、**URL・Markdownファイル名・内部ID自体**には引き続きsourceKey由来の長いIDがそのまま使われている（例: `stories/EVT_250626_DANCER_E01.md`）
- 公開Wiki化を検討する前に、このURL/ID方針をこのまま維持してよいか、変更すべきかを判断する必要がある

---

# 3. 現行仕様の整理

## 3.1 MAIN

- 仕様: `Identifier_Specification.md` §4.1/§4.2。`MAIN_S{season}_C{chapter}` / `MAIN_S{season}_C{chapter}_E{episode}`
- 実装状況: **手動指定のみ**。`scripts/normalize_story.py`の`--story-id`/`--episode-id`を人間が明示的に渡す運用（`story_manifest.yaml`によるMAINカテゴリの自動候補生成は未実装、`Story_Manifest_Design.md` §6 OD-002）
- 実データ配置規約: 未確認（後述§4.4）

## 3.2 EVENT

- 仕様: `Identifier_Specification.md` §4.3が定義する`EVT_{eventNumber}`（数値管理番号）と、`Story_Manifest_Design.md` §8が実装した`EVT_{sourceKey}`（raw配置由来のslug）の**2種類の設計が併存**している
- 実装状況: **`EVT_{sourceKey}`形式が実装済み**（`agents/parser/story_manifest_candidates.py` `build_story_manifest_candidate`）。`storyId = f"EVT_{source_key.upper()}"`、`episodeId = f"{storyId}_E{episodeNumber:02d}"`
- `sourceKey`抽出: `EVENT/csl_script_event_{sourceKey}_export/`ディレクトリ名の正規表現一致（`_EXPORT_DIRECTORY_PATTERN`）、ファイル名側`CAB-csl_script_event_{sourceKey}-episode{N}.dec`との一致確認あり（不一致ファイルは候補から除外、`Story_Manifest_Design.md` §7）
- title/subtitle: 候補生成時は常に`null`、`metadataStatus: pending`固定。人間確認後に`story_manifest.yaml`へ反映する運用（未実施、`Story_Manifest_Design.md` §11.7）
- manifestの役割: raw配置⇔正規ID⇔title/subtitleの対応表。`storyId`/`episodeId`自体の生成ロジックは`agents/parser/story_manifest_candidates.py`側にあり、manifestは「候補として記録された結果」を保持するのみ（IDの再割り当て機構は無い）
- schema上の制約: `schemas/story_manifest.schema.json`の`storyId`/`episodeId`パターンは`^[A-Z][A-Z0-9_]*$`のみで、**長さ上限は無い**

## 3.3 RAID

- 仕様: `Identifier_Specification.md` §4.4。`RAID_{raidNumber}`
- 実装状況: **未実装**。候補生成・manifest対応ともに無し（`Story_Manifest_Design.md` §6 OD-002、EVENTと同じraw配置規約に従うかも未確認）

## 3.4 OTHER

- 仕様: `Identifier_Specification.md` §4.5。`OTHER_{number}`
- 実装状況: **未実装**（RAIDと同様）

## 3.5 CHARACTER（CHAR_MAIN / CHAR_EXTRA / CHAR_DATE）

- 仕様: `Identifier_Specification.md` §4.6-4.8。`CHAR_MAIN_{characterId}_E{episode}`等
- 実装状況: **未実装**。raw配置だけからCHAR_MAIN/CHAR_EXTRA/CHAR_DATEのどれに該当するかを機械的に判定する方法が未確認（`Story_Manifest_Design.md` §6 OD-003）

---

# 4. 実データサンプル観察結果（匿名化）

ローカルに実際に存在する少数の実データサンプル（既存の`workspace/local_inputs/manual_review_001`・`manual_review_002`のEVENT実データ2件、および互換性チェック用の`data/raw/dry_run/`配下の実ファイル名6件）から観察した。**実sourceKey・実イベント名・実ファイル名は一切記載しない**。件数もこのローカル環境で確認できた範囲に限られ、母集団全体を代表するものではない。

## 4.1 EVENTカテゴリ（`EVENT/csl_script_event_{sourceKey}_export/`規約に一致する実サンプル、5件）

| サンプル | sourceKey文字数 | storyId文字数 | episodeId文字数 | URL文字数（`stories/{episodeId}.md`） | episode数 |
|---|---:|---:|---:|---:|---:|
| EVENT sample A | 20 | 24 | 28 | 39 | 2 |
| EVENT sample B | 20 | 24 | 28 | 39 | 2 |
| EVENT sample C | 20 | 24 | 28 | 39 | (folder規約外、filename規約のみ一致) |
| EVENT sample D | 17 | 21 | 25 | 36 | (同上) |
| EVENT sample E | 20 | 24 | 28 | 39 | (同上) |

観察:

- sourceKeyは概ね17〜20文字（`{YYMMDD}_{slug}`形式、日付6桁+アンダースコア+slug）。極端に短い／長い外れ値は今回のサンプルには無かった
- サンプルA/Bはfolder名（`_export`ディレクトリ）とfile名の両方でsourceKeyが一致しており、`build_story_manifest_candidate`のfolder/file一致チェックを問題なく通過した（folder/file不一致による候補除外は今回発生しなかった）
- slug部分は英字（ローマ字化されたイベント固有名詞）で構成されており、人間がある程度意味を推測できる場合もあれば、判別しにくい略称の場合もある
- 日付部分（先頭6桁）は同一イベント内の全episodeで安定していた（当然だが、episode単位で日付が変わることは無い）
- episodeNumber抽出（`-episode{N}`からの数値抽出）は今回のサンプルでは全件安定して成功した
- **今回のサンプル数（5件）ではsourceKey collisionは観測されなかった**が、これは母集団全体でcollisionが起きないことを意味しない（同日開催の類似イベント名がある場合のリスクは§6で後述）

## 4.2 EVENT以外のカテゴリ（`data/raw/dry_run/`のファイル名パターン、6件）

`data/raw/dry_run/`は互換性チェック用に配置された実ファイルで、`EVENT/{sourceKey}_export/`という正式なraw配置規約には従っていない（フラット配置）。ファイル名の構造を見るだけでも、以下の重要な観察が得られた。

- **MAIN相当のファイルは`-episode{N}`ではなく`-main{N}`という別のsuffix規約を使っていた**。これは単に category prefixが違うだけでなく、**episode番号を示すsuffix文字列自体が規約ごとに異なる**ことを意味する。現行の`_EPISODE_FILE_PATTERN`（`-episode(?P<episode_number>\d+)\.dec`固定）はMAINには適用できない
- **CHARACTER相当と見られるファイルには`charastory_{key}`という別のprefixがあり、`{key}`部分が既に数字を含む識別子的な文字列だった**（slugというより構造化IDに近い見た目）。EVENTの「日付+slug」パターンとは性質が異なる
- **`surprise_{key}`という、現行`Identifier_Specification.md`の7種プレフィックス（MAIN/EVT/RAID/OTHER/CHAR_MAIN/CHAR_EXTRA/CHAR_DATE）のどれにも明確に対応しないraw category名も観測された**。これは「実データのraw category語彙が、現行の設計ドキュメントが想定する7分類より多い可能性」を示す具体的な根拠である
- **`_export`サフィックスの有無・`-episode{N}`/`-main{N}`/`_{N}`のsuffix規約は、raw category語彙ごとに異なっていた**（EVENTだけを見て一般化できない）
- **1件、スペースと`#`記号を含む非定型のファイル名も確認された**（`CAB-csl_script_...`という定型パターンに一切従わない）。このようなファイルは現行の正規表現ベース抽出では一致せず、候補生成対象外になる。将来的にmanifestへ人間が直接エントリを追加する「エスケープハッチ」が必要になる具体例

**重要な注記**: `data/raw/dry_run/`は互換性チェック用の少数サンプルであり、正式なraw配置規約に従っていない。上記の観察は「MAIN/RAID/OTHER/CHARACTERの正式なraw配置規約がまだ判明していない」（`Story_Manifest_Design.md` §18 OD-002/OD-003）という既知の未確定事項を、実際のファイル名多様性の観点から補強するものである。

---

# 5. 問題点の具体化

実データ観察を踏まえ、現行のEVENT ID方針（`EVT_{sourceKey}`をそのままstoryId/episodeId/URLに使う）には以下の問題点がある。

1. **URLとして長い**: `stories/{episodeId}.md`が36〜39文字（サンプル観察）。将来、より長いイベント名のsourceKeyが来た場合はさらに伸びる。公開URLとして特別に長すぎるとまでは言えないが、短縮の余地はある
2. **slugが公開URLにそのまま出る**: raw配置のディレクトリ・ファイル命名という「ゲーム運営側の内部事情」が、Wiki公開URLにそのまま反映される。ゲーム側の命名規則変更・表記揺れの影響を受けやすい
3. **sourceKey変更への耐性が無い**: 現行方式はsourceKeyそのものがstoryIdの一部であるため、ゲーム側が同一イベントの再配布時にディレクトリ名を変える等した場合、storyIdが変わってしまう（`Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」という安定性原則に反するリスク）
4. **同日複数イベントでのcollisionリスク**: 日付+slugの組み合わせが偶然重複する可能性は理論上排除できない（今回のサンプルでは未観測だが、母集団全体を確認したわけではない）
5. **他カテゴリへの拡張性が不明**: MAIN/RAID/OTHER/CHARACTERは、EVENTと同じ「日付+slug」パターンに従うと決め打ちできない（§4.2の観察）。カテゴリごとに個別のID生成ロジックが必要になる可能性が高い
6. **title/subtitle未確定時の表示はPR #69で解決済みだが、URLは未解決のまま**: 表示層（Story index/Episode page）は既に改善済みのため、「表示は分かりやすいがURLは長いまま」という状態が残っている

---

# 6. 比較するID案

## 案A: 現行維持（`EVT_{sourceKey}`）

```text
storyId:   EVT_250626_DANCER
episodeId: EVT_250626_DANCER_E01
URL:       stories/EVT_250626_DANCER_E01.md
```

- 長所: sourceKeyとの対応が明確、raw fileとの追跡がしやすい、eventNumberが無くても機械的に生成できる、既存実装と完全互換（追加実装コスト無し）
- 短所: URLが長くなりやすい、slugが公開URLに出る、raw配置由来の内部事情が見える、sourceKey変更に弱い

## 案B: date + sequence

```text
storyId:   EVT_250626_001
episodeId: EVT_250626_001_E01
URL:       stories/EVT_250626_001_E01.md
```

- 長所: URLが短い、source slugが露出しにくい、同日複数イベントに対応可能
- 短所: sequence（`001`等）の採番管理が必要、manifestでstable mappingを持つ必要がある、raw fileとの対応はsourceKeyを別フィールドで保持する必要がある、自動生成だけでは同日内のcollision対策（採番順の決定方法）が必要

## 案C: manifest-assigned stable ID

```text
storyId:   EVT_000123
episodeId: EVT_000123_E01
```

- 長所: 最も安定しやすい（raw namingの変化に一切影響されない）、URLが最も短い、raw namingに依存しない
- 短所: ID割当を人間または別の採番システムが管理する必要がある、初期投入コストが高い、manifestが実質必須になる、人間レビュー負荷が増える

## 案D: category-specific policy

```text
MAIN:  MAIN_S01_C02_E01        （既存のまま）
EVENT: EVT_YYYYMMDD_001_E01    （案Bの短縮形）
RAID:  RAID_YYYYMMDD_001_E01
CHAR:  CHARSTORY_{characterId}_E01
```

- 長所: カテゴリごとに自然なID形式にできる、MAIN/CHARACTERは既に意味のある構造にしやすい、EVENT/RAIDは短縮可能
- 短所: 仕様全体が複雑になる、helper/test/schemaがカテゴリ数だけ増える、docsの説明コストが増える

---

# 7. 評価表

評価: ◎ 優れる / ○ 普通 / △ やや弱い / × 弱い（相対比較であり絶対評価ではない）

| 評価軸 | 案A 現行維持 | 案B date+sequence | 案C manifest-assigned | 案D category-specific |
|---|---|---|---|---|
| URLの短さ | △ | ○ | ◎ | ○（カテゴリによる） |
| 公開Wikiとしての見た目 | △ | ○ | ◎ | ○ |
| raw data traceability | ◎ | ○（別フィールド保持で維持可） | △（manifest必須） | ○ |
| IDの安定性 | △ | ○ | ◎ | ○ |
| sourceKey変更への耐性 | × | ○ | ◎ | ○ |
| title/subtitle変更への耐性 | ◎（既にID非依存） | ◎ | ◎ | ◎ |
| eventNumber不明時の扱いやすさ | ◎（不要） | △（採番待ちが発生しうる） | ×（割当必須） | △〜×（カテゴリによる） |
| 同日複数イベント対応 | ○（slugが違えば区別可） | △（採番ルールが必要） | ◎ | △〜◎ |
| collision防止 | △ | ○ | ◎ | ○ |
| manifest管理コスト | ◎（低い） | △ | × | △ |
| 既存実装への影響 | ◎（無し） | △（生成ロジック変更） | ×（大幅変更） | ×（最大） |
| migrationコスト | ◎（無し） | △（既存storyId変更） | ×（全件再割当） | ×（最大） |
| MAIN/RAID/OTHER/CHARACTERへの拡張性 | △ | ○ | ○ | ◎ |
| 人間レビュー負荷 | ◎（低い） | ○ | ×（高い） | △ |
| 将来の外部リンク安定性 | △ | ○ | ◎ | ○ |

---

# 8. 推奨方針

## 8.1 結論

**今すぐ案A〜Dのいずれかへ全面移行することは推奨しない。** 実データサンプル数が少なく（EVENT 5件相当）、MAIN/RAID/OTHER/CHARACTERのraw配置規約自体が未確認（§4.2）のままカテゴリ横断の仕様を決め打ちするのはリスクが高い。

## 8.2 段階的な推奨方針

- **短期（このPR以降、実装は次PR）**: `story_manifest.yaml`に、`storyId`/`episodeId`（現行のsourceKey由来ID、raw traceability用）とは**別に**、将来のWiki公開用ID（`publicStoryId`/`publicEpisodeId`等、案名は次PRで確定）を任意フィールドとして設計する余地を作る。**この分離設計自体は今回実装しない**（Non-goals参照）。まずは「storyId ＝ 内部trace ID」と「公開URL用ID」を将来分離できるという方針だけをdocs上で明文化する
- **中期**: EVENT/RAIDについて、`EVT_{sourceKey}`のまま運用を続けるか、案B（date+sequence）へ移行するかを、より多くの実データサンプル（複数カテゴリ・同日複数イベントの実例を含む）が揃った時点で判断する。判断にあたっては、実際に同日複数イベントが発生するか、sourceKeyの命名がどれだけ安定しているかを追加確認する
- **長期**: 公開Wikiとして外部リンクの安定性を最優先する段階になった時点で、案C（manifest-assigned stable ID）または案D（category-specific policy）の本格導入を再検討する。この判断は`public-publishing-platform-evaluation`（Backlog）と合わせて行うのが自然

## 8.3 raw traceabilityの保持

いずれの案を採用する場合でも、`sourceKey`/`rawPath`/`sourceFileName`は`story_manifest.yaml`側にそのまま保持し続ける（既存方針を変更しない）。**storyId/episodeIdが将来短縮・再設計されても、raw fileへのtraceabilityは失わない**という原則を維持する。

## 8.4 MAIN方針への影響

MAINの既存`MAIN_S{season}_C{chapter}_E{episode}`形式は変更不要という仮説を支持する（実データ観察でも、MAINは既にepisode番号ベースの意味のある構造を持っており、EVENT/RAIDのような「raw配置由来の長いslug問題」を抱えていない）。

---

# 9. public URL と internal source trace ID の分離について

現行方針では、`storyId`/`episodeId`が「(1) raw fileへのtraceability」「(2) Wiki公開URL」「(3) merged knowledge collection内の内部参照キー」の3役を兼ねている。これが今回洗い出された問題の根本原因である。

**将来的には、この3役を分離できる設計を検討する価値がある。**

- (1) raw traceability: `sourceKey`/`rawPath`/`sourceFileName`（既に`story_manifest.yaml`側で保持済み、変更不要）
- (2) Wiki公開URL: 短く安定したIDが望ましい（案B/C/Dのいずれか）
- (3) 内部参照キー（evidence/candidate/merged entityの相互参照）: 現行の`storyId`/`episodeId`がそのまま使われている。この用途では長さよりも「既存データとの一貫性」が重要なため、急いで変更する理由は薄い

3つの役割を無理に1つのIDへ統合し続けると、どの要求（安定性・可読性・短さ・traceability）を優先しても他が犠牲になる。**役割ごとに異なるIDを許容する設計（例: 内部処理は現行storyId、Wiki公開URLのみ`publicStoryId`を別途持つ）を次PRで具体化することを推奨する。**

---

# 10. 次PR候補（実装しない、タスク分解のみ）

1. **story-id-policy-design-decision**: このレビュー結果を踏まえ、実際にどの案（またはハイブリッド）を採用するかを決定する設計PR（実装はまだしない）
2. **story-manifest-public-id-fields-design**: `story_manifest.yaml`に`publicStoryId`/`publicEpisodeId`（案名未確定）を任意フィールドとして追加する設計（§9の分離方針の具体化）。schema変更を伴うが、既存`storyId`/`episodeId`生成ロジックは変更しない
3. **story-id-policy-real-sample-review-002**: より多くの実データサンプル（複数カテゴリ、同日複数イベントの実例）を確認し、本レビューの仮説（sourceKey長さ、collision非発生、カテゴリごとのraw配置規約）を再検証する
4. **story-manifest-raw-layout-main-raid-other-character**: MAIN/RAID/OTHER/CHARACTERの実際のraw配置規約を確認し、`story_manifest_candidates.py`をEVENT以外にも対応拡張する（`Story_Manifest_Design.md` §18 OD-002/OD-003の解消）

---

# 11. Migration impact（もし将来ID方式を変更する場合）

このPRでは実施しないが、将来案B/C/Dのいずれかへ移行する場合に影響する範囲を記録しておく。

- `agents/parser/story_manifest_candidates.py`（storyId/episodeId生成ロジック）
- `schemas/story_manifest.schema.json`（IDパターン自体は`^[A-Z][A-Z0-9_]*$`のままで対応可能、変更不要な見込み）
- `agents/wiki_generator/paths.py`（`episode_page_path`が返すファイル名がstoryId/episodeIdに依存）
- 既存の合成fixture（`tests/fixtures/wiki/synthetic_merged_collection.json`等）のepisodeId命名は、テスト用の固定値であり実運用のID方式とは独立しているため、**移行の影響を受けない**（このPRでも変更していない）
- 実データ由来の`story_manifest.yaml`が既に人間確認・confirmed化されている場合、そのID変更は`Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」という安定性原則との兼ね合いを個別に検討する必要がある（本PR時点ではconfirmed化された実データが無いため、影響は無い）

---

# 12. Open Questions

- 実際に同日複数イベントは発生するか（母集団確認が必要、§6案Bの判断材料）
- sourceKeyの命名は運営側でどれだけ安定しているか（同一イベントの再配布・修正でディレクトリ名が変わることはあるか）
- MAIN/RAID/OTHER/CHARACTERの正式なraw配置規約はどうなっているか（`Story_Manifest_Design.md` §18 OD-002/OD-003、未解消のまま）
- 「surprise」等、現行7分類に含まれないraw category語彙をどう扱うか（新しいstoryId prefixを追加するか、既存分類へマッピングするか）
- 公開Wiki化の優先度・時期（`public-publishing-platform-evaluation`との関係）
- `publicStoryId`等の分離設計を採用する場合、Wiki renderer側の参照ロジックをどこまで変更する必要があるか

---

# 13. このPRで実装しないこと（Non-goals）

- `storyId`/`episodeId`生成ロジックの変更
- URL/file pathの変更
- 既存fixtureのID大量変更
- migration scriptの作成
- `publicStoryId`/`stableStoryId`のschema実装
- story title/subtitleの実import
- 実タイトル・実サブタイトルの投入
- 実DEC・実manifest・実Normalized Story JSON・実extraction/merged collection・実Wiki Markdownのcommit

---

# 14. 参照

- `docs/architecture/05_Parser/Identifier_Specification.md`（§4.3 EVT形式の原設計、§10 OD-002イベント番号基準の未確定事項）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（§8 storyId生成方針、§8.1 Identifier_Specification.mdとの相違点、§18 OD-001〜OD-003）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（§14 URL/slug方針）
- `agents/parser/story_manifest_candidates.py`（現行のEVENT ID生成実装）
- `agents/wiki_generator/paths.py`（Episode page URLの組み立て）
- `TASKS.md`（次PR候補の追跡）

---

# 15. 採用方針（サマリ）

- このPRではID生成ロジック・URL・file pathを一切変更しない
- 実データサンプル（EVENT 5件相当、他カテゴリのファイル名観察6件）を匿名化して記録し、現行方針の問題点を具体化した
- 4つのID案（現行維持/date+sequence/manifest-assigned/category-specific）を評価軸付きで比較した
- 推奨方針は「今すぐ全面移行しない」「raw traceability用IDと公開URL用IDの分離を次PRで設計する」という段階的アプローチ
- MAINの既存ID方針は変更不要という仮説を支持する
- 次PR候補4件をタスク分解した
