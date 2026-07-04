# Character Dictionary Review（キャラクター辞書 confirmed化ルール）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Character_Dictionary_Review.md`

---

# 1. 目的

`knowledge/dictionaries/characters.yaml`（人手管理のキャラクター辞書）の `status: confirmed` エントリを、安全に・段階的に増やすための運用ルールを定義する。

このドキュメントが解決する問題: 実データdry-runを重ねるほど「辞書に無い `sourceCharacterId`（unknown ID）」が見つかるが、これを機械的に・大量に `confirmed` 化すると、`docs/architecture/06_AI/Canonical_ID_Policy.md` §5 が禁止する「名前一致だけでの自動確定」「人間の確認を経ないcanonical ID付与」に抵触する。そのため、**confirmed化は常に人間のレビューを経由する**運用に固定する。

---

# 2. status の意味

| status | 意味 | `existingCharacterId` として解決されるか |
|---|---|---|
| `confirmed` | `characterId`（canonical ID、`CHAR_{ROMANIZED_NAME}`形式）を人間が確認・確定済み | される（`agents/parser/resolver.py` の `CharacterDictionary._id_map` に反映され、Extractor/Mergerで `status: merged` になる） |
| `name_only` | `displayName`（表示名）のみ判明しており、`characterId` は `null` のまま | **されない**（`_id_map` に反映されないため `existingCharacterId` は常に `None`。Merger側では `status: unresolved` のまま） |

`agents/parser/resolver.py` の `_resolve_character_id` は、`displayName` が分かっていれば（statusを問わず）`Speaker.is_resolved=True` にするが、これは「表示名が分かっている」ことを意味するに過ぎない。`speakerId`（→ `existingCharacterId`）は `characterId` が設定されている場合（= `status: confirmed`）のみ設定される。**「表示名の解決」と「canonical IDとしての確定（confirmed化）」は別物である**ことに常に注意する。

---

# 3. confirmed にしてよい条件

以下の**すべて**を満たす場合のみ、`status: confirmed` にしてよい。

1. 人間が実データ（該当 `sourceCharacterId` が使われている実際のスクリプト該当箇所）を直接確認し、キャラクター名・ローマ字表記を特定した
2. ローマ字表記が `docs/architecture/05_Parser/Identifier_Specification.md` §6.1（`CHAR_{ROMANIZED_NAME}`形式）に従って一意に決まる
3. 既存の `characterId` と重複しない（`agents/parser/character_dictionary.py` の `validate_character_dictionary` で機械的に検証可能）
4. 複数話・複数バッチで同一 `sourceCharacterId` が同一人物を指していることを確認した（単発の1話のみの観測では確定しない、`Canonical_ID_Policy.md` §5「単一エピソード内でしか観測されていない候補」に該当する場合は確定しない）

---

# 4. confirmed にしてはいけない条件

以下のいずれかに該当する場合、**絶対に** `status: confirmed` にしてはならない。

- **displayName（表示名）が他の確認済みキャラクターと一致する、というだけの理由**（同名の別人が存在しうる。`Canonical_ID_Policy.md` §5、`Merged_Knowledge_Design.md` §4.1原則2）
- AIが実データを読まずに、コマンド名や周辺の演出から**推測**しただけの場合（このリポジトリでのAI/Claudeによる推測confirmed化は禁止。人間が実データを確認したときのみ確定してよい）
- 出現回数が多いから、というだけの理由（頻出＝重要とは限らない。頻出はレビュー優先度を上げる材料に過ぎない）
- 一時的な変装・偽名・特殊演出用の別スロットである可能性が排除できない場合（`27: ブラックレイン`のような、既存confirmedキャラクターの別名義スロットに見えるエントリは、人間が別人格か同一人物の別名義かを明確に判断してから扱うこと）

---

# 5. sourceCharacterId / characterId / displayName の扱い

- `sourceCharacterId`: ゲームスクリプト上のキャラクター番号（文字列）。安定しているが、そのままでは canonical ID ではない。空にしない（`_validate_single_entry` が空を拒否する）
- `characterId`: `status: confirmed` の場合のみ設定する。`null` のまま（`status: name_only`）にできる。`CHAR_{ROMANIZED_NAME}` 形式（`CHARACTER_ID_PATTERN`）に従う
- `displayName`: 表示名。`status` を問わず必須（空文字は `validate_character_dictionary` がエラーにする）

---

# 6. aliases の扱い

`aliases` は `resolve_character_by_name` による名前検索の補助にのみ使う。**同一人物であることの確定根拠には使わない**（`resolve_character_by_name` 自体、自動解決パイプラインからは一切呼び出されない、`character_dictionary.py` docstring参照）。

- 同一エントリ内で `aliases` の値が重複していれば `validate_character_dictionary` がエラーにする
- 同じ `alias` 値が複数エントリで使われていれば `validate_character_dictionary` がエラーにする（`resolve_character_by_name` が最初に一致した方を返すため、重複があると常に片方だけが見つかる曖昧さが黙って発生する）

---

# 7. notes の扱い

`notes` は自由記述の任意フィールド。confirmed化の根拠（例: 「S01_C02にて実データ確認、他話でも同一キャラクターと確認」）を残す用途に使ってよいが、**実データの本文・セリフをそのまま書き写さない**（辞書ファイル自体はcommit対象のため、実スクリプト全文をここに転記するとNon-goals「実データ由来fixtureの追加」相当になる）。ローマ字表記の根拠や確認日など、短い要約にとどめる。

---

# 8. 実データ由来の未確認dumpをcommitしないルール

`scripts/check_character_dictionary_coverage.py --review-template-output <path>` が生成するテンプレートファイル・`docs/runbooks/Real_Data_Dry_Run.md` に従った dry-run 出力・`workspace/dry_runs/` 配下の出力は、**いずれもcommitしない**。

- `--review-template-output` の出力先は必ず `.gitignore` 済みの領域（`workspace/dry_runs/<timestamp>/` 等）を指定すること
- 出力ファイル自体に `sourceCharacterId` と出現回数以外の実データ内容（本文・セリフ）は含まれない設計だが（`build_review_candidates` 参照）、念のため `scripts/check_dry_run_inputs.py` でcommit対象外領域に置かれていることを確認すること
- PRやTASKS.mdに記録してよいのは、**確認済み（confirmed化した）エントリの `sourceCharacterId`/`characterId`/`displayName` の組**と、**未確認IDの件数サマリー**のみ。未確認ID一覧の生の値をそのままTASKS.mdやPR本文に貼り付けない（人数が多い場合は「n件のレビュー候補あり」で十分）

---

# 9. 人間確認済みmappingだけcommitするルール

`knowledge/dictionaries/characters.yaml` への変更は、以下のいずれかの場合のみ行う。

1. 人間がこのリポジトリの会話・Issue・別ファイル等で明示的に「この `sourceCharacterId` はこの `characterId`/`displayName` で確定（confirmed）」と提供したmapping
2. 既存テスト・fixtureの維持に必要な合成エントリ（`CHAR_TEST_*` 等）

AI（Claude等）が、coverage reportで見つけた頻出unknown IDを推測でconfirmed化することは、**このドキュメントが禁止する**。unknown IDはTASKS.mdの「確認候補」セクション、またはローカルのreview templateにのみ記録し、人間の確認を待つ。

---

# 10. 名前一致だけではresolvedにしないルール

`resolve_character_by_name` はdisplayName/aliasesの完全一致で辞書エントリを検索できるが、戻り値をそのまま `status: confirmed` や `existingCharacterId` に昇格させる自動処理を**作らない**。名前が一致した場合でも、必ず人間が「同一人物かどうか」を確認してから、手動で `characterId` を設定し `status: confirmed` に変更する。

---

# 11. dry-run後のcoverage report確認手順

```bash
# 基本のcoverage確認 (confirmed/name_only内訳・unknown上位を表示)
uv run python scripts/check_character_dictionary_coverage.py data/raw/dry_run/

# 未登録IDのレビュー用テンプレートをローカル(ignored領域)へ書き出す
uv run python scripts/check_character_dictionary_coverage.py data/raw/dry_run/ \
    --review-template-output workspace/dry_runs/20260704_000000/character_review_candidates.yaml
```

確認するフィールド:

- `confirmedObservedCount`/`confirmedCoveragePercentage`: 実際に `existingCharacterId` として解決される割合（Merger以降の`status: merged`に直結する指標）
- `nameOnlyObservedCount`/`nameOnlyCoveragePercentage`: 表示名は分かるが未確定のまま残っている割合
- `unknownCount`/`topUnknownIds`: 辞書に一切登録が無いID（レビュー候補）

出力されたreview templateは、`docs/templates/character_dictionary_review_template.yaml` の形式に沿って人間が1件ずつ埋め、確認が取れたエントリだけを `knowledge/dictionaries/characters.yaml` へ手動で反映する。テンプレートファイル自体はcommitしない（§8参照）。

---

# 12. 関連ドキュメント

- `docs/architecture/06_AI/Canonical_ID_Policy.md`（canonical ID全体の方針、confirmed化の上位ルール）
- `docs/architecture/05_Parser/Identifier_Specification.md` §6.1（`CHAR_{ROMANIZED_NAME}`形式、OD-001ローマ字表記ルール未確定事項）
- `docs/runbooks/Real_Data_Dry_Run.md`（実データdry-run全体の手順、実データ・生成物をcommitしないルール）
- `docs/templates/character_dictionary_review_template.yaml`（人間確認用テンプレートの見本、合成データのみ）
- `agents/parser/character_dictionary.py`（`load_character_dictionary`/`validate_character_dictionary`/`build_character_dictionary_coverage_report`/`build_review_candidates`の実装）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
