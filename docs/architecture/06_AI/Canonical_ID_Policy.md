# Canonical ID Policy（Stage B canonical ID方針）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Canonical_ID_Policy.md`

---

# 1. 目的

Stage B（`agents/merger/`）が出力するmerged entity/relationship/timeline entryに対して、「canonical ID」をいつ・どう扱うかを明文化する。

このPR（`feature/canonical-id-policy`）は方針・helper・validationの追加のみを行う。**既存merged entityへcanonical IDを大量に自動付与することはしない。** 実データでのcanonical ID確定は別フェーズ（実データdry-run以降）で行う。

canonical IDが本文書で扱う対象:

- merged character / location / organization / item / lore / event の `canonicalId`
- merged relationship / timeline entry の `canonicalId`（当面は付与しない、§8参照）

本文書が扱わない対象:

- Story/Episode/Scene/Block ID（`docs/architecture/05_Parser/Identifier_Specification.md` で規定済み。安定しており、本文書の対象外）
- Wiki page slug、ファイル名（Identifier_Specification.md §9で規定済み）

---

# 2. merged entity id と canonicalId の違い

`schemas/merged_knowledge.schema.json` の `MergedEntityBase` は、entity識別に関わる3つの異なるフィールドを持つ。

| フィールド | 意味 | 安定性 |
|---|---|---|
| `id` | 現時点で権威的な識別子。`canonicalId`が確定していればそれと同じ値、未確定なら`mergedId`（暫定merge ID）と同じ値 | **不安定**（`mergedId`側は再マージで変わりうる） |
| `canonicalId` | 確定済みcanonical Entity ID。未確定は`null` | **安定**（一度確定したら原則変更しない） |
| `mergedId` | canonical未確定時の暫定merge ID（`UNRESOLVED_{TYPE}_{number}`等）。再マージで変わりうるため外部から参照しない | 不安定 |

`id`は「このmerge実行の結果として、今どのIDでこのentityを指せるか」を表す**処理結果内の技術的ID**である。`canonicalId`は「Wiki/Knowledge Graph上で外部から安定して参照してよいID」であり、**人間が確認・確定したID**、または**明確な構造化IDから安全に導けるID**のいずれかでなければならない。

`canonicalId`が`null`のentityは、`id`（= `mergedId`）を一時的な参照キーとして使えるが、この値は再マージのたびに変わりうるため、Wiki/Knowledge Graph側からは決して参照しない（`Merged_Knowledge_Design.md` §4.4）。

---

# 3. source candidate id / existing*Id / sourceCharacterId との違い

Stage Bのcanonical ID判定に関わる識別子はいくつかあるが、それぞれ性質が異なる。

| 識別子 | 由来 | 信頼度 | canonicalIdとの関係 |
|---|---|---|---|
| `sourceCandidates[].candidateId` | Stage A（rule-based抽出）が生成した暫定ID（例: `MAIN_S01_C02_E01_CAND_CHAR001`） | provenance追跡専用。参照キーには使わない（`Merged_Knowledge_Design.md` §10.4） | canonicalIdには**絶対にならない** |
| `existingCharacterId`/`existingOrganizationId`/`existingLocationId` | Parser（`agents/parser/resolver.py` の `CharacterDictionary`）が既知キャラクター辞書から解決した構造化ID | **高い**（人間が管理する辞書由来） | 値がそのまま`id`/`canonicalId`として採用される（既存実装、`agents/merger/entity_base.py` `_resolve_entity_identity`）。**このPRでもこの挙動は変更しない** |
| `sourceCharacterId` | ゲームスクリプト上のキャラクター番号 | 中（安定しているが、canonical ID形式ではない） | canonical ID化はしない。同じ値のcandidate同士は安全にmergeするが、`status: unresolved`のまま（`agents/merger/character.py` `_character_merge_key`） |
| `manualOverrides[].value`（`field: "canonicalId"`） | 人間が`manual_overrides.schema.json`経由で明示指定 | **最も高い**（人間の直接判断） | そのまま`entity.canonicalId`へ書き込まれる（`agents/merger/overrides.py`、PR #23） |
| `agents/merger/canonical_ids.py` の `build_canonical_id()` | 人間が確認した安定キー（ローマ字表記等）からの機械的な組み立て | 呼び出し元次第 | **このPRでは自動呼び出しされない**（helper提供のみ、§6参照） |

---

# 4. canonical IDを自動付与してよい条件

以下のいずれかを満たす場合のみ、システムがcanonicalIdを自動で決定してよい。

1. Stage Aの時点で、Parserの既知キャラクター辞書（またはそれに相当する人間管理の構造化辞書）が値を解決済みである（`existingCharacterId`等）。この場合、値はすでに人間管理下にあるとみなせるため、そのまま採用する（既存実装のまま、変更なし）。
2. 将来、`Merged_Knowledge_Design.md` §2.4の「Canonical ID辞書」（`knowledge/dictionaries/*.yaml`）が整備された場合、その辞書からの解決結果（これも人間管理下）。**このPRでは辞書自体を実装しない。**

---

# 5. canonical IDを付与してはいけない条件

以下のいずれかに該当する場合、システムは絶対にcanonicalIdを自動で決定・付与してはならない。

- **名前（displayName/aliases/nameCandidates）が一致するというだけの理由**（`Merged_Knowledge_Design.md` §4.1原則2。同名の別人・別組織が存在しうる）
- 単一エピソード内でしか観測されていない候補（横断的な確認が取れていない）
- `sourceCharacterId`のような「構造化されてはいるが人間管理の辞書に基づかない」キーのみに基づく場合
- confidenceが低いcandidate（`Merged_Knowledge_Design.md` §4.5の隔離対象）
- LLM推定・自然文からの推定結果のみに基づく場合

これらのケースはすべて`status: unresolved`のまま維持し、`canonicalId: null`とする。人間が確認してから、manual override（§7）で確定する。

---

# 6. helperの位置づけ（自動付与ではない）

`agents/merger/canonical_ids.py` は以下のhelperを提供するが、**このPRのmerge pipeline (`agents/merger/entity_base.py`, `relationship.py`, `timeline.py`) からは一切自動的に呼び出されない**。

- `sanitize_canonical_id_segment(value)`: 文字列をID断片として安全な形式（`^[A-Z0-9_]+$`相当）へ変換する
- `build_canonical_id(entity_type, key)`: `{PREFIX}_{sanitize(key)}` の形式でcanonical ID文字列を組み立てる
- `is_valid_canonical_id(value)`: canonical IDとして形式上妥当かを判定する（意味的な正しさは判定しない）
- `classify_canonical_id_source(entity)`: 既存entityの`canonicalId`が構造化ID由来（`structured_id`）/ manual override由来の可能性（`manual_override`）/ 不明（`unknown`）/ 未設定（`none`）のいずれかを、entityの`status`・`id`・`manualOverridesApplied`から推測する（**per-fieldの正確な由来追跡はしていない、ベストエフォートの分類**であることに注意）
- `validate_canonical_ids(collection)`: collection全体のcanonicalId整合性を検証する（§9）

これらは、将来「人間が確認したキーからcanonical IDを機械的に組み立てる」ツール（manual override作成支援、canonical ID辞書ツール等）を作る際の土台として用意するものであり、**このPRでは呼び出し元（CLI等）を作らない**。

---

# 7. manual overrideとの関係

`agents/merger/overrides.py`（PR #23）は、`operation: set_field, field: "canonicalId"` により、人間が明示的にcanonicalIdを指定できる。これは本文書における**最も信頼度の高いcanonical ID確定手段**である。

- manual overrideで指定されたcanonicalIdは、`validate_canonical_ids()`によるvalidation対象に含める（§9）。
- 不正な形式のcanonicalIdがmanual overrideで指定された場合、**このPRではCLIのexit codeやvalidation結果を変更しない**（report warningとして記録するに留める）。理由: overrides.py自体のoperation単位のerror/skip判定ロジックを変更すると、manual overrideの適用範囲が広がり「manual overrideの高度化」という本PRのNon-goalsに抵触するため。厳格化（invalid canonicalIdをoverride適用時点でerror化する等）は、将来のPRで改めて検討する。

---

# 8. unresolved entityとの関係

`status: unresolved` のentityは、原則として`canonicalId: null`である。

`validate_canonical_ids()`は、`status: unresolved`でありながら`canonicalId`が設定されているentityを検出した場合、**warningとして記録する**（エラーにはしない。manual overrideで意図的にunresolved entityへ先行してcanonicalIdを指定するケース——例えば「このentityは将来このIDになる予定」という運用——を将来的に否定しないため）。

---

# 9. relationship / timeline のcanonical ID方針

- **Relationship**: `Merged_Knowledge_Design.md` §6.3よりrelationshipType自体のtaxonomyが未確定であり、`Identifier_Specification.md` §7の`REL_{sourceId}_{relationshipType}_{targetId}`はcanonical化されたsource/targetに依存する。両端が構造化IDで解決済み（`status: merged`）のRelationshipは`canonicalId`が実質的にID全体と一致する形になるが、**taxonomy確定前に`REL_`のcanonical ID運用を本格化しない**。
- **Timeline**: `Merged_Knowledge_Design.md` §7.1の通り、Stage Bでは順序の確定・canonical化を行わない方針を継続する。**merged timeline entryには当面canonicalIdを付与しない**（常に`null`のまま）。

`agents/merger/canonical_ids.py`の`ENTITY_TYPE_TO_CANONICAL_PREFIX`はrelationship（`REL`）/timeline_entry（`TL`）の形式チェック用マッピングも含むが、これは「もし将来canonicalIdが設定されたら形式チェックする」ための準備であり、両者へのcanonicalId自動付与を今回開始するものではない。

---

# 10. 実データdry-run前の暫定方針

実データ（`.dec`スクリプトから生成した本番のepisode_extraction）でのStage B試験運用（`TASKS.md` Next Actions「real data dry-run procedure」）を行う前の暫定方針:

- 既存のキャラクター辞書（`reference/parser/characters_reference.json`等、Parser Phase 1で使用しているもの）に載っているキャラクターは、`existingCharacterId`経由で既にcanonical ID相当の値を持つ。これはこのPRのvalidation対象になる。
- それ以外のOrganization/Location/Item/Lore/Eventについては、実データを通してみるまでcanonical ID命名の実例が乏しい。**大量の実データ由来canonical IDをこのPRで作成しない**（Non-goals）。
- `docs/architecture/05_Parser/Identifier_Specification.md` §10の未確定事項（OD-001: ローマ字表記ルール）は、このPRでも解消しない。「主要キャラクター・主要組織は手動でcanonical IDを管理する」という同文書の推奨方針を、Stage Bでも踏襲する（= manual overrideでの確定を正とする）。

---

# 11. 将来のmigration方針（設計メモ、未実装）

canonical ID辞書（`knowledge/dictionaries/*.yaml`、`Merged_Knowledge_Design.md` §2.4）が整備された段階で、以下のmigrationが必要になる見込み。このPRでは設計メモとして残すのみで、実装はしない。

1. 既存の`UNRESOLVED_{TYPE}_{number}`エントリのうち、辞書に一致するキーを持つものを洗い出す（`classify_canonical_id_source`が`none`を返すentityが対象）
2. 対象entityに対してmanual override（`operation: set_field, field: "canonicalId"`）を生成する（人間のレビューを経てGit管理下のoverrideファイルへ追加）
3. overrideを適用した新しいcollectionを再生成し、`validate_canonical_ids()`で重複・形式エラーが無いことを確認する
4. `mergedId`（暫定ID）を外部から参照していないこと（Wiki/Graph生成が実装される段階で、`canonicalId`のみを参照キーにしていること）を確認してから、辞書運用を本採用する

`canonical ID migration tool`（自動化されたバッチ処理）自体の実装は、このPRのNon-goalsに含まれる。

---

# 12. まとめ

- `canonicalId`は「人間が確定した安定ID」または「明確な構造化ID（人間管理の辞書経由）から安全に導けるID」のみが持つべき値である
- 名前一致だけでcanonicalIdを作らない、unresolved entityには原則付けない、という既存のマージ原則（`Merged_Knowledge_Design.md` §4.1）を、canonical ID運用の観点から再確認・明文化したものが本文書である
- `agents/merger/canonical_ids.py` はvalidationとhelperのみを提供し、既存entityへの自動付与・大量生成は行わない
