# Real Data Dry-Run Procedure（実データdry-run手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Real_Data_Dry_Run.md`

---

# 1. 目的

実データ（実際の`.dec`スクリプト）を使って、Parser → Extractor → Merger → Report確認までの一連のパイプラインをローカル環境だけで試験実行するための手順を定義する。

**実データ・生成物は一切Gitにcommitしない。** このdocumentはあくまで「ローカルのignored領域でどう試すか」の手順書であり、dry-runの実行結果自体をリポジトリへ持ち込むための手順ではない。

---

# 2. 前提

- `uv sync` 済みであること（`pyproject.toml`参照）
- 実データ（`.dec`ファイル）を別途、社内配布・個人保有等の手段でローカルに用意していること（本ドキュメントは配布経路自体を扱わない）
- 以下のスキーマ・スクリプトを把握していること
  - `schemas/extraction.schema.json`（Stage A: episode_extraction）
  - `schemas/merged_knowledge_collection.schema.json`（Stage B: merge engine collection wrapper）
  - `scripts/normalize_story.py` / `scripts/extract_story.py` / `scripts/validate_extraction_json.py` / `scripts/merge_extractions.py`
- `docs/architecture/06_AI/Merged_Knowledge_Design.md`・`docs/architecture/06_AI/Canonical_ID_Policy.md` を一読していること（report確認時の用語の意味を理解するため）

`schemas/normalized_story.schema.json` という名前のファイルは現時点で存在しない。正規化済みStory JSONの構造は `agents/parser/normalizer.py` および `docs/architecture/05_Parser/Normalized_Story_JSON.md` を参照する。

---

# 3. 実データをcommitしないルール（最重要）

以下は`TASKS.md` §5の既存ルールをdry-run手順の文脈で再掲する。

- 実`.dec`スクリプト全文をcommitしない
- `data/raw/` `data/normalized/` `data/extracted/` `data/reports/` 配下の生成物をcommitしない
- `workspace/` 配下のdry-run出力をcommitしない
- APIキー・`.env`をcommitしない
- 実データ由来のfixtureを`tests/fixtures/`に追加しない（`tests/fixtures/`は小さい自作データのみ）

これらは`.gitignore`（§4）で機械的に担保するが、**`.gitignore`は「うっかりaddしてしまう」ことへの保険であり、`git add -f`等での意図的な追加までは防げない**。dry-run後は必ず§9のチェックリストで確認すること。

---

# 4. .gitignoreの確認

このPRで`.gitignore`に以下を追加・確認した。

| パターン | 対象 | 状態 |
|---|---|---|
| `data/raw/**/*.dec` | 実.decスクリプト | 既存 |
| `data/raw/**/*.txt` | 実スクリプトのtxt書き出し | 既存 |
| `data/normalized/**/*.json` | Normalized Story JSON生成物 | 既存 |
| `data/extracted/**/*.json` | episode_extraction生成物 | 既存 |
| `data/reports/**/*.json` | レポート生成物（JSON） | 既存 |
| `data/reports/**/*.md` | レポート生成物（Markdown） | 既存 |
| `workspace/dry_runs/` | dry-run出力一式 | **今回追加** |
| `.env` / `.env.*`（`.env.example`除く） | 環境変数ファイル | **今回追加** |
| `*.log` | ログファイル | **今回追加** |

**`workspace/`全体は今回ignoreしていない。** 既存の`workspace/experiments/`・`workspace/notebooks/`・`workspace/reviews/`・`workspace/tmp/`は`.gitkeep`でGit管理されており、`workspace/reviews/`には既に人間が作成したレビュー文書（`Script_Compatibility_Analysis_ja_v0.1_updated.md`）がcommit済みである。これらの既存運用（人間が意図して残す文書はcommitしてよい領域）を壊さないため、dry-run出力専用の`workspace/dry_runs/`だけをignore対象にした。

`tests/fixtures/` 配下は引き続きignore対象に含めない（小さい自作fixtureは既存ルール通りcommit対象）。

確認コマンド:

```bash
git check-ignore -v workspace/dry_runs/20260703_000000/merged_collection.json
git check-ignore -v data/extracted/_raw/MAIN_S01_C02_E01.extraction.json
```

---

# 5. 推奨ローカルディレクトリ構成

```text
data/
  raw/            # 実.decスクリプトの配置場所 (既存、.gitignore済み)
    main/
    event/
    character/
    collaboration/
    other/
  normalized/     # Normalized Story JSON出力先 (既存、.gitignore済み)
  extracted/      # episode_extraction出力先 (既存、.gitignore済み)
    _raw/
  reports/        # script_compatibility_report等 (既存、.gitignore済み)

workspace/
  dry_runs/
    20260703_000000/   # dry-run実行ごとのタイムスタンプディレクトリ (今回追加、.gitignore済み)
      merged_knowledge_collection.json
```

`data/raw/` `data/normalized/` `data/extracted/` `data/reports/` は既にリポジトリに`.gitkeep`付きで存在する（`data/reports/`は`.gitkeep`なしだが`.gitignore`で保護済み）。追加でディレクトリを作る必要があるのは`workspace/dry_runs/<timestamp>/`のみ。

`workspace/dry_runs/<timestamp>/`のタイムスタンプ命名は`YYYYMMDD_HHMMSS`形式を推奨する（複数回のdry-runを時系列で見分けるため）。

---

# 6. 入力配置例

```bash
mkdir -p data/raw/main
cp /path/to/your/local/copy/MAIN_S01_C02_E01.dec data/raw/main/
```

実データの入手経路（社内共有ドライブ、個人保有アーカイブ等）はプロジェクト外の運用に委ねる。本ドキュメントはこの後の処理手順のみを扱う。

---

# 7. normalized JSON生成手順

```bash
uv run python scripts/normalize_story.py \
    --input data/raw/main/MAIN_S01_C02_E01.dec \
    --story-id MAIN_S01_C02 --episode-id MAIN_S01_C02_E01 --category MAIN \
    --output data/normalized/main/ \
    --validate --check-compat
```

- `--check-compat`は`scripts/check_script_compatibility.py`相当のチェックを内包する。事前に単独で実行してもよい:

```bash
uv run python scripts/check_script_compatibility.py data/raw/main/MAIN_S01_C02_E01.dec --output data/reports/
```

- `story_manifest.yaml`（`docs/architecture/05_Parser/Story_Manifest_Design.md`）が用意できている場合は、任意で`--manifest`/`--raw-root`を追加すると`--story-id`/`--category`等を毎回手動指定する代わりにmanifestから自動解決できる（`--manifest`未指定時は本セクションの手順のまま変わらない）:

```bash
uv run python scripts/normalize_story.py \
    --input EVENT/csl_script_event_250626_dancer_export/CAB-csl_script_event_250626_dancer-episode1.dec \
    --output data/normalized/event/ \
    --manifest workspace/story_manifest/story_manifest_candidates.yaml \
    --raw-root . \
    --validate --check-compat
```

  - exit code `0`: compatible、`1`: needs_update、`2`: blocked。`1`/`2`の場合は`config/script_commands.yaml`または`reference/parser/characters_reference.json`相当のキャラクター辞書を確認してから先に進む（`CLAUDE.md`参照）。

---

# 8. extraction JSON生成手順

```bash
uv run python scripts/extract_story.py \
    --input data/normalized/main/MAIN_S01_C02_E01.json \
    --output data/extracted/_raw/ \
    --validate
```

複数エピソードがある場合はエピソードごとに実行する（`extract_story.py`は`--input`にファイル1件のみを受け付ける、Phase 1時点の仕様）。

---

# 9. extraction validation手順

```bash
# schema検証のみ
uv run python scripts/validate_extraction_json.py --input data/extracted/_raw/

# semantic validationも含める (evidenceIds実在確認、duplicate candidate id、
# extractionRun整合性、relationship基本チェック、timeline基本チェック)
uv run python scripts/validate_extraction_json.py --input data/extracted/_raw/ --semantic
```

`--input`にはファイル・ディレクトリのどちらも指定できる（ディレクトリ指定時は再帰的に`*.json`を検証する）。

dry-run前後の状態確認には、このPRで追加した補助スクリプトも使える。

```bash
uv run python scripts/check_dry_run_inputs.py --count-json data/extracted/_raw
```

`data/extracted/_raw/`配下のJSON件数と、`documentType: "episode_extraction"`を持つファイル（= `merge_extractions.py --input`の対象候補）の一覧が表示される。

---

# 10. merge手順

```bash
mkdir -p workspace/dry_runs/20260703_000000

uv run python scripts/merge_extractions.py \
    --input data/extracted/_raw \
    --output workspace/dry_runs/20260703_000000/
```

- `--input`はファイル・ディレクトリ・globパターンのいずれも複数指定可（`--input`, `-i`, `nargs="+"`）
- `--recursive`/`-r`でサブディレクトリまで再帰的に探索する
- 出力は`workspace/dry_runs/20260703_000000/merged_knowledge_collection.json`固定名で書き出される

---

# 11. manual overrideを使う場合の手順

```bash
uv run python scripts/merge_extractions.py \
    --input data/extracted/_raw \
    --overrides knowledge/overrides/base.json \
    --output workspace/dry_runs/20260703_000000/
```

- `--overrides`は`schemas/manual_overrides.schema.json`準拠のファイルを1つ以上指定できる（`nargs="+"`）
- overrideファイル自体はGit管理対象（`Merged_Knowledge_Design.md` §8.1、`knowledge/overrides/`配下に置く想定。**このPRでは`knowledge/overrides/`ディレクトリ自体はまだ作成していない**）
- overrideファイルがschema検証に失敗した場合、merge実行前にexit code `1`で停止する（無駄なmerge処理を避けるため。`scripts/merge_extractions.py`の既存実装）
- 対象entityが見つからないoverrideは`skipped`扱いになる（エラーにはならない）。`report.manualOverrides.skippedCount`で件数を確認する（§12）

---

# 12. report確認ポイント

`workspace/dry_runs/<timestamp>/merged_knowledge_collection.json` の `report` フィールドを、以下の順に確認する。

| フィールド | 確認内容 |
|---|---|
| `report.inputResults` | 各入力ファイルが`valid`/`invalid`/`skipped`のどれか。`invalid`があれば`errors`を確認する |
| `report.candidateCounts` | Stage A candidate件数の全体合算（type別） |
| `report.mergedEntityCounts` | merged entity件数（type別）。0件が続く場合はcandidate抽出自体を疑う |
| `report.unresolvedEntityCounts` | `status: unresolved`のentity件数（type別）。構造化ID（`existing*Id`）が解決されていない候補が多い場合はキャラクター辞書の充実度を疑う |
| `report.conflictCounts` | `total`/`bySeverity`/`byType`/`byEntityType`。`field_value_conflict`（displayName等の表記ゆれ）が多い場合は正規化ルール・辞書の見直しを検討 |
| `report.warningCounts` | `unresolvedRelationships`（source/target未解決でskipされたrelationship件数）、`skippedOverrides`（overrides未適用件数） |
| `report.relationshipTypeSummary` | `knownTypes`/`unknownTypes`。`unknownTypes`が多い場合、暫定taxonomy（`agents/merger/relationship_taxonomy.py`）に追加すべき語彙が無いか検討する（ただしtaxonomy本確定はこのPRのNon-goals） |
| `report.canonicalIdSummary` | `totalAssigned`/`duplicateCount`/`invalidCount`。`invalidCount`/`duplicateCount`が0でない場合は`warnings`を確認する（`docs/architecture/06_AI/Canonical_ID_Policy.md`参照） |
| `report.manualOverrides` | （`--overrides`指定時のみ）`appliedCount`/`skippedCount`/`errorCount`と`results[]` |
| `entities.*` の件数 | `collection.entities.characters` 等8配列それぞれの`length`。`mergedEntityCounts`と一致するはず |
| unresolved relationship warnings | `report.warnings`のうち、`agents/merger/relationship.py`の`UNRESOLVED_ENDPOINT_MARKER`文言を含むもの |
| unknown relationshipType | `report.relationshipTypeSummary.unknownTypes`のキー一覧 |
| invalid / duplicate canonicalId | `report.canonicalIdSummary.warnings`のうち「形式が不正」「重複しています」を含むもの |
| timeline unresolved entries | `entities.timeline`は現状の設計上**常に`status: unresolved`**（`Merged_Knowledge_Design.md` §7.1）。件数のみ確認すればよく、`unresolved`であること自体はエラーではない |
| `sourceDocuments` | どの入力ファイルがmergeに使われたか（`documentId`/`episodeId`/`candidateCounts`） |

---

# 13. よく見るwarning / error

| メッセージの特徴 | 意味 | 対応 |
|---|---|---|
| `relationshipTypeが空のためrelationship mergeをskipしました` | RelationshipCandidateの`relationshipType`が空文字 | Stage A抽出ロジック側の確認（`agents/extractor/relationship.py`） |
| `...をmerged entityへ解決できなかったためrelationship mergeをskipしました` | source/targetがcandidate id・merged entity idのどちらとしても解決できない | Character/Organization等のcandidateが先に解決されているか確認。`sourceCandidate`/`targetCandidate`の値を確認 |
| `未知のrelationshipType '...' はtaxonomy未登録のため '...' として保持しました` | `relationship_taxonomy.py`のKNOWN_RELATIONSHIP_TYPESに無い値 | 破棄はされない。taxonomy追加が必要か検討（本確定はNon-goals） |
| `canonicalId '...' の形式が不正です` | `is_valid_canonical_id`が形式チェックで拒否 | 手動で設定したcanonicalId（manual override等）の表記を確認 |
| `canonicalId '...' がentity type '...' 内で...件重複しています` | 同一type内で同じcanonicalIdが複数entityに付いている | 構造化ID解決ロジックまたはmanual overrideの誤りを確認 |
| `status=unresolvedのentityにcanonicalId '...' が設定されています` | unresolvedのままcanonicalIdだけ設定された状態 | 意図的（manual overrideでの先行指定）か誤りかを確認 |
| schema検証エラー（`validate_extraction_json.py`） | `schemas/extraction.schema.json`との不一致 | Stage A出力側の実装バグの可能性が高い。fixtureで再現できるか確認してから`agents/extractor/`側を疑う |

---

# 14. dry-run後の掃除方法

```bash
# dry-run出力の削除 (workspace/dry_runs/ 配下のみ)
rm -rf workspace/dry_runs/20260703_000000/

# 生成物すべての削除 (実データそのものは別途手動で扱う)
rm -rf data/normalized/main/*.json
rm -rf data/extracted/_raw/*
rm -rf data/reports/*.json data/reports/*.md

# 実.decスクリプトの削除 (ローカル保管方針に従って別途管理する)
rm -rf data/raw/main/*.dec
```

`.gitkeep`ファイルは誤って削除しないよう注意する（`git status`で復元可能だが、ディレクトリ構成を保つため）。

---

# 15. commit前チェックリスト

dry-run実施後、何かをcommitする前に必ず以下を確認する。

- [ ] `git status` に `data/raw/` 配下の実データファイルが出ていない
- [ ] `git status` に `data/normalized/` 配下の生成物が出ていない
- [ ] `git status` に `data/extracted/` 配下の生成物が出ていない
- [ ] `git status` に `data/reports/` 配下の生成物が出ていない
- [ ] `git status` に `workspace/dry_runs/` 配下の出力が出ていない
- [ ] 実`.dec`スクリプトがcommit対象（`git diff --cached --stat` / `git status`）に含まれていない
- [ ] 実データ由来のJSON（Normalized Story JSON・episode_extraction・merged collection）がcommit対象に含まれていない
- [ ] `.env`・APIキーらしき文字列がcommit対象に含まれていない
- [ ] `tests/fixtures/` に追加したファイルが合成データ（`CHAR_TEST_*`等の合成ID）のみで、実データ由来の名前・本文・IDを含まない

このPRで追加した`scripts/check_dry_run_inputs.py`（引数なし実行）で、上記のうち「commitしてはいけないファイルがgit tracked状態になっていないか」を機械的に確認できる。

```bash
uv run python scripts/check_dry_run_inputs.py
```

exit code `0`なら問題なし、`1`なら該当ファイルが一覧表示される。

---

# 16. 関連ドキュメント

- `docs/architecture/06_AI/Merged_Knowledge_Design.md`（Stage B全体設計、§11 Directory layout）
- `docs/architecture/06_AI/Canonical_ID_Policy.md`（canonicalId関連のreport確認時に参照）
- `docs/architecture/05_Parser/Script_Compatibility_Check.md`（`check_script_compatibility.py`の判定基準）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
- `docs/runbooks/Real_Data_Dry_Run_Result_Template.md`（実施結果の数値サマリーテンプレート・直近の実施記録）

---

# 17. 実施記録からの補足（2026-07-03 real data dry-run trial）

実データ2話での初回dry-run trialで、本手順書の想定通りに動作しない点・追加の注意点が見つかった。詳細は `docs/runbooks/Real_Data_Dry_Run_Result_Template.md` を参照。要点のみここに記す。

- Windows日本語環境（cp932コンソール）では、`normalize_story.py`/`check_script_compatibility.py`のコンソールサマリーに絵文字が含まれていると`UnicodeEncodeError`でクラッシュ・誤ったエラー報告になっていた（このtrialで修正済み）。今後同様のCLIを追加する場合、コンソール向け出力に絵文字を使う際はcp932環境での動作確認を行うこと。
- `normalize_story.py --check-compat`は互換性レポートの出力先を指定できず、常にプロジェクトルート直下`data/reports/`に出力される（`data/reports/dry_run/`等のサブディレクトリを指定していても効果が無い）。dry-run後のクリーンアップ（§14）では、指定したサブディレクトリだけでなく`data/reports/`直下も確認すること。
- `check_script_compatibility.py`単体実行時の判定と、`normalize_story.py --check-compat`経由でNormalized JSONに埋め込まれる`compatibilityReport`の判定が食い違うことがある（新規会話コマンド候補の検出件数など）。report確認（§12）の際はどちらの経路の結果を見ているか区別すること。
- 実データに`itemId`/`relationshipType`等の明示的な構造化タグが含まれない場合、Item/Lore/Event/Relationship/Timeline Candidateは0件になる（rule-based抽出の設計上の制約であり、バグではない）。Character/Locationの抽出件数のみを見て「抽出が動いていない」と誤解しないこと。

---

# 18. Unknown Commandの継続的な取り込み運用

実データは今後も継続的に投入される想定であり、`config/script_commands.yaml`・`agents/parser/parser.py`（`DIRECTION_TYPE_MAP`）・`agents/parser/tokenizer.py`（`KEYWORD_TOKENS`）は一度整備して終わりではない。新しい実データバッチを投入するたびに、以下の運用でunknown commandを段階的に取り込む（`feature/script-command-coverage`でEVT/CHAR_MAIN各1話のunknownブロック率を68.8%/60.7%→0.1%/0%まで下げた際の手順を一般化したもの）。

## 18.1 検出（破棄しない）

unknown commandは以下の2経路で検出される。**どちらの経路でも、未知コマンドは破棄せず必ずreportまたはcompatibilityReportに残す**（AI_CONTEXT.md §13.3の既存不変条件）。

- Parser経由: Normalized Story JSONの`compatibilityReport.unknownCommands`（コマンド名と出現数）、および各Sceneの`blocks`内の`type: "unknown"`ブロック（`notes`に元のコマンド名を保持）
- compatibility check経由: `scripts/check_script_compatibility.py`（単体実行）の`report.unknownCommands`（`sampleLines`付き）。§17で記録した通り、この2経路の判定は現状完全には一致しない（`feature/compatibility-check-consistency`で対応予定）ため、両方を確認すること

## 18.2 一覧化

実データ投入・dry-run実施後、以下のいずれかでunknown command一覧を確認する。

```bash
# 標準出力にunknownCommands一覧が出る (--check-compat込みのnormalize_story.pyでも同等の情報が出る)
uv run python scripts/check_script_compatibility.py data/raw/<対象>/ --output data/reports/<対象>/
```

```python
# コマンド名だけを機械的に列挙したい場合 (tokenizerを直接使う簡易確認、実データ本文は出力に含めない)
import sys; sys.path.insert(0, ".")
from agents.parser.tokenizer import Tokenizer, TokenType
from pathlib import Path
from collections import Counter

counter = Counter()
for f in Path("data/raw/<対象>").glob("*.dec"):
    for t in Tokenizer().tokenize_file(f):
        if t.token_type == TokenType.UNKNOWN:
            counter[t.command] += 1
print(counter.most_common(50))
```

（`TokenType.COMMAND`かつ`agents.parser.parser.STAGE_DIRECTION_COMMANDS`/`SPEAKER_ASSIGNMENT_COMMANDS`/会話コマンド集合のいずれにも含まれないものが、`@`付きの未登録コマンド）

出力される一覧・件数は**実データの生の内容**なので、コミット対象のファイル（TASKS.md・runbook等）にはコマンド名と件数のみを記録し、引数の実データ（キャラクター名・セリフ本文等）は書かないこと。

## 18.3 分類の優先順位

一覧化したunknown commandは、出現頻度が高いものから次の優先順位で分類方針を決める。

1. **会話・話者・分岐に影響するもの**を最優先で確認する（`@ChTalk`系の新規バリエーション、話者スロット割り当て、`branch`/`#if`系に類する分岐構文など）。これらは`speech`/`speaker_assignment`/`choice`カテゴリに関わる可能性があり、`config/script_commands.yaml`の追加だけでなく`agents/parser/parser.py`（`StoryParser._parse_tokens`）の分岐ロジック自体の変更が必要になる場合がある。会話・選択肢・speakerAssignmentsの抽出を壊さないことを最優先し、必要なら別PRとして慎重に扱う
2. **演出のみで意味解析が不要なもの**（カメラ・モーション・UI・サウンド・画面演出等）は、`stage_direction`として保持できれば十分とする。意味を完全解析しようとしない（`direction_type`は既存カテゴリ: `background`/`sound`/`character_display`/`camera`/`motion`/`ui`/`video`/`system`、既存カテゴリに収まらない場合のみ最小限の新カテゴリを追加する。§3.2の`screen`のように、既存カテゴリで無理に表現しようとしない）
3. **意味が不明・出現頻度が極端に低いもの**（1〜数回のみ、コマンド名が不自然な形式のもの等）は、無理に分類せず`unknown`のまま残してよい（例: `feature/script-command-coverage`で残した`@ChBlueMan/BlueMan2`）

## 18.4 追加手順

分類方針が決まったコマンドは、以下の3箇所に追加する（`config/script_commands.yaml`とParser本体は別システムであり、`CLAUDE.md`記載の通りどちらか片方だけでは反映されない）。

1. `config/script_commands.yaml`の該当カテゴリ（`speech`/`speaker_assignment`/`choice`/`stage_direction`等）にコマンド名を追加（`check_script_compatibility.py`の既知コマンド判定に反映）
2. `@`プレフィックス無しのコマンドの場合のみ、`agents/parser/tokenizer.py`の`Tokenizer.KEYWORD_TOKENS`にも追加（`@`付きコマンドは`tokenizer.py`側の変更不要。先頭が`@`であれば自動的に`TokenType.COMMAND`になるため）
3. stage_directionとして保持する場合、`agents/parser/parser.py`の`DIRECTION_TYPE_MAP`にコマンド名→`direction_type`のマッピングを追加（`STAGE_DIRECTION_COMMANDS`は`DIRECTION_TYPE_MAP`のキーから自動導出されるため、この1箇所で両方に反映される）。会話・話者・分岐カテゴリに追加する場合は、該当する既存ロジック（`SPEAKER_ASSIGNMENT_COMMANDS`、`_parse_tokens`内の分岐処理等）を確認し、必要な分だけ変更する

## 18.5 テスト方針（実データ由来fixtureを使わない）

追加したコマンドの検証は、**実データそのものではなく合成fixtureで行う**（`tests/fixtures/`に実データ由来の本文・IDを追加しない、既存の`.gitignore`ルールとも一致）。

- `tests/parser/test_tokenizer.py`: 追加したコマンドが期待通りのTokenType（`KEYWORD`または`COMMAND`）になることを、短い合成スクリプト文字列で確認する
- `tests/parser/test_parser_basic.py`: 追加したコマンドが期待通りの`block_type`/`direction_type`になることに加え、**既存の会話・モノローグ・ナレーション抽出の件数やevidence用line_start/line_endが変わらないこと**を、演出コマンドとセリフを混在させた合成スクリプトで確認する（`feature/script-command-coverage`の`test_dialogue_count_unaffected_by_interleaved_camera_commands`が参考例）
- 本当に未知のコマンドが引き続き`unknown`として残ることを確認する回帰テストも合わせて追加する（分類対象を広げすぎていないことの担保）

実データでの効果測定（unknown率の変化等）は、ローカルの`data/raw/dry_run/`等ignored領域で確認してよいが、その結果（生成JSON・数値以外の実データ本文）はcommitしない。数値サマリーのみ`docs/runbooks/Real_Data_Dry_Run_Result_Template.md`またはTASKS.mdに記録する（§8-10と同じ方針）。

## 18.6 残ったunknownの扱い

分類しきれなかったunknown commandは、無理に分類せず`unknown`のまま残してよい。**破棄しないことが最優先**であり、`compatibilityReport.unknownCommands`・`report.unknownCommands`・`type: "unknown"`ブロックのいずれかに記録され続けている限り、後続バッチで再検討する機会は失われない。unknown件数が0になることを目標にしない（意味不明なコマンドを無理に既知カテゴリへ押し込めると、誤ったstage_direction分類やdirection_typeの誤用につながる）。

---

# 19. branch / choice を含む実データのdry-run（2026-07-04実施）

選択肢・分岐（`branch`/`#if`/`#elseif`/`#else`/`#endif`）を含む実データでのdry-runは、既存の実データ6話には`branch`コマンドが1件も含まれていなかったため未実施だった。ユーザーに選択肢入りの実データを追加配置してもらい、初めて検証した。

## 19.1 見つかった問題（Parser本体のバグ、すべて修正済み）

branch/choiceの検証は、`compatibilityReport`や`unknownCommands`のような表面的な指標だけでは不十分で、**Normalized Story JSONの実際のブロック構造（特にchoiceの各optionのblocks件数・line範囲）を直接確認する必要がある**ことが分かった。実際に以下の重大なバグが見つかった。

- **`#endif`後にシーンレベルへ戻らない**: トップレベルのbranchで`#if`が`branch`直後のcurrent_choice自身を退避スタックへpushしていたため、`#endif`で同じオブジェクトが戻ってくるだけで、本来`None`（シーンレベル）に戻るべき状態に戻らなかった。結果、`#endif`以降の内容（実データでは500行超）が最後のoptionへ丸ごと閉じ込められていた。
- **ネストしたbranchの配置ミス**: `branch`コマンドが新しいchoiceブロックを常にシーン直下へ追加しており、既に別のchoiceのoption内で使われた場合に配置がずれていた。
- **ネスト解除後のoption位置ずれ**: 退避スタックがcurrent_choiceのみを保持しoption位置を保持していなかったため、ネストしたbranch終了後に外側choiceの誤ったoptionへ後続ブロックが混入していた。

これらはすべて`agents/parser/parser.py`の分岐状態管理（`branch_stack`のpush/popタイミング）に起因しており、`docs/runbooks/Real_Data_Dry_Run_Result_Template.md`と同じ数値検証だけでは検出できない。**branch/choiceを含む実データを検証する際は、必ず choice block の各 option の中身（件数・line_start/line_end・対応する raw script の範囲）を目視確認すること。**

## 19.2 見つかった問題（Tokenizerのバグ、修正済み）

`agents/parser/tokenizer.py`の日本語判定（`JAPANESE_PATTERN`）が、かな・カナ・漢字・全角記号の範囲のみを対象としており、句読点・省略記号（「……」等、Unicode General Punctuationブロック）を含まない行を見落としていた。「……」のみの本文行がUNKNOWN扱いになり、対応するモノローグ・ナレーションの本文が欠落する不具合につながっていた。

**branch/choice以外でも、dialogue/monologue/narration件数を確認する際は、生スクリプトの`@ChTalk`系コマンド出現数と突き合わせて完全一致することを必ず確認すること**（§4のチェック項目参照）。今回はこの突き合わせによって発見した。

## 19.3 choice内話者の扱い（設計通り、問題なし）

choice内のdialogue/monologueのspeakerはCharacterCandidate抽出の対象外という既存設計（`agents/extractor/character.py`、Extraction_Pipeline.md §5.4）が実データでも正しく機能していることを確認した。choice内のblock IDはevidenceIndexには存在するが、どのCharacterCandidateのevidenceIdsからも参照されない。

---

# 20. キャラクター辞書 confirmed化のレビュー運用

`knowledge/dictionaries/characters.yaml`の`status: confirmed`エントリを安全に増やすための詳細ルール（confirmed/name_onlyの意味、confirmed化してよい条件・いけない条件、aliases/notesの扱い、実データ由来dumpをcommitしないルール等）は`docs/runbooks/Character_Dictionary_Review.md`に切り出した。本ドキュメントの§18（Unknown Commandの継続的な取り込み運用）と対になる、キャラクター辞書版の運用ドキュメントである。

`scripts/check_character_dictionary_coverage.py`は`--review-template-output <path>`オプションで、未登録sourceCharacterIdの人間確認用テンプレート（`docs/templates/character_dictionary_review_template.yaml`と同形式）をローカル（`.gitignore`対象領域）へ書き出せる。出力にはID番号・出現回数と空のプレースホルダーのみが含まれ、実データの本文・displayNameは含まれない。**この出力ファイル自体はcommitしない。**
