# Identifier Specification（ID設計仕様）

Version: 0.3 Draft  
Project: Detariki Knowledge Base (DKB)  
Path: `docs/architecture/05_Parser/Identifier_Specification.md`

---

# 1. 目的

この文書は、Detariki Knowledge Base（DKB）で使用するID体系を定義する。

IDは以下の領域で共通利用する。

- 正規化済みストーリーJSON
- Knowledge Graph のノード
- Knowledge Graph のリレーション
- Evidence（根拠）参照
- 生成されるWikiページ
- ファイル名
- 将来の検索インデックス
- 将来のAPI

この文書では **IDそのもの** の仕様だけを扱う。

以下のような情報は、この文書では扱わない。

- タイトル
- サブタイトル
- 表示名
- 短縮名
- 公開日
- 開催期間
- 表示順
- 公開順
- 画像
- 解放条件

それらは `Story_Metadata.md` で定義する。

---

# 2. 基本方針

## 2.1 安定性

一度割り当てたIDは原則として変更しない。

表示名、タイトル、要約文、Wikiページ名は変更されてもよいが、IDは維持する。

---

## 2.2 人間にも読めること

IDは人間やAIツールが意味を理解しやすい形式にする。

望ましい例:

```text
MAIN_S01_C02_E01
```

望ましくない例:

```text
a8f4c2e1
```

---

## 2.3 機械処理しやすいこと

IDには原則として以下のみを使用する。

```text
A-Z
0-9
_
-
```

使用しないもの:

- 空白
- 日本語
- 全角記号
- 機種依存文字

---

## 2.4 タイトルをIDに含めないこと

ストーリータイトルやエピソードタイトルはIDに含めない。

理由:

- タイトル変更に強くするため
- 表記揺れを避けるため
- URLやファイル名を安定させるため
- 後から短縮タイトルや表示タイトルを変更できるようにするため

例:

```text
MAIN_S01_C02_E01
```

このIDが指すエピソードのタイトルは `Story_Metadata.md` で定義されるメタデータとして保持する。

---

## 2.5 出典カテゴリを含めること

ストーリーIDには、どの種類のストーリーかを表す接頭辞を含める。

例:

```text
MAIN
EVT
RAID
OTHER
CHAR_MAIN
CHAR_EXTRA
CHAR_DATE
```

---

## 2.6 Evidenceに使える粒度であること

Scene、Dialogue、Narration、Choiceなど、根拠として引用したい最小単位にもIDを割り当てる。

例:

```text
MAIN_S01_C02_E01_SC001_DLG0007
```

---

# 3. ストーリー種別プレフィックス

DKBでは以下のストーリー種別を採用する。

| Prefix | 種別 | 説明 |
|---|---|---|
| `MAIN` | メインストーリー | 本編ストーリー |
| `EVT` | イベントストーリー | 通常イベントストーリー |
| `RAID` | 共同戦線イベントストーリー | 共同戦線系イベント |
| `OTHER` | その他ストーリー | その他カテゴリのストーリー |
| `CHAR_MAIN` | キャラクターメインストーリー | キャラクター個別のメインストーリー |
| `CHAR_EXTRA` | キャラクターエクストラストーリー | キャラクター個別の追加・補足ストーリー |
| `CHAR_DATE` | キャラクターデートストーリー | キャラクター個別のデートストーリー |

この分類はDKBの正規ID体系の一部とする。

---

# 4. Story ID

## 4.1 メインストーリー章ID

形式:

```text
MAIN_S{season}_C{chapter}
```

例:

```text
MAIN_S01_C02
```

意味:

```text
メインストーリー 第1期 第2章
```

---

## 4.2 メインストーリー エピソードID

形式:

```text
MAIN_S{season}_C{chapter}_E{episode}
```

例:

```text
MAIN_S01_C02_E01
```

意味:

```text
メインストーリー 第1期 第2章 エピソード1
```

---

## 4.3 イベントストーリーID

形式:

```text
EVT_{eventNumber}
```

例:

```text
EVT_0162
```

エピソードID:

```text
EVT_0162_E01
```

`eventNumber` はDKB内で安定したイベント番号とする。

公式の内部イベントIDが判明している場合は、IDそのものではなくメタデータとして保持する。

---

## 4.4 共同戦線イベントストーリーID

形式:

```text
RAID_{raidNumber}
```

例:

```text
RAID_0027
```

エピソードID:

```text
RAID_0027_E01
```

---

## 4.5 その他ストーリーID

形式:

```text
OTHER_{number}
```

例:

```text
OTHER_0024
```

エピソードID:

```text
OTHER_0024_E01
```

---

## 4.6 キャラクターメインストーリーID

形式:

```text
CHAR_MAIN_{characterId}_E{episode}
```

例:

```text
CHAR_MAIN_AKAGI_HINA_E01
```

---

## 4.7 キャラクターエクストラストーリーID

形式:

```text
CHAR_EXTRA_{characterId}_E{episode}
```

例:

```text
CHAR_EXTRA_AKAGI_HINA_E01
```

---

## 4.8 キャラクターデートストーリーID

形式:

```text
CHAR_DATE_{characterId}_E{episode}
```

例:

```text
CHAR_DATE_AKAGI_HINA_E01
```

---

# 5. Episode / Scene / Content ID

## 5.1 Episode ID

Episode IDはストーリー種別と親ストーリーIDから派生する。

例:

```text
MAIN_S01_C02_E01
```

---

## 5.2 Scene ID

SceneはEpisode内で連番とする。

形式:

```text
{episodeId}_SC{sceneNumber}
```

例:

```text
MAIN_S01_C02_E01_SC001
```

`sceneNumber` は1始まり、3桁ゼロ埋めとする。

---

## 5.3 Dialogue ID

DialogueはEpisode内で連番とする。

形式:

```text
{episodeId}_DLG{number}
```

例:

```text
MAIN_S01_C02_E01_DLG0001
```

`number` は1始まり、4桁ゼロ埋めとする。

---

## 5.4 Monologue ID

形式:

```text
{episodeId}_MONO{number}
```

例:

```text
MAIN_S01_C02_E01_MONO0001
```

---

## 5.5 Narration ID

形式:

```text
{episodeId}_NAR{number}
```

例:

```text
MAIN_S01_C02_E01_NAR0001
```

---

## 5.6 Choice ID

形式:

```text
{episodeId}_CHOICE{number}
```

例:

```text
MAIN_S01_C02_E01_CHOICE001
```

---

## 5.7 Choice Option ID

形式:

```text
{choiceId}_OPT{number}
```

例:

```text
MAIN_S01_C02_E01_CHOICE001_OPT01
```

---

## 5.8 Stage Direction ID

Stage Directionは演出・背景・音声・制御命令などを保持する場合に使用する。

形式:

```text
{episodeId}_STAGE{number}
```

例:

```text
MAIN_S01_C02_E01_STAGE0001
```

Stage Directionを最初からすべて保存するかはParser仕様で決定する。

---

# 6. Entity ID

## 6.1 Character ID

キャラクターIDはローマ字表記をベースにした安定IDとする。

形式:

```text
CHAR_{ROMANIZED_NAME}
```

例:

```text
CHAR_AKAGI_HINA
```

キャラクターには複数の別名や表記揺れが存在してよいが、正規IDは1つだけとする。

ゲームスクリプト上のキャラクター番号はメタデータとして保持する。

例:

```json
{
  "id": "CHAR_AKAGI_HINA",
  "sourceCharacterId": "1",
  "name": "赤城陽菜"
}
```

---

## 6.2 ゲスト・コラボキャラクターID

ゲストキャラクターやコラボキャラクターも原則として `CHAR_` を使用する。

作品名による区別が必要な場合:

```text
CHAR_{WORK}_{NAME}
```

例:

```text
CHAR_COLLAB_EXAMPLE_HEROINE
```

正確な命名規則は、コラボ元データの確認後に確定する。

---

## 6.3 Organization ID

形式:

```text
ORG_{ROMANIZED_NAME}
```

例:

```text
ORG_IGYO_SEIBUTSU_TAISAKUHAN
```

略称や通称は `aliases` として別途保持する。

---

## 6.4 Location ID

形式:

```text
LOC_{ROMANIZED_NAME}
```

例:

```text
LOC_TAISAKUHAN_HONBU
```

---

## 6.5 Item ID

形式:

```text
ITEM_{ROMANIZED_NAME}
```

例:

```text
ITEM_DETARIKI
```

---

## 6.6 Event Entity ID

ここでのEventは「イベントストーリー」ではなく、作中で発生した出来事を指す。

形式:

```text
EVENT_{SHORT_NAME}
```

例:

```text
EVENT_TEAM1_FIRST_MISSION
```

---

## 6.7 Concept / Lore ID

世界設定・概念・用語には `LORE_` を使用する。

形式:

```text
LORE_{ROMANIZED_NAME}
```

例:

```text
LORE_DETARIKI_Z
```

---

# 7. Relationship ID

リレーションを独立した記録として保存する場合、IDを割り当てる。

形式:

```text
REL_{sourceId}_{relationshipType}_{targetId}
```

例:

```text
REL_CHAR_AKAGI_HINA_MEMBER_OF_ORG_IGYO_SEIBUTSU_TAISAKUHAN
```

時間経過で変化する関係には連番を付ける。

形式:

```text
REL_{sourceId}_{relationshipType}_{targetId}_{number}
```

例:

```text
REL_CHAR_AKAGI_HINA_TRUSTS_CHAR_AOI_NANAMI_0001
```

---

# 8. Evidence ID

Evidenceは、可能な限り最小単位を参照する。

優先順位:

1. Dialogue
2. Monologue
3. Narration
4. Choice Option
5. Scene
6. Episode
7. Story

例:

```json
{
  "sourceId": "MAIN_S01_C02_E01_DLG0007",
  "storyId": "MAIN_S01_C02",
  "episodeId": "MAIN_S01_C02_E01",
  "sceneId": "MAIN_S01_C02_E01_SC001",
  "confidence": 0.94
}
```

---

# 9. ファイル命名

## 9.1 正規化済みストーリーJSON

章単位:

```text
data/normalized/main/MAIN_S01_C02.json
```

エピソード単位:

```text
data/normalized/main/MAIN_S01_C02_E01.json
```

Parser開発時はエピソード単位を優先する。

将来的には章単位・エピソード単位の両方を扱えるようにする。

---

## 9.2 抽出済みKnowledge JSON

例:

```text
data/extracted/characters/CHAR_AKAGI_HINA.json
data/extracted/stories/MAIN_S01_C02.json
data/extracted/relationships/REL_....json
```

---

## 9.3 Wiki Markdown

Wikiのファイル名・URLは小文字スラッグを使用してよい。

例:

```text
site/docs/characters/akagi-hina.md
site/docs/stories/main/s01/c02.md
site/docs/organizations/igyo-seibutsu-taisakuhan.md
```

ただし、内部の正規IDは必ず大文字IDを維持する。

---

# 10. 未確定事項

## OD-001: ローマ字表記ルール

以下のどれを採用するか未確定。

- ヘボン式ローマ字
- 読みやすさ優先の独自ローマ字
- 手動管理のcanonical ID
- alias辞書による管理

推奨:

主要キャラクター・主要組織は手動でcanonical IDを管理する。

---

## OD-002: イベント番号の基準

イベント番号を何に基づけるか未確定。

候補:

- 公開順
- 内部ファイル順
- 公式ID
- 手動管理順

推奨:

初期段階では手動管理の安定したイベント順を使用する。

**関連（`feature/story-id-policy-real-sample-review`で追加）**: 現行実装（`Story_Manifest_Design.md` §8）はこのOD-002を未解消のまま、raw配置由来の`EVT_{sourceKey}`形式を暫定採用している。実データサンプルを踏まえた比較・推奨方針は`docs/architecture/05_Parser/Story_ID_Policy_Review.md`を参照（本PRではID生成ロジック自体は変更していない）。

---

## OD-003: キャラクターストーリーの番号体系

以下を確認する必要がある。

- 各キャラクターのエピソード番号が固定か
- 種別ごとに独立した番号か
- 解放順が存在するか
- ゲーム内カテゴリ名と一致させるか

現在採用するカテゴリ:

- `CHAR_MAIN`
- `CHAR_EXTRA`
- `CHAR_DATE`

---

# 11. 例

## 11.1 メインストーリー

```text
MAIN_S01_C02
MAIN_S01_C02_E01
MAIN_S01_C02_E01_SC001
MAIN_S01_C02_E01_DLG0001
```

---

## 11.2 キャラクター

```text
CHAR_AKAGI_HINA
CHAR_MAIN_AKAGI_HINA_E01
CHAR_EXTRA_AKAGI_HINA_E01
CHAR_DATE_AKAGI_HINA_E01
```

---

## 11.3 Evidence

```json
{
  "evidenceId": "MAIN_S01_C02_E01_DLG0001",
  "speakerId": "CHAR_RAIN",
  "speakerName": "レイン",
  "text": "というわけで、本日付けで異形生物対策班作戦参謀に任命されましたレインです"
}
```

---

# 12. 現時点の採用方針

採用済みのストーリー分類:

- `MAIN`: メインストーリー
- `EVT`: イベントストーリー
- `RAID`: 共同戦線イベントストーリー
- `OTHER`: その他ストーリー
- `CHAR_MAIN`: キャラクターメインストーリー
- `CHAR_EXTRA`: キャラクターエクストラストーリー
- `CHAR_DATE`: キャラクターデートストーリー

この文書はID仕様のみを扱う。

タイトル・表示名・公開日・開催期間・公開順・ソート順・画像などのメタ情報は `Story_Metadata.md` で定義する。
