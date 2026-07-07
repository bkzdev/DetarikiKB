# Story Page Design（Story page中心Wiki構造の設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/07_Wiki/Story_Page_Design.md`

---

# 1. 目的

本文書は、現在「Episode page中心」になっているWiki構造を、今後「Story page中心」へ寄せるための設計を行う。

**本PRではStory page rendererの実装は行わない。** URL構造変更・Episode page path変更・`agents/wiki_generator/renderer.py`/`paths.py`の大規模変更も行わない。Story page/Episode page/Summary/Evidence管理の役割分担を決め、次PR（`wiki-story-page-renderer`、§13）で実装できるように設計を固めることが本PRのゴールである。

---

# 2. Background（背景）

`feature/public-id-renderer-manual-review`（PR #74）で、実データ小規模サンプルを使ったmanual reviewを行った際、現在のWikiがエピソードごとのページ生成中心になっていることを確認した。これは`evidenceId`/`episodeId`/`blockId`の管理上は自然だが、閲覧者目線では「ストーリー単位のページ」が別途必要である。

ユーザー方針:

- ストーリーは、エピソードごとのページだけではなく、ストーリー単位のページを作りたい
- `evidenceId`等の管理上は、従来通りepisode単位・block単位で分かれていてよい
- 各Story pageには将来的に要約を付けたい
- 要約はStory全体だけでなく、Episodeごとに区切って表示する方がよい
- ただし、AI要約生成パイプラインはまだ後続でよい
- まずはStory pageの設計と、Summary placeholderの方針を決めたい

---

# 3. Current structure（現状構造）

`docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.2/§9.3、`agents/wiki_generator/paths.py`・`renderer.py`（PR #72〜#74時点）の実装状況を整理する。

- `stories/index.md`がStory/Episode一覧として機能している（`render_story_index_page`）。表は`Story ID`/`Episode`/`Status`/`Category`の4列で、`Episode`列がEpisode pageへのリンクを兼ねる
- Episode pageは`stories/{episodeId または publicEpisodeId}.md`として生成される（`episode_page_path`/`resolve_episode_path_id`、PR #73）
  - `publicEpisodeId`が設定されている場合はそちらをfilenameに使う
  - `publicEpisodeId`が無い（または空文字列・whitespaceのみ）場合は既存`episodeId`（無ければ`documentId`）へfallback
- **Story単位の独立ページはまだ存在しない**。`storyId`はStory index表の1列として、また各Episode pageのSummary内に表示されるのみ
- **Summaryはまだ生成されていない**。Episode pageの`## Summary`は、`storyTitle`/`episodeSubtitle`/`displayTitle`等のmanifest由来メタデータの表示であり、AI生成の要約文ではない
- Evidence管理は`episodeId`/`sceneId`/`blockId`/`evidenceId`中心（`Identifier_Specification.md` §5〜§8、`Wiki_Output_Design.md` §4）

---

# 4. Problem（課題）

- 閲覧者目線では、ストーリー単位のページ（「このイベント/このメインストーリー章はどんな話か」を一目で把握できる入口）が必要
- 現状はStory index表からいきなりEpisode pageへ飛ぶため、複数episodeにまたがるストーリー全体像を把握しにくい
- ただし、内部管理・evidence管理はEpisode単位（`episodeId`/`sceneId`/`blockId`）で維持する必要がある。これはEvidence ID体系（`Identifier_Specification.md` §2.6/§8）・AI抽出検証・unresolved/candidate確認との相性が良いためであり、Story単位へ統合すべきではない
- Story pageとEpisode pageの役割が未整理のまま実装を進めると、責務が重複したページや、逆に必要な情報がどちらにも無いページになりかねない

---

# 5. Adopted direction（採用方針）

## 5.1 短期（次PR `wiki-story-page-renderer`）

- Story pageを新規生成する
- Episode pageは残す（廃止しない）
- Story indexは将来的にStory pageへリンクする（本PRでは変更しない、次PRのスコープ）
- Story page内にEpisode一覧を出す
- Story pageにSummary placeholder（「未生成」表示）を置く
- Episode pageは詳細確認用として維持する

## 5.2 中期

- AI生成のEpisode Summaryを追加する
- Story pageにEpisodeごとの要約を表示する
- Story Summaryを追加する
- Story pageに登場人物・関連キャラ・未解決項目への導線を追加する

## 5.3 長期

- Story全体要約、考察、矛盾点、登場人物関係、重要イベント、時系列などをStory pageに統合する
- AI考察は通常要約とは分離して表示する（`Wiki_Output_Design.md` §3の情報分離方針を踏襲）
- Evidence index / Knowledge Graphとの連携を検討する

---

# 6. Story page role（Story pageの役割）

Story pageは、閲覧者が最初に見るストーリー単位ページとする。

## 6.1 将来的に載せるもの

- Story title（`storyTitle`/`displayTitle`）
- `publicStoryId` / `storyId`
- category（MAIN/EVENT/RAID/OTHER/CHARACTER）
- `metadataStatus`
- Story Summary（§8参照、当面はplaceholder）
- Episode Summaries（§8参照、当面はplaceholder）
- Episode list（このstoryに属するepisode一覧、Episode pageへのリンク）
- Related Characters（このstoryに関係するcharacter一覧）
- Related Locations / Organizations（将来）
- Unresolved / Special Speaker Labelsへの導線（該当する未解決項目がある場合）
- Evidence summary（件数・参照情報のみ。**元セリフ全文は出さない**）
- AI Analysis / Speculationへのリンク（将来、Phase 3、`Wiki_Output_Design.md` §9.17）

## 6.2 載せないもの

- raw DEC text
- 元セリフ全文
- raw command（`@ChTalk`等）
- ローカル絶対パス
- extraction JSONの生dump
- AI考察を通常要約と混ぜた内容（`Wiki_Output_Design.md` §3の分離方針を踏襲）

**実装状況（`feature/wiki-story-page-renderer`で実施）**: `render_story_page`（`agents/wiki_generator/renderer.py`）を実装した。Story title（`storyTitle`優先、無ければ`publicStoryId`、無ければ`storyId`）・`storyId`/`publicStoryId`（未登録時は「未登録」表示）・category・`metadataStatus`（story内のepisodeで値が異なる場合は`mixed`）・Story Summary/Episode Summaries（placeholder、§8参照）・Episode list（このstoryに属するepisode一覧とEpisode pageへのリンク）・Related Characters・Unresolved reportへの導線を表示する。Related Locations/Organizations・AI Analysisリンクは未実装のまま（中期・長期方針）。

---

# 7. Episode page role（Episode pageの役割）

Episode pageは残す。役割は以下の通り、Story pageとは明確に分離する。

## 7.1 Episode pageの役割

- Episode単位の詳細確認
- Episode ID / Public Episode ID確認
- Candidate counts
- Related Characters
- Validation status
- Evidence references
- Debug / review寄りの情報

## 7.2 Episode pageを完全に廃止しない理由

- `evidenceId`/`blockId`/`episodeId`管理と相性が良い（Evidence ID体系はEpisode単位のまま、§9参照）
- AI抽出結果の検証に使える（Extraction/Merge結果をEpisode単位で確認する既存フロー、`Merged_Knowledge_Design.md`と整合）
- unresolvedやcandidate確認に使える
- Story pageが肥大化しすぎるのを防げる（1 storyに複数episodeがある場合、全episode detailをStory page 1枚に詰め込むと閲覧性が悪化する）

**実装状況（`feature/wiki-story-page-renderer`で実施）**: Episode pageは廃止していない。`render_episode_page`・`episode_page_path`（`publicEpisodeId`優先、無ければ`episodeId`へfallback、PR #73の方針を維持）はいずれも変更していない。Story page内のEpisode listから各Episode pageへリンクする形で連携する。

---

# 8. Summary placement（Summary配置方針）

要約生成（AI要約生成パイプライン）は後続PRで扱う。本PRではStory pageのSummary placeholder方針のみを決める。

## 8.1 方針

- **Story Summary**: ストーリー全体の要約。Story page先頭付近に配置する
- **Episode Summaries**: Episodeごとの要約。Episode単位で明確に区切って表示する（例: `### Episode 1`のようなsubsection、または箇条書きでepisodeIdごとに区切る）
- AI要約生成パイプラインができるまでは「未生成」と表示する（クラッシュせず、fallback表示として扱う。既存の`_missing_value_label`等と同じ「未登録/未生成」系プレースホルダーの流儀を踏襲する）
- AI考察・推測はSummaryとは別section、または別ページに分ける（`Wiki_Output_Design.md` §3・§9.17の分離方針をそのまま適用する）
- Summaryには元セリフ全文を出さない（`Wiki_Output_Design.md` §4のevidence方針と同じ）
- Summaryにはevidence referencesを持たせる可能性を残す（将来、どのシーン・どのdialogueを要約の根拠にしたかを参照できるようにする余地。本PRでは設計のみ、実装しない）

## 8.2 placeholder例（合成イメージ、次PRでの実装イメージ）

```markdown
## Summary

未生成

## Episode Summaries

### Episode 1

未生成

### Episode 2

未生成
```

**実装状況（`feature/wiki-story-page-renderer`で実施）**: 上記placeholder例の通り実装した（`_render_story_summary_section`/`_render_episode_summaries_section`）。Episode Summariesの見出しは`episodeSubtitle > displayTitle > Episode {index}（story内の並び順） > episodeId`の優先順位で解決する（merged knowledge collectionの`sourceDocuments`に`episodeNumber`が無いため、`episodeNumber`の代わりにstory内の並び順を使う）。AI要約生成はまだ実装していない。

**Summaryデータ構造の設計（`feature/story-summary-schema-design`で実施）**: 「未生成」placeholderを実際のSummaryデータへ置き換えるためのデータモデル・保存場所・status/review workflow・evidenceRefs方針・renderer連携方針を`docs/architecture/06_AI/Story_Summary_Design.md`で設計した。保存場所は`knowledge/summaries/stories/{storyId}.yaml`（1 story 1 file）を採用し、`review.status`が`reviewed`/`approved`のもののみcommit・表示対象とする方針。schema実装・renderer統合は次PR（`story-summary-schema-implementation`/`story-summary-renderer-integration`）で行う。

**Summary schema実装（`feature/story-summary-schema-implementation`で実施）**: `schemas/story_summary.schema.json`・`agents/wiki_generator/story_summaries.py`（loader/validator）・`scripts/validate_story_summaries.py`（CLI）を実装した。`knowledge/summaries/stories/{storyId}.yaml`は空ディレクトリ（`.gitkeep`のみ）のまま、実データsummaryは投入していない。**Story pageのplaceholder自体は変更していない**（`_render_story_summary_section`/`_render_episode_summaries_section`はまだ「未生成」固定のまま、renderer統合は次PR`story-summary-renderer-integration`）。

**Summary renderer統合（`feature/story-summary-renderer-integration`で実施）**: `scripts/render_wiki.py --story-summaries <path>`を追加し、`review.status`が`reviewed`/`approved`・`generationStatus`が`generated`のSummaryのみ、Story pageの`## Story Summary`/`## Episode Summaries` placeholderを実際の本文へ差し替えるようにした。`storyId`優先→`publicStoryId`、`episodeId`優先→`publicEpisodeId`で照合し、矛盾する場合は安全側に倒して非表示にする。未指定・非表示条件のSummaryは従来通り「未生成」のまま。**Episode pageへのSummary表示・evidenceRefs表示はこのPRでは行っていない**（Episode page/Character page/Characters index/Unresolved reportはいずれも無変更）。合成fixtureでのみ確認、実データ未投入。

---

# 9. Evidence management（Evidence管理方針）

- `evidenceId`/`episodeId`/`blockId`は従来通りEpisode単位で維持する（`Identifier_Specification.md` §5〜§8、変更しない）
- Story pageはEpisode単位のevidenceを**集約表示**してよい（例: 「登場エピソード一覧」「関連キャラクターの言及件数」等の要約表示）
- Story pageができても、evidenceのsource of truthはEpisode/Normalized Story JSON側のままである。Story pageは閲覧用のaggregationにすぎず、evidence自体を新たに生成・保持するものではない
- Evidence ID体系は本PRでもStory page実装PRでも変更しない
- Raw script textはStory page・Episode pageいずれにも出さない（既存方針の継続）

---

# 10. URL structure options（URL構造候補）

**本PRではURL変更を実装しない。** 将来候補の比較のみ行う。

## 候補A: flat構造維持

```text
stories/{publicStoryId or storyId}.md
stories/{publicEpisodeId or episodeId}.md
```

- 長所: 既存構造に近い、実装が簡単、既存PR #73の`publicEpisodeId`対応を活かしやすい
- 短所: Story pageとEpisode pageが同じ階層に混在する、ファイル名だけでは種類が分かりにくい可能性がある
- 補足: `episodeId`は常に`storyId`+`_E{number}`形式（`Identifier_Specification.md` §5.1）のため、同一ディレクトリに置いてもファイル名の衝突は起きない

## 候補B: story page + episodes subdir

```text
stories/{publicStoryId or storyId}.md
stories/episodes/{publicEpisodeId or episodeId}.md
```

- 長所: Story pageとEpisode detail pageの役割が分かれやすい、Story indexからStory pageへ自然につながる
- 短所: 既存Episode page path変更が必要、リンク更新範囲が増える

## 候補C: nested構造

```text
stories/{publicStoryId or storyId}/index.md
stories/{publicStoryId or storyId}/{publicEpisodeId or episodeId}.md
```

- 長所: Story単位でまとまる、将来公開Wikiとして自然（`Wiki_Output_Design.md` §11の出力ディレクトリ案が元々この構造を想定していた）
- 短所: 実装・migration・relative linkが複雑、`publicStoryId`未設定時のfallback設計が必要、MkDocs directory URLとの相性確認が必要

## 推奨

**短期は候補A、長期は候補Cを再検討する段階方針を推奨する。**

- 短期（次PR`wiki-story-page-renderer`）: 候補Aを採用する。既存の`episode_page_path`/`resolve_episode_path_id`（PR #73）の実装をそのまま活かせ、Story page追加に伴うリンク更新範囲を最小化できる。`storyId`と`episodeId`のファイル名衝突が起きない前提（上記補足）も、候補Aの採用を後押しする
- 中期: 候補Aの運用でStory pageとEpisode pageの混在が閲覧性を損なうと判断された場合、候補B（`stories/episodes/`への分離）を再検討する
- 長期: 公開Wiki化（`public-publishing-platform-evaluation`）のタイミングで、候補C（nested構造）への移行を`publicStoryId`の活用と合わせて再評価する。`Wiki_Output_Design.md` §11が既にnested構造を出力ディレクトリ案として示しており、長期的な方向性とは矛盾しない

**実装状況（`feature/wiki-story-page-renderer`で実施）**: 候補Aをそのまま採用した。`agents/wiki_generator/paths.py`の`story_page_path`（`resolve_story_path_id`）が`stories/{publicStoryId or storyId}.md`を返す。nested構造（候補C）への移行はまだ行っていない。

---

# 11. Recommended phase plan（推奨段階方針、まとめ）

| フェーズ | 内容 |
|---|---|
| 短期（次PR） | Story page新規生成、Episode page維持、Story index→Story pageリンク、URL構造は候補A |
| 中期 | AI生成Episode Summary追加、Story Summary追加、Story pageへの登場人物・未解決項目導線追加 |
| 長期 | Story全体要約・考察・矛盾点・登場人物関係・重要イベント・時系列のStory page統合、AI考察分離表示、Evidence index/Knowledge Graph連携、URL構造候補Cの再評価 |

**実装状況（`feature/wiki-story-page-renderer`で実施）**: 短期フェーズを実装完了した（Story page新規生成・Episode page維持・Story index→Story pageリンク・URL構造候補A）。中期・長期フェーズは未着手。

---

# 12. Non-goals（このPRで実装しないこと）

- Story page rendererの実装
- Story page path helperの実装
- Story index link先の変更
- Episode page pathの変更
- Story summary schemaの実装
- AI要約生成の実装
- AI provider/prompt実装
- Story title/subtitleの実import
- 実タイトル/実サブタイトルの投入
- `publicStoryId`を使ったネストURL化の実装
- `agents/wiki_generator/renderer.py`/`paths.py`の再設計
- `storyId`/`episodeId`生成ロジックの変更
- Story manifest candidate builderの変更
- Character page pathの変更
- 実DEC・実manifest・実Normalized Story JSON・実extraction/merged collection・実Wiki Markdownのcommit

---

# 13. Next PR scope（次PR `wiki-story-page-renderer` のスコープ）

次PRで実装候補とすること（**`feature/wiki-story-page-renderer`で実装完了**）:

- ~~Story pageを生成する（`render_story_page`相当の新規関数）~~ → 完了
- ~~Story page path helperを追加する（`agents/wiki_generator/paths.py`、候補A: `stories/{publicStoryId or storyId}.md`）~~ → 完了（`story_page_path`/`resolve_story_path_id`）
- ~~Story indexからStory pageへリンクする~~ → 完了
- ~~Story page内にEpisode一覧を出す~~ → 完了
- ~~Story Summary / Episode Summaries placeholder（「未生成」）を出す~~ → 完了
- ~~Episode pageは残す（変更しない）~~ → 変更していない
- ~~`publicStoryId`がある場合はStory page filenameに使う~~ → 完了
- ~~`publicStoryId`が無い場合は`storyId`へfallback~~ → 完了
- ~~`publicEpisodeId`のEpisode page path方針はPR #73のまま維持（変更しない）~~ → 変更していない
- ~~`tests/fixtures/wiki/synthetic_merged_collection.json`を更新（Story page生成確認用の合成データ追加）~~ → 完了（同一storyId複数episode・publicStoryIdあり/なし・publicEpisodeIdあり/なし・storyTitleあり/なし・mixed metadataStatusを追加）
- ~~`mkdocs build --strict`確認~~ → 完了

## 13.1 次PR候補（さらに後続）

- **story-summary-schema-design**: Story Summary/Episode Summaryのデータ構造（schema）設計（AI要約生成パイプライン自体はさらに後続）
- **story-page-manual-review**: 実データ小規模サンプルでStory page表示（Story index→Story page→Episode pageの導線、Related Characters集約）を目視確認する
- Related Locations/Organizationsのstory page表示、AI Analysisリンク（中期・長期方針、§5参照）

---

# 14. 参照

- `docs/architecture/07_Wiki/Wiki_Output_Design.md`（Wiki出力設計全体、§9.2 Story index・§9.3 Episode page・§11 出力ディレクトリ案）
- `docs/architecture/06_AI/Story_Summary_Design.md`（Story Summary/Episode Summaryのデータ構造・保存場所・status/review workflow設計）
- `docs/architecture/05_Parser/Story_ID_Policy_Decision.md`（`publicStoryId`/`publicEpisodeId`採用方針）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（`story_manifest.yaml`のtitle/subtitle/public ID設計）
- `docs/architecture/05_Parser/Identifier_Specification.md`（Story ID/Episode ID/Evidence ID体系）
- `agents/wiki_generator/paths.py`（現行`episode_page_path`/`resolve_episode_path_id`実装）
- `agents/wiki_generator/renderer.py`（現行`render_story_index_page`/`render_episode_page`実装）
- `TASKS.md`（次PR候補の追跡）
