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

## 6.4 §5.5.1との対応

本節は`03_Scope.md` §5.5.1が要求していた5点の設計方針のうち、(1)動的判定方式・(2)(3)取り込み方針・(4)内容同一性の判定子をそのまま踏襲し、episodeId suffix規則という具体的な採番ルールを新たに追加したものである。(5)「storyId/manifest設計の一部として組み込む」という要求は、本文書自体がその設計にあたる。

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
| **PR C** | `story_manifest` schema拡張＋候補生成builderのCHARACTER/CHARACTER_DATE対応（§8） | `schemas/story_manifest.schema.json`・`scripts/build_story_manifest_candidates.py` |
| **PR D** | 動的部分集合判定＋CHAR_HS例外変種episode生成＋storyCategory enum/exporter対応（§5.2・§6） | `agents/parser/`・`schemas/story.schema.json`・`agents/parser/exporter.py` |
| **PR E** | 抽出段階のアセットpath重複排除（§6.3） | `agents/extractor/`（または該当する抽出段階のモジュール） |

依存関係: PR Dの動的判定はPR Bの`@SpineTalk`登録に依存する（§7.1）。PR EはPR Dの例外変種episode生成結果に依存する。PR Cは他PRと独立して着手可能。

---

# 10. Open questions（本PRでは決定しない）

## 10.1 本編episodeの`_n`変種（新発見）

`episodeN_n` 13件・`episode_osawariN_start_n` 3件（§3.3）。本編episode系にも`_n`変種が存在することが新たに判明した。`03_Scope.md` §5.3の検証対象はH_scene変種のみであり、本編episodeの`_n`変種は未検証である。

本編episodeは公開対象（軸(B)=Yes、`03_Scope.md` §6）であるため、もし本編episode側にも部分集合関係が成立しない例外が存在した場合、内部取り込みだけでなく**公開スコープ判断**（Wiki出力・Evidence Index promotionに変種内容を含めるか）も絡む。H_sceneと同じ動的部分集合判定を適用するかどうかは未決とする。

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
