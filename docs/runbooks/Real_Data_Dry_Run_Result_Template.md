# Real Data Dry-Run Result（実データdry-run結果サマリー）

Version: 0.1
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Real_Data_Dry_Run_Result_Template.md`
関連: `docs/runbooks/Real_Data_Dry_Run.md`（手順書）

---

# 1. 目的

`docs/runbooks/Real_Data_Dry_Run.md` の手順に従って実データでdry-runを行った際の結果を、**実データ本文・実セリフ・実データ由来IDを含めずに**数値サマリーとして記録するためのテンプレート。

このファイル自体はテンプレート兼直近1回分の実施記録を兼ねる。次回以降dry-runを実施する場合は、このファイルの数値セクションを更新するか、日付を付けた別ファイルとして複製する。

---

# 2. 実施記録（2026-07-03 実施分）

## 2.1 dry-run対象

- 対象話数: 2話
  - EVTカテゴリ 1話（イベントストーリー、会話・演出コマンドを含む）
  - CHAR_MAINカテゴリ 1話（キャラクターストーリー、会話・演出コマンドを含む）
- 選択肢（`branch`/`#if`）を含む話は今回の対象データセット（6話中）に1件も無かった。次回dry-runでは選択肢を含む話を優先的に選定する。
- 実データ本体は `data/raw/dry_run/`（ignored）に配置し、本ドキュメントには一切含めていない。

## 2.2 Parser dry-run結果

- 2話とも parse 成功（exit code 0、`--validate --check-compat` 込み）
- Normalized Story JSON生成件数: 2件（`data/normalized/dry_run/`、ignored）
- 総ブロック数: 話1=1431、話2=842
- ブロック種別内訳（重要な発見、§3参照）:
  - dialogue/monologueの件数は、raw scriptの `@ChTalk` 系コマンド出現数と完全一致（欠落なし）
  - 一方で全ブロックの58〜69%が `unknown` に分類された（stage_directionとしては認識されない演出コマンド群が多数存在するため。破棄はされていない）
- 互換性チェック結果: 話1=warning、話2=needs_update（standalone `check_script_compatibility.py` 実行時）/ warning（`normalize_story.py --check-compat` 経由でNormalized JSONに埋め込まれるcompatibilityReport）
  - 未知コマンド種類: 話1=5、話2=5
  - 新規会話コマンド候補: 話1=0、話2=2（standalone実行時のみ検出。§3.4参照）
  - 未登録キャラクターID: 話1=5、話2=3
  - 制御文字除去: 話1=8件、話2=0件

## 2.3 Extractor dry-run結果

- 2話ともextraction成功（exit code 0、`--validate` 込み）
- episode_extraction生成件数: 2件（`data/extracted/dry_run/`、ignored）
- Extraction validation結果: schema validation / semantic validation ともに2/2件で成功（`--semantic` 込み）
- evidenceIds破損: 無し（semantic validationで実在確認済み）
- candidateCounts概要（2話合算）:
  - characters: 12
  - locations: 2
  - organizations / items / lore / events / relationships / timelineCandidates: いずれも0
- unknown/warningの大量発生: 無し（validation warning 0件）

## 2.4 Merger dry-run結果

- merge成功（exit code 0、manual overrideなし）
- `report.inputResults`: 2件とも `valid`
- `report.candidateCounts`: characters=12, locations=2, 他0（Extractorの合算と一致）
- `report.mergedEntityCounts`: characters=12, locations=2, 他0
- `report.unresolvedEntityCounts`: characters=12, locations=2（**candidateCounts / mergedEntityCountsと完全一致 = 生成された全entityが `status: unresolved`**。§3.3参照）
- `report.conflictCounts`: total=0
- `report.warningCounts`: total=0
- `report.relationshipTypeSummary`: knownTypes={}, unknownTypes={}（relationship candidateが0件のため計算対象なし）
- `report.canonicalIdSummary`: totalAssigned=0, duplicateCount=0, invalidCount=0
- `report.manualOverrides`: 未指定のため無し
- `entities.*` 件数: characters=12, locations=2, organizations/items/lore/events/relationships/timeline=0（`mergedEntityCounts`と一致）

---

# 3. 主な問題点

## 3.1 [このPRで修正済み] コンソール出力の絵文字によるWindows cp932コンソールでのクラッシュ

`scripts/normalize_story.py` と `scripts/check_script_compatibility.py` のコンソールサマリー表示に絵文字（✅/⚠️/🔶/🚫）が含まれており、Windows日本語版の既定コンソールコードページ（cp932）では `print()` 自体が `UnicodeEncodeError` を送出していた。

- `normalize_story.py`: JSON Schema検証が実際には成功しているにもかかわらず、成功メッセージの絵文字printが例外を送出し、広い `except Exception` に捕捉されて「検証中にエラーが発生しました」という**誤った**エラー報告・非ゼロ終了になっていた。
- `check_script_compatibility.py`: 同種の絵文字printが**未捕捉**のまま `main()` 内で例外送出し、tracebackとともに終了コード1でクラッシュしていた。CLAUDE.mdはこのスクリプトの終了コード（0/1/2）を「意味のあるシグナル」として明記しているため、これは特に重大（cp932コンソールでは「クラッシュ由来の1」と「本来のneeds_updateとしての1」が区別できなくなる）。

**対応**: コンソール表示専用の文字列から絵文字を除去（Markdownレポート内の絵文字は変更していない）。回帰防止のため `tests/scripts/test_console_output_encoding.py` を追加（`PYTHONIOENCODING=cp932` を子プロセスに渡してOSに依らず再現）。

## 3.2 [未修正・既知の課題] 演出コマンドのブロック分類カバレッジ不足

実データでは全ブロックの58〜69%が `unknown` に分類された。セリフ・モノローグ自体は raw script の `@ChTalk` 系コマンド出現数と完全一致しており欠落は無いが、`pos`/`euler`/`fov`/`camera`/`wait`/`ui`/`rdraw`/`ch`/`hide`/`screen`/`prefab`/`image` 等、カメラ・演出系の大量のコマンドが `stage_direction` として認識されず `unknown` のまま保持されている。

設計上「不明情報を破棄しない」（AI_CONTEXT.md §13.3）という不変条件には違反していない（破棄されていない）が、`config/script_commands.yaml` / `agents/parser/parser.py` の `STAGE_DIRECTION_COMMANDS` を実データに合わせて拡充しないと、Wiki生成等の後工程で演出情報を活用しづらい。

## 3.3 [未修正・既知の課題] キャラクター辞書の実データカバレッジ不足

`reference/parser/characters_reference.json` は66件（数値ID `"1"`〜`"66"` 相当）を登録済みだが、実データが参照する数値キャラクターIDは66を大きく超える範囲（例: 200番台）にあり、今回の2話で使われたIDは1件も辞書内で解決できなかった。

結果として、merge後の全12キャラクター・2場所エンティティが `status: unresolved` のまま（`canonicalIdSummary.totalAssigned = 0`）。実データを本格投入する前に、キャラクター辞書（または将来の `knowledge/dictionaries/*.yaml`）の拡充が実質的な前提条件になることが分かった。

## 3.4 [未修正・既知の課題] 2つの互換性チェック経路の判定不一致

`check_script_compatibility.py` を単体実行した場合（`needs_update`、新規会話コマンド候補2件）と、`normalize_story.py --check-compat` 経由でNormalized JSONに埋め込まれる `compatibilityReport`（`warning`、新規会話コマンド候補0件）とで、同じ入力ファイルに対する判定が食い違うケースを確認した。

CLAUDE.mdに既存の既知ギャップとして記載されている「`config/script_commands.yaml` と `parser.py` のハードコードされたマップが統一されていない」という制約が、実データで具体的な数値の食い違いとして顕在化した一例。

## 3.5 [未修正・既知の課題] `--check-compat` のレポート出力先がカスタマイズ不可

`normalize_story.py --check-compat` は内部で `check_script_compatibility.py` を `--output` 指定なしのまま呼び出すため、互換性レポートは常にプロジェクトルート直下の `data/reports/` に出力される。dry-run手順が推奨する `data/reports/dry_run/` のようなサブディレクトリ配下に出力先を統一できない（`.gitignore` は深さに依らず `data/reports/**/*.json` 等をカバーするためcommit事故のリスクは無いが、整理上の不便がある）。

---

# 4. 次に直すべきこと

1. `config/script_commands.yaml` / `agents/parser/parser.py` の演出コマンド辞書を、実データで見つかった `pos`/`euler`/`fov`/`camera`/`wait` 等のコマンド群に合わせて拡充する（§3.2）
2. キャラクター辞書（`reference/parser/characters_reference.json` または `knowledge/dictionaries/*.yaml`）を実データが参照する番号帯まで拡充する（§3.3）
3. `check_script_compatibility.py` 単体実行と `normalize_story.py --check-compat` 経由の判定差異の原因を特定し、解消方針を検討する（§3.4）
4. `--check-compat` のレポート出力先をオプションで指定可能にするか、既定動作として明示的にドキュメント化する（§3.5）
5. ~~選択肢（`branch`/`#if`）を含む実データでの追加dry-run実施~~ → §6（2026-07-04実施）で対応完了。branch/choiceのブロック配置バグ3件と、句読点のみの本文行が欠落する不具合1件を発見・修正
6. `RelationshipCandidate`/`TimelineCandidate`/`ItemCandidate`/`LoreCandidate`/`EventCandidate` は、実データに明示的な構造化タグ（`itemId`/`relationshipType`等）が無いため0件だった。自然文からの推定（LLM抽出）が無い限り、rule-based抽出だけでは実データからこれらのCandidateを得られないことが確認された（設計通りの制約であり、バグではない）

---

# 5. 生成物・commit状況

- 実データ・生成物（`data/raw/dry_run/`、`data/normalized/dry_run/`、`data/extracted/dry_run/`、`data/reports/dry_run/`、`workspace/dry_runs/*/`）は一切commitしていない（すべて`.gitignore`で保護済み、`scripts/check_dry_run_inputs.py`で無検出を確認済み）
- commitした内容: `scripts/normalize_story.py`・`scripts/check_script_compatibility.py`の絵文字print修正、回帰テスト`tests/scripts/test_console_output_encoding.py`、本ドキュメント、`TASKS.md`/`AI_CONTEXT.md`の軽微更新のみ

---

# 6. 実施記録（2026-07-04 branch / choice included dry-run）

## 6.1 dry-run対象

- 対象話数: 1話（選択肢`branch`/`#if`/`#else`/`#endif`を含むMAINカテゴリ相当のエピソード。既存の実データ6話には`branch`コマンドが無かったため、ユーザーに追加配置してもらった）
- 分岐構造: `branch`（2択）+ `#if`/`#else`/`#endif`（`#elseif`無し、ネストなし）

## 6.2 Parser dry-run結果

- Parser成功（exit code 0、`--validate --check-compat`込み）
- **修正前の総ブロック数: 312件 → 修正後: 623件**（後述のバグにより#endif以降のブロックがchoiceの最後のoptionに隠れていたため、修正で約2倍に増加）
- dialogue件数（58件）・monologue件数（6件）が、生スクリプトの`@ChTalk`（58件）・`@ChTalkMono`（6件）出現数と完全一致することを確認
- choice blockは2つのoptionそれぞれに4ブロックずつの対称な構造（修正前はoption側に315ブロックが誤って集中）

## 6.3 Extractor / Merger dry-run結果

- Extraction成功、schema validation・semantic validationともに成功
- candidateCounts: characters=6、locations=1、他0
- Merger成功。mergedEntityCounts=candidateCountsと一致、conflictCounts=0、warningCounts=0
- CHAR_RAIN/CHAR_AKAGI_HINAが正しく`existingCharacterId`解決され、`canonicalIdSummary.totalAssigned=2`
- choice内話者がCharacterCandidate抽出の対象外という既存設計（PR #7）が正しく機能していることを確認（choice内block IDはevidenceIndexに存在するが、CharacterCandidateのevidenceIdsからは参照されない）

## 6.4 見つけた問題点（Parser本体のバグ、すべて修正済み）

1. **`#endif`後にcurrent_choiceがトップレベルのNoneへ戻らない不具合（最重要）**: `#if`ハンドラが`branch`直後のcurrent_choice自身を退避スタックへpushしていたため、`#endif`で同じオブジェクトが戻るだけで、本来Noneに戻るべき状態に戻らなかった。修正: 退避スタックへのpush/popを`branch`コマンド呼び出し時点に変更
2. **ネストしたbranchの新choiceが常にシーン直下へ追加される不具合**: 修正: 配置を`_add_block`経由に変更
3. **ネストしたbranch終了後にoption位置が復元されない不具合**: 修正: 退避スタックの要素を`(current_choice, current_option_idx)`のタプルに変更
4. **句読点・省略記号のみの本文行（「……」等）がUNKNOWN扱いになり本文が欠落する不具合**: `tokenizer.py`の日本語判定がGeneral Punctuationブロック（省略記号等）を含んでいなかった。修正: TEXT判定条件に「ASCII以外の文字を含む」を追加

## 6.5 見つけたが今回修正しなかったもの

実データ中の未登録コマンド（bare-word: `costume`/`fa`、`@`付き: `@TalkPosR`/`@TalkPosL`/`@ChEyeOff`/`@VisibleS`/`@FadeOutBlack`）を発見した。これらはbranch/choice固有の課題ではなく`script command coverage`と同じ性質の課題のため、今回は追加せずTASKS.mdに記録した（次回のcommand coverage作業へ持ち越し）。

## 6.6 教訓: branch/choiceの検証はブロック構造の目視確認が必須

`compatibilityReport`や`candidateCounts`のような集計指標だけでは、branch/choiceのブロック配置バグは検出できなかった（集計値は「合計は合っているが配置が間違っている」ケースを見逃す）。今回発見できたのは、choiceの各optionのblocks件数・line範囲を直接確認し、かつdialogue/monologue件数を生スクリプトの`@ChTalk`系コマンド出現数と突き合わせたため。今後branch/choiceを含む実データを検証する際は、この2点を必ず確認すること（詳細は`docs/runbooks/Real_Data_Dry_Run.md` §19）。
