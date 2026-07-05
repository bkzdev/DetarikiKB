# Story Title/Subtitle Import Procedure（story/episodeの公式タイトル・サブタイトル取り込み手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Story_Title_Subtitle_Import.md`

---

# 1. 目的

`docs/architecture/05_Parser/Story_Manifest_Design.md`で設計した`story_manifest.yaml`の`title`（ストーリータイトル）・`subtitle`（エピソードサブタイトル）・`displayTitle`を、**安全に、人間確認を経て**埋めるための手順を定義する。

**本手順書はcandidate生成→人間レビュー→`story_manifest.yaml`反映という一連の運用フローを扱う。** 実際の大量データ投入（`story manifest confirmed metadata batch`）は本手順書のスコープ外であり、将来のbatch単位PRで行う。

---

# 2. 前提

- `docs/architecture/05_Parser/Story_Manifest_Design.md`（特に §11 title/subtitle/displayTitleの扱い）を読んでいること
- `schemas/story_manifest.schema.json`・`docs/templates/story_manifest_template.yaml`を把握していること
- 以下は**絶対に行わない**方針であることを理解していること
  - DEC本文からtitle/subtitleを推測する
  - AIに公式タイトルを生成させる
  - 外部一覧から取れた値を確認なしに`confirmed`扱いにする

---

# 3. 入力候補source

`title`/`subtitle`の情報源として、以下を想定する（`Story_Manifest_Design.md` §11.5のsource種別に対応）。

| sourceType | 具体例 |
|---|---|
| `manual` | 人間が直接入力（口頭確認、社内共有メモ等） |
| `official_game_ui` | ゲーム内のイベント選択画面・エピソード選択画面のスクリーンショット・実プレイ時のメモ |
| `official_announcement` | 公式サイト・公式SNSの告知文言 |
| `wiki_story_list` | 攻略Wiki等のストーリー一覧ページ |
| `wiki_event_page` | 攻略Wiki等の個別イベントページ |
| `imported_candidate` | 上記以外の外部一覧・CSV等（出典分類が不明なもの） |
| `unknown` | 出典不明 |

いずれのsourceであっても、**取得した値をそのまま`story_manifest.yaml`へ書き込まない**。必ず§4のcandidate生成ステップを経る。

---

# 4. candidate生成方針

1. 入力source（Wiki一覧ページのHTML、CSVエクスポート、手入力メモ等）から、`storyId`/`episodeId`/`proposedTitle`/`proposedDisplayTitle`/`proposedSubtitle`をCSV（列: `storyId,episodeId,episodeNumber,proposedTitle,proposedDisplayTitle,proposedSubtitle,confidence,notes`）としてまとめる
2. `scripts/build_story_title_subtitle_candidates.py`を使い、CSVから`documentType: "story_title_subtitle_candidates"`のcandidateドキュメントを生成する

```bash
uv run python scripts/build_story_title_subtitle_candidates.py \
    --input-csv workspace/story_manifest/title_subtitle_rows.csv \
    --source-type wiki_story_list \
    --source-label "デタリキZ攻略Wiki ストーリー一覧" \
    --manifest workspace/story_manifest/story_manifest_candidates.yaml \
    --output workspace/story_manifest/title_subtitle_candidates.yaml
```

3. `--manifest`を指定すると、各`storyId`/`episodeId`が既存manifestに実在するかを`foundInManifest`として記録する（**一致有無に関わらず、candidateとしては必ず出力される**。unmatchedを黙って除外しない）
4. 生成されるcandidateはすべて`reviewStatus: "pending"`。このscript自体は`story_manifest.yaml`を一切更新しない

---

# 5. 人間レビュー手順

1. `--output`で書き出したcandidateドキュメント（`docs/templates/story_title_subtitle_candidates_template.yaml`と同じ形式）を人間が確認する
2. 各candidateについて、以下を判断する
   - 値が正しいか（出典元と実際に照合する）
   - `foundInManifest: false`の場合、`storyId`/`episodeId`の誤記か、それとも`story_manifest.yaml`側にまだそのストーリーが登録されていないだけかを確認する
   - 複数candidateソースで矛盾する値が無いか（§7）
3. 採用する値には`reviewStatus: "confirmed"`、不採用には`"rejected"`を人間が手動で付ける（このscriptはreviewStatusを書き換えない、あくまで人間がcandidateファイルを編集する運用）

---

# 6. story_manifest.yamlへの反映手順

`confirmed`と判断したcandidateのみ、人間が`story_manifest.yaml`の該当エントリへ以下を反映する。

| candidateのフィールド | 反映先 (`story_manifest.yaml`) |
|---|---|
| `proposedTitle` | `stories[].title` |
| `proposedDisplayTitle` | `stories[].displayTitle` |
| （episodeの）`proposedSubtitle` | `stories[].episodes[].subtitle` |
| candidateドキュメントの`source` | `stories[].titleSource` または `episodes[].subtitleSource`（§13.1のスキーマ、`sourceType`/`label`/`referenceId`/`notes`） |

反映後、`stories[].metadataStatus`（該当エントリがtitle/subtitle両方確認済みなら）または`episodes[].metadataStatus`を`"pending"`から`"confirmed"`へ更新する。公式タイトル自体が存在しない・非公開と判明した場合は`"title_unknown"`にする（`Story_Manifest_Design.md` §12）。

**この反映作業は人間が`story_manifest.yaml`を直接編集して行う。自動反映スクリプトはこのPRでは実装しない。**

---

# 7. 矛盾時の扱い

複数candidateソースが同じ`storyId`/`episodeId`について異なる値を提示した場合（`Story_Manifest_Design.md` §11.8参照）:

1. 自動的にどちらかを採用しない
2. 両方の値と出典（`sourceType`/`label`）を比較する
3. 優先順位の目安（強制ではない）: `official_announcement` > `official_game_ui` > `wiki_event_page` > `wiki_story_list` > `manual` > `imported_candidate` > `unknown`
4. 採用しなかった値は`notes`に記録し、判断の経緯を残す

---

# 8. 表記ゆれの扱い

全角/半角・句読点・記号の表記ゆれは自動で正規化しない（`Story_Manifest_Design.md` §11.9）。原文ママを採用するか統一表記にするかは人間が判断し、修正した場合は`notes`にその旨を記録する。

---

# 9. commit禁止対象（最重要）

- 実イベント名・実タイトル・実サブタイトルを含む`docs/templates/`配下のファイル
- 実Wiki由来のraw HTML
- 実データ由来のcandidate CSV/YAML（`workspace/story_manifest/`配下、`.gitignore`対象）
- 実データ由来の`story_manifest.yaml`本体
- rawPath実一覧
- ローカル絶対パスを含む結果ファイル

`docs/templates/story_title_subtitle_candidates_template.yaml`は完全な合成データのみで構成する（実イベント名は一切使わない）。

---

# 10. 実データ運用時の注意

- Wiki等からHTMLを取得する場合は、`docs/runbooks/Character_Profile_Wiki_Import.md`と同じ方針（robots.txt確認、1ページのみ取得、個別ページ巡回はしない）を踏襲すること
- candidate生成・レビュー・反映のいずれの段階でも、実データ本文（生成されたcandidateファイル自体、レビュー中のメモ等）は`workspace/`配下（`.gitignore`対象）に留め、commitしない
- 大量のstoryId/episodeIdを一度に`confirmed`化する場合は、`character dictionary confirmed batch`と同様に「batch」単位のPRへ分割し、人間確認済みの範囲を明示する（`story manifest confirmed metadata batch 001`等）

---

# 11. 次にやること

- `story title/subtitle candidate builder`（本手順書のscript自体）は本PRで実装済み。実際のWiki/CSV入力での動作確認は別途行う
- `story manifest confirmed metadata batch 001`: 人間確認済みcandidateを実際に`story_manifest.yaml`へ反映する最初のbatch
- `wiki episode title display integration`: Wiki Episode pageでtitle/subtitleを表示するrenderer実装（`Wiki_Output_Design.md` §9.3）

---

# 12. 関連ドキュメント

- `docs/architecture/05_Parser/Story_Manifest_Design.md`（§11 title/subtitle/displayTitleの扱い、§13.1 source tracking）
- `docs/templates/story_title_subtitle_candidates_template.yaml`（candidateドキュメントの合成テンプレート）
- `schemas/story_manifest.schema.json`（`titleSource`/`subtitleSource`を含むschema）
- `scripts/build_story_title_subtitle_candidates.py`（candidate生成CLI）
- `docs/runbooks/Character_Profile_Wiki_Import.md`（同種の「候補生成→人間確認→batch反映」運用の先例）
