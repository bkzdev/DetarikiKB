# Canonical Timeline Public Renderer

Version: 0.1
Status: Implemented
Project: Detariki Knowledge Base (DKB)
Implementation: `agents/wiki_generator/canonical_timeline.py`

---

# 1. 目的

preflight済みのCanonical Timeline public projectionから、`timelines/index.md`単一集約ページのMarkdownを決定的に生成する。

本実装は純粋rendererとsafe link checkerに限定する。file I/O、projection生成、private mapping参照、公開判定、既存`build_pages()` / CLIへの統合、実データrender、hosting、deployは行わない。

---

# 2. APIとpath

```python
canonical_timeline_page_path() -> "timelines/index.md"

render_canonical_timeline_page(
    projection,
    preflight_report,
) -> str

validate_canonical_timeline_page_links(
    markdown,
    projection,
    available_page_paths,
) -> list[dict]
```

rendererは次のpreflight reportとの完全一致だけを受け付ける。

```json
{
  "status": "clean",
  "publishStatus": "projection_candidate",
  "findings": []
}
```

`blocked`、findingあり、追加fieldあり、またはprojectionが`projection_candidate`以外ならMarkdownを返さず例外で停止する。rendererがpreflightを迂回して公開判定することはない。

---

# 3. 表示契約

## 3.1 固定説明

page冒頭で、次を明示する。

- 確認済み関係を辿る補助ページである
- 全出来事の総順序ではない
- 未確認relationは掲載しない

## 3.2 Connected component

projectionの各componentを「関係グループ」として順番に表示する。internal `componentKey`は表示しない。各groupは公開確認済みlabelだけを使うEpisode一覧と関係一覧を持つ。

relation文言は自由記述せず、projectionの固定`labelKey`から次へ変換する。

| label key | 表示 |
|---|---|
| `timeline_before` | source は target より前 |
| `timeline_after` | source は target より後 |
| `timeline_same_time` | source と target は同時期 |

source / targetの主語と比較対象を明示し、canonical relationの方向を日本語の語順で曖昧にしない。

## 3.3 Unknown / conflict

個別relationやreasonは表示せず、`unresolvedRelationSummary`の`unknownCount` / `conflictCount`だけを「確認対象データ内の件数」として表示する。公開本文では開発者向けの`artifact`表現を使わない。空componentも有効で、「表示できる確認済み関係はありません」と明示する。

## 3.4 Label escaping

public labelはHTML特殊文字をentity化し、Markdown link textのbackslash / bracketをescapeする。labelからHTMLや別linkを注入できないようにする。

---

# 4. Link契約

`timelines/index.md`から既存flat URLへ次の相対linkを生成する。

- Story: `../stories/{publicStoryId}.md`
- Episode: `../stories/{publicEpisodeId}.md`

`validate_canonical_timeline_page_links()`は次を固定rule/countだけで検査する。

- projectionが要求するlinkがMarkdownに存在する
- 全link targetが`available_page_paths`に存在する
- projectionに由来しないlocal Markdown linkが無い

Windows separatorを受け取った場合もPOSIXへ正規化する。findingにpublic ID、label、target pathを含めない。

---

# 5. Front matter

次を固定する。

```yaml
title: "Canonical Timeline"
page_type: "timeline"
status: "projection_candidate"
generated_from: "canonical_timeline_public_projection"
```

preflightと同様に、renderer成功も公開承認を意味しない。

---

# 6. 合成fixture検証

`tests/wiki/test_canonical_timeline.py`で、path、front matter、固定説明、3 relation文言、Story / Episode link、unknown / conflict aggregate、空projection、label escape、preflight fail-closed、決定性・入力不変、link欠落・target欠落・unexpected linkを検証する。

実artifact、実public ID、実label、実Wiki Markdownは使用・commitしない。

---

# 7. Non-goals

- `build_pages()` / `scripts/render_wiki.py`への入力統合
- projection / preflightのfile loader・writer・CLI
- private mapping、Registry、public label sourceの参照
- Story / Episode rendererや既存URLの変更
- 実データrender / local preview
- publish-ready判定
- hosting、deploy、rollback実行

---

# 8. Local preview結果

ignored workspaceだけで匿名合成projectionを用いたlocal previewを構成し、`mkdocs serve`経由でdesktop幅と390px狭幅を確認した。3 relation種別、長い日本語label、Story / Episode link遷移、横overflowなし、内部field・raw拡張子・絶対path・script tag露出0を確認した。公開本文の`artifact`表現だけを一般向けに修正した。詳細は`Canonical_Timeline_Public_Preview.md`を参照する。

public publishing platform / workflow、deploy gate、rollbackは`Public_Publishing_Workflow_Decision.md`で2026-09-02に採択した。Zensical合成dual-buildは`Zensical_Synthetic_Dual_Build_Decision.md`で完了し、次はZensical exact pinの段階統合である。実データ由来projection、mapping、report、Markdown、HTMLは引き続きcommit・deployしない。

---

# 9. 関連文書

- `Canonical_Timeline_Public_Projection_Decision.md`
- `Canonical_Timeline_Public_Projection_Schema.md`
- `Canonical_Timeline_Public_Projector.md`
- `Canonical_Timeline_Public_Preflight.md`
- `Canonical_Timeline_Public_Preview.md`
- `Public_Publishing_Workflow_Decision.md`
- `Timeline_Page.md`
- `Wiki_Output_Design.md`
- `Story_URL_Structure_Decision.md`
- `../../runbooks/AI_PR_Playbook.md`
