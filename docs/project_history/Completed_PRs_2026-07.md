# Completed PRs — 2026-07 時点

`AI_CONTEXT.md`・`TASKS.md`から移した完了済み作業の履歴。各PRの詳細な作業ログ・テスト件数・diff statは省略し、「何を達成したか」中心に1〜3行で記録する。実イベント名・実キャラ名・実タイトル・実セリフ・実ファイル名は含まない（元のTASKS.mdも既に匿名化済み）。

各Phaseの設計判断そのもの（マージ4原則、canonical ID方針等）は`docs/architecture/`配下の設計書が正であり、ここでは繰り返さない。

---

## Parser / Normalization

- **Parser Phase 1**: `agents/parser/`一式（tokenizer/resolver/parser/normalizer/exporter）・`schemas/story.schema.json`・compatibility checker・テストを実装。会話/ナレーション/分岐/話者解決のPhase 1 Mustすべてに対応。
- **script command coverage improvement**: real data dry-run trialで判明した演出コマンド未対応（unknown率58〜69%）を、`config/script_commands.yaml`・`tokenizer.py`・`parser.py`へ37コマンド追加して解消（unknown率0〜0.1%）。
- **character dictionary coverage improvement**: `knowledge/dictionaries/characters.yaml`を新設し、Parser/Mergerがcanonical ID解決に使える構造化辞書を整備（confirmed 2件で開始）。merge後全entityがunresolvedのままだった根本原因を特定・解消。
- **compatibility check consistency**: standalone実行と`normalize_story.py --check-compat`埋め込みの判定ロジックを`agents/parser/compatibility.py`へ共有化し、両経路の判定結果を一致させた。
- **branch / choice included dry-run**（PR #33）: 選択肢/分岐を含む実データで、Parserの重大なブロック配置バグ3件と省略記号のみの本文行が欠落するtokenizerバグ1件を発見・修正。
- **script command coverage followup**: branch/choice dry-runで見つかった未登録コマンド7種を既存stage_directionカテゴリへ分類。
- **story manifest design**（PR #56）: raw DEC配置とDKB正規ID体系を分離する`story_manifest.yaml`/schemaを設計。title/subtitleはDEC本文から自動推測しない方針を確立。
- **normalize_story manifest integration**（PR #57）: `normalize_story.py`に`--manifest`/`--raw-root`/`--manifest-strict`を追加し、manifest経由でstoryId/episodeId/title/subtitleを解決できるようにした。未指定時の既存挙動は完全維持。
- **story title/subtitle import design**（PR #58）: manifestスキーマに`titleSource`/`subtitleSource`を追加し、CSV由来candidate→人間レビュー→manifest反映という運用フローを設計。

## Extraction / Merge

- **Extraction Pipeline / Result Schema設計**: `docs/architecture/06_AI/Extraction_Pipeline.md`・`Extraction_Result_Schema.md`・`schemas/extraction.schema.json`を整備（PR #4）。
- **Extractor skeleton〜Stage A統合**（PR #5〜#13）: `agents/extractor/`にsemantic validation、8種Candidate（Character/Location/Organization/Item/Lore/Event/Relationship/Timeline）のrule-based最小抽出を実装。すべて構造的な手がかりのみを対象とし、本文の自然文推定は行わない。Stage A統合レビューで全種の整合性を横断確認。
- **Stage B設計〜Merge engine実装**（PR #14〜#22）: `Merged_Knowledge_Design.md`設計、`schemas/merged_knowledge.schema.json`・`merged_knowledge_collection.schema.json`、`agents/merger/`によるMerge engine（複数入力対応）、8種entity全ての最小merge（Character/Location/Organization/Item/Lore/Event/Relationship/Timeline）を実装。構造化IDありのみ自動merge、名前一致だけでは統合しない方針を徹底。
- **manual override loader**: `agents/merger/overrides.py`で人間が明示した補正レイヤーを後から重ねて適用する仕組みを実装（`set_field`/`add_alias`/`remove_alias`のみ対応）。
- **merge report強化**: `MergeReport`にtype別・入力別の内訳（`unresolvedEntityCounts`/`conflictCounts`/`warningCounts`/`entityTypeSummaries`/`inputSummaries`）を追加。
- **relationshipType taxonomy**: 暫定taxonomy16種を導入し表記ゆれを正規化。ただし本確定はせず、未知typeも破棄しない。
- **canonical ID policy**: `docs/architecture/06_AI/Canonical_ID_Policy.md`を新設し、`id`/`canonicalId`/`sourceCandidates`の違いと自動付与してよい条件を明文化。既存entityへの自動付与は行わず。
- **real data dry-run procedure**: `docs/runbooks/Real_Data_Dry_Run.md`を新設し、実データでのParser→Extractor→Merger→Report確認手順を整備。
- **no invisible unicode check**: `scripts/check_invisible_unicode.py`を新設し、bidi override等の危険な不可視文字のみを検出（日本語・全角記号は対象外）。
- **real data dry-run trial**: 実データ2話でParser→Extractor→Merger→Reportを試験実行。cp932コンソールでのクラッシュバグを発見・修正し、演出コマンド/キャラクター辞書のカバレッジ不足という2つの既知課題を特定。
- **real data merged collection dry-run**（PR #45）: 実データ8話でExtractor→Merger→Wiki render handoffまで完走を確認。キャラクター辞書のID帯不足により大半のキャラクターがunresolvedのまま、relationshipsは実データに構造化タグが無いため0件という既知の制約を確認。

## Character Dictionary / Profiles

- **character dictionary confirmed review workflow**: confirmed化してよい条件・いけない条件を明文化したrunbookとレビュー用テンプレートを整備。AI推測によるconfirmed追加は禁止。
- **character dictionary reference JSON import batch 001**: レガシー`characters_reference.json`との差分が0件（既に完全移行済み）であることを確認。今後のbatch用比較スクリプトを整備。
- **character dictionary confirmed batch 002**: 人間確認済みmappingが未提供だったため辞書は無変更のまま据え置き。
- **character dictionary review packet**: 未解決キャラクターの人間レビュー用YAML/CSV packet生成の仕組みを整備。
- **character dictionary confirmed batch 003**: レビュー済みpacketに基づき人間確認済み12件をconfirmed化（confirmed 2→14件）。実データ再dry-runでcanonicalId解決を確認。
- **character profile schema design**: ID解決用`characters.yaml`とは別に、公式プロフィール情報を管理する`character_profiles.yaml`/schema/validatorを新設。confirmed済みcharacterIdにのみ紐づく設計。
- **character profile wiki import pipeline**（PR #51）: Wikiメンバー一覧テーブルのスクレイピング→照合の仕組みを構築。displayName完全一致のみ自動match、それ以外はunmatchedとして人間確認へ。
- **character profile wiki url discovery**: 正しいメンバー一覧テーブルURLを特定し、matched 6件/unmatched 200件のcandidate生成に成功。
- **character profile import batch 001**（PR #53）: matched 6件のみを`character_profiles.yaml`へ人間確認済みとして投入。unmatched 200件は未投入。
- **character profile renderer section**: `render_wiki.py`に任意`--character-profiles`引数を追加し、Character pageに「基本プロフィール」sectionを実装（未指定時は既存出力を完全維持）。

## Wiki / MkDocs

- **wiki output design**: merged knowledge collectionからのWikiページ構成をPhase 1〜3に分けて設計（renderer実装は別PR）。
- **wiki renderer skeleton**（PR #40）: `agents/wiki_generator/`にTop/Story index/Episode/Character/Unresolved reportの最小rendererを実装。canonicalId確定+status:mergedのentityのみ個別ページ化。
- **character page renderer expansion**: Aliases・Source Candidates summary・Conflicts表示を追加。
- **episode page renderer expansion**: Candidate Counts表・Related Characters summary・Validationセクションを追加。
- **unresolved report renderer refinement**: Overview/Conflict Summary/Warning Summary/Canonical ID Summary/Relationship Type Summaryを追加。
- **real data wiki render dry-run**: 実データmerged collectionが無かったため合成縮退collectionで代替検証。warning未truncateバグを発見・修正。
- **MkDocs Material minimal site**（PR #55）: ローカルpreview専用の最小`mkdocs.yml`/`docs/site_preview/`を整備。story indexのepisodeリンク二重prefixバグを発見・修正。
- **mkdocs local preview dry-run**（PR #59）: render→MkDocs preview運用手順・目視確認チェックリスト・結果テンプレートを整備。Episode pageのSource Pathがローカル絶対パスを露出しうるバグを発見・修正。
- **mkdocs local preview real sample trial**（PR #60）: 実データ小規模サンプルでmanifest候補生成→normalize→extract→merge→render→`mkdocs build --strict`まで警告0件で完走。ブラウザでの実目視確認はツール制約で持ち越し。

## Quality / CI / Refactor

- **ruff known issues cleanup**: C901複雑度6件中5件とE501/F841/E402を解消。`agents/parser/parser.py::_parse_tokens`（複雑度43）は大規模リファクタが必要なため意図的に据え置き。
- **GitHub Actions CI**: `.github/workflows/ci.yml`を新設し、pytest・不可視Unicode検査・dry-run入力安全確認・ruff format/checkをPR/main pushで自動実行。

---

## 参照

- Parser/Story Manifest設計の詳細: `docs/architecture/05_Parser/Story_Manifest_Design.md`
- Extraction/Merge設計の詳細: `docs/architecture/06_AI/Extraction_Pipeline.md`, `Merged_Knowledge_Design.md`, `Canonical_ID_Policy.md`
- Character Profile設計の詳細: `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`
- Wiki設計の詳細: `docs/architecture/07_Wiki/Wiki_Output_Design.md`
- 実データ運用手順: `docs/runbooks/Real_Data_Dry_Run.md`, `MkDocs_Local_Preview_Dry_Run.md`, `Story_Title_Subtitle_Import.md`
