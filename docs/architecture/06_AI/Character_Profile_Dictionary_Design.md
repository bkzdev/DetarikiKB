# Character Profile Dictionary Design（キャラクター公式プロフィール辞書設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`

---

# 1. 目的

`knowledge/dictionaries/characters.yaml`（ID解決用辞書、`sourceCharacterId`/`characterId`/`displayName`/`aliases`/`status`/`notes`）とは別に、キャラクターの**公式プロフィール情報**（読み仮名・所属・身長・誕生日・血液型・CV・キャラ別特記事項・自己紹介文）を管理する専用辞書 `knowledge/dictionaries/character_profiles.yaml` を設計する。

このドキュメントは設計・schema・validator・templateの整備のみを対象とする。**実キャラクターのプロフィールデータ投入・Wiki rendererへの表示実装は行わない**（`TASKS.md`のfollow-upタスクとして別途扱う）。

---

# 2. characters.yamlとの役割分担

| ファイル | 役割 | 主なフィールド |
|---|---|---|
| `knowledge/dictionaries/characters.yaml` | **ID解決用辞書**。`sourceCharacterId`（ゲーム内キャラクター番号）と`characterId`（canonical ID）の対応付け、Extractor/Merger/Parserの構造化ID解決に使う | `sourceCharacterId`/`characterId`/`displayName`/`aliases`/`status`（`confirmed`/`name_only`）/`notes` |
| `knowledge/dictionaries/character_profiles.yaml`（本設計） | **公式プロフィール辞書**。Wiki Character pageの「基本プロフィール」section表示用の公式情報を保持する。ID解決・merge処理には一切関与しない | `characterId`/`displayName`/`reading`/`affiliation`/`heightCm`/`birthday`/`bloodType`/`cv`/`profileHighlight`/`selfIntroduction`/`source`/`status`/`notes` |

両者は`characterId`（`CHAR_{ROMANIZED_NAME}`形式のcanonical ID）で紐づく。`character_profiles.yaml`は`characters.yaml`の**下流**に位置し、`characters.yaml`側のID解決ロジック・Extractor/Merger処理には一切影響しない（読み取り専用の参照関係）。

---

# 3. Source of Truth方針

- `character_profiles.yaml`が保持するのは**公式（ゲーム内で明示された）プロフィール情報のみ**。AI抽出（Stage A/B由来の`sourceTypes`/`evidenceRefs`）やAI推測・AI考察とは明確に分離する（`AI_CONTEXT.md` §4.5「Official / AI Summary / AI Analysisを分離する」の具体化）
- 公式プロフィール本文（自己紹介文等）は`source`フィールドで出典（`sourceType`/`label`/`referenceId`）を明示し、由来を追跡できるようにする
- AIが公式プロフィールを推測・生成してエントリを追加することは禁止する（`docs/architecture/06_AI/Canonical_ID_Policy.md` §5と同様の精神: 人間の確認を経ない情報を確定情報として扱わない）

---

# 4. confirmed済みcharacterIdに紐づける方針

`character_profiles.yaml`の各エントリの`characterId`は、`knowledge/dictionaries/characters.yaml`で**`status: confirmed`**になっているcharacterIdのみを参照してよい。

理由: `status: name_only`のcharacterId（`characterId: null`の状態）はまだcanonical IDが確定していないため、プロフィール情報を紐づける安定したキーが存在しない。confirmed化（`docs/runbooks/Character_Dictionary_Review.md`の運用）を経てから、プロフィール登録の対象にする。

`scripts/validate_character_profiles.py`（§7）は、`character_profiles.yaml`の`characterId`が`characters.yaml`に存在しない、または`status: confirmed`でない場合に検証エラーとする。

---

# 5. 公式プロフィール / AI抽出 / AI考察を分離する方針

| 情報の種類 | 保持場所 | 例 |
|---|---|---|
| 公式プロフィール | `character_profiles.yaml`（本設計） | 読み仮名、所属、身長、誕生日、血液型、CV、キャラ別特記事項、自己紹介文 |
| AI抽出（Stage A/B） | merged knowledge collection（`schemas/merged_knowledge.schema.json`） | `evidenceRefs`由来の`displayName`/`aliases`/`fieldValues` |
| AI考察（Phase 3、未実装） | 別途AI analysis page（`Wiki_Output_Design.md` §8 Phase 3） | キャラクター考察・関係性分析等 |

Wiki Character pageでは、これら3種類の情報源を明確に区別して表示する（`Wiki_Output_Design.md` §8参照）。

---

# 6. フィールドごとの扱い

## 6.1 読み仮名（reading）

`{kana, romaji}`の構造体として保持する。読み仮名はID解決（`characterId`のローマ字表記）とは別軸の情報であり、`characters.yaml`側のIDそのものに影響しない。`aliases`/`searchAliases`（名前検索補助）との関係は本設計では定義しない（将来検討、§11参照）。

## 6.2 所属（affiliation）

**文字列配列**として保持する（`["Synthetic Team 1"]`のように所属が1つでも配列にする）。理由: 複数所属・所属変更履歴を将来表現しやすくするため。

## 6.3 身長（heightCm）

**整数（cm単位）**として保持する（例: `153`）。単位はフィールド名（`heightCm`）で表現し、値そのものには単位を含めない。表示時にWiki renderer側で「153cm」のように整形する方針とする（本PRでは表示実装は行わない）。

## 6.4 誕生日（birthday）

`{month, day, display}`の構造体として保持する。

- `month`（1-12）・`day`（1-31）で構造化し、和暦・西暦に依存しない月日のみの情報として扱う（年は保持しない）
- `display`は`"4/23"`のような表示用文字列を任意で持てる（無ければmonth/dayから機械的に組み立てられる想定、本PRでは組み立てロジックは実装しない）

## 6.5 血液型（bloodType）

初版では**文字列**として保持する（`A`/`B`/`O`/`AB`/`unknown`程度を想定するが、表記ゆれ吸収のためenum化はせず自由文字列とする）。

## 6.6 CV（cv）

現時点で参考にしたプロフィール例に無い項目だが、将来項目として保持できるよう最初からフィールドを用意する（文字列、null許容）。

## 6.7 キャラ別特記事項（profileHighlight）

【好きなこと】【将来の夢】【怖いこと】等、キャラクターごとにラベルが異なる短い特記事項を、`{label, value}`の**1件の構造体**として保持する（配列にしない、初版はキャラごとに1件のみ）。

- `label`: 「好きなこと」「将来の夢」「怖いこと」等の見出し文字列
- `value`: 1文程度の短文（想定文字数100〜200字程度、schema上の`maxLength`は緩め）

## 6.8 自己紹介文（selfIntroduction）

公式プロフィール本文として、複数行を許可した文字列で保持する。

- 最大500字程度に制限する（`schemas/character_profiles.schema.json`の`maxLength: 500`）
- AI要約・AI考察とは混ぜない（公式本文そのもの、または人間が要約した公式本文であることを`source`フィールドで明示する）
- **公開時の引用量・著作権面の確認は本設計のスコープ外**とし、別途確認が必要な事項として残す（実データ投入時に判断する）

## 6.9 出典（source）

`{sourceType, label, referenceId, notes}`の構造体。`sourceType`は`official_profile`（公式プロフィール由来）/`manual`（人間が手動で補足）/`unknown`（出典不明）を想定する。

## 6.10 status

エントリ自体の状態。`draft`（未確認・下書き）/`confirmed`（人間確認済み）/`deprecated`（廃止）を想定する。`characters.yaml`の`status`（ID解決の確定状態）とは別軸の値であることに注意する。

---

# 7. Wiki Character pageへの表示方針

**`feature/character-profile-renderer-section`で実装完了。**

- Character page（`Wiki_Output_Design.md` §9.4）に「基本プロフィール」sectionを新設し、`character_profiles.yaml`から該当`characterId`のエントリを参照して表示する（`render_character_page`、`agents/wiki_generator/renderer.py`）
- プロフィールが未登録のcharacterは「プロフィール未登録」と表示する（既存の「別名は登録されていません。」等と同じ、空状態を明示するパターンを踏襲）
- 表示フィールド: 読み仮名（reading）/所属（affiliation）/身長（heightCm、"150cm"のように整形）/誕生日（birthday.display優先、無ければmonth/dayから組み立て）/血液型（bloodType）/CV（cv）/Status/出典（source.label）/キャラ別特記事項（profileHighlight.label: profileHighlight.value）/自己紹介文（selfIntroduction）
- 「基本プロフィール」sectionは、既存の`## Summary`（AI抽出由来のEntity ID/Canonical ID/Status/Confidence等）とは明確に区別された見出しにする
- 自己紹介文は複数行のままMarkdown本文として表示する（AI要約・AI考察とは別sectionに分離）
- `scripts/render_wiki.py`に任意の`--character-profiles`引数を追加した。未指定でも既存の出力は変わらない（全Character pageが「プロフィール未登録」表示のまま）

---

# 8. 実データ・公式本文をこのPRで投入しない方針

本設計PR（`feature/character-profile-schema-design`）では以下を行わない。

- 実キャラクターのプロフィールデータの`character_profiles.yaml`への投入
- 実データ由来の自己紹介文・公式本文のcommit
- `characters.yaml`へのプロフィール項目追加
- `characters.yaml`のconfirmed化（本設計とは独立した作業）
- Wiki rendererへのプロフィール表示実装

実データ投入は次のfollow-upタスク（`TASKS.md` Backlog「character profile import batch 001」）で、人間が確認した公式プロフィール情報のみを対象に行う。

---

# 9. 参照

- `schemas/character_profiles.schema.json`（本設計のJSON Schema実装）
- `agents/parser/character_profiles.py`（loader/validator/index構築のPython実装）
- `scripts/validate_character_profiles.py`（CLI validator）
- `docs/templates/character_profiles_template.yaml`（合成データのみのテンプレート見本）
- `knowledge/dictionaries/characters.yaml`（ID解決用辞書、本設計の紐づけ先）
- `docs/architecture/06_AI/Canonical_ID_Policy.md`（canonical ID全体の方針）
- `docs/runbooks/Character_Dictionary_Review.md`（characters.yamlのconfirmed化運用）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.4（Character pageの表示設計）

---

# 10. 未確定事項（将来検討）

- `aliases`/`searchAliases`（名前検索補助）と`reading`の関係
- `birthday.display`の自動組み立てロジック（month/dayからの機械的整形）
- `profileHighlight`を複数件持てるようにするか（初版はキャラごとに1件の想定）
- 自己紹介文の引用量・著作権面の公開方針
- CVフィールドの実データでの扱い（複数CV・改名等のケース）
