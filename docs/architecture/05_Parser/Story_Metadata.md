# Story Metadata（ストーリーメタデータ仕様）

Version: 0.1 Draft  
Project: Detariki Knowledge Base (DKB)  
Path: `docs/architecture/05_Parser/Story_Metadata.md`

---

# 1. 目的

この文書は、Detariki Knowledge Base（DKB）で扱うストーリーおよびエピソードのメタデータを定義する。

メタデータとは、本文そのものではなく、ストーリーを識別・表示・並び替え・検索・分類するために必要な補助情報である。

例:

- タイトル
- サブタイトル
- 表示名
- 短縮タイトル
- 公開順
- 時系列順
- 公開日
- 開催期間
- 関連キャラクター
- 関連組織
- 画像
- ソースファイル情報

IDそのものは `Identifier_Specification.md` で定義する。

---

# 2. 基本方針

## 2.1 IDとタイトルは分離する

タイトルはIDに含めない。

理由:

- タイトルは変更される可能性がある
- 表記揺れが起きやすい
- Wiki表示用タイトルと内部管理名は用途が異なる
- IDは安定させる必要がある

例:

```json
{
  "storyId": "MAIN_S01_C02",
  "storyTitle": "異形生物対策班、始動！"
}
```

---

## 2.2 メタデータは後から補完できる

Parserが初回変換時にすべてのメタデータを取得できるとは限らない。

そのため、メタデータ項目には以下の状態を許容する。

- 取得済み
- 未取得
- 手動補完予定
- AI補完候補
- 不明

---

## 2.3 公式情報とAI推定情報を分ける

タイトルや公開日などは公式情報を優先する。

AIが推定した情報は、必ず `sourceType` や `confidence` を持たせる。

---

## 2.4 表示用とソート用を分ける

ユーザーに見せるタイトルと、機械的に並び替えるための値は分ける。

例:

```json
{
  "displayTitle": "異形生物対策班、始動！",
  "sortKey": "MAIN_S01_C02"
}
```

---

# 3. Story Metadata

Storyは章・イベント・キャラクターストーリー単位のまとまりを表す。

## 3.1 基本項目

```json
{
  "storyId": "MAIN_S01_C02",
  "storyCategory": "MAIN",
  "storyTitle": "異形生物対策班、始動！",
  "shortTitle": "異形生物対策班、始動",
  "subtitle": null,
  "displayTitle": "第1期 第2章「異形生物対策班、始動！」",
  "sortTitle": "01-02 異形生物対策班、始動！"
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `storyId` | Yes | `Identifier_Specification.md` で定義されたStory ID |
| `storyCategory` | Yes | `MAIN`, `EVT`, `RAID`, `OTHER`, `CHAR_MAIN`, `CHAR_EXTRA`, `CHAR_DATE` など |
| `storyTitle` | No | 公式または表示用のストーリータイトル |
| `shortTitle` | No | 一覧表示向けの短縮タイトル |
| `subtitle` | No | サブタイトル |
| `displayTitle` | No | Wikiで表示する完全なタイトル |
| `sortTitle` | No | 並び替えや一覧表示に使うタイトル |

---

## 3.2 メインストーリー用項目

```json
{
  "season": 1,
  "chapter": 2,
  "chapterLabel": "第2章",
  "seasonLabel": "第1期"
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `season` | MAINではYes | 期番号 |
| `chapter` | MAINではYes | 章番号 |
| `seasonLabel` | No | 表示用の期ラベル |
| `chapterLabel` | No | 表示用の章ラベル |

---

## 3.3 イベント系ストーリー用項目

対象:

- `EVT`
- `RAID`
- `OTHER`

```json
{
  "eventNumber": 162,
  "eventName": "イベント名",
  "eventType": "seasonal",
  "eventStartDate": null,
  "eventEndDate": null
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `eventNumber` | No | DKB内のイベント管理番号 |
| `eventName` | No | イベント名 |
| `eventType` | No | seasonal, collaboration, raid, campaign など |
| `eventStartDate` | No | 開催開始日 |
| `eventEndDate` | No | 開催終了日 |

---

## 3.4 キャラクターストーリー用項目

対象:

- `CHAR_MAIN`
- `CHAR_EXTRA`
- `CHAR_DATE`

```json
{
  "characterId": "CHAR_AKAGI_HINA",
  "characterName": "赤城陽菜",
  "characterStoryType": "CHAR_MAIN",
  "unlockCondition": null
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `characterId` | キャラストーリーではYes | 対象キャラクターID |
| `characterName` | No | 表示用キャラクター名 |
| `characterStoryType` | Yes | `CHAR_MAIN`, `CHAR_EXTRA`, `CHAR_DATE` |
| `unlockCondition` | No | 解放条件 |

---

# 4. Episode Metadata

EpisodeはStory内の個別エピソードを表す。

## 4.1 基本項目

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "episodeNumber": 1,
  "episodeTitle": "エピソード1",
  "episodeSubtitle": null,
  "displayTitle": "第1期 第2章 エピソード1",
  "sortKey": "MAIN_S01_C02_E01"
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `episodeId` | Yes | Episode ID |
| `episodeNumber` | Yes | Story内でのエピソード番号 |
| `episodeTitle` | No | エピソードタイトル |
| `episodeSubtitle` | No | エピソードサブタイトル |
| `displayTitle` | No | Wiki表示用タイトル |
| `sortKey` | No | ソート用キー |

---

## 4.2 エピソードタイトルが存在する場合

エピソードタイトルが判明している場合は、`episodeTitle` に保持する。

IDには含めない。

例:

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "episodeNumber": 1,
  "episodeTitle": "作戦参謀レイン",
  "displayTitle": "第1期 第2章 エピソード1「作戦参謀レイン」"
}
```

エピソードタイトルが存在しない場合:

```json
{
  "episodeId": "MAIN_S01_C02_E01",
  "episodeNumber": 1,
  "episodeTitle": null,
  "displayTitle": "第1期 第2章 エピソード1"
}
```

---

# 5. 順序情報

## 5.1 表示順

Wikiや一覧ページで表示する順番。

```json
{
  "displayOrder": 10201
}
```

例:

```text
Season 1 Chapter 2 Episode 1
→ 10201
```

---

## 5.2 公開順

ゲーム内で公開された順番。

```json
{
  "releaseOrder": 15
}
```

公開順が不明な場合は `null` とする。

---

## 5.3 作中時系列順

作中世界での時系列順。

```json
{
  "canonicalOrder": null
}
```

時系列が不明な場合は `null` とする。

AIが推定した場合は `sourceType` を `ai_inferred` とする。

---

# 6. ソースファイル情報

Parserで変換元ファイルを追跡するための情報。

```json
{
  "source": {
    "sourceFile": "main1-02-1",
    "sourcePath": "data/raw/main/season1/chapter02/episode01.txt",
    "sourceFormat": "game_script",
    "parserVersion": "0.1.0",
    "convertedAt": "2026-07-01T00:00:00+09:00"
  }
}
```

| Field | 必須 | 説明 |
|---|---:|---|
| `sourceFile` | Yes | 元ファイル名 |
| `sourcePath` | No | 元ファイルパス |
| `sourceFormat` | Yes | `game_script`, `merged_text`, `manual` など |
| `parserVersion` | No | 変換に使用したParserのバージョン |
| `convertedAt` | No | 変換日時 |

---

# 7. 関連情報

## 7.1 関連キャラクター

```json
{
  "relatedCharacters": [
    "CHAR_AKAGI_HINA",
    "CHAR_RAIN",
    "CHAR_AOI_NANAMI"
  ]
}
```

これはAI抽出結果でもよいが、後でKnowledge Graphから再計算可能にする。

---

## 7.2 関連組織

```json
{
  "relatedOrganizations": [
    "ORG_IGYO_SEIBUTSU_TAISAKUHAN",
    "ORG_GAL"
  ]
}
```

---

## 7.3 関連用語・世界設定

```json
{
  "relatedLore": [
    "LORE_DETARIKI",
    "LORE_DETARIKI_Z",
    "LORE_JAMMER"
  ]
}
```

---

# 8. 画像情報

人物ページやイベントページなどで使用する画像を参照する。

```json
{
  "images": {
    "bannerImage": null,
    "thumbnailImage": null,
    "mainVisual": null
  }
}
```

| Field | 説明 |
|---|---|
| `bannerImage` | イベント・章のバナー画像 |
| `thumbnailImage` | 一覧表示用サムネイル |
| `mainVisual` | ページ上部に表示する代表画像 |

画像の実体は `assets/images/` または `reference/screenshots/` に配置する。

---

# 9. 情報源管理

メタデータごとに情報源を持てるようにする。

例:

```json
{
  "storyTitle": "異形生物対策班、始動！",
  "metadataSources": {
    "storyTitle": {
      "sourceType": "manual",
      "confidence": 1.0,
      "note": "ユーザー提供の章タイトル"
    },
    "canonicalOrder": {
      "sourceType": "ai_inferred",
      "confidence": 0.62,
      "note": "本文内容から推定"
    }
  }
}
```

| `sourceType` | 意味 |
|---|---|
| `official` | 公式情報 |
| `script` | スクリプト本文から取得 |
| `manual` | 手動入力 |
| `ai_extracted` | AI抽出 |
| `ai_inferred` | AI推定 |
| `unknown` | 不明 |

---

# 10. Story Metadata 完全例

```json
{
  "storyId": "MAIN_S01_C02",
  "storyCategory": "MAIN",
  "storyTitle": "異形生物対策班、始動！",
  "shortTitle": "異形生物対策班、始動",
  "subtitle": null,
  "displayTitle": "第1期 第2章「異形生物対策班、始動！」",
  "sortTitle": "01-02 異形生物対策班、始動！",
  "season": 1,
  "chapter": 2,
  "seasonLabel": "第1期",
  "chapterLabel": "第2章",
  "displayOrder": 10200,
  "releaseOrder": null,
  "canonicalOrder": null,
  "episodes": [
    {
      "episodeId": "MAIN_S01_C02_E01",
      "episodeNumber": 1,
      "episodeTitle": null,
      "episodeSubtitle": null,
      "displayTitle": "第1期 第2章 エピソード1",
      "sortKey": "MAIN_S01_C02_E01"
    },
    {
      "episodeId": "MAIN_S01_C02_E02",
      "episodeNumber": 2,
      "episodeTitle": null,
      "episodeSubtitle": null,
      "displayTitle": "第1期 第2章 エピソード2",
      "sortKey": "MAIN_S01_C02_E02"
    },
    {
      "episodeId": "MAIN_S01_C02_E03",
      "episodeNumber": 3,
      "episodeTitle": null,
      "episodeSubtitle": null,
      "displayTitle": "第1期 第2章 エピソード3",
      "sortKey": "MAIN_S01_C02_E03"
    }
  ],
  "source": {
    "sourceFile": "merged_scripts_20260113_014536_1_coeiroink.txt",
    "sourcePath": "data/raw/main/season1/chapter02/merged_scripts_20260113_014536_1_coeiroink.txt",
    "sourceFormat": "merged_text",
    "parserVersion": "0.1.0",
    "convertedAt": null
  },
  "relatedCharacters": [],
  "relatedOrganizations": [],
  "relatedLore": [],
  "images": {
    "bannerImage": null,
    "thumbnailImage": null,
    "mainVisual": null
  },
  "metadataSources": {
    "storyTitle": {
      "sourceType": "manual",
      "confidence": 1.0,
      "note": "ユーザー提供またはファイルヘッダーから取得"
    }
  }
}
```

---

# 11. 未確定事項

## OD-001: `displayOrder` の計算式

メインストーリーでは以下のような計算式が候補。

```text
season * 10000 + chapter * 100 + episode
```

例:

```text
MAIN_S01_C02_E01
→ 10201
```

イベント・キャラクターストーリーでは別の計算式が必要。

---

## OD-002: `canonicalOrder` の扱い

作中時系列は公式に明示されない場合がある。

そのため、以下の方針が必要。

- 不明なら `null`
- AI推定なら `ai_inferred`
- 人間が確定したら `manual`
- 公式情報があるなら `official`

---

## OD-003: エピソードタイトルの取得元

エピソードタイトルが以下のどこから取れるか確認が必要。

- スクリプトファイル名
- ヘッダー
- ゲーム画面表示
- 手動入力
- AI推定

---

# 12. 採用方針

- IDにはタイトルを含めない
- タイトルは `storyTitle` / `episodeTitle` として保持する
- 表示用タイトルは `displayTitle` として別管理する
- ソート用情報は `sortTitle` / `sortKey` / `displayOrder` として別管理する
- 公開順と作中時系列順は別管理する
- AI推定情報は必ず `sourceType` と `confidence` を持つ

次の設計書では、このメタデータ仕様とID仕様を前提に `Normalized Story JSON` を定義する。
