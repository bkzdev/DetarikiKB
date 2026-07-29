# Public ID Manifest Assignment Procedure（Public ID採番・割当手順）

Version: 1.0
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Public_ID_Manifest_Assignment.md`

---

# 1. 目的

`story_manifest.yaml`の`publicStoryId` / `publicEpisodeId`を安全に確定し、公開可能な部分集合を`knowledge/public_ids/story_public_ids.yaml`へ登録するまでの運用を定義する。

採用する方式は、**候補生成・照合は半自動、確定と永続化は人間レビュー必須**である。候補スクリプトや番号表から`story_manifest.yaml`、Public ID Registry、Evidence Indexへ自動反映してはならない。

---

# 2. 対象とNon-goals

本手順の対象:

- `publicStoryId`候補の根拠確認
- `publicEpisodeId`候補の生成と正式なepisode順との照合
- 人間レビュー後の`story_manifest.yaml`への反映
- Public ID Registryへの公開可能な部分集合の登録
- normalize後の伝播確認と公開前検証

本手順のNon-goals:

- 実データ由来の`story_manifest.yaml`、番号表、候補、review memoのcommit
- `story_manifest.yaml`またはRegistryを自動更新するwriterの実装
- MAIN / OTHER / CHARACTERカテゴリの未確定命名規約を推測で補うこと
- 公開済みIDの自動改名、削除、再利用
- Evidence IndexやStory Summaryの自動promotion

---

# 3. 権威とライフサイクル

Public IDの権威は、カテゴリ内割当・Registry登録前・Registry登録後で異なる。

| 段階 | 記録 | 位置づけ |
|---|---|---|
| カテゴリ内割当 | `workspace/local_inputs/`配下のEVENT / RAID番号表 | 非commitだが、確定済み規約に基づくprivate allocation mappingの正 |
| 候補 | その他の`workspace/`候補、`check_public_episode_ids.py`のsuggestions | 非commit・非権威。人間レビューの入力 |
| 公開前の確定 | 実データ由来`story_manifest.yaml` | 人間確認済みの内部運用上の正。normalize以降へ伝播する |
| Registry登録後 | `knowledge/public_ids/story_public_ids.yaml` | PRがmergeされた時点で予約済みとなる公開IDの不変な正。manifest側はRegistryと一致させる |

次の規則を守る。

1. EVENT / RAID番号表はカテゴリ内の採番を決める正だが、内部storyとの対応確認・manifest伝播・公開登録まで自動的に確定するものではない。
2. その他のworkspace候補からmanifestまたはRegistryへ自動反映しない。
3. 初回Registry登録前は、人間がmanifest上の対応関係を確認してから、公開可能なIDだけをRegistryへ手動転記する。
4. Registry entryをcommitしたPRがmergeされた時点で、そのIDは下流のEvidence Index / Summaryが未公開でも予約済み・不変となる。以後は必ずその値を再利用する。
5. manifestとRegistryが不一致なら処理を止め、Registryを勝手に上書きせず人間がmanifest側の対応を確認する。
6. Registryからmanifestへの自動backfillも行わない。内部IDとの対応を機械的に推測できないためである。
7. internal `storyId` / `episodeId`とのmapping、raw path、title、subtitleをRegistryへ含めない。

---

# 4. publicStoryIdの候補作成

## 4.1 EVENT / RAID

EVENT / RAIDでは、`docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16.7〜§16.9の確定済み規約を使う。

- 通常のstoryは、カテゴリ全量に対して人間確認済みの番号表にある採番を候補とする。
- 遅延発見storyは、§16.9のアンカーseq + `_ADD`マーカー方式を使う。既存seqを繰り下げない。
- sourceKeyの日付部分は確定済み規約が許可する範囲だけで使用し、slug、実タイトル、実イベント名をIDへ含めない。
- 番号表は`workspace/local_inputs/`配下の非commit入力だが、EVENT / RAIDカテゴリ内のpublicStoryId private allocation mappingについては正とする。人間レビューでは番号表の割当から逸脱せず、対象の内部storyとの対応が正しいことを確認する。番号表に欠落・矛盾があれば独自採番せずblockingにする。

## 4.2 その他のカテゴリ

MAIN / OTHER / CHARACTERなど、カテゴリ別命名規約が未確定のものは自動採番しない。既存の設計で明示的に確定した値が無い場合は`publicStoryId: null`を維持し、カテゴリ方針の決定へエスカレーションする。

title、subtitle、raw path、単一候補との名前一致からPublic IDを推測してはならない。

---

# 5. publicEpisodeIdの候補作成

形式は次で固定する。

```text
{publicStoryId}_E{episodeNumber:02d}
```

正式な順序根拠は、**人間確認済み`story_manifest.yaml`の`episodeNumber`**である。`scripts/check_public_episode_ids.py`がEvidence Index候補のentry初出順から計算する`episodeOrder`は、欠落検出と候補作成のためのヒューリスティックにすぎない。

候補を採用する前に、各episodeについて次を照合する。

- `episodeNumber`が1以上の整数で、同一story内で重複していない
- manifestのepisode対応がraw配置と人間確認済みの順序に一致する
- suggestionの`missingEpisodeOrder`がmanifestの`episodeNumber`と一致する
- 既存Registryの`episodeOrder` / `publicEpisodeId`と矛盾しない
- 同じ`publicEpisodeId`が別episodeまたは別storyで使われていない

不一致はblockingである。entry初出順を理由にmanifestの`episodeNumber`を書き換えたり、suggestionをそのまま採用したりしてはならない。

---

# 6. 人間レビューと反映手順

## 6.1 候補をworkspaceへ生成する

Public Evidence Index候補がある場合は、既存Registryを併用してcheck-onlyで候補を生成する。

```powershell
uv run python scripts/check_public_episode_ids.py `
  --input workspace/evidence_index_dry_runs/<run-id>/stories `
  --registry knowledge/public_ids/story_public_ids.yaml `
  --report workspace/public_episode_ids/<run-id>/report.md `
  --suggestions-output workspace/public_episode_ids/<run-id>/suggestions.yaml `
  --strict
```

exit code `1`は欠落または衝突を含むレビュー要求、`2`は入力・schema・出力先等の設定エラーである。suggestionsは常に`reviewRequired: true`であり、成功・失敗にかかわらず永続化を行わない。

## 6.2 人間が対応と順序を確認する

1. §4のカテゴリ別規約と番号表から`publicStoryId`候補を確認する。
2. manifestの`episodeNumber`を正式順序として、§5の形式で`publicEpisodeId`候補を作る。
3. suggestion、manifest、既存Registryの3者を照合する。
4. 不明・欠落・矛盾を推測で解消せず、未確定のまま記録して処理を止める。

## 6.3 manifestへ手動反映する

人間が確認した値だけを実データ由来`story_manifest.yaml`へ手動反映する。manifestは内部情報を含むためcommitしない。

反映後に対象storyを再normalizeし、Normalized Story JSONの次の値を確認する。

- `source.manifest.publicStoryId`
- `source.manifest.publicEpisodeId`

さらに必要なExtractor / Merger / renderer経路で同じ値が維持され、内部ID fallbackへ意図せず戻っていないことを確認する。

## 6.4 Registryへ手動登録する

公開対象として別途承認されたstoryだけを、`knowledge/public_ids/story_public_ids.yaml`へ手動追加する。Registryにはschemaで許可された公開ID・category・episodeOrderだけを含める。Registry変更PRがmergeされた時点で、そのIDは予約済み・不変となる。

登録前後に次を確認する。

- `publicStoryId`と`publicEpisodeId`が全Registry内で一意
- `publicEpisodeId`が`publicStoryId`をprefixとして持つ
- `episodeOrder`が確認済みmanifestの`episodeNumber`と一致
- 既存entryが意図せず変更・並べ替え・削除されていない
- 廃止済みまたは過去に公開したIDを再利用していない
- internal ID、sourceKey、raw path、title、subtitleが混入していない

Registry変更とEvidence Index / Summary promotionは権限とレビュー条件が異なる。Registryへ追加しただけで自動promotionしてはならず、該当runbookのcheck・人間承認・PRを別途満たす。

---

# 7. episode追加・順序変更

## 7.1 Registry未登録の場合

Registry未登録かつ未公開であれば、人間がmanifestのepisode対応と`episodeNumber`を修正し、候補を再生成して全件レビューし直せる。古いworkspace候補は権威として再利用しない。

## 7.2 Registry登録済みの場合

Registry変更PRがmergeされた`publicEpisodeId`と`episodeOrder`は、下流コンテンツが未公開でも自動変更しない。

- 末尾への新規episode追加で、既存値を変更せず未使用の次番号を割り当てられる場合も、人間レビューと通常のRegistry更新PRを必須とする。
- 途中挿入、既存episodeの順序変更、重複解消など、既存のIDまたは`episodeOrder`変更が必要な場合はassignmentをblockingにする。
- blocking時は専用のmigration設計を先に作り、redirect・既存Evidence/Summary参照・廃止ID記録・再利用禁止を個別に決定する。本手順だけを根拠に改名しない。

---

# 8. commit前チェック

変更対象がdocs・テストだけの場合も、標準検証を実行する。

```powershell
uv run pytest
uv run python scripts/check_invisible_unicode.py
uv run python scripts/check_dry_run_inputs.py
uv run ruff format scripts agents tests --check
uv run ruff check scripts agents tests
uv run mkdocs build --strict
```

実Registryを変更するPRでは、対象候補に対する`check_public_episode_ids.py --registry ... --strict`と、関連するprojection / promotion checkも追加で実行する。

---

# 9. 関連ドキュメント

- `docs/architecture/05_Parser/Story_Manifest_Design.md` §10・§13.2
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md` §16
- `docs/architecture/05_Parser/Story_ID_Policy_Decision.md`
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`
- `schemas/story_manifest.schema.json`
- `schemas/public_id_registry.schema.json`
- `scripts/check_public_episode_ids.py`
