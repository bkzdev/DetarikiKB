# Content Scope Policy（コンテンツスコープ方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/01_Project/03_Scope.md`

---

# 1. Purpose（目的）

`data/raw/`配下のraw scriptは、本編ストーリー（`main`/`event`/`raid`カテゴリ）だけでなく、キャラクター別の演出コンテンツ（`character`カテゴリ）を含む多様な構成になっている。本文書は、どの範囲を**内部KB（Knowledge Base）の対象**とし、どの範囲を**公開面（Wiki出力・Evidence Index promotion）の対象**とするかを、カテゴリ横断で一貫した方針として定義する。

本文書が扱わないもの: 個別コマンドのparser実装（`config/script_commands.yaml`・`agents/parser/parser.py`）、実データのnormalize/promotion実行そのもの、`publicStoryId`/`storyId`の採番体系（`docs/architecture/05_Parser/Identifier_Specification.md`・`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`を参照）。

---

# 2. Background（背景）

`data/raw/`へ実データ全量（4,307件）が配置された時点（2026-07-13）で、大きく2種類のコンテンツが存在することが判明した。

- **本編系**（`-episode\d+\.dec$`等のファイル名パターン）: 2,301件。`main`/`event`/`raid`カテゴリの本編ストーリーに加えて、**`character`カテゴリの本編系エピソード（`episode1`〜`episode3`/`episode_EX`）および`character_date`カテゴリ（Surprise系）も含む**（内訳: episodeN 1,008件・episode_EX 220件・mainN 214件・Surprise_N（日付付き）859件）。既存のcompatibility check・辞書拡張作業（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md` §4.7）が完了済みで、既に内部KB化・Evidence Index promotionの両方が進行中。
- **演出系**: 残る約2,006件。`character`カテゴリのうち本編系エピソード（上記2,301件側に属する）を除いた残りであり、`H_sceneN`という命名パターンの演出コンテンツ本体・その変種（表記違い接尾辞や複製と見られる同名パターン）、および`camera`/`finish`/`episode_bgm`等の純コマンド演出ファイルからなる。

この演出系コンテンツ（特に`H_scene`系）をKBのどの範囲まで対象にするかは、`script-command-dictionary-expansion-batch-002`（PR #131）の時点で「演出系（H_scene等）2,006件のスコープ判断・対応」として保留（`Evidence_Index_Batch_Promotion_Policy.md` §4.7.4）にされ、複数セッションにわたり未決だった。本文書は、ユーザーが2026-07-15に行った決定に基づき、この保留を解消するものである。

---

# 3. スコープの2軸

コンテンツのスコープ判断は、独立した2つの軸で行う。あるカテゴリが軸(A)=Yesでも軸(B)=Noになりうる（two-tier方針）。

## 3.1 軸(A): 内部KB対象か

Normalized Story JSONへの正規化・Extraction/Merge（Stage A/B）・character dictionary解決等、`knowledge/`配下の内部データとして扱ってよいかどうか。`AI_CONTEXT.md` §3.2の「不明情報を破棄しない」不変則がそのまま適用される（未知コマンド・未登録キャラIDは`unknown`ブロック/`compatibilityReport`として保持し、破棄しない）。

## 3.2 軸(B): 公開対象か

Wiki生成（`agents/wiki_generator/`）・Public Evidence Index promotion（`knowledge/evidence/stories/`）等、ユーザー以外の閲覧者に見える成果物として扱ってよいかどうか。`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`・`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`のpromotion criteriaが前提とする「公開してよいstory」の判断はこの軸に属する。

軸(A)=Yes・軸(B)=Noの組み合わせ（内部KB化はするが公開はしない）は、既存の内部ID/公開ID分離構造（`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`の内部trace ID/公開ID分離、`docs/architecture/06_AI/Canonical_ID_Policy.md`のcanonical ID未確定管理）と同じ設計思想の延長であり、新しい概念を導入するものではない。

---

# 4. H_scene系（characterカテゴリ演出コンテンツ）の決定

**決定日: 2026-07-15。以下はユーザーが明示的に決定した内容であり、数値・結論はAIエージェントが変更してはならない。**

## 4.1 対象ファイル構成

`data/raw/character/`配下は、キャラクター別ディレクトリ（72キャラクター分）で構成される。各キャラクターディレクトリは概ね以下の要素からなる。

- 本編系エピソード: `episode1`〜`episode3`/`episode_EX`（既存スコープ、§6参照）
- `H_sceneN`という命名パターンの演出コンテンツ本体: 全キャラクター合計517件
- 上記の変種と見られるファイル群: 接尾辞`_n`付き（504件）・接尾辞`_VR`付き（45件）・接尾辞`_spine`付き（約94件）・`#N`形式の複製と見られるもの（113件）・接尾辞`_s`付き（72件）
- 純コマンド演出ファイル: `camera`/`finish`/`episode_bgm`等、テキスト行を含まない演出専用script

## 4.2 決定1: two-tier方針（内部KB対象・公開対象は分離）

**H_scene系はすべて、軸(A)内部KBの対象に含める。軸(B)公開面（Wiki出力・Evidence Index promotion）からは恒久的に除外する。**

既存のinternal/public分離構造（§3.2）と整合する設計であり、H_scene系を内部KBの一部として正規化・保持することと、それをWikiやPublic Evidence Indexとして一般公開しないことは矛盾しない。恒久除外であるため、将来的な方針転換（例外的に一部を公開する）を行う場合は、本文書の改訂と、ユーザーによる新たな明示的決定を要する。

## 4.3 決定2: パース対象範囲の限定

**H_scene系のうち、実際にパース対象とするのはH_sceneN本体517件と`H_scene_s`接尾辞ファイル72件の合計約589件のみとする。**

`_n`接尾辞・`_VR`接尾辞・`_spine`接尾辞・`#N`複製は、「本体と同一内容の変種」として将来のmanifest（内部KB内でのファイル間対応関係の記録、設計は別タスク）に記録するのみに留め、パース対象には含めない。

### 4.3.1 根拠

1キャラクター分のサンプル検証（機械的比較）で、`_n`接尾辞変種のセリフ行（33行）が、本体のセリフ行（146行）の完全な部分集合であり、新規テキストが1行も含まれていないことを確認した。

### 4.3.2 検証範囲の限定に関する留保

上記の根拠は**1キャラクター分・1変種パターンのみのサンプル検証**である。全72キャラクター・全変種パターン（`_n`/`_VR`/`_spine`/`#N`）にわたって同じ部分集合関係が成立するかどうかは未検証であり、実際にパース対象を確定させて着手する際には、**全キャラクター横断での部分集合性検証を先行させる**（§5.3、後続タスク）。本決定はその検証結果を待たずに「589件のみをパース対象とする」という**方針**を先に確定するものであり、実パース着手のgateとして§5.3の検証を要求する。

## 4.4 技術的裏付け

1キャラクター分15ファイルに対するcompatibility check（2026-07-15実施）の結果は以下のとおりである。

- 未知コマンド: `@ToCloud`（4回出現）・`@VR`/`VRSelect`（1回出現）の2種のみ
- 未登録キャラクターID: 5〜6桁の数字帯（モブ/システムキャラクターと疑われる）が16種・延べ40回出現

パース自体は、`AI_CONTEXT.md` §3.2・§13.3（不明情報を破棄しない不変則）により、未登録キャラクターIDの辞書確定を待たずに実行可能である（未解決IDは「不明人物」placeholderとして保持され、破棄されない）。5〜6桁ID帯の辞書整備自体は別の未決事項として残る（§5.2）。

---

# 5. Open questions（未決事項）

以下は本文書の対象範囲ではあるが、2026-07-15時点でユーザー決定が行われていない事項である。

## 5.1 純コマンド演出ファイルの扱い

`camera`/`finish`/`episode_bgm`等、テキスト行を一切含まない純コマンド演出ファイルを、内部KB対象（軸A）に含めるかどうかは、本文書では決定していない。§4の決定はH_sceneN本体・`H_scene_s`にのみ適用され、これらの純コマンドファイルには及ばない。

## 5.2 5〜6桁キャラクターID帯の辞書整備

§4.4で判明した5〜6桁の数字IDを持つ未登録キャラクター（モブ/システム系と疑われる）を`knowledge/dictionaries/characters.yaml`へどう登録するかは、既存の未決事項（`docs/runbooks/Character_Dictionary_Review.md`関連）のまま未決である。

## 5.3 変種の全キャラクター横断部分集合性検証

§4.3.2で述べたとおり、`_n`/`_VR`/`_spine`/`#N`変種が全キャラクター・全パターンで本体の部分集合であることを機械的に検証するdry-runは、実パース着手前の後続タスクとして残っている。

---

# 6. 本編系（main / event / raid / character episode等）のスコープ整理

`main`/`event`/`raid`カテゴリの全story、および`character`カテゴリ内の本編系エピソード（`episode1`〜`episode3`/`episode_EX`）は、本文書の対象外（従来どおり）であり、**軸(A)内部KB対象・軸(B)公開対象の両方**に含まれる（two-tierの対象ではない、通常のstoryと同じ扱い）。既存のEvidence Index promotion運用（`docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`）・selection criteria（同§4.3）は、これら本編系storyにのみ適用され続ける。

---

# 7. 関連ドキュメント

- `AI_CONTEXT.md` §3.2・§13.3（不明情報を破棄しない不変則）
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`（Evidence Index batch promotion運用方針。promotion対象外カテゴリの明文ルールは同文書側にも追記済み）
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`（内部trace ID/公開ID分離方針）
- `docs/architecture/06_AI/Canonical_ID_Policy.md`（内部ID/canonical ID分離の同種の設計思想）
- `docs/runbooks/Character_Dictionary_Review.md`（characterId確定運用、§5.2の未登録ID帯と関連）
- `TASKS.md`（後続タスクの追跡）
