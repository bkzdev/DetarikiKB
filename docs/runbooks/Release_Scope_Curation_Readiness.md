# Release Scope Curation Readiness

Version: 0.1

## 1. 目的

M2 / M3の同一release scopeに対し、canonical ID、Character Profile、story内順序、story間Canonical Timelineの「確定済み」と「保留中」を匿名件数で横断確認する。未解決値を推測して補完する処理ではなく、既存artifactが検証可能で、保留を欠落なく説明できるかを判定する。

`reviewable: true`は全値の確定やrelease承認を意味しない。全入力が検証され、確定・保留・conflict・scope外を匿名集計できたことを表す。`fullyConfirmed`は`reviewable: true`を前提に、保留・conflict・validation warning・scope差が無い場合だけtrueとなる別の指標である。

## 2. 入力と境界

入力は次の7点である。

- M2 `release_scope_normalization_report.json`
- M3 `release_scope_knowledge_report.json`
- M3 `merged_knowledge_collection.json`
- `knowledge/dictionaries/characters.yaml`
- `knowledge/dictionaries/character_profiles.yaml`
- release scope全件の`timeline_consistency_report`
- internal canonical Timeline

M2 reportのSHA-256と件数をM3 reportへ照合し、dictionary / profile、Timeline report、canonical Timelineを既存schema / semantic validatorで検証する。M2 / M3 / collectionのcategory件数、collection / story内Timelineのstory・episode multiset、collection内report / M3 reportのcanonical ID・unresolved・conflict集計も完全一致させる。出力には個別ID、名前、path、本文、warning本文、review本文を含めず、input digestと件数だけを残す。

実collection、詳細Timeline report、canonical Timeline、生成したreadiness reportは`workspace/`限定・非commitとする。report schemaは`schemas/release_scope_curation_readiness_report.schema.json`を正とする。

## 3. 実行

まずM3の全Extractionからstory内Timeline reportを作る。

```powershell
uv run python scripts/check_timeline_consistency.py `
  --input workspace/dry_runs/<m3-run>/extracted `
  --recursive `
  --report-output workspace/dry_runs/<readiness-run>/story_timeline_report.json
```

次に4領域を集約する。

```powershell
uv run python scripts/check_release_scope_curation_readiness.py `
  --normalization-report workspace/dry_runs/<m2-run>/release_scope_normalization_report.json `
  --knowledge-report workspace/dry_runs/<m3-run>/release_scope_knowledge_report.json `
  --collection workspace/dry_runs/<m3-run>/merged/merged_knowledge_collection.json `
  --story-timeline-report workspace/dry_runs/<readiness-run>/story_timeline_report.json `
  --canonical-timeline workspace/canonical_timeline/canonical_timeline.json `
  --output workspace/dry_runs/<readiness-run>/release_scope_curation_readiness_report.json
```

出力先は`workspace/dry_runs/`配下に限定し、既存fileは上書きしない。

## 4. 読み方

- `canonicalIds`: entity種別の総数、canonical ID割当数、保留数、conflict数とID形式・重複検証
- `characterProfiles`: release scopeで観測したsource IDの辞書照合、canonical Characterのprofile有無
- `storyLocalTimeline`: 全story / episodeのcomparable・missing・ambiguousとconstraint finding
- `crossStoryTimeline`: node / edge、relation / review / adoption状態、release scope内外node、semantic finding

unknown、unresolved、profile未登録、story-local missing、scope外nodeが0でないこと自体は失敗ではない。件数が黙示破棄されず、対応する内部artifactで追跡できることがM4のreviewability条件である。個別値の確定、profile作成、canonical Timeline promotion、公開projection変更、総順序化は本手順の対象外とする。

## 5. 2026-09-17 baseline

M2 / M3の2,840 episodeを同一digestで照合し、4領域すべて`reviewable: true`、全体`fullyConfirmed: false`を確認した。canonical IDは184件、保留はCharacter 1,344件・Location 3,250件、Character conflictは3件。観測source character ID 187件中184件は辞書登録済み、3件は未登録として保持した。release scopeのcanonical Character 184件中profile確認済みは6件、保留は178件だった。

story内順序は全2,840 episode / 511 storyを検査し、finding 0、保留511 storyだった。EVENTの確定済み537 episode / 137 storyは別の最終corpus検証で全件readyを確認済みであり、release scope全体の保留と混同しない。story間Timelineは72 node / 40 confirmed canonical edge、semantic finding 0で、65 nodeが現release scope内、7 nodeがscope外だった。これらは全確定を装わず、保留・scope差として匿名reportに保持した。
