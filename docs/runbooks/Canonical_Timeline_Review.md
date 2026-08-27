# Canonical Timeline Review運用手順

Version: 0.2

対象: 2 EVENT story間のcanonical Timeline review packet

CLI:

- `scripts/build_canonical_timeline_review_packet.py`
- `scripts/validate_canonical_timeline_review_packet.py`

---

# 1. 目的

検証済みStage Aに既に存在するcross-story `relative_order`から、2 EVENT storyだけのlocal internal packetを安全に構築し、schema・cross-story semantic・free-text安全境界の3層で読み取り専用検証する。packetはreview用の中間artifactであり、validator PASSや`reviewStatus: confirmed`はcanonical artifactへのpromotionを起動しない。

本runbookは合成fixtureで検証したbuilder / validator運用を定義する。human-confirmedなknown relationを非実行proposalとして保持するschema契約は`../architecture/03_Data_Model/Canonical_Timeline_Promotion_Plan.md`で定義済みだが、Normalized Story本文からの候補推定、review結果import、canonical artifact作成・更新、promotion plan builder / validator / executorは未実装である。confirmed edgeからplanやpromotionが自動起動することはない。

---

# 2. 固定rootと入力境界

packetは固定root `workspace/review_packets/canonical_timeline/`直下のJSONだけを対象にする。

- CLI引数は`--packet-name`のbasenameだけで、任意pathを受けない
- file名は`canonical_timeline_review_<local-name>.json`形式とする
- 読込前にGit worktree root、repo内固定root、git ignored、untrackedを確認する
- repo rootからleafまでの既存祖先とleafでsymlink / Windows reparse pointを拒否する
- UTF-8 JSONのregular fileだけを読む
- packet、review note、内部ID対応表はcommitしない

validatorはfileを書き換えず、reportも保存しない。builderは既定dry-runで、`--execute`を明示した場合だけ新規packetをno-clobberで作成する。

---

# 3. Builder実行

入力はrepo内のschema-validなStage A JSON file / directory / globである。builderは各resolved fileのrepo / reparse境界を読込前に検査し、EVENT scopeにある明示的な`relative_order`だけをinventory化する。利用可能pairと決定的な1-based indexは、先に`Cross_Story_Constraint_Inventory.md`のinventory reportで確認し、builderではそのindexを1件選ぶ。builderの匿名集計は選択済みpairが1件であることだけを示す。

```powershell
uv run python scripts/build_canonical_timeline_review_packet.py `
  --input workspace/dry_runs/{run}/extraction `
  --recursive `
  --story-pair-index 1 `
  --packet-name canonical_timeline_review_batch_001.json `
  --review-batch-id review-batch-001
```

正常なdry-runではpacketを書かず、匿名集計だけを表示する。内容を確認後、同じ引数へ`--execute`を追加して新規packetを作成する。既存packetは上書きしない。

builderはrelationを反転・統合・推定せず、全観測の元方向、candidate ID、Evidence ID、source type、confidence、extraction runをpacket内provenanceへ保持する。stdout / stderrへこれらの内部値やpathを出さない。

builderのexit codeは、0=正常、1=invalid inputまたは選択可能pairなし、2=固定root・packet名・write等の設定異常である。

---

# 4. Validator実行

```powershell
uv run python scripts/validate_canonical_timeline_review_packet.py `
  --packet-name canonical_timeline_review_batch_001.json
```

正常時はedge数と4 review statusの匿名集計だけをstdoutへ出す。`--render-review-brief`では関係別・provenance・review状態・保持期限の匿名集計を固定templateの自然文で表示する。`--quiet`では正常時に何も出さないが、期限切れwarningは隠さない。異常時はfixed issue code（固定issue code）と件数だけをstderrへ出し、path、story / episode / candidate / Evidence ID、free-text、raw内容を表示しない。

exit codeは次の通り。

| code | 意味 |
|---:|---|
| 0 | schema・semantic・free-text検証がすべてvalid（期限切れwarningを含みうる） |
| 1 | JSON / schema / semantic / free-textがinvalid |
| 2 | packet名、固定root、Git境界、reparse point、schema読込等の設定異常 |

---

# 5. Schema検証

packet schemaとcanonical Timeline schemaをrepo内`referencing.Registry`へ明示登録し、external `$ref`を完全offlineで解決する。network / remote schema fetchへfallbackしない。

Draft 7とFormatCheckerで、2 distinct EVENT story、5 relation state、4 review status、humanDecision conditional、candidate provenance、internal-only / commit禁止、禁止fieldを検証する。v0.1は`expiresAt`なしで後方互換、v0.2は`expiresAt`必須である。

---

# 6. Semantic検証

schema valid後、入力dictを変更せず次を決定的に検査する。

- `reviewEdgeKey`重複
- edgeの`from` / `to`が`storyPair`外、同一story、selfでないこと
- candidate provenanceの両端がedge両端と順方向または逆方向で一致すること
- conflict provenanceをedge方向へ一時的に正規化したとき、実際に2種類以上の両立不能なrelationを持つこと
- 完全同一ReviewEdge recordの重複

両端やrelationが同じでも、provenance、status、decision等が異なる観測は重複として削除・統合しない。before / afterの一時正規化はconflict検査だけに使い、入力edgeを書き換えない。

unknown / conflict、pending / rejected / needs_more_context / confirmedをcanonical graphへ渡さず、winner選択、relation反転、edge生成、promotionを行わない。

---

# 7. Free-text検証

`stateReason`、`humanDecision.reviewer`、`evidenceSummary`、`notes`を検査し、次をblocking issueとして扱う。

- Windows absolute path、UNC path、Unix absolute path
- URL
- `.dec`、raw command marker、script marker
- packet内のstory / episode / candidate / Evidence ID

内容そのものはerror出力へ複写しない。根拠は原文を転載せず、短い非逐語要約だけを記録する。

---

# 8. 保持期限と削除境界

ユーザー決定（2026-08-27）により、新規builder出力はpacket v0.2、保持期限は作成時刻から90日とする。v0.2では`expiresAt = createdAt + 90日`の完全一致をvalidatorが検査し、ずれはblocking issueとする。

期限切れはwarningだけでexit 0を維持する。validatorもbuilderも期限切れpacketを削除・変更しない。自動cleanup、期限延長、上書き更新は実装しない。v0.1 packetには`expiresAt`がないため、retention検査の対象外である。

builderは固定root作成後にもrootからleafまでを再検査し、一時fileを排他的に作成する。生成packetがschema + semantic + free-text検証に通った後だけ、同一directoryのhard linkを使ってreplace-freeに公開する。`os.replace`や上書きfallbackは使わず、publish失敗時は一時fileを片付ける。

---

# 9. 次の人間・データgate

保持期限とbuilderの契約は確定した。実corpusの既存inventoryは0件なので、本物のpacketを作るには、Normalized Storyを根拠として2 EVENT story間の関係候補をagentが提示し、人間確認gateを通す小規模local sampleが必要である。候補提示では対象2 storyの内容と関係根拠を自然文で説明し、ユーザーが内部IDを読まなくても判断できる形にする。

ユーザーは2026-08-27に、Normalized Storyからのagent-assisted候補抽出、internal-only、人間確認前の自動確定・promotion・公開を行わない条件を承認した。この承認は`agents/extractor/`のLLM provider実装や自然文からの自動大量抽出を意味しない。まず小規模local sampleをagentが読み取り、候補を個別に説明する。

---

# 10. Non-goals

- Normalized Story本文から候補を自動生成するLLM / provider実装、大量抽出
- humanDecision自動記入、review結果import
- canonical artifact作成・更新、promotion plan / execute
- report永続化、期限切れpacketの自動cleanup
- global integer、total order、story-local `canonicalOrder`比較・補完
- EVENT外拡張、renderer、Wiki、public projection
- 実packet / 実データfixture / raw / generated artifactのcommit

---

# 11. 検証

```powershell
uv run pytest tests/schemas/test_canonical_timeline_review_packet_schema.py tests/extractor/test_canonical_timeline_review_packet_consistency.py tests/extractor/test_canonical_timeline_review_packet_builder.py tests/scripts/test_validate_canonical_timeline_review_packet.py tests/scripts/test_build_canonical_timeline_review_packet.py
```

すべて合成`TEST_*` packetを一時directoryで扱い、実workspaceへpacketを生成しない。
