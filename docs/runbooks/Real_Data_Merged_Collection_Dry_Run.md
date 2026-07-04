# Real Data Merged Collection Dry-Run Procedure（実データmerged collection dry-run手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`

---

# 1. 目的

ローカルに存在する実データ由来のNormalized Story JSON（`scripts/normalize_story.py`の出力）を入力に、Extractor（`scripts/extract_story.py`）→ Merger（`scripts/merge_extractions.py`）を実行し、Wiki rendererの入力になるmerged knowledge collectionをローカル生成できるかを確認する手順を定義する。

`docs/runbooks/Real_Data_Dry_Run.md`が Parser → Extractor → Merger の一連の手順を扱うのに対し、本ドキュメントは**Normalized Story JSONが既に存在する状態からExtractor/Mergerのみを実行する**手順に絞って再掲する。生成できたmerged collectionをそのまま`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`のWiki render dry-runへ渡す手順も含める。

**実データ由来のextraction result・merged collection・Wiki Markdown・raw script・normalized JSONは一切Gitにcommitしない。**

---

# 2. 前提

- `uv sync` 済みであること
- ローカルに実データ由来のNormalized Story JSON（`scripts/normalize_story.py`の出力、`schemas/story.schema.json`準拠）が存在すること。存在しない場合は`docs/runbooks/Real_Data_Dry_Run.md` §6-7の手順で先に生成する
- 以下を把握していること
  - `docs/architecture/06_AI/Extraction_Pipeline.md`（Stage A: Extractorの設計）
  - `docs/architecture/06_AI/Extraction_Result_Schema.md`（episode_extractionの構造）
  - `docs/architecture/06_AI/Merged_Knowledge_Design.md`（Stage B: Mergerの設計）
  - `docs/architecture/06_AI/Canonical_ID_Policy.md`（canonicalId関連のreport確認時に参照）
  - `schemas/extraction.schema.json`・`schemas/merged_knowledge_collection.schema.json`

merged collectionの生成後にWiki Markdownまで確認したい場合は、`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`も参照する。

---

# 3. 入力ファイルの想定

- パス例: `data/normalized/<category>/<episodeId>.json`（`Real_Data_Dry_Run.md` §7の出力）
- 形式: `schemas/story.schema.json`準拠のNormalized Story JSON
- 既存の複数話・複数カテゴリ（main/character/event/other/raid等）をまとめて処理してよい

---

# 4. 出力先の想定

```text
workspace/dry_runs/<RUN_ID>/
  extracted/                          # Extractor出力 (episode_extraction JSON, episodeごと)
    <episodeId>.extraction.json
  merged/
    merged_knowledge_collection.json  # Merger出力 (merge_extractions.pyの固定出力ファイル名)

workspace/wiki_preview/<RUN_ID>/      # Wiki render handoff時の出力 (Real_Data_Wiki_Render_Dry_Run.md参照)
```

`<RUN_ID>`は`YYYYMMDD_HHMMSS`形式を推奨（`Real_Data_Dry_Run.md`と同じ命名方針）。

---

# 5. Extractor実行手順

Normalized Story JSON 1件につき1回実行する（`scripts/extract_story.py`は`--input`にファイル1件のみを受け付ける、Phase 1時点の仕様）。複数話ある場合はループで実行する。

```bash
mkdir -p workspace/dry_runs/<RUN_ID>/extracted

uv run python scripts/extract_story.py \
    --input data/normalized/main/<episodeId>.json \
    --output workspace/dry_runs/<RUN_ID>/extracted/ \
    --validate

# 複数話をまとめて処理する場合 (bash)
for f in data/normalized/*/*.json; do
    uv run python scripts/extract_story.py --input "$f" \
        --output workspace/dry_runs/<RUN_ID>/extracted/ --validate
done
```

`--validate`指定時、`schemas/extraction.schema.json`との検証結果がコンソールに表示される（`[DKB] JSON Schema 検証: OK`）。

---

# 6. Merger実行手順

```bash
mkdir -p workspace/dry_runs/<RUN_ID>/merged

uv run python scripts/merge_extractions.py \
    --input workspace/dry_runs/<RUN_ID>/extracted/ \
    --output workspace/dry_runs/<RUN_ID>/merged/
```

- `--input`はファイル・ディレクトリ・globパターンのいずれも複数指定可（`nargs="+"`）。ディレクトリを渡すと配下の`*.json`をまとめて処理する
- 出力は`workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json`固定名で書き出される
- manual overrideを使う場合は`--overrides`オプション（`docs/runbooks/Real_Data_Dry_Run.md` §11参照）

出力後、`schemas/merged_knowledge_collection.schema.json`で改めてschema検証しておくとよい（`merge_extractions.py`自体はschema検証結果を標準出力に出さないため）。

```bash
uv run python -c "
import json
from jsonschema import Draft7Validator
with open('schemas/merged_knowledge_collection.schema.json', encoding='utf-8') as f:
    schema = json.load(f)
with open('workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json', encoding='utf-8') as f:
    data = json.load(f)
errors = list(Draft7Validator(schema).iter_errors(data))
print('VALID' if not errors else [e.message for e in errors])
"
```

---

# 7. Wiki renderへ渡す手順

生成したmerged collectionをそのまま`scripts/render_wiki.py`の`--input`に渡す（`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`と同じ手順）。

```bash
uv run python scripts/render_wiki.py \
    --input workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json \
    --output workspace/wiki_preview/<RUN_ID> \
    --validate \
    --clean
```

---

# 8. commit禁止対象（最重要）

以下は`docs/runbooks/Real_Data_Dry_Run.md` §3・`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` §6・`TASKS.md` §5の既存ルールを再掲する。

- 実データ由来のNormalized Story JSON・episode_extraction JSON・merged knowledge collection JSON
- 実データ由来Wiki Markdown（`workspace/wiki_preview/`配下すべて）
- 実`.dec`スクリプト
- `data/raw/` `data/normalized/` `data/extracted/` `data/reports/` 配下の生成物
- `workspace/dry_runs/` 配下の出力
- `.env`・APIキー・ログファイル

これらは`.gitignore`（§9）でカバー済み。`git add -f`等での意図的な追加までは防げないため、dry-run後は必ず§14のチェックリストで確認すること。

---

# 9. .gitignoreの確認

本手順書で使うパスは、既存の`.gitignore`エントリで既にカバーされている（追加変更は不要）。

| パターン | 対象 |
|---|---|
| `workspace/dry_runs/` | Extractor/Merger dry-run出力一式 |
| `workspace/wiki_preview/` `workspace/wiki_render/` | Wiki render dry-run出力一式 |
| `data/extracted/**/*.json` | episode_extraction生成物 |
| `data/reports/**/*.json` `data/reports/**/*.md` | レポート生成物 |
| `data/normalized/**/*.json` | Normalized Story JSON生成物 |
| `generated/wiki/` `docs/wiki_generated/` `site_src/` | 将来のWiki生成物・サイトソース向け予備パターン |

確認コマンド:

```bash
git check-ignore -v workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json
git check-ignore -v data/normalized/main/<episodeId>.json
```

---

# 10. 確認項目

- [ ] Extractorがexit code `0`で完了する（episodeごと）
- [ ] `--validate`指定時、Extraction Result schema検証が通る
- [ ] Mergerがexit code `0`で完了する
- [ ] Merged Knowledge Collection schema検証が通る（§6の検証コマンド）
- [ ] `entities.*`（characters/locations/organizations/items/lore/events/relationships/timeline）の件数が確認できる
- [ ] `report.unresolvedEntityCounts`が確認できる
- [ ] `report.conflictCounts`が確認できる
- [ ] `report.warningCounts`が確認できる
- [ ] `report.canonicalIdSummary`が確認できる（0件でもキー自体は存在する）
- [ ] `report.relationshipTypeSummary`が確認できる
- [ ] 実データ本文・実セリフをdocsへ貼っていない（§12参照）
- [ ] 生成物（`workspace/dry_runs/`・`data/extracted/`・`data/normalized/`配下）が`git status --short`に出ていない、または`.gitignore`で保護されている

Wiki render handoffまで実施した場合、`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md` §9の確認項目も合わせて確認する。

---

# 11. よくある失敗

| 症状 | 想定される原因 | 対応 |
|---|---|---|
| Extractorが`--input`にディレクトリを渡してエラーになる | `extract_story.py`はファイル1件のみ受け付ける仕様（`merge_extractions.py`とは異なる） | ループで1ファイルずつ実行する（§5参照） |
| Merger実行後、`entities.*`が全種別0件 | 実データに構造化タグ（`itemId`/`relationshipType`等）が含まれない場合の既知の制約（rule-based抽出の設計上の制約、バグではない） | `docs/runbooks/Real_Data_Dry_Run.md` §17参照。Character/Locationの抽出件数のみを見て判断する |
| `unresolvedEntityCounts`が`mergedEntityCounts`と一致（全件unresolved） | キャラクター辞書（`knowledge/dictionaries/characters.yaml`）が実データの数値ID帯をカバーしていない既知の課題 | `scripts/check_character_dictionary_coverage.py`で確認。本dry-runのスコープでは辞書拡充は行わない |
| `characters/*.md`が1件も生成されない（Wiki render handoff時） | 上記と同じ理由でcanonicalId確定entityが0件 | 想定通りの挙動（`is_page_eligible`の判定基準通り）。バグではない |
| Merger実行時にschema検証エラー | Extractor出力側の実装バグの可能性 | エラーメッセージのJSON Pathを確認し、`agents/extractor/`の該当箇所を疑う |

---

# 12. 結果記録方法

実施結果は`docs/runbooks/Real_Data_Merged_Collection_Dry_Run_Result_Template.md`のテンプレートに沿って記録する。

**記録してよいもの**: extraction result件数、merged entity件数、unresolved/conflict/warning件数、canonicalIdSummary/relationshipTypeSummaryの集計値、Extractor/Mergerが落ちた場合の一般的な問題点、follow-up task。

**記録してはいけないもの**: 実セリフ、実ストーリー本文、実データ由来JSON全文、実データ由来Markdown全文、ローカル絶対パス、大量のキャラクター名一覧、raw payload、`data/raw`等の内容。

---

# 13. 次にやること

- Extractor/Merger/Rendererがdry-runで見つけたバグを修正した場合は、必ず合成fixtureで回帰テストを追加する（実データ由来fixtureは追加しない）
- キャラクター辞書の数値ID帯拡充（`docs/runbooks/Character_Dictionary_Review.md`の手順）は本手順書のスコープ外
- relationshipType/canonical ID関連のtaxonomy本確定は別途対応

---

# 14. commit前チェックリスト

dry-run実施後、何かをcommitする前に必ず以下を確認する。

- [ ] `git status --short`に`workspace/dry_runs/`配下の出力が出ていない
- [ ] `git status --short`に`workspace/wiki_preview/`配下の出力が出ていない
- [ ] `git status --short`に`data/normalized/`・`data/extracted/`・`data/reports/`配下の生成物が出ていない
- [ ] 実データ由来のNormalized Story JSON・episode_extraction・merged knowledge collectionがcommit対象に含まれていない
- [ ] `docs/runbooks/`配下に追加した結果記録に、実データ本文・実セリフ・大量の固有名詞・ローカル絶対パスが含まれていない

```bash
uv run python scripts/check_dry_run_inputs.py
```

---

# 15. 関連ドキュメント

- `docs/runbooks/Real_Data_Dry_Run.md`（Parser → Extractor → Merger dry-run手順、本手順書の前提）
- `docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`（Merger出力 → Wiki Markdown dry-run手順、本手順書の後段）
- `docs/runbooks/Real_Data_Merged_Collection_Dry_Run_Result_Template.md`（実施結果の数値サマリーテンプレート）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
