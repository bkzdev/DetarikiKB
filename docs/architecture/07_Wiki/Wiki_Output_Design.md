# Wiki Output Design（Wiki出力設計）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/07_Wiki/Wiki_Output_Design.md`

---

# 1. 目的

この文書は、Stage B（`agents/merger/`、`docs/architecture/06_AI/Merged_Knowledge_Design.md`）が出力する merged knowledge collection から、将来どのようなWikiページを生成するかを設計する。

**このPRではWiki生成パイプラインの実装は行わない。** ページ種別・責務・front matter方針・出力ディレクトリ案・テンプレート方針・merged collectionとの対応表を整理し、実装PR分割案（§12）を示すことがゴールである。

---

# 2. Knowledge BaseとWikiの関係

```text
Raw Script (.dec)
  → Story Parser → Normalized Story JSON
  → Extractor (Stage A: episode_extraction, Candidate単位)
  → Merger (Stage B: merged knowledge collection, Entity単位)
  → Wiki Generation（本文書の対象）
```

- **Source of Truth は merged knowledge collection である。** `schemas/merged_knowledge.schema.json` / `schemas/merged_knowledge_collection.schema.json` に準拠したデータが、Wikiページの内容を決定する唯一の情報源になる。
- **Wikiページは生成物であり、原則として手編集しない。** Merged Knowledge Design（`Merged_Knowledge_Design.md` §11.1）が「生成物（`data/extracted/`）と手動管理ソース（`knowledge/`）を分離する」方針を採っているのと同じ原則を、Wiki層でも踏襲する。人間が加えたい情報は、Wikiページを直接編集するのではなく、`knowledge/overrides/`（manual override）を通じて merged knowledge collection 側に反映し、そこから再生成する。
- 例外として、`docs/`配下の設計文書・ランブック（本文書を含む）は人間が直接管理する。これらはWiki生成物ではなく、プロジェクトの設計・運用ドキュメントである。

---

# 3. 情報の分離方針（公式情報 / AI要約 / AI考察 / manual override）

`AI_CONTEXT.md` §4.5「Official / AI Summary / AI Analysisを分離する」を、Wikiページの構成原則としてここで具体化する。

| 区分 | 由来（`sourceType`） | ページ上の扱い |
|---|---|---|
| 公式情報 | `official`（ゲーム公式設定資料等、将来入力） | 「公式情報」セクションにそのまま掲載。confidence表示は不要（公式情報は確度100%として扱う） |
| 本文抽出（fact） | `script` / `ai_extracted`（Normalized Story JSONから機械的に抽出した情報） | 「抽出情報」セクション。evidenceRefsと合わせて表示し、rule-based抽出であることが分かるようにする |
| AI推定（inference） | `ai_inferred`（将来のLLM抽出。「〜らしい」等の推定） | **公式情報・抽出情報とは必ず別セクション、または別ページに分離する。** 見出しに `AI-generated analysis` 等の明示ラベルを付け、confidenceとevidenceRefsを必ず併記する |
| manual override | `manual`（人間が明示的に確定した値。`confidence: 1.0`） | 通常セクション内に反映してよいが、「人間により確認済み」であることが分かるバッジ・注記を付ける（`manualOverridesApplied`を参照） |

この分離は`Merged_Knowledge_Design.md` §4.1原則4（fact/inferenceをマージで混ぜない）がStage Bのデータ構造レベルで既に担保しているため、Wiki生成側は`fieldValues`/`sourceTypes`の`sourceType`を見てセクションを振り分けるだけでよい（Wiki側で新たな判定ロジックを作る必要はない）。

---

# 4. evidenceRefs の扱い

**方針: 元セリフ全文を大量転載しない。参照情報を残し、AI要約と元データ参照を分離する。**

- ページ上には evidenceの**要約**（どのエピソード・どのシーンで言及されたか）と、`evidenceId` / `episodeId` / `sceneId` / `blockId` の参照情報のみを表示する。
- `MergedEvidenceRef.textExcerpt`（`schemas/merged_knowledge.schema.json`で任意フィールドとして定義済み）は、表示する場合も**短い抜粋**にとどめる。全文転載はしない（著作権・引用量への配慮、`AI_CONTEXT.md` §4.6 静的サイト公開前提と合わせて特に注意する）。
- 将来的にローカル・内部ツールからは、`evidenceId`から Normalized Story JSON の該当Blockまで遡れる（`Merged_Knowledge_Design.md` §10.1の遡及チェーンをそのまま使う）。公開Wiki側ではこの遡及リンクを外部公開しない（Raw Scriptを公開する意図は無いため）。
- 表示形式の例:

  ```markdown
  ### 登場エピソード
  - MAIN_S01_C02_E01（seq: 3件の言及）
  - MAIN_S01_C03_E01（seq: 1件の言及）
  ```

  のように、evidence件数の要約＋episodeIdのリンクにとどめ、本文そのものは載せない。

---

# 5. unresolved entity / canonicalId なし entity の表示方針

`docs/architecture/06_AI/Canonical_ID_Policy.md` の「canonicalIdが無いentityのURLは不安定」という原則（§2「`mergedId`は再マージで変わりうるため外部から参照しない」）を、Wiki生成の可否判定にそのまま適用する。

| 状態 | 判定 | 理由 |
|---|---|---|
| `status: merged`かつ`canonicalId`あり | 通常ページを生成する | URLが安定（canonicalIdは一度確定したら原則変更しない） |
| `status: unresolved`（`canonicalId: null`） | **通常ページは生成しない。** `reports/unresolved/`配下にのみ一覧掲載する | `id`（`mergedId`）は再マージで変わりうるため、外部から参照可能なURLを持たせるべきではない |
| `status: conflict` | 通常ページは生成するが、warning boxを表示する | canonicalIdは確定しているため生成してよいが、未解決の衝突があることを読者に明示する必要がある |
| `status: deprecated` | ページを生成しない、または「統合済み」として新IDへのリダイレクト情報のみ残す | 打ち消し・統合済みのエンティティを独立ページとして残す意味が薄い |

- unresolved entityは「まだ確定していないが観測されている」情報であり、破棄はしない（`AI_CONTEXT.md` §13.3 unknown/unresolvedを破棄しない原則と同じ思想）。個別ページの代わりに、Unresolved Report（§7 Phase 1）へ集約する。
- `report.unresolvedEntityCounts`（`schemas/merged_knowledge_collection.schema.json`）をそのままレポートの数値サマリーとして使える。

---

# 6. hidden / excluded entity の扱い

以下に該当するentityは、Wiki生成対象から明示的に除外する（生成しない、または非公開扱いにする）。

- `confidence < 0.4`（`Merged_Knowledge_Design.md` §4.5「低confidence candidateの隔離」対象。そもそも`_unresolved/`へ隔離されているため、通常は§5の「unresolved」扱いに自然と合流する）
- `evidenceRefs`が0件のentity（`Merged_Knowledge_Design.md` §10.1「Evidenceを持たないmerged entityは出力しない」により、Stage B時点で既にこの状態のentityは出力されない設計だが、Wiki生成側でも同じ条件を防御的に確認する）
- `status: deprecated`（`suppressed: true`相当のmanual overrideで打ち消されたentity。§8.2 `suppress` action）
- 将来、`manual override`で明示的に「非公開」フラグが立てられたentity（現時点の`manual_overrides.schema.json`にはそのようなoperationは無いため、必要になった時点で別途設計する）

これらは「存在しないもの」として扱うのではなく、`report`（merge report）側の集計には含め続ける（破棄しない原則）。Wikiページとしての独立公開のみを保留する。

---

# 7. 実データ由来生成物をcommitしない方針

`docs/runbooks/Real_Data_Dry_Run.md` / `docs/runbooks/Character_Dictionary_Review.md` と同じ既存ルールを、Wiki生成物にもそのまま適用する。

- 実データ（実際の`.dec`スクリプト由来のセリフ・キャラクター名・merged knowledge collection）から生成したWikiページ・Markdownファイルは、**commitしない**。
- 合成データ（`CHAR_TEST_*`等）から作った**サンプル**のみ、`docs/examples/wiki_output/`または`tests/fixtures/`に置いてよい（本PRで追加するものは§13参照）。
- 将来、実データからのローカルdry-run render（§12 実装PR案6）を行う場合も、出力先は`.gitignore`済みの領域（`workspace/wiki_preview/`等）を使う。

**実装状況（`feature/real-data-wiki-render-dry-run`で追加）**: 実データWiki render dry-run専用の手順書`docs/runbooks/Real_Data_Wiki_Render_Dry_Run.md`と結果記録テンプレート`docs/runbooks/Real_Data_Wiki_Render_Dry_Run_Result_Template.md`を追加した。`.gitignore`に`workspace/wiki_preview/`・`workspace/wiki_render/`・`site_src/`・`docs/wiki_generated/`・`generated/wiki/`を追加済み。このPR実施時点ではローカルに実データ由来merged knowledge collectionが存在しなかったため、実データでのdry-runは未実施（合成の縮退collectionでrendererの堅牢性のみ検証、詳細はTASKS.md参照）。

- 公開時（GitHub Pages / Cloudflare Pages等）の運用方針は、本文書のスコープ外とし、別PRで決める（Non-goals参照）。

---

# 8. ページ種別と優先順位

以下のページ種別を設計する。全てを最初から実装する必要はないため、Phase分けする。

## Phase 1（最優先）

| ページ種別 | 概要 |
|---|---|
| Top page | Wikiサイトのトップ。ストーリー一覧・統計サマリーへの入口 |
| Story index | ストーリー（`storyId`）一覧。カテゴリ（MAIN/EVENT/CHARACTER等）別に整理 |
| Story page | ストーリー単位の閲覧者向け入口ページ（`docs/architecture/07_Wiki/Story_Page_Design.md`で設計、`feature/wiki-story-page-renderer`で実装完了。Overview・Story/Episode Summary placeholder・Episode一覧・Related Characters・Unresolved report導線を表示） |
| Episode page | エピソード単位のページ。登場人物・場所・あらすじ相当の抽出情報 |
| Character page | キャラクター単位のページ（§9で詳細） |
| Unresolved report page | `status: unresolved`のentity一覧。canonicalId未確定のため個別ページを持たない代わりに、ここに集約する |

## Phase 2

| ページ種別 | 概要 |
|---|---|
| Location page | 場所単位のページ |
| Organization page | 組織単位のページ |
| Item page | アイテム単位のページ |
| Lore page | 用語・設定単位のページ |
| Event page | 作中出来事単位のページ |
| Relationship section | 独立ページではなく、Character/Organizationページ内の関係セクションとして表示（§9） |
| Timeline page | エピソード横断の時系列情報一覧（`timeline_entries.json`由来。§7参照の通り順序確定はしない） |

## Phase 3

| ページ種別 | 概要 |
|---|---|
| AI analysis / speculation page | AI推定（`ai_inferred`）のみで構成される考察ページ。公式情報と混在させない（§3） |
| Evidence / source index page | `sourceDocuments`一覧。どのepisode_extractionがマージに使われたかの索引 |
| Knowledge Graph view | Neo4jベースのグラフビュー（`docs/architecture/04_Knowledge_Graph/`との連携。本文書のスコープ外に近いため最終フェーズ） |

Relationship page（独立ページ）は現時点では見送り、Character/Organizationページ内のセクションとする方針を推奨する。理由: 現状のRelationshipは「2つのエンティティ間の1つながり」であり、独立ページにするほどの内容量（本文・evidence以外の固有情報）が無いため。将来、Relationshipに付随する情報（変化の経緯`temporalNote`等）が増えた場合に独立ページ化を再検討する。

---

# 9. ページ責務

各ページについて、入力source・表示フィールド・非表示情報・evidenceRefs表示方法・unresolved時の表示・manual override反映方針・AI由来情報のラベル付け・将来のテンプレート名を整理する。

## 9.1 Top page

- source: `report`（merge report全体）のサマリー、`sourceDocuments`件数
- 表示: ストーリー数・キャラクター数・場所数等の統計、Story indexへのリンク、Unresolved reportへのリンク
- 表示しないもの: 個別entityの詳細、AI考察
- テンプレート名（案）: `templates/wiki/index.md.j2`

## 9.2 Story index

- source: `sourceDocuments`（`storyId`でグルーピング）
- 表示: ストーリーID・カテゴリ（MAIN/EVENT/CHARACTER/COLLABORATION/OTHER）・エピソード一覧
- 表示しないもの: エピソード本文
- テンプレート名（案）: `templates/wiki/story_index.md.j2`

**実装状況（`feature/episode-page-renderer-expansion`で拡張、`feature/wiki-episode-title-display-integration`でDisplay Title列を追加、`feature/wiki-renderer-readability-improvements`で列数削減）**: `render_story_index_page`は、storyId・episodeId（Episode pageへのリンク）・Display Title（`displayTitle > episodeSubtitle > storyTitle > episodeId`のfallback、§9.3参照）・`report.inputResults`から突き合わせたstatus（見つからない場合は空欄）・categoryの5列表を出力する。manual visual review 001で「表が横長すぎる」と指摘されたため、documentId（通常episodeIdと同値）とcandidate合計件数（Episode pageのCandidate Counts sectionで確認可能）は表から外した（情報自体は失われない）。

**Story page中心構造への設計方針（`feature/wiki-story-page-design`で追加）**: manual review（PR #74）を踏まえ、現在のEpisode page中心構造から、ストーリー単位の閲覧者向け入口ページ（Story page）を追加する方向へ設計を進めることにした。詳細な役割分担・Summary配置・Evidence管理方針・URL構造候補の比較は`docs/architecture/07_Wiki/Story_Page_Design.md`を参照。**このPRではStory page rendererの実装・URL変更・Episode page path変更は行っていない。**

**Story page renderer実装（`feature/wiki-story-page-renderer`で追加）**: `render_story_index_page`を、Episode単位の行からStory単位（`storyId`でグルーピング）の行へ変更した。表は`| Story | Episodes | Status | Category |`の4列で、Story列はStory pageへのリンク（リンクtextは`storyTitle > publicStoryId > storyId`の優先順位、`displayTitle`はEpisode単位のためStory titleには使わない）、Episodesはそのstoryに属するepisode数、Statusはstory内のepisodeで`metadataStatus`が一致すればその値、異なれば`mixed`と表示する。Episode単位のtitle fallback（`displayTitle > episodeSubtitle > storyTitle > episodeId`）はStory page内のEpisode一覧セクションへ引き継いだ（詳細は`Story_Page_Design.md`参照）。`agents/wiki_generator/paths.py`に`story_page_path`/`resolve_story_path_id`を追加し、`publicStoryId`があればそれを、無ければ`storyId`をfilenameに使う（短期URL構造は候補A、flat維持）。Episode pageの`episode_page_path`・`publicEpisodeId`によるfallback方針（PR #73）は変更していない。

**Episode link text改善（`feature/wiki-story-index-link-text-improvement`で実装）**: manual visual review 001/002で「Episode pageへのリンクテキストがepisodeId中心で分かりにくい」と指摘されたため、Episode列自体を`displayTitle > episodeSubtitle > storyTitle > episodeId`優先の人間向けタイトルへのリンクへ変更した（`_episode_link_text`/`_get_episode_display_title`/`_first_non_blank`）。空文字列・whitespaceのみの値は未登録として次の優先順位へfallbackする。リンク先URL・ファイル名（`stories/{episodeId}.md`）・`episodeId`自体は一切変更していない。あわせて、Episode link textと内容が重複していた独立の「Display Title」列を廃止し、`report.inputResults`由来のinput validation status（valid/invalid、Episode page側のValidation sectionで引き続き確認可能）をmetadataStatus表示（`_format_metadata_status`、PR #62から継続）へ置き換えた。表構成は`| Story ID | Episode | Status | Category |`の4列（storyIdはcode表示）。titleに`|`/`[`/`]`が含まれる場合に備え、`_escape_markdown_table_text`で最小限のMarkdown escapeを行う。storyId/episodeId体系・URL・ファイル名は本PRの対象外（別PRで扱う）。

## 9.3 Episode page

- source: 個別`entities.*`のうち、`sourceCandidates[].episodeId`がこのエピソードに一致するもの（登場キャラクター・場所等の索引として）
- 表示: `episodeId`、登場キャラクター一覧（Character pageへのリンク）、登場場所一覧、`unresolvedEntityCounts`のうちこのエピソード由来分
- 表示しないもの: 本文セリフ全文（§4 evidence方針と同じ理由）
- unresolved時の表示: このエピソード由来のunresolvedエンティティは名前のみ列挙し、リンクは張らない（個別ページが無いため）
- テンプレート名（案）: `templates/wiki/episode.md.j2`

**実装状況（`feature/episode-page-renderer-expansion`で拡張）**: `render_episode_page`（`agents/wiki_generator/renderer.py`）は、Summary・Candidate Counts表（8種、`Wiki_Output_Design.md` §13対応表と同じ順序・ラベル）・Related Characters（`entities.characters`の`evidenceRefs.episodeId`/`sourceCandidates.episodeId`/`extractionRunRefs`キーのいずれかがこのepisodeIdに一致するcharacterを列挙。canonicalIdがあれば`` `CHAR_XXX` ``、unresolvedなら内部idと`unresolved`表記）・Validation（`report.inputResults`をpathで突き合わせられた場合のみinput status/errors件数/warnings件数を表示、見つからない場合はセクション自体を省略）の順でセクションを出力する。front matterには`page_type: "episode"`（`entity_type`ではなくepisodeがmerged knowledge schema上のentityではないことを明示するため）・`episode_id`/`story_id`/`document_id`を追加した。`source_path`は本文Summaryのみに表示し、front matterには含めない（ローカルパス漏洩懸念への配慮）。Location/Organization等の関連entity summaryは今回未実装（characters優先、Phase 2で拡張予定）。

**Summaryのdefinition list化（`feature/wiki-renderer-readability-improvements`）**: manual visual review 001で「Summary tableが横長すぎる」と指摘されたため、Summaryは`| 項目 | 値 |`のtableから箇条書き（`_render_key_value_list`）へ変更した。Episode ID/Story ID/Document IDはcode表示（`` `EP_TEST_001` ``のようにバッククォート囲み）とし、人間が見て重要なDisplay Title/Story Title/Episode Subtitle/Metadata Statusを先頭に、内部provenance情報（Document ID/Source Path/Extraction Version/Category）を末尾に配置する。値自体はすべて維持しており削除していない。Candidate Counts表（2列のみ、既に狭幅）とValidation表（3列のみ）は変更していない。

**title/subtitle表示方針（`feature/wiki-episode-title-display-integration`で実装完了）**: `docs/architecture/05_Parser/Story_Manifest_Design.md`で設計した`story_manifest.yaml`由来の値が、`normalize_story.py --manifest`（Normalized Story JSONの`metadata.storyTitle`/`episodes[].metadata.episodeSubtitle`/`displayTitle`/`metadataStatus`）→Extractor（`episode_extraction`の`storyTitle`/`episodeSubtitle`/`displayTitle`/`metadataStatus`、任意フィールド）→Merger（`sourceDocuments[]`の同名フィールド、任意フィールド）→Wiki rendererまで伝播するようになった。`render_episode_page`はSummary tableへStory Title/Episode Subtitle/Display Title/Metadata Statusの4行を追加する（既存の見出し`# {episodeId}`・`Episode ID`行は変更しない）。値がnullまたはキー自体が無い場合（story_manifest.yaml未使用の既存fixture含む）は「未登録」と表示し、クラッシュしない。`metadataStatus`は`pending`/`confirmed`/`title_unknown`/`deprecated`に日本語の補足を付けて表示し、未知の値も破棄せずそのまま表示する。`render_story_index_page`は「Display Title」列を追加し、`displayTitle > episodeSubtitle > storyTitle > episodeId`の優先順位でfallbackした値を表示する（どれも未設定なら既存どおりepisodeId）。AI-generated titleは生成せず、公式title/subtitleと混在させない（§3の情報分離方針を踏襲）。**このPRでは実タイトル・実サブタイトルの投入は行っていない**（合成fixtureのみで検証）。

## 9.4 Character page

- source: `entities.characters`（`status: merged`のみ。§5参照）
- 表示する主なフィールド:
  - `displayName`（`canonicalName`）
  - `aliases`
  - `status`
  - `sourceTypes`
  - `confidence`
  - 関連するRelationship（Character/Organizationへの所属等、§8 Relationship section）
  - 登場エピソード一覧（evidence由来、§4の要約形式）
  - evidence概要（件数・エピソード別内訳、本文なし）
  - `conflicts`（存在する場合、warning box）
  - `manualOversidesApplied`（人間確認済みフィールドがあれば明示）
- 表示してはいけないもの: 本文セリフ全文、`sourceCandidateId`等の内部処理用ID（provenance情報として保持はするが、ページ本文には出さない。デバッグ用途のfront matterまたは別セクションに留める）
- evidenceRefsの表示方法: §4の通り、要約＋エピソードリンクのみ
- unresolved時の表示方法: このページ自体を生成しない（§5）。名前のみの言及はUnresolved reportに掲載
- manual override反映後の表示方針: `manualOverridesApplied`が非空なら「人間により確認済み」の注記を表示
- AI由来情報のラベル付け: `sourceTypes`に`ai_inferred`が含まれるフィールドは「AI推定」ラベルを付けるか、AI analysis pageへ分離する
- テンプレート名（案）: `templates/wiki/character.md.j2`

**基本プロフィールsection（`feature/character-profile-schema-design`で設計、`feature/character-profile-renderer-section`で実装完了）**: Character pageに、`knowledge/dictionaries/character_profiles.yaml`（公式プロフィール辞書、`docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`参照）を参照元とする「基本プロフィール」sectionを実装した（`render_character_page`の`## Summary`直後、`## Aliases`より前に挿入。AI抽出・merge由来の`## Summary`等とは明確に区別する）。entityの`canonicalId`（= `characters.yaml`のconfirmed済み`characterId`）と`character_profiles.yaml`の`characterId`が一致した場合のみ表示し、表示項目は名前（`displayName`）・ふりがな（`reading.kana`）・ローマ字（`reading.romaji`）・所属（`affiliation`、複数件は読点区切り）・身長（`heightCm`を"150cm"のように整形）・誕生日（`birthday.display`優先、無ければ`month`/`day`から組み立て）・血液型（`bloodType`）・CV（`cv`）・特記事項（`profileHighlight`、`feature/wiki-character-profile-display-refinement`で表内の1行へ変更、次段落参照）・Status（プロフィール自体の`status`）・自己紹介文（`selfIntroduction`、複数行はそのままMarkdown本文として表示）。値が無い項目は「未登録」、該当`characterId`のプロフィールが存在しない場合はsection自体は省略せず「プロフィール未登録」と表示する。`scripts/render_wiki.py`に任意の`--character-profiles`引数を追加し、指定時のみ`character_profiles.yaml`を読み込む（未指定時は全Character pageが「プロフィール未登録」表示のまま、既存の生成結果を変えない）。**このPRでは新しいプロフィールデータの追加・修正、WIKI再取得は行っていない**（`character_profiles.yaml`を読み取るのみ）。

**profileHighlight表示・出典非表示への変更（`feature/wiki-character-profile-display-refinement`で実装完了）**: manual visual reviewでの要望を受け、`profileHighlight`は独立sectionではなく「基本プロフィール」表の「特記事項」行として表示するよう変更した（`_format_profile_highlight`）。表示形式はWiki記載と同じ雰囲気の`【label】value`（例: `【好きなこと】食べ歩き`）とし、labelのみ・valueのみ・両方欠落の場合も「未登録」等へ安全にfallbackする。あわせて、`source`（出典）はCharacter page上から**非表示**にした。`character_profiles.yaml`側の`source`フィールド自体（`sourceType`/`label`/`referenceId`/`notes`）は変更・削除しておらず、schema・loaderも無変更である（表示側でのみ省略）。**このPRでも実プロフィールデータの追加・修正は行っていない**（合成fixtureのみで検証）。

**実装状況（`feature/character-page-renderer-expansion`・`feature/character-profile-renderer-section`で拡張）**: `render_character_page`（`agents/wiki_generator/renderer.py`）は、Summary（Entity ID/Canonical ID/Status/Confidence/Source types）・**基本プロフィール**（上記参照）・Aliases（空なら「別名は登録されていません。」）・Evidence（既存のID参照のみ表示）・Source Candidates（candidateId/candidateType/episodeId/evidenceIds件数/sourceDocumentIdのsummary、元candidateのraw payloadは含めない）・Conflicts（空なら「記録されている矛盾はありません。」、存在する場合はconflictType/field/severity/resolutionStatusを表示）の順でセクションを出力する。front matterには`confidence`/`source_types`を任意フィールドとして追加した。関連Relationship・登場エピソード一覧・manualOverridesApplied表示・AI推定ラベル付けは、Relationship section（Phase 2）・AI analysis page（Phase 3）実装時にあわせて対応する（今回は未実装）。

**Characters index page（`feature/wiki-character-index-page`で追加）**: manual visual review 001で「Top pageからCharacter pageへの直接導線が無く、Episode pageのRelated Characters経由でしか辿れない」ことが判明したため、`characters/index.md`を新設した。`render_character_index_page(characters, character_profiles=None)`は、`is_page_eligible`がtrue（canonicalId確定 + `status: merged`）のcharacterのみを一覧表示する（unresolved・canonicalId未確定・status不一致のcharacterはここには載せず、`reports/unresolved.md`側でのみ確認できるようにする、§5の判定基準をそのまま流用）。Overview（Character pages件数・プロフィール登録あり/なし件数、`Unresolved report`へのリンク案内）とCharacter List表（Character名（リンク付き）・Profile Status（登録あり/未登録）・ID の3列のみ、manual visual review 001で判明した「表が横長すぎる」問題を踏まえ列数を最小限に抑えた）で構成する。profile登録判定は`render_character_page`の基本プロフィールsectionと同じ照合ロジック（`entity.canonicalId == character_profiles`のキー一致）を再利用する。Top pageの「## リンク」セクションに`[Characters](characters/index.md)`を追加し、`build_pages()`が返すページ一覧へ`characters/index.md`を含めるようにした。profileHighlightの表示統合・profile source非表示化・表の可読性改善（列のさらなる整理、モバイル対応）は本PRのスコープ外（それぞれ`feature/wiki-character-profile-display-refinement`・`feature/wiki-renderer-readability-improvements`）。

## 9.5 Location page

- source: `entities.locations`
- 表示: `displayName`、`aliases`、`sceneRefs`件数、登場エピソード
- テンプレート名（案）: `templates/wiki/location.md.j2`

## 9.6 Organization page

- source: `entities.organizations`
- 表示: `displayName`、`aliases`、所属キャラクター（Relationship `MEMBER_OF`/`AFFILIATED_WITH`経由）
- Relationship sectionをここに埋め込む（§8参照）
- テンプレート名（案）: `templates/wiki/organization.md.j2`

## 9.7 Item page

- source: `entities.items`
- 表示: `displayName`、`aliases`、登場エピソード
- テンプレート名（案）: `templates/wiki/item.md.j2`

## 9.8 Lore page

- source: `entities.lore`
- 表示: 用語表記（`termCandidates`相当）、`aliases`、関連エピソード
- 注意: Loreは「同じ語が別概念を指すリスクが最も高い」種別（`Merged_Knowledge_Design.md` §5.5）。ページ上でも、複数の意味が疑われるentity（`conflicts`が`merge_suggestion`を含む場合）はwarningを強めに出す
- テンプレート名（案）: `templates/wiki/lore.md.j2`

## 9.9 Event page

- source: `entities.events`
- 表示: `displayName`、参加キャラクター（`participantEntityIds`）、発生場所（`locationEntityIds`）、関連エピソード
- テンプレート名（案）: `templates/wiki/event.md.j2`

## 9.10 Relationship section（独立ページではない、§8参照）

- source: `entities.relationships`。`sourceEntityId`/`targetEntityId`のいずれかが該当ページの主体と一致するものを抽出
- 表示: `relationshipType`、方向（`direction`）、`temporalNote`（変化があれば）、evidence概要
- AI由来情報のラベル付け: `sourceType: ai_inferred`のRelationshipは「AI推定の関係」ラベルを付ける（`Merged_Knowledge_Design.md` §6.4がfact/inferenceを別レコードで保持する設計のため、Wiki側は`sourceType`で振り分けるだけでよい）

## 9.11 Timeline page

- source: `entities.timeline`（`timeline_entries.json`相当）
- 表示: `kind`別（`explicit_order`/`temporal_marker`）にセクション分割、`scope`（episode/block）ごとの一覧
- 表示してはいけないもの: 順序の「確定」表現。`Merged_Knowledge_Design.md` §7.1の通りStage Bでは順序を確定しないため、Wikiページ上も「観測された順序情報の一覧」であることを明示し、確定した年表のように見せない
- テンプレート名（案）: `templates/wiki/timeline.md.j2`

## 9.12 Unresolved report page

- source: `report.unresolvedEntityCounts`、および`_unresolved/`相当のentity一覧（`status: unresolved`）
- 表示: entity種別ごとの件数、代表的なdisplayName（あれば）、`mergedId`（内部参照用、外部リンクにはしない）
- テンプレート名（案）: `templates/wiki/unresolved_report.md.j2`

**実装状況（`feature/unresolved-report-renderer-refinement`で拡張、`feature/wiki-renderer-readability-improvements`で列数削減）**: `render_unresolved_report`（`agents/wiki_generator/renderer.py`）は、Overview（Total unresolved entities/Total conflicts/Total warnings/Invalid canonical IDs/Duplicate canonical IDs）・entity種別別セクション（8種、`is_page_eligible`で個別ページ対象外と判定されたentityのみ。Display Name/Entity ID/Status/Canonical ID/Refsの5列表）・**Special Speaker Labels**（次段落参照）・Conflict Summary（`report.conflictCounts.bySeverity`/`byType`/`byEntityType`）・Warning Summary（`report.warningCounts`と`report.warnings`の先頭N件）・Canonical ID Summary（`report.canonicalIdSummary`、任意フィールドのため無ければセクション省略）・Relationship Type Summary（`report.relationshipTypeSummary`、`unknownTypes`を見出し付きで一覧表示、自動修正はしない）の順でセクションを出力する。

**Special Speaker Labels section（Speaker Label Normalization設計）**: `name`コマンド/`@ChTalkName`由来のspeaker labelのうち`labelType`が`single_speaker`以外のもの（speaker group・modifier付き・generic/ambiguousな表記）は、`entities.characters`ではなく`entities.specialSpeakerLabels`（`docs/architecture/06_AI/Merged_Knowledge_Design.md` §7.5）から取得し、entity種別別セクション（通常のUnresolved Characters）とは別に「Special Speaker Labels」sectionとして一覧表示する。Character merged entityと構造的に分離されているため、通常セクションへの重複表示は発生しない。表はLabel/Type/Inferred（confirmed character dictionaryとの参考照合結果のmatchedNameのみ、characterId/matchStatus自体は表示しない）/Refs（evidence件数/source candidate件数）の4列のみで、自動でconfirmed character解決をしたことを示す表示（`confirmed`という語）は一切出さない。Characters index page・Character page（個別ページ）にはspecial speaker labelは一切現れない。§9.13〜9.15で独立ページとして構想していたConflict/Relationship type/Canonical ID summaryは、今回はこの単一のUnresolved reportページ内のセクションとして統合実装した（独立ページとして分離するかは未確定、Phase 2以降で再検討）。evidenceRefs/sourceCandidatesは件数のみ表示し、元セリフ全文・raw payloadは一切含めない。**Refs列統合**: manual visual review 001で「entity種別別表が横長すぎる」と指摘されたため、Evidence件数とSource Candidates件数の独立2列を「Refs」列（`evidence件数/source candidate件数`形式、例: `1/1`）へ統合した（元の6列表から5列表へ、件数情報自体は失っていない）。運用上重要な情報（Canonical ID等）は引き続き列として残す。

## 9.13 Conflict report page

- source: `report.conflictCounts`
- 表示: `conflictType`別・`severity`別・entity type別の件数。個別conflictの詳細は該当entityページのwarning boxで確認する形とし、このページはサマリーに留める

**実装状況**: `feature/unresolved-report-renderer-refinement`で、独立ページではなくUnresolved report内のConflict Summaryセクションとして実装済み（§9.12参照）。

## 9.14 Relationship type report page

- source: `report.relationshipTypeSummary`
- 表示: `knownTypes`/`unknownTypes`の内訳。taxonomy確定（`docs/architecture/04_Knowledge_Graph/Relationships.md`）前の暫定状況の可視化用

**実装状況**: `feature/unresolved-report-renderer-refinement`で、独立ページではなくUnresolved report内のRelationship Type Summaryセクションとして実装済み（§9.12参照）。

## 9.15 Canonical ID report page

- source: `report.canonicalIdSummary`
- 表示: `totalAssigned`/`duplicateCount`/`invalidCount`と`warnings`

**実装状況**: `feature/unresolved-report-renderer-refinement`で、独立ページではなくUnresolved report内のCanonical ID Summaryセクションとして実装済み（§9.12参照）。

## 9.16 Source / evidence index page

- source: `sourceDocuments`
- 表示: マージに使われたepisode_extractionドキュメントの一覧（`documentId`/`episodeId`/`candidateCounts`）
- Phase 3。実データのepisode一覧をそのまま公開する意味があるかは、公開方針決定時に再検討する

## 9.17 AI analysis / speculation page

- source: `sourceType: ai_inferred`のFieldValue/Relationshipのみ
- 表示: 「AI-generated analysis」の明示ラベル、confidence、evidenceRefs
- 表示してはいけないもの: 公式情報・抽出情報との混在（§3）
- Phase 3。LLM抽出自体が未実装のため、当面は空またはページ自体を生成しない
- Story/Episode Summary（§9.2 Story index/`Story_Page_Design.md`のStory page Summary placeholder）とは別物である。要約（明示された事実の簡潔なあらすじ）とAI考察（推測・伏線考察・矛盾点考察）の分離方針・データ構造は`docs/architecture/06_AI/Story_Summary_Design.md` §2.3・§7を参照（`feature/story-summary-schema-implementation`でschema/loader/validatorを実装済み、renderer統合はまだ未実装）

---

# 10. Markdown front matter 方針

MkDocs Material等での利用を見据え、以下のfront matter方針を設計する。**実データページはまだ生成しない。以下は合成例のみ。**

```markdown
---
title: "Example Character"
entity_type: "character"
entity_id: "CHAR_EXAMPLE"
canonical_id: "CHAR_EXAMPLE"
status: "merged"
confidence: 0.9
source_types: ["script"]
generated_from: "merged_knowledge_collection"
generated_at: "2026-07-04T00:00:00Z"
schema_version: "0.1"
---
```

フィールド方針:

- `entity_id` / `canonical_id`: 両方持たせる。`entity_id`は`MergedEntityBase.id`（現時点で権威的な識別子）、`canonical_id`は`MergedEntityBase.canonicalId`（確定済みのみ、`null`なら生成しない §5）。将来`id`と`canonicalId`が分離運用される場合に備え、あえて両方残す
- `status`: `schemas/merged_knowledge.schema.json`の`Status`列挙値（`merged`/`unresolved`/`conflict`/`deprecated`）をそのまま使う。ページを生成するのは実質`merged`/`conflict`のみ（§5）
- `generated_from`: 常に`"merged_knowledge_collection"`固定。手編集ではなく生成物であることをfront matterレベルでも明示する（§2）
- `generated_at`: 生成日時（実データ生成時にのみ入る。合成例では固定値でよい）
- `ai_generated` / `ai_confidence`: AI analysis page（§9.17）でのみ使う追加フィールド案。Phase 3実装時に確定する

---

# 11. 出力ディレクトリ案

```text
site_src/
  index.md
  stories/
    index.md
    {storyId}/
      index.md
      {episodeId}.md
  characters/
    index.md
    {canonicalId}.md
  locations/
    {canonicalId}.md
  organizations/
    {canonicalId}.md
  items/
    {canonicalId}.md
  lore/
    {canonicalId}.md
  events/
    {canonicalId}.md
  timelines/
    index.md
  reports/
    unresolved.md
    conflicts.md
    relationship_types.md
    canonical_ids.md
    sources.md
```

- `docs/wiki_generated/`案も検討したが、`docs/`配下は既に設計文書・ランブックというGit管理対象の手書きドキュメント置き場として使われている（`docs/architecture/`、`docs/runbooks/`）。生成物を同じ`docs/`配下に混在させると、`Merged_Knowledge_Design.md` §11.1が生成物ディレクトリで既に解決した「生成物と手書きソースの混在問題」を、Wiki層で再発させることになる。そのため**`site_src/`（リポジトリ直下、生成物専用）を推奨**する。
- **現時点の推奨: 実データ由来の生成物は当面commitしない。** `site_src/`は`.gitignore`対象とし、ローカル・CI内での生成→静的サイトビルド→デプロイのパイプライン内でのみ実体化する（公開時の運用は別PRで決める、§14 Non-goals）。
- 合成fixtureから作ったサンプルは`docs/examples/wiki_output/`（本PRで追加、§13）または`tests/fixtures/`に置く。

---

# 12. テンプレート方針

## 12.1 候補

| 方式 | メリット | デメリット |
|---|---|---|
| Jinja2 templates | 表現力が高い、MkDocs等のエコシステムと相性が良い、条件分岐・ループが書きやすい | 新規依存追加が必要（`pyproject.toml`変更） |
| Python string builder | 依存追加不要、既存の`agents/parser/normalizer.py`等と同じ手続き的スタイル | ページ数が増えるとテンプレートロジックが肥大化しやすい |
| Markdown renderer module（自作の小さな関数群） | 依存追加不要、テストしやすい単位に分割できる | Jinja2ほどの表現力・保守性は無い |

## 12.2 推奨

**このPRではテンプレート方式を確定しない。設計のみ行い、依存追加の要否は実装PR（§14 実装PR案 1. wiki renderer skeleton）で判断する。**

理由: Jinja2導入は将来的に便利だが、依存追加は実装が具体化してから判断すべきであり、設計段階で決め打ちしない（Non-goals「Wiki生成パイプライン実装」に該当するため、このPRのスコープ外）。

## 12.3 テンプレート名候補（実装時の参考）

```text
templates/wiki/index.md.j2
templates/wiki/story_index.md.j2
templates/wiki/episode.md.j2
templates/wiki/character.md.j2
templates/wiki/location.md.j2
templates/wiki/organization.md.j2
templates/wiki/item.md.j2
templates/wiki/lore.md.j2
templates/wiki/event.md.j2
templates/wiki/timeline.md.j2
templates/wiki/unresolved_report.md.j2
```

このPRでは`.j2`ファイル本体は追加しない（テンプレートエンジン未確定のため）。

---

# 13. merged collection との対応表

| merged knowledge collection側 | Wiki側 |
|---|---|
| `entities.characters` | Character pages（§9.4） |
| `entities.locations` | Location pages（§9.5） |
| `entities.organizations` | Organization pages（§9.6） |
| `entities.items` | Item pages（§9.7） |
| `entities.lore` | Lore pages（§9.8） |
| `entities.events` | Event pages（§9.9） |
| `entities.relationships` | Relationship sections（独立ページではない、§9.10） |
| `entities.timeline` | Timeline page（§9.11） |
| `report.unresolvedEntityCounts` | Unresolved report（§9.12） |
| `report.conflictCounts` | Conflict report（§9.13） |
| `report.relationshipTypeSummary` | Relationship type report（§9.14） |
| `report.canonicalIdSummary` | Canonical ID report（§9.15） |
| `sourceDocuments` | Source / evidence index（§9.16） |

---

# 14. URL / slug 方針

**名前ベースslugは原則避ける。** `displayName`は変更されうる（表記揺れの統合、manual overrideによる`canonicalName`変更等）ため、URLの安定性をdisplayNameに依存させない。

| 種別 | URL方針 | 例 |
|---|---|---|
| Character/Location/Organization/Item/Lore/Event（canonicalIdあり） | `{type}/{canonicalId}.md` | `characters/CHAR_RAIN.md` |
| 同上（canonicalIdなし = unresolved） | ページを生成しない。`reports/unresolved.md`にのみ一覧掲載 | （URLなし） |
| Story/Episode | `stories/{storyId}/{episodeId}.md` | `stories/MAIN_S01_C02/MAIN_S01_C02_E01.md`（`feature/wiki-renderer-skeleton`のrenderer skeletonでは、暫定的にフラット構成`stories/{episodeId}.md`を採用。ネスト構成への移行は今後のepisode page renderer拡張で検討する） |
| index系 | `{type}/index.md` | `characters/index.md` |
| Timeline | `timelines/index.md`（単一集約ファイル、`Merged_Knowledge_Design.md` §7が「エンティティ統合しない」方針のため個別ページを持たない） | |

`canonicalId`自体が`Identifier_Specification.md`の規則で安定運用される前提（`Canonical_ID_Policy.md` §2「一度確定したら原則変更しない」）に、Wiki URLの安定性を委ねる。

**関連（`feature/story-id-policy-real-sample-review`で追加）**: Story/EpisodeのURL（`stories/{episodeId}.md`）は、EVENTカテゴリの場合raw配置由来の長い`episodeId`（`EVT_{sourceKey}_E{episode}`）をそのまま使うため、公開Wiki化前に見直す余地がある。実データサンプルを踏まえたレビューは`docs/architecture/05_Parser/Story_ID_Policy_Review.md`を参照（本PRではURL/file pathは変更していない）。

**方針決定（`feature/story-id-policy-design-decision`で追加）**: 上記レビューを踏まえた採用方針を`docs/architecture/05_Parser/Story_ID_Policy_Decision.md`で決定した。現行URL（`stories/{episodeId}.md`）は当面維持し、将来公開URL用に`publicStoryId`/`publicEpisodeId`が導入された場合のみ、renderer/paths.pyの段階移行を検討する（本PRでもURL/file pathは変更していない）。

**field設計実装（`feature/story-manifest-public-id-fields-design`で追加）**: `publicStoryId`/`publicEpisodeId`を`story_manifest.yaml`の任意フィールドとして実装した（`docs/architecture/05_Parser/Story_Manifest_Design.md` §13.2）。**renderer/paths.pyのURL切替はまだ行っていない。** 現行URL（`stories/{episodeId}.md`）は変更なし。この2フィールドをrenderer/paths.pyで実際に使うかどうかの判断・実装は引き続き将来PRの対象とする。

**renderer/paths.py切替実装（`feature/story-manifest-public-id-renderer-switch`で追加）**: `agents/wiki_generator/paths.py`の`episode_page_path`（内部で`resolve_episode_path_id`を使用）が、`sourceDocument.publicEpisodeId`（空文字列・whitespaceのみは無視）を優先し、無ければ既存の`episodeId`（無ければ`documentId`）へfallbackするようにした。`publicEpisodeId`が無い既存データは`stories/{episodeId}.md`のまま変更されない。Story indexのEpisodeリンク先も同じ解決結果を使うため自動的に追従するが、リンクtext（`displayTitle > episodeSubtitle > storyTitle > episodeId`優先順位）は変更していない。Character page path・Characters index・Unresolved reportは変更していない。

---

# 15. 将来の実装PR案

1. ~~**wiki renderer skeleton**~~ → `feature/wiki-renderer-skeleton`で対応完了。`agents/wiki_generator/`（既存の空placeholder package）に、`renderer.py`（Top page/Story index/Episode page簡易版/Character page/Unresolved report pageの生成関数）・`paths.py`（canonicalId優先URL方針の実装）・`models.py`（front matter組み立て）を実装し、`scripts/render_wiki.py`（CLI、`--validate`/`--clean`オプション付き）を追加した。当初計画の「個別ページ生成ロジックはまだ実装しない」段階を超え、Character page/Unresolved report pageまで最小実装した（合成fixtureのみ、実データ由来生成物のcommitなし）
2. ~~**character page renderer with synthetic fixture**~~ → 上記1と同時に対応完了（`render_character_page`、canonicalIdありのresolved characterのみ生成）
3. **episode page renderer with synthetic fixture**: 簡易版（sourceDocumentsベース）は1で対応済み。Episode本文相当の情報を持つ本格版は今後の課題（現状のmerged knowledge collectionにEpisode entityが存在しないため）
4. ~~**unresolved report renderer**~~ → 上記1と同時に対応完了（全8種entity type対応、`reports/unresolved.md`）。~~**unresolved report renderer refinement**~~ → `feature/unresolved-report-renderer-refinement`で対応完了（Overview/Conflict Summary/Warning Summary/Canonical ID Summary/Relationship Type Summaryセクション追加、entity種別別表にCanonical ID・Source Candidates列を追加）
5. **MkDocs Material minimal site**: 生成したMarkdown群を実際にMkDocs Materialでビルドできることを確認する最小構成（本文書のNon-goals「MkDocs本格導入」とは異なり、ビルド可否の疎通確認のみ）
6. **real data local render dry-run**: ローカルignored領域で、実データ由来のmerged knowledge collectionから実際にレンダリングしてみる（`docs/runbooks/Real_Data_Dry_Run.md`と同じ運用: 生成物はcommitしない）
7. **public publishing workflow**: GitHub Pages / Cloudflare Pages等への公開ワークフロー（Non-goals、別PRで検討）
8. **wiki-story-page-renderer**: `docs/architecture/07_Wiki/Story_Page_Design.md`で設計したStory pageの実装（Story page path helper・Story index→Story pageリンク・Episode一覧・Story/Episode Summary placeholder。詳細スコープは同文書§13参照）

各PRは小さく、`uv run pytest`の全通過と、実データを使わない自作fixtureによる検証を維持する（`Merged_Knowledge_Design.md` §13と同じ進め方）。

---

# 16. Non-goals

本設計書では以下を**スコープ外**とする。

- Wiki生成パイプラインの実装（Python。§15のPR群で別途行う）
- 実データ由来Wikiページ・生成Markdownのcommit
- MkDocs Materialの本格導入・サイト構築
- GitHub Pages / Cloudflare Pages設定
- Knowledge Graph生成（Neo4j投入処理。`docs/architecture/04_Knowledge_Graph/`は別文書群）
- LLM/provider/prompt実装、AI考察本文の生成
- canonical ID自動割り当て
- キャラクター辞書の推測confirmed化
- Parser大規模再設計
- Jinja2等テンプレートエンジンの依存追加可否の確定（§12.2の通り実装PRで判断）

---

# 17. 採用方針（サマリ）

- Wikiのsource of truthはmerged knowledge collectionであり、Wikiページは常に再生成可能な生成物として扱う（手編集しない）
- 公式情報・抽出情報（fact）・AI推定（inference）・manual overrideは、`sourceType`を軸に必ず分離して表示する
- evidenceRefsは要約と参照情報（evidenceId/episodeId/sceneId/blockId）のみを表示し、元セリフ全文は転載しない
- `canonicalId`が未確定（`status: unresolved`）のentityは通常ページを生成せず、Unresolved reportへ集約する。URLの安定性を`canonicalId`にのみ依存させる
- Phase 1（Top/Story index/Episode/Character/Unresolved report）→ Phase 2（Location/Organization/Item/Lore/Event/Relationship section/Timeline）→ Phase 3（AI analysis/Evidence index/Knowledge Graph view）の順で実装する
- テンプレート方式（Jinja2 / 自作builder）はこのPRでは確定せず、実装PRで判断する
- 実データ由来の生成物は当面commitしない。合成fixtureのサンプルのみ`docs/examples/`等に置く
