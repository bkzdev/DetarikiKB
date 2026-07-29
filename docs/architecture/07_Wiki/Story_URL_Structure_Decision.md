# Story URL Structure Decision（Story / Episode URL構造の決定）

Version: 1.0
Status: Accepted
Decision date: 2026-07-29
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

`Story_Page_Design.md` §10で比較したStory / Episode pageのflat構造・episodes subdirectory・nested構造について、現時点の正式方針と将来の再評価条件を決める。

本決定は`TASKS.md`の`story-manifest-public-id-nested-path`を解消する。URL/file pathの実装変更は行わず、既存の`agents/wiki_generator/paths.py`を正として運用を固定する。

---

# 2. 現状

現在のWiki rendererは以下のflat構造を生成する。

```text
stories/{publicStoryId or storyId}.md
stories/{publicEpisodeId or episodeId}.md
```

- `publicStoryId` / `publicEpisodeId`が空でなければ公開IDを優先し、無ければ内部`storyId` / `episodeId`へfallbackする
- Episode pathのlegacy入力互換は、`episodeId`も無い場合にrequiredな`documentId`を最終fallbackとする（`publicEpisodeId > episodeId > documentId`）
- Story pageとEpisode pageは同じ`stories/`直下に置く
- Story index、Story page内Episode一覧、Story/Episode SummaryのEvidence参照、Character page、Unresolved reportはこの構造を前提とした相対リンクを生成する
- Evidence pageはStory page配下へネストせず、`evidence/{publicStoryId or storyId}.md`に置く
- MkDocs Materialはlocal preview用途では利用しているが、長期公開基盤は未決定である

公開ID導入により、公開対象データで`publicStoryId` / `publicEpisodeId`を確定できれば、内部IDをURLへ出さないという目的はnested化なしでも達成できる。nested化が追加で解決する主な問題は、Story pageとEpisode pageのディレクトリ上の階層整理である。

---

# 3. 評価基準

次の観点で`Story_Page_Design.md` §10の3候補を再評価した。

1. 現在のlocal preview / rendererに対する閲覧上の利益
2. 相対リンク、path helper、テスト、既存生成物への変更範囲
3. MkDocs以外の将来公開基盤へ移行できるportableさ
4. 公開前後のURL migrationとredirect設計の必要性
5. 内部IDを公開URLへ出さないというpublic ID方針への寄与

---

# 4. 候補比較

## 候補A: flat構造を維持

```text
stories/{publicStoryId or storyId}.md
stories/{publicEpisodeId or episodeId}.md
```

- 現行実装と生成リンクを変更しない
- `publicStoryId` / `publicEpisodeId`により公開用IDへ切り替えられる
- Story / Episodeの階層はfile pathだけでは表現しないが、Story page内Episode一覧と表示タイトルで閲覧導線を確保できる
- 特定の静的サイト基盤のdirectory URL仕様に依存しない

## 候補B: Episodeだけをsubdirectoryへ移動

```text
stories/{publicStoryId or storyId}.md
stories/episodes/{publicEpisodeId or episodeId}.md
```

- Story / Episodeのpage種別はpathから判別しやすくなる
- Story単位のまとまりは表現できず、候補Cより情報構造上の利益が小さい
- Episodeへの全リンクを変更する必要があり、移行コストに対する利益が限定的である

## 候補C: Story単位のnested構造へ移動

```text
stories/{publicStoryId or storyId}/index.md
stories/{publicStoryId or storyId}/{publicEpisodeId or episodeId}.md
```

- Story単位の階層をfile pathでも表現でき、長期的な情報構造としては3候補中で最も自然である
- 現行の`episode_page_path(source_document)`だけでは親Story pathを明示的に扱えず、path helper APIの見直しが必要になる
- renderer内の「同じ`stories/`階層なのでfilenameだけを使う」という相対リンク前提を変更する必要がある
- MkDocsのdirectory URL、別の静的サイト基盤、redirect/legacy URL方針を決める前に実装すると、公開基盤決定時に再移行する可能性がある
- 公開IDによる内部ID非露出は候補Aでも達成できるため、nested化だけを急ぐ安全上の理由はない

---

# 5. 決定

**現時点の正式構造として候補A（flat構造）を維持する。候補Bは採用せず、候補Cは再評価ゲートを満たした場合の長期候補としてのみ残す。**

具体的な契約は以下の通り。

- Story page: `stories/{publicStoryId or storyId}.md`
- Episode page（通常）: `stories/{publicEpisodeId or episodeId}.md`
- Episode page（legacy fallback）: `episodeId`が無い場合は`stories/{documentId}.md`
- Evidence page: `evidence/{publicStoryId or storyId}.md`（Story配下へ移動しない）
- 公開IDが無い場合の内部ID fallbackはlocal preview / internal buildの後方互換として維持する
- 公開workflowでは、公開対象Story/Episodeのpublic ID completenessを検証し、内部ID fallbackへ依存しないことを別途保証する
- `agents/wiki_generator/paths.py` / `renderer.py`、schema、ID生成規則は本決定PRでは変更しない

候補Cは「次に実装する予定」ではない。公開基盤とmigration要件が確定するまでは、flat構造がcanonicalな生成契約である。

この決定が扱う「内部ID fallback」はURL/file pathに限る。Story / Episode page本文やfront matterのpublic-safe projection方針は変更せず、公開workflow設計で別途検証する。

---

# 6. 候補Cの再評価ゲート

候補Cへの移行検討は、少なくとも以下を満たしてから開始する。

1. `public-publishing-platform-evaluation`が完了し、採用する公開基盤とdirectory URL仕様が確定している
2. `public publishing workflow`の設計で公開URLの互換性・redirect可否・base URLが確定している
3. 公開対象Story/Episodeの`publicStoryId` / `publicEpisodeId` completenessを機械検証できる（`public-id-manifest-assignment-policy`の確定フローと接続する）
4. 既に公開済みのflat URLがある場合、redirectまたはlegacy URL mappingの保持方針が決まっている
5. nested化が閲覧性・運用性を改善する具体的な問題を、manual reviewまたは公開基盤PoCで再現できる

これらを満たしても自動的に候補Cへ移行しない。候補Aとの比較を更新し、breaking URL changeとして独立PRで再決定する。

---

# 7. 将来migration PRの受入条件

再評価の結果、候補Cを採用する場合は以下を同一migration計画で扱う。

- Story contextを明示的に扱うpath helper APIと、page間の相対リンクhelper
- Story index → Story page → Episode page → Evidence / Character / Unresolved reportの全リンク
- `publicStoryId` / `publicEpisodeId`あり・なし・空文字列時、およびEpisodeの`documentId`最終fallback
- Story/Episode filename衝突と出力path重複の検出
- Summary evidenceRefsとEvidence page anchorの無回帰
- flat URLからnested URLへのredirectまたはlegacy mapping
- MkDocs strict buildと採用公開基盤でのlink check
- 合成fixtureによるpath単体テスト、全page setの統合テスト、通常幅・狭幅のmanual review

---

# 8. Non-goals

- `agents/wiki_generator/paths.py` / `renderer.py`の変更
- Story / Episode / Evidence pageの移動
- `storyId` / `episodeId` / public IDの形式・採番・割当変更
- 実データmanifest、Evidence Index、Summary、生成Wikiの追加・更新
- 公開基盤の選定
- public publishing workflowやredirectの実装
- Story / Episode page本文・front matterのpublic-safe projection
