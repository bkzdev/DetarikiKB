# Canonical Timeline Review運用手順

Version: 0.1

対象: 2 EVENT story間のcanonical Timeline review packet

CLI: `scripts/validate_canonical_timeline_review_packet.py`

---

# 1. 目的

`canonical_timeline_review_packet.schema.json`に従うlocal internal packetを、schema・cross-story semantic・free-text安全境界の3層で読み取り専用検証する。packetはreview用の中間artifactであり、validator PASSや`reviewStatus: confirmed`はcanonical artifactへのpromotionを起動しない。

本runbookは合成fixtureで検証したvalidator運用だけを定義する。実packetの生成、review結果import、canonical artifact作成・更新、promotion plannerは未実装である。

---

# 2. 固定rootと入力境界

packetは固定root `workspace/review_packets/canonical_timeline/`直下のJSONだけを対象にする。

- CLI引数は`--packet-name`のbasenameだけで、任意pathを受けない
- file名は`canonical_timeline_review_<local-name>.json`形式とする
- 読込前にGit worktree root、repo内固定root、git ignored、untrackedを確認する
- repo rootからleafまでの既存祖先とleafでsymlink / Windows reparse pointを拒否する
- UTF-8 JSONのregular fileだけを読む
- packet、review note、内部ID対応表はcommitしない

validatorはfileを書き換えず、reportも保存しない。`--write` / `--execute`は存在しないため、常に非変更である。

---

# 3. 実行

```powershell
uv run python scripts/validate_canonical_timeline_review_packet.py `
  --packet-name canonical_timeline_review_batch_001.json
```

正常時はedge数と4 review statusの匿名集計だけをstdoutへ出す。`--quiet`では正常時に何も出さない。異常時はfixed issue code（固定issue code）と件数だけをstderrへ出し、path、story / episode / candidate / Evidence ID、free-text、raw内容を表示しない。

exit codeは次の通り。

| code | 意味 |
|---:|---|
| 0 | schema・semantic・free-text検証がすべてvalid |
| 1 | JSON / schema / semantic / free-textがinvalid |
| 2 | packet名、固定root、Git境界、reparse point、schema読込等の設定異常 |

---

# 4. Schema検証

packet schemaとcanonical Timeline schemaをrepo内`referencing.Registry`へ明示登録し、external `$ref`を完全offlineで解決する。network / remote schema fetchへfallbackしない。

Draft 7とFormatCheckerで、2 distinct EVENT story、5 relation state、4 review status、humanDecision conditional、candidate provenance、internal-only / commit禁止、禁止fieldを検証する。

---

# 5. Semantic検証

schema valid後、入力dictを変更せず次を決定的に検査する。

- `reviewEdgeKey`重複
- edgeの`from` / `to`が`storyPair`外、同一story、selfでないこと
- candidate provenanceの両端がedge両端と順方向または逆方向で一致すること
- conflict provenanceをedge方向へ一時的に正規化したとき、実際に2種類以上の両立不能なrelationを持つこと
- 完全同一ReviewEdge recordの重複

両端やrelationが同じでも、provenance、status、decision等が異なる観測は重複として削除・統合しない。before / afterの一時正規化はconflict検査だけに使い、入力edgeを書き換えない。

unknown / conflict、pending / rejected / needs_more_context / confirmedをcanonical graphへ渡さず、winner選択、relation反転、edge生成、promotionを行わない。

---

# 6. Free-text検証

`stateReason`、`humanDecision.reviewer`、`evidenceSummary`、`notes`を検査し、次をblocking issueとして扱う。

- Windows absolute path、UNC path、Unix absolute path
- URL
- `.dec`、raw command marker、script marker
- packet内のstory / episode / candidate / Evidence ID

内容そのものはerror出力へ複写しない。根拠は原文を転載せず、短い非逐語要約だけを記録する。

---

# 7. 保持期限とbuilderの境界

packet v0.1 schemaは`expiresAt`を持たない。validatorはretentionや期限切れを検査せず、実装済みとも扱わない。

builder着手前に、schema version、`expiresAt`、既定保持日数、許容範囲、期限切れをerror / warningのどちらにするか、削除主体を決める必要がある。builderはその決定後に、固定rootの再検査、一時fileの排他的作成、schema + semantic validation、replaceしないatomic publish、no-clobberを別PRで実装する。`os.replace`や上書きfallbackは使わない。

---

# 8. 次の人間・データgate

builderへ進むには、次の両方が必要である。

1. retention運用の明示的な決定
2. story-local順序から推測していない、2 EVENT story間の根拠付きcross-story candidateを1件以上、人間確認済みlocal sampleとして用意すること

このgateを満たすまで、inventory 0件から自然文推定・LLM抽出で候補を補完しない。

---

# 9. Non-goals

- packet / candidate / edge生成、inventory変換
- humanDecision自動記入、review結果import
- canonical artifact作成・更新、promotion plan / execute
- file / report write、retention、promotion
- cleanup / expiration判定
- global integer、total order、story-local `canonicalOrder`比較・補完
- EVENT外拡張、renderer、Wiki、public projection
- 実packet / 実データfixture / raw / generated artifactのcommit

---

# 10. 検証

```powershell
uv run pytest tests/extractor/test_canonical_timeline_review_packet_consistency.py tests/scripts/test_validate_canonical_timeline_review_packet.py
```

すべて合成`TEST_*` packetを一時directoryで扱い、実workspaceへpacketを生成しない。
