# Story ID Policy Decision（Story ID / Episode ID / URL path方針決定）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/05_Parser/Story_ID_Policy_Decision.md`

---

# 1. 目的

本文書は、`docs/architecture/05_Parser/Story_ID_Policy_Review.md`（PR #70 `story-id-policy-real-sample-review`）で行った実データ小規模サンプルレビューをもとに、DKBが採用する`storyId`/`episodeId`/URL path方針を正式に決定する。

**本PRでは`storyId`/`episodeId`生成ロジックを変更しない。schema変更も原則行わない。URL/file pathも変更しない。** 今回決めるのは「どの方針で進めるか」という設計判断であり、実装は次PR（`story-manifest-public-id-fields-design`、§10）以降で行う。

---

# 2. Decision summary

- `storyId`/`episodeId`の生成ロジック・既存URL/file pathは**当面維持する**（このPRでも次PRでも変更しない）
- 将来の公開Wiki URL用に、`story_manifest.yaml`側へ**`publicStoryId`/`publicEpisodeId`**という任意フィールドを分離して持てる設計へ進むことを決定する（フィールド名の採用候補、§7）
- `sourceKey`/`rawPath`/`sourceFileName`は引き続きraw trace用として`story_manifest.yaml`に保持する（変更なし）
- MAINは現行`MAIN_Sxx_Cxx_Exx`方針を維持し、public ID分離の優先度はEVENT/RAIDより低い
- migrationはadditive firstとする。既存storyId/episodeIdへの破壊的変更・既存fixtureの大量書き換え・renderer/paths.pyの切替は行わない
- title/subtitle由来のURL生成は、今回も将来も採用しない（§8）
- 次PR`story-manifest-public-id-fields-design`のスコープを明確化する（§10）

---

# 3. Background

`Story_ID_Policy_Review.md`（PR #70）は、EVENT実データ小規模サンプル（5件相当）と他カテゴリのファイル名観察（6件）をもとに、現行`EVT_{sourceKey}`方式の長所・短所を整理し、4つのID案（現行維持/date+sequence/manifest-assigned stable ID/category-specific policy）を評価軸付きで比較した。結論は「今すぐ全面移行しない」「raw traceability用IDと公開URL用IDの分離を次PRで設計する」という段階的アプローチであり、次PR候補として`story-id-policy-design-decision`（本PR）と`story-manifest-public-id-fields-design`が挙がっていた。

本PRは、その比較結果を受けて実際にDKBとして採用する方針を確定する設計PRである。

---

# 4. Inputs from PR #70

`Story_ID_Policy_Review.md`の結論を以下に短く整理する。

## 4.1 現行ID方針の長所

- sourceKeyとの対応が明確で、raw fileとの追跡がしやすい（raw traceability ◎）
- eventNumberが無くても機械的に生成できる（採番管理不要）
- 既存実装と完全互換、追加実装コスト無し、migrationコスト無し

## 4.2 現行ID方針の短所

- 公開URLとして長くなりやすい（観察サンプルで36〜39文字）
- raw配置由来のslug（ゲーム運営側の内部事情）がそのまま公開URLに出る
- sourceKey変更（ゲーム側の再配布・命名変更）への耐性が無い
- 同日複数イベントでのcollisionリスクを理論上排除できない
- MAIN/RAID/OTHER/CHARACTERへの拡張性が不明（カテゴリごとにraw配置規約が異なる可能性、§4.2観察）

## 4.3 public URLとinternal source trace IDを兼ねる問題

現行方針では`storyId`/`episodeId`が「(1) raw fileへのtraceability」「(2) Wiki公開URL」「(3) merged knowledge collection内の内部参照キー」の3役を兼ねている。これが問題の根本原因であり、3つの役割を無理に1つのIDへ統合し続けると、どの要求（安定性・可読性・短さ・traceability）を優先しても他が犠牲になる。

## 4.4 MAIN/EVENT/RAID/OTHER/CHARACTERごとの現状

| カテゴリ | 仕様 | 実装状況 |
|---|---|---|
| MAIN | `MAIN_Sxx_Cxx_Exx` | 手動指定のみ、意味のある構造を既に持つ |
| EVENT | `EVT_{eventNumber}`（仕様）と`EVT_{sourceKey}`（実装）が併存 | `EVT_{sourceKey}`実装済み、raw配置由来の長いslug問題を抱える |
| RAID | `RAID_{raidNumber}` | 未実装、raw配置規約も未確認 |
| OTHER | `OTHER_{number}` | 未実装 |
| CHARACTER | `CHAR_MAIN`/`CHAR_EXTRA`/`CHAR_DATE`+characterId | 未実装、raw配置からのprefix判定方法も未確認 |

## 4.5 EVENT実データサンプルで見えた問題

sourceKeyは概ね17〜20文字（`{YYMMDD}_{slug}`形式）、URLは36〜39文字。folder/file一致チェックは今回のサンプルでは全件通過し、sourceKey collisionも観測されなかったが、母集団全体を代表するものではない。`data/raw/dry_run/`のファイル名観察では、MAIN相当は`-main{N}`、CHARACTER相当は`charastory_{key}`、現行7分類に対応しない`surprise_{key}`も観測されており、raw category語彙が現行の設計ドキュメントが想定する7分類より多い可能性が具体的に示された。

## 4.6 `sourceKey`の扱い

`sourceKey`はDKB正規ID（storyId）の材料であり、それ自体はタイトルではない。raw配置（ディレクトリ名・ファイル名）から機械的かつ安定して抽出できる値として、いずれのID案を採用する場合でも`story_manifest.yaml`側に保持し続ける。

## 4.7 URL安定性

`Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」という安定性原則に対し、現行`EVT_{sourceKey}`方式はsourceKeyそのものがIDの一部であるため、ゲーム側のraw配置命名変更に弱い（安定性原則に反するリスクがある）。

## 4.8 migration cost

現行維持（案A）はmigrationコストが最小（◎）。date+sequence（案B）は既存storyId変更が必要（△）、manifest-assigned（案C）は全件再割当が必要（×）、category-specific（案D）はカテゴリ数だけhelper/test/schemaが増え最大のコストになる（×）。

## 4.9 open questions（PR #70から持ち越し）

- 実際に同日複数イベントは発生するか（母集団確認が必要）
- sourceKeyの命名は運営側でどれだけ安定しているか
- MAIN/RAID/OTHER/CHARACTERの正式なraw配置規約
- 「surprise」等、現行7分類に含まれないraw category語彙をどう扱うか
- 公開Wiki化の優先度・時期
- `publicStoryId`等の分離設計を採用する場合、Wiki renderer側の参照ロジックをどこまで変更する必要があるか

これらはPR #70時点で未解消であり、本PRでも一部（public ID field naming）を除き引き続きopenのままとする（§12）。

---

# 5. Adopted policy（採用方針）

## 5.1 結論

- `storyId`/`episodeId`は**当面既存互換を維持する**。生成ロジックは変更しない
- 将来の公開Wiki URL用に、`publicStoryId`/`publicEpisodeId`相当のIDを`story_manifest.yaml`側に**分離して持てる設計**へ進む（実装は次PR）
- `sourceKey`/`rawPath`/`sourceFileName`はraw trace用として引き続き保持する
- 公開URL/Wiki filenameは将来的にpublic IDを使う余地を作るが、いきなり既存storyId/episodeIdを破壊的変更しない
- 次PRで`story_manifest`にpublic ID系フィールドの設計を行う
- renderer（`agents/wiki_generator/renderer.py`）やpaths.py（`agents/wiki_generator/paths.py`）の切替はさらに後続PRに回す

この方針は、PR #70の「今すぐ全面移行しない」「raw traceability用IDと公開URL用IDの分離を次PRで設計する」という推奨と矛盾しない。§9のPR #70の3役分離提案（raw traceability / Wiki公開URL / 内部参照キー）をそのまま踏襲し、(1)と(3)は現行`storyId`/`episodeId`が引き続き担い、(2)のみを将来`publicStoryId`/`publicEpisodeId`として分離する。

## 5.2 短期（このPR）

- 現行ID生成を維持する（実装変更なし）
- 既存URL/file pathを維持する（変更なし）
- docs上でpublic ID分離方針を正式決定する（本文書）

## 5.3 中期（次PR以降）

- `story_manifest`にpublic ID系フィールドを追加設計する（`story-manifest-public-id-fields-design`）
- `publicStoryId`/`publicEpisodeId`の命名を決める（§7で決定）
- raw trace用`sourceKey`と公開用IDを分離する

## 5.4 長期

- Wiki renderer/paths.pyがpublic IDを使えるようにする
- ただしmigrationと外部リンク安定性を考慮して段階移行する
- 公開前ならURL変更可能、公開後は互換redirect等を検討する（`public-publishing-platform-evaluation`と合わせて判断）

---

# 6. Category-specific policy（category別方針）

## 6.1 MAIN

- 現行方針`MAIN_Sxx_Cxx_Exx`を維持する方向
- raw sourceKey直出しではなく、人間に意味がある構造化ID
- public ID分離の対象にはなるが、優先度はEVENT/RAIDより低い（現行IDが既に短く意味を持つため）

## 6.2 EVENT

- 現行`EVT_{sourceKey}`はraw traceには便利だが、公開URLとしてはsourceKey露出が気になる
- public ID分離の**優先対象**
- 将来的には`EVT_YYYYMMDD_001`、またはmanifest-assigned stable IDを検討する
- 最終決定はpublic ID field設計時（次PR）に行う

## 6.3 RAID

- EVENTに近い扱い。EVENTと同様にpublic ID分離対象
- `RAID_YYYYMMDD_001`などの可能性を検討する（RAID自体のraw配置規約はまだ未確認、`Story_Manifest_Design.md` §18 OD-002）

## 6.4 OTHER

- raw categoryが多様になりやすいため、sourceKey依存だけにしない
- manifest-assigned stable IDとの相性がよい可能性がある

## 6.5 CHARACTER

- `characterId`/`sourceCharacterId`との関係を慎重に扱う
- `CHARSTORY_{characterId}_E01`のような方針候補を残す
- ただし`characterId`confirmed前の扱いは要検討（`AI_CONTEXT.md` §3.6 name_only/confirmed区別を踏襲する）

## 6.6 SURPRISE / 未分類

- PR #70で現行7分類にないraw category語彙（`surprise_{key}`等）が観測された
- すぐID設計を広げず、manifest上で`category`/`collection`/`type`を明示する方針を検討する
- public ID設計で拡張可能にする（次PRのスコープ、確定はしない）

---

# 7. Public ID field naming decision（public ID系フィールド名の決定）

## 7.1 候補比較

| 候補 | フィールド名 | 長所 | 短所 |
|---|---|---|---|
| 候補A | `publicStoryId` / `publicEpisodeId` | 公開URL用途だと分かりやすい、raw/internal IDとの役割分離が明確 | 公開しない用途では少し限定的 |
| 候補B | `stableStoryId` / `stableEpisodeId` | 長期安定IDであることが分かりやすい、URL以外にも使いやすい | 現行storyIdもstableに見えるため意味が曖昧になりやすい |
| 候補C | `canonicalStoryId` / `canonicalEpisodeId` | canonicalという意味は強い | character canonicalIdと意味が衝突しやすい、raw storyIdとの関係が分かりにくい |
| 候補D | `wikiStoryId` / `wikiEpisodeId` | Wiki出力用と分かりやすい | 将来Wiki以外の出力にも使いにくい |

## 7.2 採用候補

**`publicStoryId` / `publicEpisodeId`（候補A）を採用する。**

理由:

- PR #70 §9が整理した「(1) raw traceability」「(2) Wiki公開URL」「(3) 内部参照キー」の3役のうち、分離したいのは(2)であり、`public`という語がその用途を最も明確に表す
- `canonicalStoryId`はキャラクターの`canonicalId`（`Canonical_ID_Policy.md`）と語彙が衝突し、「人間確認済みの安定ID全般」という別の意味と混同されるリスクが高い
- `stableStoryId`は既存`storyId`自体も安定性原則（`Identifier_Specification.md` §2.1）に従うため、「何がより安定か」が伝わりにくい
- `wikiStoryId`はWiki以外の公開先（将来の別プラットフォーム等）を想定すると限定的すぎる

この採用候補は次PR（`story-manifest-public-id-fields-design`）での最終決定・schema実装に先立つ設計判断であり、次PR側で追加の懸念が見つかった場合は再検討してよい。

---

# 8. Non-adopted options（採用しない案と理由）

以下は**現時点では採用しない**。

| 案 | 理由 |
|---|---|
| 現行sourceKey IDへの全面固定（public ID分離をしない） | PR #70で明らかになった「公開URLとしての長さ・slug露出・sourceKey変更への弱さ」を放置することになり、公開Wiki化前に解決すべき課題を先送りするだけになる |
| 即時の`EVT_YYYYMMDD_001`移行 | 採番ルール（同日複数イベントの順序決定）が未確定であり、実データサンプルが少ない現時点で決め打ちするとmigrationをやり直すリスクが高い |
| 即時のmanifest-assigned numeric ID移行 | ID割当を人間または別の採番システムが管理する必要があり、初期投入コスト・人間レビュー負荷が高い。実データ母集団の確認前に導入する理由が薄い |
| 既存storyId/episodeIdの破壊的変更 | `Identifier_Specification.md` §2.1「一度割り当てたIDは原則として変更しない」という安定性原則に反する。既存fixture・既存参照との整合性コストも大きい |
| URL/file pathの即時変更 | rendererとpaths.pyの変更が必要になり、本PRのスコープ（設計決定のみ）を超える。次PR以降の段階移行で対応する |
| 実データに基づく手動ID大量投入 | 実データや生成物をcommitしない方針（`AI_CONTEXT.md` §3.11）に反し、本PRの目的（方針決定）から外れる |
| title/subtitle由来のURL生成 | 下記§8.1で詳述する理由により、今回も将来も採用しない |

## 8.1 title/subtitle由来URLを避ける理由

- タイトル修正でURLが変わってしまう（`Identifier_Specification.md` §2.4「タイトルをIDに含めない」の原則に反する）
- 公式表記変更に弱い
- 日本語URL・表記揺れ・長文化の問題がある
- DKBのevidence-first方針（IDは安定したraw trace由来の値から機械的に導出する）と合わない

---

# 9. Migration strategy（migration方針）

- 既存storyId/episodeIdは当面維持する
- public IDは追加フィールドとして導入する（既存フィールドの置き換えではない）
- public IDが無い場合は現行episodeIdへfallbackする
- renderer/paths切替は後続PRで行う
- 公開前であればURL変更は許容可能、公開後はURL変更に慎重になる
- 将来必要ならredirect mappingやlegacy ID mappingを検討する

**migration is additive first: このPRではbreaking changeを一切行わない。** 既存の生成URLはrenderer/paths切替が行われるまで変更されない。`sourceKey`は引き続きraw traceability用として利用可能なまま保持される。

まとめると以下の3点に集約される。

1. migration is additive first
2. no breaking change in this PR
3. generated URLs remain unchanged until renderer/paths switch
4. sourceKey remains available for traceability

---

# 10. Implementation phases / 次PRのスコープ

## 10.1 次PR: `story-manifest-public-id-fields-design`

次PRで実装候補とすること:

- `story_manifest`schema（`schemas/story_manifest.schema.json`）に`publicStoryId`/`publicEpisodeId`系フィールドを追加設計する
- field names（§7.2の`publicStoryId`/`publicEpisodeId`）を最終確定する
- validation方針を決める（null許容か、パターン制約をどうするか等）
- EVENT/RAID/MAIN/OTHER/CHARACTERのpublic ID例を書く
- public ID未設定時のfallback方針を書く（現行episodeIdへfallback）
- raw trace fields（`sourceKey`/`rawPath`/`sourceFileName`）との関係を書く
- renderer/paths切替はまだ行わない可能性がある（次PRのスコープに含めるかは着手時に判断）

## 10.2 次PRで行わないこと（次PR側のNon-goalsの参考）

- `agents/wiki_generator/renderer.py`/`agents/wiki_generator/paths.py`の実際の切替
- 既存storyId/episodeIdの生成ロジック変更
- 既存fixtureのID書き換え

## 10.3 実装状況（`feature/story-manifest-public-id-fields-design`で実施）

§7.2で採用した`publicStoryId`/`publicEpisodeId`を`schemas/story_manifest.schema.json`（story-level/episode-levelの任意フィールド、既存`storyId`/`episodeId`と同じ`^[A-Z][A-Z0-9_]*$`パターン、null許容）・`agents/parser/story_manifest.py`（`StoryManifestStory.public_story_id`/`StoryManifestEpisode.public_episode_id`）へ追加した。`scripts/normalize_story.py`は`source.manifest.publicStoryId`/`source.manifest.publicEpisodeId`としてtraceability目的でのみNormalized Story JSONへ転記する。**`storyId`/`episodeId`生成ロジック・URL/file path・`agents/wiki_generator/renderer.py`/`paths.py`は変更していない。** category別の合成例は`Story_Manifest_Design.md` §13.2を参照。

## 10.4 実装状況（`feature/story-manifest-public-id-renderer-switch`で実施）

§5.4「長期」で述べたrenderer/paths.py段階移行の第一段階として、`publicEpisodeId`をWiki Episode pageのfilename/URL/Story indexリンク先へ実際に反映した。`metadata.publicStoryId`/`episodes[].metadata.publicEpisodeId`経由でExtractor（`episode_extraction.publicStoryId`/`publicEpisodeId`）→Merger（`sourceDocuments[].publicStoryId`/`publicEpisodeId`）へ伝播し、`agents/wiki_generator/paths.py`の`episode_page_path`が`publicEpisodeId`（空文字列・whitespaceのみは無視）を優先、無ければ既存`episodeId`へfallbackする。Episode page SummaryにはEpisode ID/Story ID（内部ID）とPublic Episode ID/Public Story ID（未設定時「未登録」）を並記する。**`storyId`/`episodeId`生成ロジック・Story manifest candidate builder・Character page pathは変更していない。** public IDの自動割当も行っていない（人間が`story_manifest.yaml`へ個別に設定する運用のまま）。

---

# 11. Impacted files for future PRs

将来public ID分離を実装する際に影響する見込みのファイル（本PRでは変更しない、確認のみ）。

- `schemas/story_manifest.schema.json`（`publicStoryId`/`publicEpisodeId`フィールド追加）
- `agents/parser/story_manifest.py`（manifest読み込み・`StoryManifest`/`StoryManifestEntry`データ構造）
- `agents/parser/story_manifest_candidates.py`（storyId/episodeId生成ロジック。public ID自体は生成しない想定だが、候補データ構造に影響しうる）
- `agents/wiki_generator/paths.py`（`episode_page_path`が返すファイル名。public ID採用時のみ変更対象）
- `agents/wiki_generator/renderer.py`（Story index/Episode pageのURL・リンクテキスト生成）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（schema説明の追記）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §14（URL/slug方針の追記）

---

# 12. Open Questions

PR #70から持ち越し、または本PRで新たに生じたもの。

- 実際に同日複数イベントは発生するか（母集団確認が必要、EVENT/RAID採番方針の判断材料）
- sourceKeyの命名は運営側でどれだけ安定しているか
- MAIN/RAID/OTHER/CHARACTERの正式なraw配置規約（`Story_Manifest_Design.md` §18 OD-002/OD-003、未解消）
- 「surprise」等、現行7分類に含まれないraw category語彙をどう扱うか
- 公開Wiki化の優先度・時期（`public-publishing-platform-evaluation`との関係）
- `publicStoryId`/`publicEpisodeId`を採用する場合、Wiki renderer側の参照ロジックをどこまで変更する必要があるか（次PRで具体化）
- public ID未設定時のfallback表示と、`displayTitle > episodeSubtitle > storyTitle > episodeId`という既存のtitle fallback優先順位（`AI_CONTEXT.md` §3.8）との関係整理

---

# 13. Non-goals（このPRで実装しないこと）

- `storyId`/`episodeId`生成ロジックの変更
- schema変更（`schemas/story_manifest.schema.json`等）
- URL/file pathの変更
- `publicStoryId`/`publicEpisodeId`フィールドの実装
- stable ID migration scriptの作成
- 既存fixtureのID大量変更
- `agents/parser/story_manifest.py` / `agents/parser/story_manifest_candidates.py`の変更
- `agents/parser/normalizer.py`（Story normalizer）の変更
- `agents/wiki_generator/renderer.py` / `agents/wiki_generator/paths.py`の変更
- story title/subtitleの実import、実タイトル・実サブタイトルの投入
- 実DEC・実manifest・実Normalized Story JSON・実extraction/merged collection・実Wiki Markdownのcommit
- workspace出力・raw HTMLのcommit
- Jinja2導入、MkDocsテーマ移行、public publishing設定、GitHub Pages/Cloudflare Pages設定
- Knowledge Graph生成、LLM/provider/prompt実装
- Parser大規模再設計、Docker/devcontainer整備

---

# 14. 参照

- `docs/architecture/05_Parser/Story_ID_Policy_Review.md`（本文書の入力となった比較レビュー、PR #70）
- `docs/architecture/05_Parser/Story_Manifest_Design.md`（`story_manifest.yaml`の既存設計、OD-001）
- `docs/architecture/05_Parser/Identifier_Specification.md`（既存Story ID/Episode ID形式の定義、§2.1安定性原則、§2.4タイトル非包含原則、OD-002）
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §14（URL/slug方針）
- `agents/parser/story_manifest_candidates.py`（現行のEVENT ID生成実装）
- `agents/parser/story_manifest.py`（manifest読み込み実装）
- `agents/wiki_generator/paths.py`（Episode page URLの組み立て）
- `schemas/story_manifest.schema.json`（現行schema、次PRでの拡張対象）
- `TASKS.md`（次PR候補の追跡）
