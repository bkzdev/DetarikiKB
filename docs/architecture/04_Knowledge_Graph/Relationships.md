# Relationship taxonomy / 公開v1契約

Status: Accepted (2026-09-14)

## 1. 目的

RelationshipはStage Aで観測された自由文字列を失わず保持しつつ、Wikiで誤った
関係を断定しない必要がある。本書は公開v1で意味を確定する最小taxonomy、Stage B
のreview境界、Wiki公開条件を定める。Knowledge Graph全体の生成は対象外である。

## 2. taxonomy state

`relationshipType`はschema上の自由文字列を維持する。Stage Bは大文字小文字と
英数字以外の区切りだけをsnake_caseへ正規化し、次の状態を別に持つ。

| `taxonomyState` | 意味 | 公開可否 |
| --- | --- | --- |
| `formal_v1` | 公開v1で意味・endpoint・方向を確定済み | 他のgateも満たす場合のみ可 |
| `provisional` | 語彙候補だが意味契約が未確定 | 不可、review対象 |
| `unrecognized` | 未登録の自由文字列 | 不可、review対象 |

意味を変えるalias変換は自動実行しない。例えば`belongs_to`から`member_of`への
変換候補は`suggestedType`としてreviewに提示できるが、merge keyを書き換えない。

## 3. 公開v1の型

| 正規化型 | 表示名 | endpoint / direction | 意味 |
| --- | --- | --- | --- |
| `member_of` | 所属 | Character → Organization / `source_to_target` | 所属が明示または手動確認済み |
| `affiliated_with` | 関係あり（所属未確定） | Character → Organization / `source_to_target` | 組織との関係は明示されるが所属までは確定できない |

`affiliated_with`から`member_of`への格上げは手動確認だけで行う。自動alias、名前一致、
confidence閾値だけでは格上げしない。

暫定型は`ally_of`、`enemy_of`、`family_of`、`friend_of`、`mentor_of`、
`subordinate_of`、`superior_of`、`appears_with`、`related_to`、`located_in`、
`owns`、`uses`、`knows`、`unknown`とする。これは公開許可を意味しない。

## 4. Stage B merge契約

merge keyは次の5値とする。

```text
(resolved sourceId, resolved targetId, normalized relationshipType,
 sourceType, direction)
```

- `sourceType`を分離し、`script`と`ai_extracted` / `ai_inferred`を同一recordへ混ぜない。
- direction矛盾は`bidirectional`へ自動拡張しない。観測方向ごとに別recordで保持し、
  両方を`review_required`にする。
- 両endpointを解決できないcandidateはmerged entityを作らず、review recordへ保持する。
- formal v1型はCharacter → Organizationかつ`source_to_target`を要求する。型・方向の
  不一致は値を修正せずreview対象とする。
- provisional / unrecognized型、意味alias、同一endpointの型矛盾もreview対象とする。

review recordはepisode / candidate ID、元・正規化type、taxonomy state、方向、
sourceType、confidence、元endpoint、解決済みendpointとtype、evidence IDs、
extractionRun、複数のreview理由を保持する。warning文字列だけを唯一の記録にしない。

## 5. 公開gate

Relationshipは次をすべて満たす場合だけ`publicationStatus: eligible`となる。

1. `taxonomyState: formal_v1`
2. 正規化型が`member_of`または`affiliated_with`
3. sourceがCharacter、targetがOrganization
4. `direction: source_to_target`
5. `sourceType`が`script`または`manual`
6. 同一endpointに型・方向矛盾がない

`official`、`ai_extracted`、`ai_inferred`、`unknown`は公開v1ではRelationshipとして
表示しない。値・根拠は内部entity / review recordに残す。rendererは上記条件を再推測
せず、`publicationStatus: eligible`だけをfail-closedで採用する。

## 6. 今後の拡張

暫定型をformalへ昇格する場合は、意味、endpoint型、方向、逆関係、時間変化、表示名、
既存record移行を別decisionで定める。公開v1の採択だけを理由にKnowledge Graph生成、
自然文推定、実データRelationshipの確定を開始しない。
