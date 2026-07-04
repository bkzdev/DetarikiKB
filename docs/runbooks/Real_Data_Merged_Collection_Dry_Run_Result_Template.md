# Real Data Merged Collection Dry-Run 結果記録テンプレート

Path: `docs/runbooks/Real_Data_Merged_Collection_Dry_Run_Result_Template.md`

このテンプレートは`docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`の手順で実データmerged collection dry-run（Extractor → Merger → Wiki render handoff）を実施した際の結果を記録するためのものである。

**記録時の注意（`Real_Data_Merged_Collection_Dry_Run.md` §12参照）**: 実セリフ・実ストーリー本文・実データ由来JSON/Markdown全文・ローカル絶対パス・大量のキャラクター名一覧は記録しない。数値は抽象化して記録する（例: `merged characters: 30`）。

---

## Run 1（2026-07-04実施）

- **Run ID**: `20260704_140500`
- **Input normalized JSON path**: ローカルの`data/normalized/{main,character,event,other,raid}/`配下（実データ由来、8ファイル。絶対パスは記録しない）
- **Extraction output directory**: `workspace/dry_runs/<RUN_ID>/extracted/`（`.gitignore`で保護、commitしていない）
- **Merge output path**: `workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json`（`.gitignore`で保護、commitしていない）
- **Extractor command**:
  ```bash
  uv run python scripts/extract_story.py --input <normalized JSON> --output workspace/dry_runs/<RUN_ID>/extracted/ --validate
  ```
  8ファイル分をループ実行
- **Merger command**:
  ```bash
  uv run python scripts/merge_extractions.py --input workspace/dry_runs/<RUN_ID>/extracted/ --output workspace/dry_runs/<RUN_ID>/merged/
  ```
- **Schema validation result**:
  - Extraction Result（8ファイル）: すべてOK（`extract_story.py --validate`の標準出力で確認）
  - Merged Knowledge Collection: OK（`Draft7Validator`で別途検証）
- **Extraction result counts**（8ファイル合算）: characters 36 / locations 6 / organizations 0 / items 0 / lore 0 / events 0 / relationships 0 / timelineCandidates 0。extractionErrors: 0件
- **Merged entity counts**: characters 30 / locations 6 / organizations 0 / items 0 / lore 0 / events 0 / relationships 0 / timeline 0
- **Unresolved entity counts**: characters 30 / locations 6 / organizations 0 / items 0 / lore 0 / events 0 / relationships 0 / timeline 0（**全件unresolved**。既知の課題＝キャラクター辞書の数値ID帯不足によるもので、本dry-runのスコープでは辞書拡充を行っていない）
- **Conflict counts**: total 1件（severity: warning 1、type: field_value_conflict 1、entity type: characters 1）
- **Warning counts**: total 0件
- **Canonical ID summary**: totalAssigned 0 / duplicateCount 0 / invalidCount 0 / warnings 0件（全件unresolvedのため）
- **Relationship type summary**: knownTypes 0種 / unknownTypes 0種 / normalizedTypes 0種（relationships自体が0件のため）
- **Extractor errors**: 0件
- **Merger errors**: 0件（`report.errors`が空配列であることを確認）
- **Wiki render handoff result**: 実施した。`scripts/render_wiki.py --validate --clean`をexit code 0で完了、schema検証OK、Markdown 11件生成（`index.md`/`stories/index.md`/`stories/*.md`×8/`reports/unresolved.md`）。`characters/*.md`は0件（全キャラクターがcanonicalId未確定のため、`is_page_eligible`の判定通りで想定通り）
  - generated file counts: 11件
  - character page count: 0件（想定通り、全件unresolved）
  - episode page count: 8件
  - unresolved report生成: あり（Overview/entity種別別section/Conflict Summary/Warning Summary/Canonical ID Summary/Relationship Type Summaryすべて表示）
  - renderer error: 0件
  - source text exposure check: passed（`textExcerpt`・実セリフ本文の混入なし、front matterへのローカル絶対パス漏れなしを`grep`で確認）
- **Findings**: Extractor・Merger・Rendererとも、実データ8話に対してエラー・クラッシュなく一連のパイプラインが完走した。全キャラクターがunresolvedになる点・relationships/timeline等が0件になる点は、既存のTASKS.md/AI_CONTEXT.mdに記載済みの既知の制約（キャラクター辞書の数値ID帯不足、実データに構造化タグが無いことによるrule-based抽出の制約）であり、今回新たに見つかった不具合ではない。renderer側の追加修正は不要だった（PR #44で追加した堅牢性修正が有効に機能した）
- **Follow-up tasks**: キャラクター辞書の数値ID帯拡充（別タスク、`docs/runbooks/Character_Dictionary_Review.md`）、relationshipType/canonical ID taxonomy本確定（別タスク）
- **Confirmation that no generated output was committed**: `git status --short`で`workspace/dry_runs/`・`workspace/wiki_preview/`・`data/normalized/`配下の出力が一切追跡対象になっていないことを確認済み

---

## Run記録用テンプレート（次回以降）

- **Run ID**: `<YYYYMMDD_HHMMSS>`
- **Input normalized JSON path**: `<ローカルディレクトリの種類のみ>`
- **Extraction output directory**: `<例: workspace/dry_runs/<RUN_ID>/extracted/>`
- **Merge output path**: `<例: workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json>`
- **Extractor command**: `<...>`
- **Merger command**: `<...>`
- **Schema validation result**: `<OK / NG>`
- **Extraction result counts**: `<type別件数>`
- **Merged entity counts**: `<type別件数>`
- **Unresolved entity counts**: `<type別件数>`
- **Conflict counts**: `<total等>`
- **Warning counts**: `<total等>`
- **Canonical ID summary**: `<totalAssigned等>`
- **Relationship type summary**: `<knownTypes/unknownTypes件数>`
- **Extractor errors**: `<件数>`
- **Merger errors**: `<件数>`
- **Wiki render handoff result**: `<実施した/しなかった、結果>`
- **Findings**: `<...>`
- **Follow-up tasks**: `<...>`
- **Confirmation that no generated output was committed**: `<...>`
