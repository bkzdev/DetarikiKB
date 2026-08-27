# Canonical Timeline Review Packet契約

Version: 0.2

Status: Implemented schema, validator, and pending packet builder

Schema: `schemas/canonical_timeline_review_packet.schema.json`

---

# 1. 目的

canonical Timelineのcross-story candidateを、2 story間の小さなedge集合として人間が確認するためのlocal internal packetを定義する。packetは候補とreview結果を保持する中間artifactであり、canonical Timelineの正ではない。

`humanReviewStatus: confirmed`に相当する`reviewStatus: confirmed`を記録しても、canonical artifactへのpromotionは起動しない。schema、validator、builderは合成fixtureだけで検証し、実packetをcommitせず、review結果の取り込みとpromotionを実装しない。

---

# 2. Root契約

rootは次の境界を固定する。

| field | 契約 |
|---|---|
| `schemaVersion` | `"0.1"`または`"0.2"`。builderの新規出力は`"0.2"` |
| `documentType` | `"canonical_timeline_review_packet"` |
| `packetId` | titleを含まないlocal packet ID |
| `reviewBatchId` | story titleを含まないlocal review batch識別子 |
| `classification` | `"local_internal"`固定 |
| `commitAllowed` | `false`固定 |
| `scopeStoryCategory` | `"EVT"`固定 |
| `visibility` | `"internal_only"`固定 |
| `createdAt` | RFC 3339 date-time |
| `expiresAt` | v0.2だけで必須。`createdAt`の90日後 |
| `storyPair` | 相異なる2 EVENT storyだけ |
| `edges` | 1件以上のreview対象edge |

`additionalProperties: false`とし、global整数、story-local `canonicalOrder`、public ID / URL、raw text / path用fieldを受理しない。v0.1は後方互換で読めるが`expiresAt`を受理せず、v0.2は`expiresAt`を必須とする。実packetは固定workspace限定・非commitである。

---

# 3. Story pairとEpisode参照

`storyPair`は`storyId`と`storyCategory: "EVT"`だけを持つ2要素の配列で、`uniqueItems: true`とする。1 story packet、3 story以上、同じStoryRefの重複、EVENT外storyを拒否する。

edgeとcandidate provenanceのEpisodeRefは既存`canonical_timeline.schema.json`の定義を再利用し、`storyId` / `episodeId` / `storyCategory: "EVT"`を保持する。JSON Schemaだけでは表せない次の動的比較は、`validate_canonical_timeline_review_packet_consistency()`が入力を変更せず決定的に検査する。

- edgeの`from` / `to`が`storyPair`内の異なるstoryを指すこと
- candidate provenanceの`sourceEpisode` / `targetEpisode`が同じpairとedgeの両端に解決できること
- `reviewEdgeKey`がpacket内で一意であること
- 完全重複edgeを検出し、provenanceが異なる観測は重複として破棄しないこと
- conflict provenanceの向きを正規化した結果が実際に両立不能であること

schema単独ではpair外EpisodeRefを受理しうるが、packet validatorはsemantic findingとして拒否する。この境界を理由にstory IDを文字列から推測したり、pair外candidateを黙って削除したりしない。

---

# 4. Review edge

ReviewEdgeは次を保持する。

- packet内だけで使う`reviewEdgeKey`。canonical edge IDではない
- `from` / `to` EpisodeRefと5値の`relationState`
- unknown / conflictを不破棄で残す`stateReason`
- 元方向を保持する`candidateProvenance`
- edge単位の`reviewStatus`と`humanDecision`

`adoptionStatus`はpacketに置かない。confirmed edgeもreview済みcandidateに留まり、promotion後のcanonical状態をpacketから表現しない。

## 4.1 Relation state

| relationState | stateReason |
|---|---|
| `before` / `after` / `same_time` | `null` |
| `unknown` / `conflict` | 非空文字列 |

conflictは最低2件のcandidate provenanceを要求する。before / afterの方向反転、same-time class化、winner選択はpacket schemaで行わない。

## 4.2 Review status

| reviewStatus | humanDecision | relationState |
|---|---|---|
| `pending` | `null` | 5状態 |
| `confirmed` | 必須 | `before` / `after` / `same_time`だけ |
| `rejected` | 必須 | 5状態 |
| `needs_more_context` | 必須 | 5状態 |

unknown / conflictをconfirmedへ変換せず、pending / rejected / needs_more_contextとして理由・provenanceと共に保持する。rejectedとneeds_more_contextも人間判断なので、reviewer、決定日時、非逐語のevidence summaryを欠落させない。

---

# 5. Canonical Timeline schemaとの関係

EpisodeRef、CandidateProvenance、HumanDecisionは`canonical_timeline.schema.json`のdefinitionsをoffline external referenceとして再利用する。これによりsource / targetの元方向、candidate / Evidence ID、source type、confidence、extraction runの契約を分岐させない。

consumer / validatorはrepo内のcanonical Timeline schemaをRegistryへ明示登録して解決し、networkやremote schema fetchへ依存しない。

canonical Timeline artifactのTimelineEdgeは`adoptionStatus`を持つが、ReviewEdgeは持たない。packetからcanonical artifactへの変換、confirmed decisionのimport、promotion前後のsemantic validationは後続toolingの責務である。

---

# 6. 安全境界

- packet、実candidate、review note、内部ID対応表はworkspace限定で、commitしない
- `stateReason` / `evidenceSummary` / `notes`は原文を転載しない短い根拠要約だけにする
- raw path、source filename、source key、DEC本文、セリフ、raw command、URLをpacketへ複写しない
- builder / validatorのstdout / stderrへ内部story / episode / candidate / Evidence IDやpathを出さない
- pendingをconfirmedへ自動変更せず、confirmedをcanonicalへ自動promotionしない
- inventory 0件からcandidate / edgeを補完しない

読取専用CLIはfree-text内容のpath / raw marker / packet内内部ID、固定workspace root、Git ignored / untracked、symlink / reparse pointをblocking検査する。schemaとsemantic validationの両方が通るまで運用上validなpacketとは判定しない。

packet v0.1には`expiresAt`がないためretention / expirationは検査しない。v0.2は`expiresAt = createdAt + 90日`を必須とし、ずれはblocking issue、期限超過はwarningだけとする。期限切れでもvalidatorはexit 0を維持し、packetを削除・変更・promotionしない。自動cleanupは実装しない。

builderは`scripts/build_canonical_timeline_review_packet.py`で、schema / semantic-validなStage A入力の既存`relative_order`だけを利用する。決定的に並べたstory pairを1-based `--story-pair-index`で1件選び、元方向と全candidate provenanceを保持した`pending` edgeへ変換する。同じedge形状の複数観測は1 ReviewEdgeのprovenance配列へ保持し、観測自体は重複排除しない。

出力先は`workspace/review_packets/canonical_timeline/`固定である。既定はdry-run、書込みは`--execute`明示時だけとし、固定rootを作成後に再検査する。一時fileを排他的に作成し、schema + semantic validation後にreplace-freeで公開する。既存targetは上書きせず、`os.replace`や上書きfallbackを使わない。

validatorの`--render-review-brief`は、edge数・関係別件数・provenance件数・review状態・期限状態だけを固定templateの自然文で表示する。story / episode / candidate / Evidence ID、path、URL、raw textは表示しない。

`createdAt`と`humanDecision.decidedAt`は、schema patternに加えてread-only validatorの`FormatChecker`でRFC 3339の暦日・時刻範囲を検査する。

---

# 7. Non-goals

- Normalized Story本文からのcandidate推定、LLM / provider実装、edge方向の反転・winner選択
- humanDecision自動記入
- canonical artifact反映、review import、promotion plan CLI / file I/O / executor（非実行schema契約とin-memory projector / validatorは`Canonical_Timeline_Promotion_Plan.md`）
- report永続化、期限切れpacketの自動削除
- global integer、total order、story-local `canonicalOrder`比較・補完
- EVENT以外への拡張、renderer、Wiki、public projection
- 実データfixture、実packet、raw / generated artifactのcommit
- 既存canonical Timeline schema / semantic validator、v0.5、inventory、manifest、Stage A / Bの変更

---

# 8. 検証

合成`TEST_*`値だけで、Draft 7 schema妥当性、2 distinct EVENT story、5 relation state、4 review statusとhumanDecision条件、unknown / conflictの理由・provenance不破棄、confirmedとpromotionの分離、internal-only / commit禁止、外部definitionのoffline解決、禁止fieldの拒否を検証する。semantic / CLI testではpair・provenance・conflict・重複、不変性・決定性、固定root / Git / reparse / free-text境界、safe aggregate出力を検証する。

```powershell
uv run pytest tests/schemas/test_canonical_timeline_review_packet_schema.py
uv run pytest tests/extractor/test_canonical_timeline_review_packet_consistency.py tests/extractor/test_canonical_timeline_review_packet_builder.py tests/scripts/test_validate_canonical_timeline_review_packet.py tests/scripts/test_build_canonical_timeline_review_packet.py
```

pair外EpisodeRefがschema単独では通りうることも合成testで境界として固定し、semantic validatorでblocking findingにする。

---

# 9. 関連文書

- `Canonical_Timeline_Scope_Decision.md`
- `Canonical_Timeline_Schema.md`
- `Canonical_Timeline_Promotion_Plan.md`
- `../../runbooks/Cross_Story_Constraint_Inventory.md`
- `../../runbooks/Canonical_Order_Review.md`
- `../../runbooks/Canonical_Timeline_Review.md`
