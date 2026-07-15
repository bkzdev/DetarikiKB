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

# 12. review packet（confirmed-batch用の人間確認packet）

`scripts/check_character_dictionary_coverage.py --review-template-output`（§11）は、辞書に**一切登録が無い**（unknown）`sourceCharacterId`のみを、出現回数だけ添えて列挙する。実データdry-runがExtractor/Mergerまで進んだ後は、より情報量の多い`scripts/build_character_review_packet.py`を使うことを推奨する。

## 12.1 目的

`scripts/build_character_review_packet.py`は、merged knowledge collection（`schemas/merged_knowledge_collection.schema.json`準拠、`scripts/merge_extractions.py`の出力）から、**unknown（辞書未登録）とname_only（表示名のみ判明、未confirmed）の両方**を対象に、人間がconfirmed化を判断しやすいメタ情報（displayName・観測回数・登場エピソード数・登場ソースドキュメント数・辞書の既存状態）を付けたreview packetをYAML/CSVで書き出す。`status: confirmed`の辞書エントリに対応する（= 実運用では`status: merged`の）entityは、再レビュー不要のため自動的に除外される。

## 12.2 生成コマンド例

```bash
# YAML形式（notes等の手入力に向く）
uv run python scripts/build_character_review_packet.py \
    --merged-collection workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json \
    --output workspace/review_packets/character_dictionary_review_batch_003.yaml \
    --format yaml \
    --batch-id character-dictionary-review-batch-003

# CSV形式（表計算ソフトでの確認に向く）。両方欲しい場合は --format both
uv run python scripts/build_character_review_packet.py \
    --merged-collection workspace/dry_runs/<RUN_ID>/merged/merged_knowledge_collection.json \
    --output workspace/review_packets/character_dictionary_review_batch_003 \
    --format both
```

出力先は必ず`.gitignore`済みの`workspace/review_packets/`配下を指定すること（§14参照）。

## 12.3 packetの編集方法

生成されたpacketの各エントリには以下のフィールドがある。

| フィールド | 意味 | 編集してよいか |
|---|---|---|
| `sourceCharacterId`/`displayName`/`existingDictionaryStatus`/`existingCharacterId`/`aliases`/`observedCount`/`appearedEpisodeCount`/`sourceDocumentCount` | 自動生成された参照情報 | 編集不要（人間が実データを確認する際の手がかりとして使う） |
| `humanReviewStatus` | レビュー状態。§12.4参照 | 人間が確認結果に応じて変更する |
| `humanConfirmedCharacterId` | 確定した場合のcanonical ID（`CHAR_{ROMANIZED_NAME}`形式） | `humanReviewStatus: confirmed`の場合のみ埋める |
| `notes` | 確認の根拠（短い要約、実データ本文は書かない） | 自由記述 |

## 12.4 humanReviewStatusの値

| 値 | 意味 |
|---|---|
| `pending` | 未確認（デフォルト） |
| `confirmed` | 人間が実データを確認し、`humanConfirmedCharacterId`を確定した |
| `rejected` | 確認した結果、今回のバッチでは確定を見送る（別人物の可能性がある等） |
| `needs_more_context` | 追加の確認が必要（他話での再確認、既存confirmedキャラクターとの類似性排除等） |

`rejected`/`needs_more_context`のエントリはconfirmed-batchへ渡さず、次回以降のバッチで再検討する。

## 12.5 confirmed-batchへ渡す方法

`humanReviewStatus: confirmed`になったエントリだけを、`docs/templates/character_dictionary_confirmed_batch_input_template.yaml`と同じ構造の`workspace/local_inputs/character_confirmed_batch_XXX.yaml`（`.gitignore`対象）に切り出し、次のconfirmed-batch PRのセッションへ渡す。

```yaml
batchId: character-dictionary-confirmed-batch-003
confirmedMappings:
  - sourceCharacterId: "1000"
    characterId: "CHAR_EXAMPLE_CONFIRMED"
    displayName: "Example Character"
    aliases: []
    notes: "Human-confirmed from review packet batch 003."
```

## 12.6 commit禁止対象・AI推測禁止（再掲）

- `scripts/build_character_review_packet.py`が生成するpacket自体（YAML/CSVいずれも）は**commitしない**（`workspace/review_packets/`は`.gitignore`対象、§14参照）
- `workspace/local_inputs/character_confirmed_batch_*.yaml`も**commitしない**（実データ由来のdisplayName・確認メモを含みうるローカル入力のため）
- `docs/templates/`配下の見本ファイル（`character_dictionary_review_packet_template.yaml`・`character_dictionary_confirmed_batch_input_template.yaml`）は合成データのみで構成されており、これはcommitしてよい
- packetの`humanConfirmedCharacterId`は**必ず人間が実データを直接確認してから**埋める。AI（Claude等）がobservedCount・displayNameの一致だけを根拠に推測で埋めることは、本ドキュメント§3-4・§9のルールにより禁止する
- packetには元セリフ・実ストーリー本文・raw payload・merged collection全文を含めない（`build_character_review_packet`の実装で機械的に保証、§12.1参照）

## 12.7 未登録ID消費文脈調査由来のレビューパケット（2026-07-15）

`docs/architecture/01_Project/03_Scope.md` §5.2が扱ってきた「5〜6桁キャラクターID帯」の未決事項は、2026-07-15に`data/raw/`全量に対する消費文脈調査（同§5.2参照）が実施され、compatibility checkerが報告する890 distinct未登録IDのうち実際に話者スロットへ束縛される（真に未登録の話者である）ものは**7件のみ**であることが判明した。

この7件（speaker-bound 2件・mixed 5件）を対象に、`workspace/local_inputs/unregistered_speaker_id_review_packet.csv`（非commit、本節§12.6のcommit禁止対象と同じ扱い）を作成済みである。フィールドは`sourceCharacterId`/消費分類/出現カテゴリ/出現ファイル数・延べ数/`name`強制上書き（または`@ChTalkName`インライン引数）から実データより抽出した表示名候補/空のuser確認列で構成し、§12.3の`humanReviewStatus`と同じ運用（`pending`→人間確認後に`confirmed`/`rejected`/`needs_more_context`）に従う。

このパケットの人間確認が完了した後は、確認済みエントリを既存の`character-dictionary-confirmed-batch-005`（PR実績）に続く**confirmed batch 006相当**として、`knowledge/dictionaries/characters.yaml`へ登録する後続PRを起票する（§9「人間確認済みmappingだけcommitするルール」に従う）。残る867件の誤検出（話者に束縛されない`$numX`/`$valueX`代入）については、この辞書登録とは別に、checker側の消費文脈ベース判定への修正PRで解消する。

---

# 13. 関連ドキュメント

- `docs/architecture/01_Project/03_Scope.md` §5.2（5〜6桁キャラクターID帯の消費文脈調査結果、§12.7のレビューパケットの前提）
- `docs/architecture/06_AI/Canonical_ID_Policy.md`（canonical ID全体の方針、confirmed化の上位ルール）
- `docs/architecture/05_Parser/Identifier_Specification.md` §6.1（`CHAR_{ROMANIZED_NAME}`形式、OD-001ローマ字表記ルール未確定事項）
- `docs/runbooks/Real_Data_Dry_Run.md`（実データdry-run全体の手順、実データ・生成物をcommitしないルール）
- `docs/runbooks/Real_Data_Merged_Collection_Dry_Run.md`（Extractor→Merger dry-run手順、review packetの入力となるmerged collectionの生成元）
- `docs/templates/character_dictionary_review_template.yaml`（`check_character_dictionary_coverage.py --review-template-output`用テンプレートの見本、合成データのみ）
- `docs/templates/character_dictionary_review_packet_template.yaml`（`build_character_review_packet.py`用packetの見本、合成データのみ）
- `docs/templates/character_dictionary_confirmed_batch_input_template.yaml`（confirmed-batch PRへ渡す入力形式の見本、合成データのみ）
- `agents/parser/character_dictionary.py`（`load_character_dictionary`/`validate_character_dictionary`/`build_character_dictionary_coverage_report`/`build_review_candidates`/`build_character_review_packet`の実装）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
