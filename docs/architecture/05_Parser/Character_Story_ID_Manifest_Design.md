# Character Story ID / Manifest Design（キャラクターストーリーのstoryId体系・manifest統合設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md`

---

# 1. 目的

Backlog `character-story-id-manifest-design`（`docs/architecture/05_Parser/Story_Manifest_Design.md` §18 OD-003・`03_Scope.md` §5.5.1で参照される保留タスク）の設計を正式文書化する。

本文書が扱うのは以下の3点である。

- `character`カテゴリ（H_scene系を含む）・`character_date`カテゴリのstoryId/episodeId体系
- H_scene系の例外変種（`03_Scope.md` §5.5で決定済みの動的部分集合判定対象）を、Phase 1の「1ファイル=1episode」前提を維持したまま内部KBへ取り込む方式
- `story_manifest.yaml`（`Story_Manifest_Design.md`）とキャラクターカテゴリの統合方針

本文書は2026-07-16のFableセッションでの実配置全量調査結果と、それに基づくユーザー決定を記録するものである。**実装（`agents/`・`scripts/`・`schemas/`・`config/`の変更）は本PRでは一切行わない。** 実装は§9の分割計画に従い、後続PRで行う。

---

# 2. 背景（03_Scope決定との関係）

`docs/architecture/01_Project/03_Scope.md`は、`character`カテゴリのH_scene系について以下を既に決定している。

- 決定1（§4.2）: H_scene系はすべて軸(A)内部KB対象・軸(B)公開対象外（恒久除外）
- 決定2（§4.3）: 実パース対象はH_sceneN本体+`H_scene_s`（589件）+本体の部分集合になっていない例外変種（最大144件、動的判定）
- §5.5決定(b): 例外変種はH_sceneN単位で動的判定し、例外が発生したもののみパース対象へ追加する
- §5.5.1: この変種取り込みは独立PRではなく、`character-story-id-manifest-design`（本文書）の要件として組み込む

一方、`Story_Manifest_Design.md` §6・§18 OD-003は「`CHARACTER`カテゴリはraw配置だけからCHAR_MAIN/CHAR_EXTRA/CHAR_DATEのどれに該当するかを機械的に判定する方法が未確認」という未決事項を残していた（実際のraw配置サンプルが得られていなかったため）。

本文書は、2026-07-16に実施された`data/raw/character/`・`data/raw/character_date/`の実配置全量調査結果をもとに、上記2つの未決事項をあわせて解消する。

---

# 3. raw配置の確認結果（2026-07-16 Fable調査）

**匿名化ルールに従い、実キャラクター名・実ローマ字ID・ローカル絶対パスは記載しない。件数とファイル名パターンのみを記録する。**

## 3.1 `data/raw/character/`

- 72ディレクトリ全件が`csl_script_charastory_character{N}_export`パターン（`{N}`は数値）
- この`{N}`は、全72件が`knowledge/dictionaries/characters.yaml`のconfirmed済み`sourceCharacterId`と一致することを機械照合済み（confirmed 184件中72件が該当）
- ファイル名は全件`CAB-csl_script_charastory_character{N}-{suffix}.dec`形式

## 3.2 `data/raw/character_date/`

- 72ディレクトリ全件が`csl_script_surprise_character{N}_export`パターン
- ファイルは全件`CAB-csl_script_surprise_character{N}-Surprise_{M}.dec`形式（859件、`M`はキャラクターごとの連番1〜13）

## 3.3 `character`カテゴリのファイル種別全量（2,419件、`.gitkeep`除く）

**パース対象確定済み（1,025件）:**

| ファイル種別 | 件数 |
|---|---|
| `episodeN` | 216 |
| `episode_EXN` | 220 |
| `H_sceneN` | 517 |
| `H_scene_s` | 72 |

**変種（H_sceneN系の接尾辞パターン）:**

| ファイル種別 | 件数 |
|---|---|
| `H_sceneN_n` | 505 |
| `H_sceneN #N` | 113 |
| `H_sceneN_spine` | 48 |
| `H_sceneN_spine #N` | 46 |
| `H_sceneN_VR` | 45 |
| `H_sceneN_n #N` | 3 |

**純コマンド/演出系ファイル:**

| ファイル種別 | 件数 | ファイル種別 | 件数 |
|---|---|---|---|
| `cameraN` | 150 | `episode_osawariN_start` | 9 |
| `cameraN #N` | 108 | `episode_osawariN_end` | 9 |
| `camera` | 25 | `camerabreastN` | 7 |
| `camera #N` | 18 | `breastN` | 7 |
| `finish #N` | 112 | `cameracrotchN` | 7 |
| `finish` | 50 | `crotchN` | 7 |
| `episode_bgmN` | 40 | `episode_ASMRN` | 6 |
| `sv_N` | 24 | `VR_N` | 4 |
| `dockingN` | 9 | `talk` | 3 |
| `cameradockingN` | 9 | `start` | 2 |
| | | `position` / `PinkMan` / `idolVR` | 各1 |

**スコープ文書（`03_Scope.md`）未記載の新発見（§4.3のパース対象範囲決定には含まれていなかった種別）:**

| ファイル種別 | 件数 |
|---|---|
| `episodeN_n` | 13 |
| `episode_osawariN_start_n` | 3 |
| `H_sceneN_img` | 7 |
| `H_scene_test` | 1 |
| `H_scene_s_tutorial` | 1 |

これらの新発見は§7.6のOpen questionsとして記録し、本文書では決定しない。

---

# 4. storyId・episodeId体系の決定（決定1）

**決定日: 2026-07-16。以下はユーザーが明示的に決定した内容であり、数値・結論はAIエージェントが変更してはならない。**

## 4.1 storyId体系

**storyId = ローマ字characterId方式を採用する。**

```text
CHAR_MAIN_{ROMAJI}
CHAR_EXTRA_{ROMAJI}
CHAR_DATE_{ROMAJI}
CHAR_HS_{ROMAJI}
```

`{ROMAJI}`は`knowledge/dictionaries/characters.yaml`のconfirmed `characterId`値から接頭辞`CHAR_`を除いた部分である（例: `characterId`が`CHAR_AKAGI_HINA`なら`{ROMAJI}`は`AKAGI_HINA`）。

**1キャラクターにつき、上記4種別のstoryをそれぞれ1つずつ持つ**（該当ファイルが存在する種別のみ）。

## 4.2 episodeId対応表

| rawファイル名パターン | episodeId形式 | 例 |
|---|---|---|
| `episode{N}.dec` | `CHAR_MAIN_{ROMAJI}_E{N:02d}` | `CHAR_MAIN_AKAGI_HINA_E01` |
| `episode_EX{N}.dec` | `CHAR_EXTRA_{ROMAJI}_E{N:02d}` | `CHAR_EXTRA_AKAGI_HINA_E01` |
| `Surprise_{M}.dec`（`character_date`） | `CHAR_DATE_{ROMAJI}_E{M:02d}` | `CHAR_DATE_AKAGI_HINA_E01` |
| `H_scene{N}.dec` | `CHAR_HS_{ROMAJI}_E{N:02d}` | `CHAR_HS_AKAGI_HINA_E06` |
| `H_scene_s.dec` | `CHAR_HS_{ROMAJI}_ES01` | `CHAR_HS_AKAGI_HINA_ES01` |

ID例はすべて`Identifier_Specification.md`既存の合成キャラクター`CHAR_AKAGI_HINA`を使用しており、実キャラクター名・実ローマ字IDではない。

## 4.3 前提条件（confirmed前提）

candidate生成の対象になるのは、対象キャラクターの`sourceCharacterId`が`knowledge/dictionaries/characters.yaml`で`confirmed`であることが前提である。未confirmedのキャラクターはcandidate生成対象外とし、pending報告として扱う。

**現時点（2026-07-16）では、`data/raw/character/`・`data/raw/character_date/`の全72キャラクターが`characters.yaml`のconfirmed 184件に含まれており、この前提を充足している。**

## 4.4 storyId固定ルール（安定性原則）

**storyIdは割当時点のcharacterId値で固定し、将来characterIdが改名されても追随しない。**

これは`Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」の安定性原則をそのまま適用したものである。`characters.yaml`の`characterId`が将来変更された場合でも、既に割り当てたキャラクターストーリーのstoryId/episodeIdは変更しない（`characterId`変更時の対応は本文書のスコープ外であり、`Character_Dictionary_Review.md`側の運用課題として扱う）。

## 4.5 Story_Manifest_Design.md OD-003の解消

**この決定により、`Story_Manifest_Design.md` §18 OD-003（CHARACTERカテゴリのraw配置だけからのprefix機械判定が未確認だった問題）は解消する。**

従来の未決事項は「raw配置（ディレクトリ名）だけからCHAR_MAIN/CHAR_EXTRA/CHAR_DATEのどれかを判定する方法が無い」というものだったが、実際には**ディレクトリ（`character`/`character_date`）とファイル名サフィックス（`episodeN`/`episode_EXN`/`Surprise_N`/`H_sceneN`/`H_scene_s`）の組み合わせで機械的に判定できる**ことが§3の全量調査で判明した。ディレクトリ名（`csl_script_charastory_character{N}_export`/`csl_script_surprise_character{N}_export`）からは`{N}`（`sourceCharacterId`）のみを抽出し、それをそのままprefixに使う判定材料にはしない（prefix自体はファイル名サフィックスから決まる）。

---

# 5. CHAR_HSカテゴリ（決定2）

**決定日: 2026-07-16。**

## 5.1 新設storyCategory

**H_scene系には、新設storyCategory `CHAR_HS`を割り当てる。**

`CHAR_HS`は内部KB専用であり、`03_Scope.md` §4.2の軸(B)恒久除外方針をそのまま引き継ぐ。既存の`CHAR_MAIN`/`CHAR_EXTRA`/`CHAR_DATE`とは異なり、`CHAR_HS`は**promotion policyがstoryCategory名だけで公開除外を機械判定できるようにする**ことを意図した新設カテゴリである。

## 5.2 将来実装が必要な変更点（本PRでは実施しない）

| 対象 | 変更内容 |
|---|---|
| `schemas/story.schema.json` | `storyCategory` enum（現行`["MAIN", "EVT", "RAID", "OTHER", "CHAR_MAIN", "CHAR_EXTRA", "CHAR_DATE"]`）へ`"CHAR_HS"`を追加 |
| `agents/parser/exporter.py` | `_category_to_subdir`のmapping（現行`CHAR_MAIN`/`CHAR_EXTRA`/`CHAR_DATE`→`"character"`）へ`"CHAR_HS": "character"`を追加 |

実装は§9のPR Dで行う。

**実装済み（`feature/hscene-variant-dynamic-judgment`、PR D）**: 上記2点をそのまま実装した。`schemas/story.schema.json`の`storyCategory` enumへ`"CHAR_HS"`を追加し、`agents/parser/exporter.py`の`_category_to_subdir`へ`"CHAR_HS": "character"`を追加した。`scripts/normalize_story.py`の`--category`選択肢にも`CHAR_HS`を追加した。合成fixtureでのschema検証テスト（`tests/parser/test_normalized_story_schema.py::test_normalized_json_char_hs_category`）を追加済み。

## 5.3 promotion除外の機械判定への効果

現行の`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §17は、H_scene系由来のstoryをpromotion対象外として扱う運用ルールを人間可読なテキストで定義しているのみで、母集団抽出段階での機械的な事前除外は「現状は運用ルールの明文化のみ」（同§17.5）と明記されている。`CHAR_HS`カテゴリが実装されれば、`storyCategory == "CHAR_HS"`という1条件でこの事前除外を機械的に実装できるようになる（実装自体はPR D以降）。

---

# 6. 例外変種の動的判定と別episode方式（決定3）

**決定日: 2026-07-16。**

## 6.1 基本方針

Phase 1の「1ファイル=1episode」前提を維持する。`03_Scope.md` §5.5.1で決定済みの動的部分集合判定方式（発話系コマンド — `@ChTalk`/`@ChTalkMono`/`@ChTalkSoundOff`/`@ChTalkSoundOffMono`/`@ChTalkName`/`@SpineTalk`および既知表記ゆれ — が参照するvoice/textアセットpath＋正規化日本語TEXT行の集合による部分集合判定）で例外と判定された変種のみ、専用suffix付きの**別episode**としてパースする。実ファイル名リストはcommitしない（`03_Scope.md` §5.5.1 (1)、`AI_PR_Playbook.md` §7）。

## 6.2 episodeId suffix規則

| 変種パターン | suffix規則 | 例（base=`CHAR_HS_AKAGI_HINA_E06`） |
|---|---|---|
| `_n`変種 | `{base}_VN` | `CHAR_HS_AKAGI_HINA_E06_VN` |
| `_spine`変種 | `{base}_VSP` | `CHAR_HS_AKAGI_HINA_E06_VSP` |
| `#K`複製（Kはファイル名の#番号） | `{base}_VD{K}` | `CHAR_HS_AKAGI_HINA_E06_VD2` |
| 複合`_n #K` | `{base}_VN_D{K}` | `CHAR_HS_AKAGI_HINA_E06_VN_D2` |
| 複合`_spine #K` | `{base}_VSP_D{K}` | `CHAR_HS_AKAGI_HINA_E06_VSP_D2` |

**`_VR`は動的判定の対象外のまま**とする。`03_Scope.md` §5.3の全量検証で`_VR`は例外0件（45/45が部分集合成立）と確認済みであり、§5.5の(b)決定も`_VR`を対象外としたまま確定している。

## 6.3 重複排除は抽出段階で実施

`03_Scope.md` §5.5.1 (2)(3)の取り込み方針に従う。

- 本体episodeの識別子集合（voice/textアセットpath＋正規化TEXT行）を正とする
- 変種episode内の重複ブロックは**抽出対象から除外マーク**するが、**normalized JSONからは削除しない**（`AI_CONTEXT.md` §3.2の不破棄不変則を維持）
- `reverse_superset`型（変種⊇本体、主に`#N`）: 本体・例外変種の両方をパースし、変種側の追加内容も本体側内容も漏れなく取り込む
- `partial_overlap`型（`_n`全件・`_spine`大半）: 本体・例外変種の両方をパースし、双方固有の内容を取り込み、共有部分をアセットpath同一性で重複排除する

具体的な重複排除ロジックの実装は§9のPR Eで行う。

**実装済み（`feature/hscene-variant-extraction-dedup`、PR E、2026-07-17）**: 上記方針を`agents/extractor/hscene_dedup.py`（新設）として実装した。詳細は§6.6を参照。

## 6.4 §5.5.1との対応

本節は`03_Scope.md` §5.5.1が要求していた5点の設計方針のうち、(1)動的判定方式・(2)(3)取り込み方針・(4)内容同一性の判定子をそのまま踏襲し、episodeId suffix規則という具体的な採番ルールを新たに追加したものである。(5)「storyId/manifest設計の一部として組み込む」という要求は、本文書自体がその設計にあたる。

## 6.5 実装状況（`feature/hscene-variant-dynamic-judgment`、PR D）

§6.1・§6.2の動的部分集合判定・episodeId suffix規則を実装した。

- **判定ロジック**: 新設`agents/parser/hscene_variant_judgment.py`。識別子集合抽出（`extract_identifier_set`、実tokenizer `agents/parser/tokenizer.py`ベース）・部分集合判定（`judge_subset`）・変種ファイル名パターン検出（`find_variant_candidates`、`_n`/`_spine`/`#K`/`_n #K`/`_spine #K`/`_VR`を本体ファイルのstemから厳密照合）・episodeId suffix導出（`derive_variant_episode_id`、§6.2の規則どおり）・本体単位の判定オーケストレーション（`judge_body_variants`）を実装した。`_VR`は常に`judgment="skipped_vr"`として記録し、部分集合判定自体は行わない（スキップした事実は判定結果に残る）。
- **CLI**: 新設`scripts/judge_hscene_variants.py`。H_sceneN本体ファイルまたはキャラクターexportディレクトリを入力に判定を実行し、判定レポート（JSON/Markdown、実ファイル名を含むためworkspace限定・非commit）を出力する。`--normalize`指定時のみ、exception判定された変種を既存のnormalize経路（`StoryParser`→`Normalizer`→`Exporter`）で`storyCategory: CHAR_HS`の別episodeとしてnormalizeする（`--story-id`必須、`episodeId`は§6.2規則から自動導出）。
- **trace情報**: `agents/parser/normalizer.py`の`Normalizer`に`variant_trace`引数を追加し、`source.hsceneVariantTrace`（baseEpisodeId/variantPattern/dupIndex/judgment等）として記録する（`SourceInfo`は`additionalProperties: true`のためschema変更不要）。
- **実データ動作確認（workspace限定・非commit）**: `data/raw/character/`全量（H_sceneN本体517件）に対し`scripts/judge_hscene_variants.py`を実行し、判定分布が`03_Scope.md` §5.3の全量検証結果（部分集合615・例外144・`_VR`45、計759件）と完全一致することを確認した（totalException=144、totalSkippedVr=45、部分集合570+`_VR`45=615）。パターン別内訳（`_n`: subset451/exception53、`#N`(hash): subset59/exception54、`_spine`+`_spine #N`(spine+spine_hash): 合計exception37）も§5.3の値と一致する。
- 合成fixtureテスト: `tests/parser/test_hscene_variant_judgment.py`（判定ロジック単体）・`tests/scripts/test_judge_hscene_variants.py`（CLIスモークテスト、`--normalize`のCHAR_HS出力を含む）・`tests/parser/test_normalized_story_schema.py::test_normalized_json_char_hs_category`（schema検証）。
- §6.3の重複排除ロジック（抽出段階のアセットpath同一性判定）は本PRでは実装しない（§9のPR Eのスコープのまま）。

## 6.6 実装状況（`feature/hscene-variant-extraction-dedup`、PR E）

§6.3の抽出段階dedupロジックを実装した。

- **配置**: 新設`agents/extractor/hscene_dedup.py`。既存の`agents/extractor/`パイプライン構造（`Extractor.extract_episode`を組み立てる各`build_*_candidates()`と同じ層）に合わせ、`Extractor`をラップするオーケストレーション関数`extract_stories_with_hscene_dedup(story_jsons: list[dict]) -> list[dict]`として実装した。複数のNormalized Story JSON document（Phase 1では1 file = 1 episodeのため、documentは実質1 episode分）を受け取り、`source.hsceneVariantTrace.baseEpisodeId`でH_sceneNグループ（本体1+例外変種0〜複数）へグループ化する。
- **Block単位の識別子抽出**: `block_identifier_set()`が、`agents/parser/hscene_variant_judgment.py`の`extract_identifier_set_from_tokens`をそのまま再利用する。Block1件分の`source.raw`（発話コマンド行）・`rawText`（本文行）・`choiceText`を結合してTokenizerへ渡し、ファイル全体判定（PR D）と全く同じ意味論（発話系コマンドのアセットpath＋正規化済み日本語TEXT行）でBlock単位の識別子集合を得る。
- **重複判定**: 本体のevidence対象Block（dialogue/monologue/narration/choice、`agents/extractor/models.py`の`EVIDENCE_BLOCK_TYPES`と同じ集合、choiceのoption内blocksも`agents/extractor/base.py`の`evidence_from_block`と同じ再帰で辿る）の識別子集合を起点(`seen`)とし、変種episodeIdの辞書順で決定的に処理する。各Blockの識別子集合が空でなく、かつ`seen`の部分集合なら重複マーク、そうでなければ`seen`へ追加して保持する。これにより変種同士の重複も初出のみが残る（後続変種は先行変種に対して重複判定される）。
- **不破棄不変則**: 重複と判定したBlockは、Extractorへ渡すepisode dictの**コピー**（`_filter_episode_for_extraction`）からのみ取り除く。入力のNormalized Story JSON辞書自体は一切変更しない（合成fixtureテストで辞書の`==`比較により無変更を確認済み）。
- **記録**: episode_extraction出力へ任意フィールド`hsceneDedup`を追加する（`schemas/extraction.schema.json`に`HsceneDedup`定義として後方互換追加、`additionalProperties: false`だが必須プロパティは無し、既存fixtureは無変更で検証を通過する）。`role: "body"`（`groupBaseEpisodeId`・今回の入力に含まれていた`variantEpisodeIds`）と`role: "variant"`（`groupBaseEpisodeId`・`baseEpisodeAvailable`・`excludedBlockCount`・`excludedBlockIds`・`dedupedAgainstEpisodeIds`）の2種を区別する。トレースの無い通常episode・CHAR_HS以外のカテゴリのepisodeには`hsceneDedup`キー自体を付与しない（完全無回帰）。`extraction.schema.json`の`storyCategory` enumへ`"CHAR_HS"`も追加した（`schemas/story.schema.json`は既にPR Dで追加済みだったが、抽出schema側は未追加だったため）。
- **本体不在時の挙動**: 入力にbaseEpisodeIdに対応する本体documentが含まれない場合、dedupは実施せず、`hsceneDedup.baseEpisodeAvailable: false`・`excludedBlockCount: 0`として本体不在の事実を記録する（黙って本体扱いしない、変種のBlockは全件フル抽出される）。
- **CLI**: `scripts/extract_story.py`に`--input-dir`（`--input`と排他）を追加した。ディレクトリ直下の全`*.json`を読み込み`extract_stories_with_hscene_dedup()`へ渡す。既存の`--input`（単一ファイル）は完全に無変更（挙動・出力とも既存テストのまま）。
- **実データ動作確認（workspace限定・非commit）**: `data/raw/character/`の一部（キャラクターexportディレクトリ15件）について、`scripts/judge_hscene_variants.py --normalize`相当の処理で本体+例外変種のNormalized Story JSON群を生成し、`extract_stories_with_hscene_dedup()`（`scripts/extract_story.py --input-dir`と同じ経路）を実行した。exception変種が発生したH_sceneNグループは11件（exception変種は計20件、1本体に複数変種が対応するケースを含む）で、そのうち9グループ・変種18件でBlock単位の重複除外が実際に発生し、除外Block数の合計は484件だった。残る2グループ（変種2件）は除外0件で、本体・変種が全く異なるアセット番号を参照するケース（`03_Scope.md` §5.5で確認済みの「本体が別H_scene番号の既存アセットを再利用した短い内容」パターンに合致）であり、Block単位judgeが意図通り保守的（誤って重複マークしない）に動作していることを示す。`scripts/extract_story.py --input-dir`のCLI経路自体も、同じ入力の一部（本体1件+変種1件）で実行し`--validate`込みでschema検証PASSを確認した。件数のみを記録し、生成物・実ファイル名はcommitしない。
- 合成fixtureテスト: `tests/extractor/test_hscene_dedup.py`（`reverse_superset`相当・`partial_overlap`相当の両形状での重複除外・変種同士の初出のみ抽出・除外件数/重複先episodeIdの記録・Normalized Story JSON不変・トレース無しepisodeの無回帰・CHAR_HS以外カテゴリの無回帰・本体不在時の挙動・extraction.schema.json検証）。

---

# 7. コマンド登録の決定（決定4）

**決定日: 2026-07-16。`03_Scope.md` §5.4の両未決事項を解決する。**

**`@SpineTalk`をspeechコマンドとして`config/script_commands.yaml`へ登録し、variant-only 17種（`03_Scope.md` §4.4.1で確認済みの、パース対象外ファイルにのみ出現する未登録コマンド群）も同一実装PRで一括登録する。**

## 7.1 根拠

§6の動的部分集合判定自体が、`_spine`変種からアセットpath集合を抽出するために`@SpineTalk`の解釈を必要とする。したがって`@SpineTalk`の登録は、例外変種取り込みを実装するうえで実質的に必須である。

17種のvariant-onlyコマンドについても、例外変種パース時（§6の`_n`/`_spine`/`#N`パターンをパースする際）に遭遇しうるため、`03_Scope.md` §4.4.2の既存batch（パース対象24種の登録）と同じ機械分類方式で登録する。

## 7.2 実装

実装（`config/script_commands.yaml`・`agents/parser/parser.py`への登録、合成fixtureテスト）は§9のPR Bで行う。本PRでは実施しない。

**実装済み（`script-command-dictionary-spinetalk-variant-only-batch`、2026-07-16）**: `@SpineTalk`をspeechカテゴリへ登録し、`agents/parser/parser.py`の発話コマンド処理で実際にdialogueブロックを生成できるようにした。variant-only非speechコマンド（実測16種、内訳はvariable-token 8種・stage_direction 6種・case-variant 2種）もあわせて機械分類方式で登録した。詳細・実測値の訂正経緯は`03_Scope.md` §5.4.1を参照。

---

# 8. manifest統合設計

**実装状況（`feature/story-manifest-character-category-support`で実施、PR C）**: 本節が設計した`schemas/story_manifest.schema.json`拡張（`characterId`/`auxiliaryFiles`）と、`scripts/build_story_manifest_candidates.py`のCHARACTER/CHARACTER_DATE対応を実装した。実装詳細は`Story_Manifest_Design.md` §13.3・§16.1を参照。

## 8.1 `schemas/story_manifest.schema.json`拡張案

実装はPR C（§9）で行う。本PRでは以下の設計のみを記録する。

- **story-level任意フィールド`characterId`**: パターン`^CHAR_[A-Z0-9_-]+$`または`null`。当該storyがどのキャラクターに紐づくかを記録する（`CHARACTER_ID_PATTERN`、`agents/parser/character_dictionary.py`と同じパターン）
- **story-level任意フィールド`auxiliaryFiles`**: 配列。各要素は以下のフィールドを持つ

  | フィールド | 説明 |
  |---|---|
  | `rawPath` | raw DECファイルの正規化済み相対パス |
  | `sourceFileName` | ファイル名そのまま |
  | `fileRole` | 下記enum |
  | `notes` | 自由記述、null許容 |

  `fileRole` enum:

  | 値 | 意味 |
  |---|---|
  | `variant` | H_sceneN変種ファイル（`_n`/`_spine`/`#N`/`_VR`）。**部分集合判定はパース時の動的判定のため、manifest生成時点では一律`variant`とする**（例外変種かどうかの判定結果はmanifestに記録しない） |
  | `direction` | camera/finish/episode_bgm等の純コマンド演出ファイル |
  | `other` | img/test/tutorial等の特殊ファイル（§3.3の新発見分を含む） |

- **後方互換**: 両フィールドとも既存manifestには存在しないため、既存の`docs/templates/story_manifest_template.yaml`はそのままschema検証を通過する

## 8.2 候補生成script（`build_story_manifest_candidates.py`）のCHARACTER/CHARACTER_DATE対応

実装はPR C（§9）で行う。

- **DEC本文を読まない原則を維持する**（`Story_Manifest_Design.md` §16の既存原則）
- `knowledge/dictionaries/characters.yaml`辞書をロードし、`{N}`（`sourceCharacterId`）→`characterId`を解決する。未confirmedのキャラクターは§4.3の前提条件どおりcandidate生成対象外とし、pending報告に含める
- `episodeN`/`episode_EXN`/`Surprise_N`/`H_sceneN`/`H_scene_s`は§4.2の対応表に従いepisode candidateとして生成する
- 変種・純コマンドファイル（§3.3の変種・純コマンド/演出系・新発見分）は、§8.1の`auxiliaryFiles`として記録する（`fileRole`は該当する種別に応じて`variant`/`direction`/`other`）

## 8.3 実データ由来manifestの扱い

実データ由来の`story_manifest.yaml`は、既存方針（`AI_PR_Playbook.md` §7）どおりworkspace限定・非commitのまま変更しない。

---

# 9. 実装PR分割計画

本PR（設計docのみ）に続く実装は、以下の4PRへ分割する。**いずれも本PRでは実施しない。**

| PR | 内容 | 対象 |
|---|---|---|
| **PR B** | `@SpineTalk` speech登録+variant-only 17種登録（§7） | `config/script_commands.yaml`・`agents/parser/parser.py`・合成fixtureテスト |
| **PR C** | `story_manifest` schema拡張＋候補生成builderのCHARACTER/CHARACTER_DATE対応（§8） | `schemas/story_manifest.schema.json`・`scripts/build_story_manifest_candidates.py`（**実装済み**、`feature/story-manifest-character-category-support`） |
| **PR D** | 動的部分集合判定＋CHAR_HS例外変種episode生成＋storyCategory enum/exporter対応（§5.2・§6） | `agents/parser/`・`schemas/story.schema.json`・`agents/parser/exporter.py`（**実装済み**、`feature/hscene-variant-dynamic-judgment`） |
| **PR E** | 抽出段階のアセットpath重複排除（§6.3） | `agents/extractor/`（**実装済み**、`feature/hscene-variant-extraction-dedup`。新設`agents/extractor/hscene_dedup.py`・`schemas/extraction.schema.json`の`hsceneDedup`定義追加・`scripts/extract_story.py`の`--input-dir`対応） |

依存関係: PR Dの動的判定はPR Bの`@SpineTalk`登録に依存する（§7.1）。PR EはPR Dの例外変種episode生成結果に依存する。PR Cは他PRと独立して着手可能。

## 9.1 全量実行の実施記録（dry-run、2026-07-17）

**実施PR: `feature/hscene-full-pipeline-dry-run`（docs-only扱いのdry-run PR）。**

PR B〜E（§9表、`feature/script-command-dictionary-spinetalk-variant-only-batch`〜`feature/hscene-variant-extraction-dedup`）で実装が完了したH_scene全パイプライン（normalize→動的部分集合判定→例外変種normalize→extraction+dedup）を、`data/raw/character/`全72キャラクターに対してworkspace限定で実行した（`agents/`・`scripts/`本体は変更していない。既存の公開関数・CLIをオーケストレーションするだけの使い捨てscriptを`workspace/local_inputs/`配下に置いて実行した）。生成物（normalized JSON・extraction JSON・判定レポート）はすべてworkspace限定・非commit。以下は件数のみの集計である。

### 9.1.1 normalize結果

| 項目 | 結果 | 期待値との対応 |
|---|---|---|
| 本体episode数（H_sceneN 517 + H_scene_s 72） | 589 | `03_Scope.md` §4.3の589件と完全一致 |
| 例外変種episode数 | 144 | §5.3確定値144と完全一致 |
| 総episode数 | 733 | 589 + 144 |
| story.schema.json検証PASS率 | 733/733（100%） | 全件PASS |

### 9.1.2 compatibility

| 項目 | 結果 |
|---|---|
| `type: "unknown"`ブロック数 | 7,049件（733episode中404episode、約55%に出現） |
| `unknownCharacterIds`が非空のepisode数（compatibilityReport集計ベース） | 614 |
| 同distinct未登録sourceCharacterId数（compatibilityReport集計ベース） | 815 |
| 実際にdialogue/monologueブロックの話者（`isResolved: false`）として出現するepisode数 | 162 |
| 同distinct sourceCharacterId数（数値ID・実際に話者として消費されたもののみ） | 3 |

**期待（unknownブロック数0近傍・distinct未登録ID数が§5.2の既知件数付近）とは大きく乖離した。** 原因調査の結果、以下3件の実装上の非対称性・不具合を確認した（**症状・再現条件の記録のみ。修正は別PR**）。

1. **裸単語コマンドの検出範囲の非対称性（既存Known Issue「compatibility checkの既知の非対称性」の実データでの顕在化）**: `_spine`/`_spine #K`系のH_scene本体・例外変種には、`@`接頭辞を持たない継続パラメータ行（`postProcess 1`・`depth length 35`・`bloom intensity 3`等、実測32種のトークン）が多数出現する。`scripts/check_script_compatibility.py`（standalone checker）はこれらを「未登録コマンド」として検出しない（`@`接頭辞トークンのみを対象とする実装のため）一方、実parser（`agents/parser/tokenizer.py`）はこれらを`unknown`トークンとして分類し、`StoryParser`が`type: "unknown"`ブロックへ変換する。この非対称性自体はTASKS.md Known Issuesに「実データでは稀」として既に記載されていたが、H_scene系コンテンツ（特に`_spine`変種）に限れば733episode中404episode・7,049ブロックという無視できない規模で顕在化することが今回の全量実行で判明した。

   **部分解消（`feature/bare-word-parameter-token-registration`、2026-07-17実施）**: workspaceの全量dry-run成果物（本節9.1のnormalized JSON）を再スキャンし、実測32種のトークンを再導出した（記載どおり32種と一致）。このうち、実データ確認（各トークンの直前直後のブロック列を確認し、`@PostProcess`直後の継続パラメータ・`camera N`直後のカメラレイヤー設定等であることを裏付けた）によりカメラ/ポストエフェクト系パラメータとして機械分類できた14種（`postProcess`/`depth`/`bloom`/`enable`/`volume`/`analogGlitch`/`retroGlitch`/`digitalGlitch`/`mozaiku`/`fade`/`mask`/`layer`/`duplication`/`shadow`）を`config/script_commands.yaml`のstage_direction、`agents/parser/tokenizer.py`のKEYWORD_TOKENS、`agents/parser/parser.py`のDIRECTION_TYPE_MAPへ登録した。加えて、実データで唯一の出現1件が`camera`と同じ配置（pos/euler/fov triadの直前）で確認できた表記ゆれ`caemra`（`camera`のtypo）をCASE_VARIANTS_MAPへ登録した。残り17種（`spine`/`func`/`eye`/`setup`/`timeScale`/`springEnable`/`add`/`skin`/`segment`/`init`/`moPart`/`cset`/`rdrawMat`/`acc`/`log`/`hlook`/`oneAuto`）は、Spine rig系（`spine`/`eye`、常に`spine`直後に`eye`が出現しキャラクター視線設定と判断）・意味が文脈依存で分岐する汎用ディスパッチャ（`func`、`ui_camera`/`ui_cameraRec`はカメラ系だが`ui_finish`/`ui_advActive`/`ui_massage`はカメラ/ポストエフェクトと無関係）・汎用初期化コマンド（`init`、postProcessブロックと非カメラ文脈`ui_massage`の両方に出現）等、カメラ/ポストエフェクト系として機械分類できず「要判断」のまま未登録とした（詳細な内訳・出現回数は`TASKS.md` Current Focus参照）。standalone checker側は`config/script_commands.yaml`の既知コマンド集合を共有しているため、登録14種+表記ゆれ1種はコード変更なしで両経路の対称性が確保された（`tests/parser/test_compatibility_consistency.py`で確認）。H_scene全パイプライン再実行（`workspace/local_inputs/hscene_full_pipeline_dry_run.py`、workspace限定・非commit）の結果、`type: "unknown"`ブロック数は7,049件→**2,377件**（66.3%減、上記残り17種の出現数の合計と一致）、`compatStatusDistribution`は`{"warning": 719, "compatible": 14}`→`{"warning": 686, "compatible": 47}`（33episodeが完全解消）に改善した。昇格済みEvidence Index 8 story（EVENT 7・RAID 1、26 episodeファイル、いずれも`_spine`系を含まないEVENT/RAIDカテゴリ）を再normalizeし、`blocks`（dialogue/monologue/narration/choice）が変更前後で26ファイル全て完全一致することを確認した（無影響）。②③は本PRのスコープ外のまま未解消。

   **全解消（`feature/bare-word-parameter-token-batch-002`、2026-07-17実施、Fable決定）**: 「要判断」のまま未登録だった残り17種（`spine`/`func`/`eye`/`setup`/`timeScale`/`springEnable`/`add`/`skin`/`segment`/`init`/`moPart`/`cset`/`rdrawMat`/`acc`/`log`/`hlook`/`oneAuto`）を、カメラ/screen系との断定を待たず全種`stage_direction`として安全側登録した（PR #153の前例「分類が割れるものは安全側」を適用）。**登録前の安全確認**として、workspace全量dry-run成果物（733 episode・normalized JSON）の`type: "unknown"`ブロック全件（2,377件）を再スキャンし、(a) 17種いずれについても`H_scene/`アセットパス・日本語TEXT・`.ogg`/`.wav`拡張子が当該ブロックの`raw`行に直接含まれる（＝発話コマンド様の使われ方をしている）事例が0件であること、(b) 出現トークンが実測でちょうど17種・合計2,377件（PR #153記録値と完全一致）であることを確認した。direction_typeはPR #153時点のエビデンス（各トークンの直前直後のブロック列）に基づき機械的に割り当てた: `spine`/`eye`は常に隣接して出現するSpine rig視線パラメータ、`hlook`は頭部視線追従トグルとして`character_display`。`timeScale`（アニメーション再生速度）・`springEnable`（spring boneコライダー、既存`@SpringBone/*`="motion"と同系統）・`add`（アニメーションレイヤートグル、`add 0 animation3 true 0`）・`moPart`（モーションパーツ速度、`moPart speed $common0`）は実データでモーション/物理系と確認できたため`motion`。残り10種（`func`=`ui_camera`/`ui_massage`等が混在する汎用ディスパッチャ、`log`=デバッグ出力、`init`=postProcess/非カメラ文脈の両方に出現し一意に分類不能、`setup`/`skin`/`segment`/`cset`/`rdrawMat`/`acc`/`oneAuto`=文脈依存または判断に迷うもの）は安全側デフォルトの`system`とした。`config/script_commands.yaml`・`agents/parser/tokenizer.py`のKEYWORD_TOKENS・`agents/parser/parser.py`のDIRECTION_TYPE_MAPへ対で登録し、standalone checker側はconfig共有により自動対称化した（`tests/parser/test_compatibility_consistency.py`で確認）。

   H_scene全パイプライン再実行（`workspace/local_inputs/hscene_full_pipeline_dry_run.py`、workspace限定・非commit）の結果、`type: "unknown"`ブロック数は**2,377件→0件**（完全解消）、`compatStatusDistribution`は`{"compatible": 503, "warning": 230}`→`{"compatible": 677, "warning": 56}`に改善した（extraction/judgment分布は無変化、無回帰）。①〜③はこれで全て解消済みとなった。

   **昇格済みEvidence Index 8 story（EVENT 7・RAID 1、26 episodeファイル）の再normalize比較**（git worktree経由、変更前後の2バージョン）: 今回のデータ再スキャンで、残り17種のうち`log`が26ファイルの1つ（EVENT_164_260425の該当episode）に実際に1件出現していることを新たに確認した（`log --------------------environment:$environment`、既存の`postProcess`等14種が_spine系character/ファイル以外には出現しない前提だった§9.1.2の1の記述を補足する新発見）。`blocks`（dialogue/monologue/narration/choice）は26ファイル全てで完全一致（差分ゼロ）を確認した——`unknown`→`stage_direction`への分類変更は`blocks`比較の対象型（dialogue/monologue/narration/choice）に含まれないため、この1件を含め無影響であることを実データで裏付けた。
2. **未登録キャラクターID記録の代入時点/消費時点の非対称性**: 実parserの`SpeakerResolver._resolve_character_id`（`agents/parser/resolver.py`）は、`@ScenarioCos`/`$numX=`/`@ScenarioCosLoad`によるスロット**代入時点**で無条件に`unresolved_character_ids`へ記録する（`assign_character`/`assign_variable`/`assign_from_variable`から呼ばれる）。これは、`scripts/check_script_compatibility.py`が`#141`（`feature/checker-consumption-context-fix`）で採用した**消費時点**（実際に発話コマンドで話者として使われたスロットのみを未登録として扱う）ベースの判定とは異なるロジックであり、`#141`修正はstandalone checker側のみに適用され、実parserの`resolver.py`側は据え置かれていた（TASKS.md Backlog「parser-auto-bind-non-speaker-slot-review」で既に検討対象として記録されている自動バインド挙動そのもの）。この非対称性により、`compatibilityReport.unknownCharacterIds`集計ベースの件数（614episode・815 distinct ID）は、実際にdialogue/monologueブロックの話者として表面化する件数（162episode・3 distinct ID）を大幅に上回った。

   **解消済み（`feature/resolver-consumption-context-report`、2026-07-17実施）**: `agents/parser/resolver.py`の`SpeakerResolver`に消費文脈シグナル（`_unresolved_char_id_signals`: sourceCharacterId→`{speaker: bool, hasOccurrence: bool}`）を追加し、standalone checkerの`_simulate_id_consumption`/`_classify_and_record_character_ids`（#141）と同じ意味論で`unresolved_character_ids`（話者消費あり、従来どおり`compatibilityReport.unknownCharacterIds`へ）/`non_speaker_numeric_assignment_ids`（話者消費なし、新設の`compatibilityReport.nonSpeakerNumericAssignments`へ）を分類するようにした。`assign_character`（`@ScenarioCos`直接ID指定）は即時話者消費ありとして記録、`assign_variable`（`$numX`/`$valueX`）は代入時点では記録せず後続の`resolve_slot`呼び出し（`@ChTalk`系コマンドからのみ発生）で確定、`assign_from_variable`（`@ScenarioCosLoad`/`@ScenarioCos`変数経由）は既存の代入記録があるIDを即時話者消費ありへ昇格させる、という3経路の意味論をchecker側の`_apply_scenario_cos`/`_apply_num_var_assignment`/`_apply_scenario_cos_load`/`_apply_speech_command_consumption`と1対1で対応させた。**スロット自動バインド挙動・話者解決結果（block.speakerの内容）は一切変更していない**（変更したのは`compatibilityReport`への記録・分類のみ）。

   **実測（H_scene全量再実行、`workspace/local_inputs/hscene_full_pipeline_dry_run.py`、workspace限定・非commit）**: `unknownCharacterIds`が非空のepisode数は**614→9**、同distinct未登録sourceCharacterId数は**815→6**へ縮小した。6件の内訳は、数値ID4件（`40286`/`40287`/`40364`/`600`）と、発見③で確認済みの非ID文字列混入2件（`$split(0,$value11)`・`11.2,-7.7,-24`）である。設計時点の期待値（162episode・distinct 3 ID）とは完全一致しなかったが、その差異は期待値算出方法の違いに起因すると判断した: 期待値の162episodeは「dialogue/monologueブロックの話者（`isResolved: false`）が出現するepisode数」を直接カウントしたものであり、この中には**スロット自体が一度も代入されず`sourceCharacterId`が最初からNoneのケース**（`resolve_slot`が`_slot_map`に存在しないスロットに対して`source_character_id=None`の`Speaker.unknown()`を返す場合。`assign_character`/`assign_variable`/`assign_from_variable`のいずれも通らないため`_unresolved_char_id_signals`に記録されようがない）も含まれていた。今回の消費文脈ベース分類は`sourceCharacterId`が実在する場合のみを対象とするため、162episodeの真部分集合である9episodeへ収束したと考えられる（この差異自体は本PRのスコープ外の別事象であり、修正・追加調査は行っていない）。distinct数値ID 4件・非ID文字列2件は、いずれも発見③の記述（「実際にdialogue/monologueブロックの話者として出現する3 distinct数値IDとは別に…2件の非数値文字列」）と整合する規模であり、消費文脈ベース分類が正しく機能していることを裏付ける。

   **昇格済みEvidence Index 8 story（EVENT 7・RAID 1、26 episodeファイル）の再normalize比較**（git worktree経由、変更前後の2バージョン）: `blocks`（dialogue/monologue/narration/choice）は26ファイル全てで完全一致（差分ゼロ）。`compatibilityReport`は26ファイル全てで差分ありと判定されたが、差分の全量は新設フィールド`nonSpeakerNumericAssignments`の追加（26ファイルすべて空配列`[]`）のみであり、`unknownCharacterIds`・`parserCompatibility`はいずれも26ファイル全てで無変化（この26ファイルには元々未登録キャラクターIDが存在せず、再分類自体が発生しなかった）。
3. **`sourceCharacterId`への非ID文字列混入**: 実際にdialogue/monologueブロックの話者として出現する3 distinct数値IDとは別に、`$split(0,$value11)`（未評価の関数呼び出し式）・`11.2,-7.7,-24`（座標様の数値列）という2件の非数値文字列が`sourceCharacterId`として記録される事例を確認した。話者名/IDの引数が単純なリテラルでない場合（式・座標データ等）の抽出処理に起因すると考えられる未調査の不具合であり、再現条件の特定（該当コマンド種別の絞り込み）は未実施。

   **解消済み（`feature/non-literal-character-id-handling`、2026-07-17実施）**。workspaceの全量dry-run成果物（normalized JSONの`source.raw`・`compatibilityReport`）から該当episodeを特定し、raw行まで遡って再現条件を確定させた（いずれもH_scene本体、`CAB-csl_script_charastory_character{N}-H_scene{M}.dec`形式のファイル。以下は匿名化表記）:

   - `$split(0,$value11)`の再現条件（あるキャラクターのH_scene本体1件）: `$value11 = {キャラID候補のカンマ区切り数値リスト}`に続けて`$num1 = $split(0,$value11)`〜`$num6 = $split(5,$value11)`という**未評価の関数呼び出し式**が`$numX`へ代入される。`@ScenarioCosLoad 1 $num1 ... ON`がスロット1を`$num1`（＝文字列`"$split(0,$value11)"`そのもの）へ束縛し、後続の`@ChTalk 1 ...` 21件がこのスロットを話者として消費する。
   - `11.2,-7.7,-24`の再現条件（別キャラクターのH_scene本体1件）: ファイル冒頭に`$value0 = 11.2,-7.7,-24`（カメラ座標triadの一部、キャラIDとは無関係）が`@ScenarioCos`/`@ScenarioCosLoad`を一切経由せず存在するのみで、`$numX`代入が無い（`max_num_index=-1`）ため`assign_variable`のスロット計算式`str(max_num_index + 1 + value_index)`が`str(-1+1+0)="0"`となり、**スロット自動バインド挙動（既知のBacklog項目、本PRでは変更しない）により座標データがそのままスロット0へ自動束縛**される。後続の`@ChTalk 0 ...` 31件がこのスロットを話者として消費する。

   **根本原因**: 両ケースとも共通して、`agents/parser/tokenizer.py`の`NUM_VAR_PATTERN`/`VALUE_VAR_PATTERN`（`$numX=`/`$valueX=`）がRHS全体を`\S+`（空白を含まない任意の文字列）として捕捉する実装になっている。これはカメラ座標代入（`$value6 = 1.2,-3.4,-5.6`等）を破棄せずそのまま保持するための意図的な設計だが、結果として関数呼び出し式・座標様数値列のような「ID形式（数字のみ）でない文字列」もそのまま`source_character_id`として下流（`resolver.py` `SpeakerResolver`）へ伝播し、話者スロットとして消費された場合に無条件で`compatibilityReport.unknownCharacterIds`（未登録キャラクターID候補）へ計上されていた。

   **修正**: `SpeakerResolver`に「ID形式（数字のみ）かどうか」を判定する`_is_literal_character_id`（正規表現`^\d+$`、`knowledge/dictionaries/characters.yaml`の全confirmedエントリが数字のみのsourceCharacterId形式であることを前提とする）を追加し、未登録`source_character_id`の消費文脈シグナル記録を分岐させた。ID形式の値は従来どおり`unresolved_character_ids`/`non_speaker_numeric_assignment_ids`（発見②の消費文脈ベース判定を経て`unknownCharacterIds`/`nonSpeakerNumericAssignments`）へ、ID形式でない値は新設の`non_literal_speaker_expressions`（`compatibilityReport.nonLiteralSpeakerExpressions`、`sourceCharacterId`と話者消費有無を示す`consumedAsSpeaker`のペア、`schemas/story.schema.json`へ後方互換な任意フィールドとして追加）へ分離する。**不破棄不変則により削除はせず、`block.speaker.sourceCharacterId`にRHS文字列がそのまま入る既存動作・スロット自動バインド挙動は一切変更していない**（変更したのはcompatibilityReportへの分類のみ）。`$split(...)`等の式の実評価・スロット自動バインド挙動の変更自体はNon-goalとしてスコープ外のまま。

   **checker側（`scripts/check_script_compatibility.py`）の対称性確認**: standalone checkerの`NUM_VAR_PATTERN`/`VALUE_VAR_PATTERN`/`SCENARIO_COS_PATTERN`は元々RHSを`\d+`（数字のみ）または`$変数名`に限定しており、`$split(...)`のような`$`始まりの非リテラル式はそもそも検出対象外（対称化の必要なし、確認済み）。ただし調査の過程で、これらのパターンが行末アンカーを持たないため、`11.2,-7.7,-24`のような数字始まりだが完全に数字のみではない値に対して**部分一致（truncated match、例:`"11.2,-7.7,-24"` → `"11"`）が発生する別種の既知の不具合**を新たに発見した（実データ全量調査で160件、うち111件は`characters.yaml`の実在するsourceCharacterId値と偶然一致することも確認済み）。この不具合はstandalone checker専用（実parser側の`tokenizer.py`は`\S+`でRHS全体を捕捉するため、この特定の部分一致問題は発生しない）であり、修正には`config/script_commands.yaml`の`$numX`/`$valueX`インデックス許容範囲の見直しを伴う可能性があるため、本PRのスコープ外として`TASKS.md` Known Issuesへ記録し、別PRでの対応を検討する。

   **検証**: 合成fixtureテスト（`tests/parser/test_resolver.py`: 関数呼び出し式/座標様数値列それぞれの話者消費あり・なし・数値ID経路の無回帰の4件、`tests/parser/test_normalizer_compatibility_report.py`: 同4件のcompatibilityReport版、`tests/parser/test_compatibility_consistency.py`: checker側で非リテラル式が検出対象外であることの対称性確認1件）をすべてPASS。昇格済みEvidence Index 8 story（EVENT 7・RAID 1、26 episodeファイル）を変更前後2バージョン（git worktree経由）で再normalizeし、`blocks`（dialogue/monologue/narration/choice）が26ファイル全て完全一致することを確認した（差分は新設フィールド`nonLiteralSpeakerExpressions`の追加、26ファイルすべて空配列`[]`のみ）。H_scene全パイプライン再実行（`workspace/local_inputs/hscene_full_pipeline_dry_run.py`、workspace限定・非commit）の結果、`unknownCharacterIds`のdistinct未登録sourceCharacterId数は**6→4**（数値IDのみ、`40286`/`40287`/`40364`/`600`）に収束し、非ID文字列2件（`$split(0,$value11)`・`11.2,-7.7,-24`）はいずれも`nonLiteralSpeakerExpressions`（`consumedAsSpeaker: true`）へ正しく分離された。§9.1.2の発見①〜③はこれで全て解消済みとなった（①は部分解消のまま残り17トークンが未登録、TASKS.md参照）。

### 9.1.3 extraction + dedup

| 項目 | 結果 |
|---|---|
| `hsceneDedup`で除外マークされたBlock総数 | 6,017 |
| dedupが発生した（除外Block数>0の）グループ数 | 71 |
| `baseEpisodeAvailable: false`の発生件数 | 0（発生なし、期待どおり） |
| extraction.schema.json検証PASS率 | 733/733（100%） |

PR Eのサンプル実測（キャラクターexportディレクトリ15件、9グループ・484 Block除外）と比較して、全量（72ディレクトリ）でも同様の傾向（重複排除が実際に機能し、本体・変種で異なるアセットを参照するケースでは誤って除外しない保守的な挙動）を確認した。

### 9.1.4 判定分布

| judgment | 件数 | §5.3確定値との対応 |
|---|---|---|
| subset（非`_VR`の部分集合） | 570 | |
| exception | 144 | 完全一致 |
| skipped_vr（`_VR`、判定対象外） | 45 | 完全一致 |
| 合計 | 759 | §5.3の「部分集合615（=570+45）・例外144・`_VR`45、計759件」と完全一致 |

パターン別内訳（`n`: subset451/exception53、`spine`: subset32/exception16、`hash`: subset59/exception54、`n_hash`: subset3/exception0、`spine_hash`: subset25/exception21、`vr`: skipped_vr45）も、§5.3・§6.5の実データ確認結果と完全一致した。

### 9.1.5 実行状況

72キャラクター全件を1回のバッチで処理し、途中失敗（例外・schema検証失敗）は0件だった。処理対象外（未confirmedキャラクター等）も0件（`data/raw/character/`全72キャラクターは§4.3前提どおり全件confirmed）。

---

# 10. Open questions（本PRでは決定しない）

## 10.1 本編episodeの`_n`変種（新発見）

`episodeN_n` 13件・`episode_osawariN_start_n` 3件（§3.3）。本編episode系にも`_n`変種が存在することが新たに判明した。`03_Scope.md` §5.3の検証対象はH_scene変種のみであり、本編episodeの`_n`変種は未検証だった。

本編episodeは公開対象（軸(B)=Yes、`03_Scope.md` §6）であるため、もし本編episode側にも部分集合関係が成立しない例外が存在した場合、内部取り込みだけでなく**公開スコープ判断**（Wiki出力・Evidence Index promotionに変種内容を含めるか）も絡む。H_sceneと同じ動的部分集合判定を適用するかどうかは未決とする。

**検証結果（`episode-n-variant-subset-verification-dry-run`、2026-07-17実施・結果確定、詳細は`03_Scope.md` §5.6.1）**: `episode_osawariN_start_n`（3件）は全件が対応本体の完全な部分集合として成立した（例外0件）。`episodeN_n`（13件）は、ファイル名から期待される対応本体（`episodeN`）が全13件で一件も存在しない孤立変種だったが、補足検証（同一手法の適用範囲拡張）で全13件が同ディレクトリの同番号H_sceneN本体に対して完全な部分集合であることを確認した。この結果は、`episodeN_n`13件が実質的にH_scene系コンテンツの命名上の例外である可能性、`episode_osawariN_start_n`は`_VR`同様に変種を一律対象外としてよい可能性を示唆するが、**いずれもスコープ決定は本文書・`03_Scope.md`のいずれでも行っていない**（未決のまま、決定は後続タスク`episode-n-variant-scope-decision`）。

## 10.2 特殊ファイル群

`H_sceneN_img` 7件・`H_scene_test` 1件・`H_scene_s_tutorial` 1件・`PinkMan`/`idolVR`/`position`/`talk`/`start`等の特殊ファイル（§3.3）。`03_Scope.md` §5.1（純コマンド演出ファイルの扱い）と同じ未決バケットとする。manifestには§8.1の`fileRole: other`または`direction`で記録するのみとし、内部KB対象化・公開スコープの判断はいずれも本文書では行わない。

## 10.3 CHAR_MAIN/CHAR_EXTRA/CHAR_DATEのpublicStoryId採番

`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16.6のopen questionのまま据え置く。

本文書としては、CHAR_MAIN/CHAR_EXTRA/CHAR_DATEの内部storyId（§4のローマ字characterId方式）が実データ由来トークン（sourceKey等）を含まないため、`Story_Manifest_Design.md` §13.2のMAINカテゴリと同様に**内部ID=公開IDのリユース案が有力**という推奨のみを記載する。決定は行わない（公開ID確定は`AI_PR_Playbook.md`が定める停止点の一つである）。

`CHAR_HS`は公開恒久除外（§5.1）のため、そもそも`publicStoryId`を必要としない。

---

# 11. Non-goals

本PRでは以下を**スコープ外**とする。

- `agents/`・`scripts/`・`schemas/`・`config/`の実装変更一切（PR B〜Eで実施）
- H_sceneの実パース・normalize・動的判定の実行
- 実データ由来manifest・例外変種リストのcommit
- CHAR_*系publicStoryIdの採番・決定
- `episodeN_n`等の新発見未決事項の決定（§10.1・§10.2）

`docs/runbooks/AI_PR_Playbook.md` §8の恒常Non-goalsもあわせて適用する。

---

# 12. 参照

- `docs/architecture/05_Parser/Identifier_Specification.md`（Story ID/Episode ID形式の基本定義、§3・§4.9・§10 OD-003・§12を本PRで更新）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（`story_manifest.yaml`設計、§6・§18 OD-003を本PRで更新）
- `docs/architecture/01_Project/03_Scope.md`（H_scene系スコープ方針、§5.4・§5.5.2・§5.6を本PRで更新）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16.6（公開ID採番のopen questions）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §17（Promotion対象外カテゴリ）
- `docs/runbooks/AI_PR_Playbook.md`（PRワークフロー・commit禁止リスト・Non-goals）
- `AI_CONTEXT.md` §3.12（コンテンツスコープ方針要約、本PRで参照ポインタを追記）
- `schemas/story.schema.json`（`storyCategory` enum、PR Dで`CHAR_HS`追加）
- `schemas/story_manifest.schema.json`（PR Cで`characterId`/`auxiliaryFiles`追加）
- `agents/parser/exporter.py`（`_category_to_subdir`、PR Dで`CHAR_HS`追加）
- `agents/parser/character_dictionary.py`（`CHARACTER_ID_PATTERN`）
