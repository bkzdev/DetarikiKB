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

## 4.3 決定2: パース対象範囲の限定（2026-07-15、方向性(b)で確定）

**H_scene系のうち、実際にパース対象とするのは、H_sceneN本体517件・`H_scene_s`接尾辞ファイル72件（合計589件）に加え、本体の部分集合になっていない例外変種（§5.3の全量検証で確認された144件が上限、実際の件数はパース時の動的判定に依存）である。純粋な部分集合だった変種（615件）・`_VR`接尾辞全45件（§5.3で例外0件と確認済み）は、引き続きパース対象外のままとする。**

当初（本節初版時点）は`_n`接尾辞・`_VR`接尾辞・`_spine`接尾辞・`#N`複製のすべてを「本体と同一内容の変種」として一律パース対象外とする方針だったが、§4.3.3・§5.3の全量検証でこの前提が崩れたため、§5.5でユーザーが2026-07-15に方向性(b)（例外が発生したH_sceneN単位のみ変種もパース対象に追加する）を決定し、本節をその内容へ改定した。例外変種の特定は、実データ由来の具体的ファイルリストをcommitしない方針（§7・`AI_CONTEXT.md` §3.11）に従い、パース時に§5.3と同じ比較手法（発話系コマンドが参照するvoice/textアセットpath＋正規化日本語TEXT行の集合による部分集合判定）で動的に行う。実装上の制約・設計方針の詳細は§5.5を参照。

### 4.3.1 根拠

1キャラクター分のサンプル検証（機械的比較）で、`_n`接尾辞変種のセリフ行（33行）が、本体のセリフ行（146行）の完全な部分集合であり、新規テキストが1行も含まれていないことを確認した。この時点では「H_sceneN本体+`H_scene_s`の約589件のみ」を方針としていたが、§4.3.3・§5.3の全量検証・§5.5の(b)決定により、この589件に加えて例外変種（最大144件、動的判定）がパース対象へ加わることが確定している（上記§4.3参照）。

### 4.3.2 検証範囲の限定に関する留保

上記の根拠は**1キャラクター分・1変種パターンのみのサンプル検証**である。全72キャラクター・全変種パターン（`_n`/`_VR`/`_spine`/`#N`）にわたって同じ部分集合関係が成立するかどうかは未検証であり、実際にパース対象を確定させて着手する際には、**全キャラクター横断での部分集合性検証を先行させる**（§5.3、後続タスク）。本決定はその検証結果を待たずに「589件のみをパース対象とする」という**方針**を先に確定するものであり、実パース着手のgateとして§5.3の検証を要求する。

### 4.3.3 全量検証の結果（`h-scene-variant-subset-verification-dry-run`、2026-07-15実施）

§5.3で要求していた全キャラクター横断の部分集合性検証（dry-run）を実施した結果、**4.3.1のサンプル検証は代表的ではなく、全量では相当数の例外が確認された**（`_VR`は例外0件で確認どおりだったが、`_n`は約1割、`_spine`・`#N`は約4〜5割が部分集合関係不成立、詳細は§5.3）。本節初版時点の決定（H_sceneN本体+`H_scene_s`のみパース対象、`_n`/`_VR`/`_spine`/`#N`はパース対象外）は、その前提（変種は本体と同一内容の変種にすぎない）が全量では成立しないことが判明したため、変種の一部を将来パース対象に含める必要があるかどうかという新たな未決事項が§5.5として発生した。**この未決事項は2026-07-15にユーザーが方向性(b)（例外が発生したH_sceneN単位のみ変種もパース対象へ追加する）を決定し解消した。上記§4.3の決定内容は、この(b)決定を反映した最新版である**（決定の詳細・実装上の制約は§5.5を参照）。

## 4.4 技術的裏付け

1キャラクター分15ファイルに対するcompatibility check（2026-07-15実施）の結果は以下のとおりである。

- 未知コマンド: `@ToCloud`（4回出現）・`@VR`/`VRSelect`（1回出現）の2種のみ
- 未登録キャラクターID: 5〜6桁の数字帯（モブ/システムキャラクターと疑われる）が16種・延べ40回出現

パース自体は、`AI_CONTEXT.md` §3.2・§13.3（不明情報を破棄しない不変則）により、未登録キャラクターIDの辞書確定を待たずに実行可能である（未解決IDは「不明人物」placeholderとして保持され、破棄されない）。5〜6桁ID帯の辞書整備自体は別の未決事項として残る（§5.2）。

### 4.4.1 全量再検証による訂正（2026-07-15追加調査）

**上記「1キャラクター分15ファイルで未知コマンド2種のみ」は、1キャラ分サンプルに基づく過小評価だったことが判明した。** `data/raw/character/`全量（2,419ファイル）に対する再検証の結果、未登録コマンドは**41 distinct**（延べ出現数はチェッカーの`summary.unknownCommandCount`生値で1,016、ただしこの値は実際には「ファイル単位のdistinctコマンド数の合計」でありコマンド出現回数の合計ではない。出現回数ベースで再集計した実測値は、後述`@SpineTalk`を除く40種で延べ**1,228回**）であり、加えて`@SpineTalk`という新規発話コマンド（`@ChTalk`と同型の`@SpineTalk $numN <voice/textアセット参照path>`形式、延べ**2,893回**・132 distinctファイル）が別枠で検出された。

`@ToCloud`（523回）・`@VR/VRSelect`（50回）を含め、この41種はいずれも**パース対象外のvariant-onlyファイル集合（`_n`/`_VR`/`_spine`/`#N`変種、および`camera`/`finish`/`episode_bgm`等の純コマンド演出ファイル）にのみ出現するもの17種**と、**パース対象ファイル（H_sceneN本体・`H_scene_s`・episode系）に1回以上出現するもの24種**（既存登録コマンドの表記ゆれ`case-variant`・`$numX`/`$valueX`/`$common`/`$return`の個別インデックス`variable-token`が大半を占め、機械的分類が可能）に分かれる。`@SpineTalk`はパース対象ファイルには一度も出現せず、variant-only集合（`_spine`変種および同梱の`finish`系ファイル）にのみ出現することを確認した。

1キャラ分サンプルがこの2種のみを検出したのは、サンプルに含まれていた15ファイルの構成（variant側ファイルを含むが全variantパターン・全コマンド種を網羅していなかった）に起因すると考えられる。

全量インベントリ（コマンド別の出現回数・分類・ファイルスコープ）は`workspace/local_inputs/hscene_unknown_command_inventory.md`（非commit、`docs/runbooks/AI_PR_Playbook.md` §4 docs-only PR方針に基づきworkspace限定）にある。実コマンド登録・`@SpineTalk`の分類決定はいずれも本節の時点では未着手であり、§5に未決事項として記録する。

### 4.4.2 パース対象24種の登録実施（`script-command-dictionary-h-scene-parse-target-batch`、2026-07-15）

§4.4.1で確認した「パース対象ファイル（H_sceneN本体・`H_scene_s`・episodeN/episode_EX）に1回以上出現する24種」について、`scripts/check_script_compatibility.py --include-name-pattern`でパース対象ファイル集合（1,025ファイル）のみに絞った再スキャンで24 distinctを再導出し、機械分類可能なもの全てを`config/script_commands.yaml`・`agents/parser/parser.py`（`DIRECTION_TYPE_MAP`・`CASE_VARIANTS_MAP`）へ登録した。

分類内訳（24種すべてを機械分類でき、`要判断`として保留したものはなし）:

- **`case-variant`（7種）**: `@motionwaitU`→`@MotionWaitU`、`@ChEYe2RightLow`→`@ChEye2RightLow`、`@ChEye2RIghtLow`→`@ChEye2RightLow`、`@ChEye2LeftlOW`→`@ChEye2LeftLow`、`@ChEYe2RightHigh`→`@ChEye2RightHigh`、`@MotioNReset`→`@MotionReset`、`@Shadowoff`→`@ShadowOff`（正規コマンドはいずれも実データのコマンド構造・既存`case_variants`の同系統パターンから確認）
- **`variable-token`（9種）**: `$num1`〜`$num6`・`$value7`・`$value10`・`$common0`。実データでは`$num1`〜`$num6`が`$split(...)`関数呼び出しの結果代入、`$common0`が浮動小数点値の代入に使われており、いずれもcharacter-id系ではないことを確認した上で、既知の変数トークンとしてのみ登録した（`agents/parser/parser.py`は正規表現ベースで汎用対応済みのため変更不要、config側のみ変更）
- **`stage_direction`（8種）**: `@ShadowOff`（character_display、既存`@Shadow`のoff対）・`@ChBlueMan/SynchroMotionMirror`（motion）・`@Cache`（system、アセットキャッシュ）・`@SpringBone/BreastTouchRemoveCollider`（motion）・`@Spine/EyeRight`/`@Spine/EyeLeft`/`@Spine/EyeCenter`（character_display）・`@ChBlueMan/BlueManSuimedo`（character_display）

登録後、同じパース対象ファイル集合（1,025ファイル）への再スキャンで未登録コマンド数は24 distinctから0へ減少したことを確認した（残る`needs_update`判定は§5.2の未登録キャラクターID5件に起因するもので、本PRのスコープ外）。合成fixtureテスト（`tests/parser/test_parser_basic.py`・`tests/parser/test_compatibility_consistency.py`）を追加し、実parser/standalone checker両経路での無回帰を確認済み。

`@SpineTalk`・variant-onlyのみに出現する17種の扱いは、引き続き§5.4の未決事項のままである（本節の登録範囲には含まれない）。

---

# 5. Open questions（未決事項）

以下は本文書の対象範囲ではあるが、2026-07-15時点でユーザー決定が行われていない事項である。

## 5.1 純コマンド演出ファイルの扱い

`camera`/`finish`/`episode_bgm`等、テキスト行を一切含まない純コマンド演出ファイルを、内部KB対象（軸A）に含めるかどうかは、本文書では決定していない。§4の決定はH_sceneN本体・`H_scene_s`にのみ適用され、これらの純コマンドファイルには及ばない。

## 5.2 5〜6桁キャラクターID帯の辞書整備（2026-07-15調査により前提が更新）

§4.4で判明した5〜6桁の数字IDを持つ未登録キャラクター（モブ/システム系と疑われる）の扱いは、2026-07-15にユーザーが実施した`data/raw/`全量（4,301件）に対する消費文脈調査により、当初の前提が覆った。

**調査結果**: `scripts/check_script_compatibility.py`が「未登録キャラクターID」として検出する890 distinct IDのうち、**867件（97.4%）は話者スロットに一切束縛されない誤検出だった**（costume/mo/fa等の非話者引数としてのみ消費されるもの762件・延べ5,379回、いずれの消費経路にも当てはまらない未消費その他121件・延べ552回）。これは、compatibility checkerが`$numX`/`$valueX`代入行を検出した時点で無条件に「キャラID候補」と記録し、その後実際に話者スロットとして参照されるかどうかを区別していないことに起因する（`agents/parser/parser.py`側も同様に無条件でスロットへ自動バインドするが、そのスロットがどの会話コマンドからも参照されなければ話者として表面化しない）。

真に話者として使われる未登録IDは、当初の調査（変数形式`@ScenarioCos`未対応の調査スキャナによる暫定値）では**7件**（speaker-bound 2件・mixed 5件、いずれも3〜5桁帯。**6桁帯には話者実体が一件も無い**）だった。うち6件は`name`強制上書き（forced-name override）または`@ChTalkName`のインライン引数から表示名候補が実データから抽出できた。この7件は後述（§5.2末尾）のとおり、`@ScenarioCos`変数引数形式対応後の再スキャンで**6件**へ確定した。

調査手法の要点: resolver.py（`SpeakerResolver`）と同じ意味論で、`$numX`/`$valueX`代入・`@ScenarioCos`（直接指定）・`@ScenarioCosLoad`（変数経由）によるスロット再束縛を時系列1パスでシミュレートし、各時点のスロット状態を参照して`@ChTalk`系コマンドが実際にどのIDを話者として消費しているかを判定した。調査成果物（distinct ID単位の分析表・サマリー）は`workspace/local_inputs/`配下（非commit・workspace限定）にある。

また、本調査により重要なparserギャップが判明した。**`@ScenarioCos`（直接指定版）の第2引数が変数の形式**（例: `@ScenarioCos slot $numN ...`）は、`agents/parser/parser.py`の`SCENARIO_COS_PATTERN`（`^@ScenarioCos\s+(\d+)\s+(\d+)`、数値直指定のみ想定）・`scripts/check_script_compatibility.py`の対応する正規表現のいずれにも一切マッチせず、話者スロットへの束縛が取りこぼされる。raw全量のgrep集計では、この変数引数形式は延べ**約3,400回**出現し、数値直指定形式（約340回）より支配的であるため、話者スロット束縛の大量取りこぼしが起きている。なお`@ScenarioCosLoad slot $var`形式は`SCENARIO_COS_LOAD_PATTERN`で正しくマッチ・消費されており、問題は3トークン目以降に追加変数が置かれるパターン（例: `@ScenarioCosLoad 1 $num1 $value1 ON`）の追加トークンが未消費という点のみである（コスチューム値の可能性が高く、話者解決への影響は限定的、`feature/scenario-cos-variable-variant-support`のNon-goalsとして対応しない）。

**このgapは`feature/scenario-cos-variable-variant-support`（2026-07-15実装）で解消済みである。** `SCENARIO_COS_PATTERN`を`^@ScenarioCos\s+(\d+)\s+(\d+|\$[\w\d]+)`へ拡張し、第2引数が`$`始まりの変数の場合は`@ScenarioCosLoad`と同じ意味論（変数マップからIDを引いてスロットへ束縛、未定義変数はunknown speakerのまま破棄しない）で処理するよう`agents/parser/parser.py`・`scripts/check_script_compatibility.py`の両方を修正した（第3引数以降はコスチューム値として従来どおり無視、数値直接指定形式の既存挙動は無回帰）。

この変数形式`@ScenarioCos`について、以下の追加事実も確認済みである（2026-07-15追加検証）。

- 変数形式は特定カテゴリに偏らず**全カテゴリに分布**する（main約1,009回・event約1,168回・raid約103回・other約55回・character約671回・character_date約464回、計約3,470回）。
- ただし`$numX`形式では slot番号==変数index となるケースが3,218/3,278回（約98%）を占め、resolver.pyが`$numX`代入時に行う自動スロット束縛（slot=X）が結果的に正しい束縛を再現する。したがって実害（話者誤帰属）の可能性があるのは、不一致の60回と、`$valueN`形式（約540回、自動束縛のslot対応が自明でない）に限られる。

### 5.2.1 再スキャン結果（`@ScenarioCos`変数引数形式対応後、2026-07-15確定）

`@ScenarioCos`変数引数形式対応（§5.2冒頭）の実装後、調査スキャナ（同じ意味論へ更新済み）で`data/raw/`全量を再走査した。**真の未登録話者は7件から6件へ確定した**（speaker-bound 3件・mixed 3件、いずれも2〜5桁帯。未登録distinct ID総数890自体は不変、costume-motion-only/unconsumed-or-otherの内訳のみ組み替わっている）。

差分の内訳:

- **離脱2件**（3〜5桁帯、いずれも旧mixed分類）: `@ScenarioCos slot $varA $varB ...`という「話者ID変数＋コスチューム値変数」形式の行で、変数形式未対応だった旧スキャナ（および旧parser/checker）が第2引数（話者ID変数）のスロット再束縛を認識できず、スロットに残っていた別の代入由来の値（実際にはコスチューム値側の変数）を誤って話者として計上していた誤検出。修正後はスロットが正しい話者IDへ再束縛されるため、この誤検出は解消した。この2件は同一の構造的バグに起因する既知の対（パートナー役の組）であり、対応するIDは既に他の消費経路で確認されていた登録済みキャラクターの可能性が高い。
- **新規1件**（2桁帯、`main`カテゴリ、speaker-bound）: `$numX`/`$valueN`変数経由で`@ScenarioCos`のスロットへ束縛される話者IDで、変数形式対応前は一切検出されていなかった（全く新規の未登録ID候補）。表示名候補は実データから確認できていない。

**現状**: 真の未登録話者6件（確定値）は、`docs/runbooks/Character_Dictionary_Review.md`の既存レビュー運用に沿ったレビューパケットとしてユーザー確認待ちであり、確認後に`knowledge/dictionaries/characters.yaml`へconfirmed batchとして登録する（`Character_Dictionary_Review.md`の該当節を参照）。867件の誤検出については、checker側を消費文脈ベースの判定へ修正する後続実装PRで解消する予定であり、本文書時点ではまだ未着手である。

## 5.3 変種の全キャラクター横断部分集合性検証（`h-scene-variant-subset-verification-dry-run`、2026-07-15実施・結果確定）

§4.3.2で述べたとおり、`_n`/`_VR`/`_spine`/`#N`変種が全キャラクター・全パターンで本体の部分集合であることを機械的に検証するdry-runを実施した（**docs-only扱いのdry-run PR、`agents/parser/`・`scripts/`本体の変更なし**）。

**比較手法**: §4.4.1で判明していたとおり、`_spine`変種は本体の`@ChTalk`系セリフコマンドを`@SpineTalk`で置換している場合があるため、コマンド名一致ではなく、発話系コマンド（`@ChTalk`/`@ChTalkMono`/`@ChTalkSoundOff`/`@ChTalkSoundOffMono`/`@ChTalkName`/`@SpineTalk`および既知表記ゆれ）が参照するvoice/textアセットpath、および日本語TEXT行（正規化済み本文、開発用ログ行`log ----- ...`・モザイク指定行`mozaiku ...`等の非セリフ行は除外）の集合をセリフ内容の識別子とし、変種側の集合が本体側の集合の部分集合かどうかを機械比較した。対象は72キャラクターdir全件、`_n`/`_VR`/`_spine`/`#N`の4パターン計759ファイル（本体対応が存在しない孤立変種は0件）。

**結果**: **全量では4.3.1のサンプル検証（`_n`1パターンのみ・部分集合が成立）ほど良好ではなく、パターンによって成立率に大きな差があることが判明した。**

| パターン | 検証件数 | 部分集合成立 | 例外（本体に無い新規内容を含む） | 孤立変種（対応本体なし） |
|---|---|---|---|---|
| `_n` | 507 | 454 (89.5%) | 53 (10.5%) | 0 |
| `_VR` | 45 | 45 (100%) | 0 (0%) | 0 |
| `_spine` | 94 | 57 (60.6%) | 37 (39.4%) | 0 |
| `#N` | 113 | 59 (52.2%) | 54 (47.8%) | 0 |
| **合計** | **759** | **615 (81.0%)** | **144 (19.0%)** | **0** |

例外144件は72キャラクター中34キャラクターに分布する（孤立していない）。例外の内容形状を機械分類したところ、2パターンに大別された:

- **reverse_superset（53件、主に`#N`）**: 変種側が本体側の内容を全て含んだ上で、さらに追加の内容を持つ（本体が変種の部分集合になっている、想定と逆方向の包含関係）。実例確認では、本体ファイルが変種側の一部区間（例: 通し番号の後半のみ）に相当し、`#N`側が通し番号の先頭からの完全な内容を持っていた。
- **partial_overlap（91件、`_n`全件・`_spine`の大半・`#N`の一部）**: 変種側・本体側の双方に相手にない内容が存在し、どちらか一方が他方を包含する関係にない。実例確認では、本体ファイルが別のH_scene番号のアセットpath（既存音声の再利用）を短く参照する一方、対応する変種側が同一H_scene番号の通し番号で始まる独自の新規内容を持つケースを確認した。

**結論**: `_VR`は全件で§4.3.1の前提（本体と同一内容）が確認された。`_n`もおおむね成立する（約9割）が、1割は本体側にない内容を含む。一方`_spine`・`#N`は約4〜5割が部分集合関係不成立であり、**§4.3の決定の前提（変種は本体と同一内容の変種にすぎず、パース対象外としてよい）は`_spine`・`#N`については全量では裏付けられなかった**。詳細な集計・キャラクター別/ファイル別の一覧（匿名化不要な件数・パターンのみで構成、実キャラ名・実セリフ本文は含まない）は`workspace/local_inputs/h_scene_variant_subset_verification.md`・同`.tsv`（非commit）、例外の実内容（セリフ本文を含む）は`workspace/local_inputs/h_scene_variant_subset_exceptions_detail.md`（非commit）を参照。後続の判断事項は§5.5。

## 5.4 `@SpineTalk`の分類・variant-onlyコマンドの登録可否（2026-07-15追加、未決）

§4.4.1の全量調査で判明した以下2点は、いずれもユーザー/Fable判断待ちであり、**本文書では決定しない**。

1. **`@SpineTalk`の分類**: `@ChTalk`と同型のセリフ形式コマンド（`@SpineTalk $numN <voice/textアセット参照path>`）でありながら、`_spine`変種（§4.3の決定によりパース対象外）にのみ出現する。発話コマンドとして`config/script_commands.yaml`の`speech`カテゴリへ登録するか、`_spine`変種がそもそもパース対象外である以上登録不要とするかは未決定。
2. **パース対象外のvariant-only集合にのみ現れるコマンド（41種中17種、`@ToCloud`・`@VR/VRSelect`等を含む）を登録するかどうか**: パーサーが実際にこれらのコマンドに遭遇するのはvariant-only側ファイルを将来パース対象に含めた場合のみであり、現行の§4.3決定（H_sceneN本体+`H_scene_s`のみパース対象）の下では遭遇しない。登録を先送りするか、`unknown`ブロックとして扱われ続けることを許容するかは未決定。

インベントリ詳細は`workspace/local_inputs/hscene_unknown_command_inventory.md`（非commit）を参照。

## 5.5 変種の一部をパース対象に含める必要があるか（(b)で決定、2026-07-15ユーザー決定）

§5.3の全量検証で、`_spine`（39.4%）・`#N`（47.8%）・`_n`（10.5%）に、本体の部分集合になっていない例外が確認された（`_VR`は例外0件）。これにより、§4.3決定の当初前提（変種は本体と同一内容にすぎずパース対象外でよい）が全量では成立しないことが判明した。

1. **`#N`（reverse_superset型が主）**: 実例確認では、本体ファイル自体が変種側の内容の一部区間（部分集合）になっているケースを含む。この場合、本体のみをパース対象とすると、変種側にしか存在しない内容が内部KBから漏れる。
2. **`_spine`（partial_overlap型が多い）・`_n`（全件partial_overlap型）**: 実例確認では、本体ファイルが別のH_scene番号の既存アセットを再利用した短い内容である一方、対応する変種側は同一H_scene番号として独自の新規内容（新規音声/テキストアセット）を持つケースを確認した。この場合、本体・変種のどちらか一方だけをパースしても、もう一方にしかない内容が内部KBから漏れる。
3. 上記を踏まえ、(a) 現状の§4.3決定（本体+`H_scene_s`のみパース対象）を維持し例外は将来のmanifestで記録するに留めるか、(b) 例外が発生したH_sceneN単位のみ変種もパース対象に追加するか、(c) 全変種パターンをパース対象に含めるよう§4.3を改定するか、の3方向性を提示していた。

**決定（2026-07-15、ユーザー明示決定）: 方向性(b)を採用する。** 本体+`H_scene_s`（589件）に加え、本体の部分集合になっていない例外変種（最大144件）のみをパース対象に追加する。`_VR`は例外0件のため引き続き対象外、純粋な部分集合だった615件の変種も対象外のまま確定である。§4.3はこの決定を反映済み。

### 5.5.1 実装上の制約・設計方針（本PRで記録、実装自体は将来PRで着手）

本PRは方針の記録のみを行い、`agents/parser/`・`scripts/`本体の変更、H_sceneの実パース、例外検出ロジックの実装は一切行わない。将来の実装（§5.5.2参照）は、以下の設計方針に従うこと。

1. **例外変種の動的判定**: 「どの変種が例外か」という実ファイル名を含むリストは`data/raw/`由来の実データ派生物であり、`docs/runbooks/AI_PR_Playbook.md` §7・`AI_CONTEXT.md` §3.11のcommit禁止対象である。したがって、例外検出はcommitされた固定リストに依存せず、**パース実行時に動的判定する方式**とする。各H_sceneN本体に対し、その変種を§5.3と同じ比較手法（発話系コマンド＝`@ChTalk`/`@ChTalkMono`/`@ChTalkSoundOff`/`@ChTalkSoundOffMono`/`@ChTalkName`/`@SpineTalk`+既知表記ゆれが参照するvoice/textアセットpath、および正規化済み日本語TEXT行の集合）で部分集合判定し、本体の部分集合でない変種のみをパース対象へ含める。
2. **`reverse_superset`（変種⊇本体、主に`#N`）の取り込み方針**: 本体と例外変種の両方をパースし、重複はアセットpath同一性で重複排除すれば、変種側の追加内容も本体側内容も漏れなく取り込める。
3. **`partial_overlap`の取り込み方針**: 本体と例外変種の両方をパースし、双方固有の内容を取り込み、共有部分はアセットpath同一性で重複排除する。
4. **内容同一性の判定子**: §5.3の検証と同じ（voice/textアセットpath＋正規化TEXT行）とする。抽出段階で本体・変種間の重複を二重計上しないための重複排除ロジックが必要になる。
5. **着手タイミング**: この変種取り込みは独立PRではなく、将来の「character storyのstoryId/manifest設計」（Backlog `character-story-id-manifest-design`）の要件として組み込む。storyId/manifest設計自体は本PRのスコープ外であり、着手時にFableセッションでの設計を想定する。

### 5.5.2 関連タスク

- `TASKS.md` Backlogの`character-story-id-manifest-design`に、上記実装制約1〜5（例外変種の動的取り込み・アセットpath重複排除を要件に含む旨）を追記済み。
- `@SpineTalk`・variant-only 17種の登録可否（§5.4）は本決定の対象外であり、引き続き別途未決のままとする。

検証成果物（キャラクター別・パターン別の件数一覧、例外の実セリフ内容を含む詳細）はいずれもworkspace限定・非commit（`workspace/local_inputs/h_scene_variant_subset_verification.md`・`.tsv`・`h_scene_variant_subset_exceptions_detail.md`）。

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
