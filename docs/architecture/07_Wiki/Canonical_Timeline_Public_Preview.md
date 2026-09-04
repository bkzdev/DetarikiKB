# Canonical Timeline Public Preview

Version: 0.1
Status: Reviewed
Review date: 2026-09-02
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

`timelines/index.md`のpublic rendererを、commit対象外のlocal previewで画面確認する。実Canonical Timeline artifact、private mapping、Registry entry、実public ID、実label、実Wiki生成物は使用しない。

---

# 2. 入力と保存境界

- 入力は合成public projectionのみ
- preview Markdown、stub Story / Episode page、一時MkDocs設定、HTMLは`workspace/wiki_preview/`配下だけへ生成
- 生成物は`.gitignore`対象でありcommitしない
- hosting、deploy、publish-ready判定は行わない

初回表示に加え、長い日本語labelと`before` / `after` / `same_time`の3 relationを持つ合成表示へ拡張して確認した。

---

# 3. 機械検査

次を確認した。

- `validate_canonical_timeline_page_links()` finding 0
- `mkdocs build --strict`成功
- internal field名、`.dec`、local absolute path、`<script`の出力hit 0
- Story / Episodeの全target pageが生成済み
- Git statusにpreview生成物が出現しない

---

# 4. Manual visual review

`mkdocs serve`経由でdesktop幅と390px狭幅を確認した。

- page見出し、制約説明、関係グループ、Episode一覧、確認済み関係、未解決件数が読める
- 長い日本語labelは折り返され、横overflowを発生させない
- `before` / `after` / `same_time`はsourceとtargetを含む定型文として判別できる
- Timelineから合成Episode pageへ遷移し、戻り導線も機能する
- 個別unknown / conflict、内部ID、provenanceは表示されない

公開本文の「対象artifact内」は読者向け表現ではないため、「確認対象データ内」へ修正した。その他に実装を止める表示問題は見つからなかった。

---

# 5. 結論

合成previewの範囲ではrendererの表示・link・狭幅可読性を受入可能と判断する。この結果は実データ公開承認ではなく、`projection_candidate`も維持する。

公開platformとpublic publishing workflowは`Public_Publishing_Workflow_Decision.md`で採択し、Zensical dual-build / exact pinとpublic-safe入力schema / push前review / local promotionまで実装した。次はsite manifest / rendered HTML exposure scanである。実データpreviewと公開は、後続gateと必要なpublic ID / label入力が揃うまで開始しない。

---

# 6. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `Canonical_Timeline_Public_Renderer.md`
- `Canonical_Timeline_Public_Preflight.md`
- `Story_URL_Structure_Decision.md`
- `Public_Publishing_Workflow_Decision.md`
- `../../runbooks/MkDocs_Local_Preview_Dry_Run.md`
- `../../runbooks/AI_PR_Playbook.md`
