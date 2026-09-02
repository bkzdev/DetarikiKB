# Canonical Timeline Scope Decision（global chronology判断枠）

Version: 0.1
Status: Accepted
Decision date: 2026-08-23
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

story内の`canonicalOrder`付与と全EVENT corpusのreadiness確認が完了した後、cross-story chronologyやcanonical Timelineへ進む前に必要な判断を一枚へ集約する。

本書はglobal chronologyの実値・個別の前後関係・公開を決定しない。現行仕様を安全側で維持しながら次の実装を開始できる初期profile、review gate、internal/public境界を確定するDecision Recordである。

---

# 2. 現在確定している境界

## 2.1 完了済み

- episode-level `canonicalOrder`の正は`story_manifest.yaml`であり、`canonicalOrderStatus: confirmed`の値だけをNormalized StoryとTimelineCandidateへ出典付きで伝播する
- 現行v0.5 checkは同一story内だけで`canonicalOrder`と`relative_order`を照合する
- readinessは、loaded episodeがすべてcomparableで既知の同一story constraint findingが無いことを表す
- EVENT全137 story・537 episodeは単一corpus監査でcomparable 537、missing / ambiguous 0 / 0、全finding 0、ready 137 / 137 storyとなった
- cross-story constraintは`cross_story_constraint`として未検査のままprovenance付きで保持する

## 2.2 未完了

- story間の前後・同時・不明・矛盾の表現
- EVENT内またはcategory横断のcanonical chronology
- 値の連番性・一意性・総順序
- story-local値をglobalな値・node・edgeへ昇格する契約
- canonical Timelineのreview、保存、promotion、internal/public出力

## 2.3 現在の安全な解釈

採択後も、既存`canonicalOrder`は**運用上story-localな順序値**として扱う。数値が同じ、隣接する、または大小関係を持つことをstory間の前後・同時性の根拠にしない。cross-story chronologyは別のpartial order graphとしてadditiveに扱う。

これは将来の表示用sequenceを禁止する恒久決定ではない。story-local値を誤ってglobalへ昇格させないための恒常的な安全境界である。

---

# 3. 用語

| 用語 | 本書での意味 |
|---|---|
| story-local order | 同じ`storyId`に属するepisode間だけで意味を持つ`canonicalOrder` |
| cross-story constraint | 異なるstoryに属する対象間の`before` / `after` / `same_time`候補 |
| partial order | 根拠のある関係だけをedgeとして持ち、比較不能な組み合わせを許す順序 |
| total order | 対象を必ず一本の順序へ並べ、任意の2対象を比較可能にする順序 |
| canonical Timeline | 人間review済みのcross-story関係を含む、保存・再検証可能な正規時系列artifact |
| unknown | 根拠不足のため関係を決めない状態。欠落ではなく明示的な保留 |
| conflict | 複数のprovenance付き根拠が両立せず、winnerを決めていない状態 |

---

# 4. 採択後も維持する不変則

1. 既存`canonicalOrder`の数値をstory間で比較しない
2. `releaseOrder` / `displayOrder` / `episodeNumber`、manifest配列順、ファイル名、ID、タイトルをglobal chronologyの補完根拠にしない
3. `cross_story_constraint`を黙って比較・削除・winner選択せず、candidate・Evidence・`extractionRun`を保持する
4. unknownとconflictを欠落扱いにせず、保留理由とprovenanceを保持する
5. AI候補、機械抽出、review済みcanonical関係を同じstatusで扱わない
6. internal review artifactとpublic表示を分離し、公開許可前にcanonical Timelineとして表示しない
7. 既存schema・CLI・manifest・v0.5 report・Wiki rendererは破壊的に変更しない。後続機能は専用契約としてadditiveに実装する

---

# 5. 人間が決める事項

## D1. 初期global scope

| 候補 | 内容 | 主なtrade-off |
|---|---|---|
| A | EVENT categoryだけ | 現在のready corpusをそのまま母集団にでき、初期検証を限定できる |
| B | MAIN / EVENT / RAID / CHARACTER等を最初から横断 | 最終像に近いが、category固有の時間軸と入力被覆を同時に設計する必要がある |
| C | categoryではなく、明示的なcross-story根拠で接続されたsubsetだけ | 根拠中心だが、全体coverageの定義が別途必要になる |

**採択: A。** EVENTで契約とreview運用を検証し、category追加は独立decisionにする。

## D2. 順序表現

| 候補 | 内容 | 主なtrade-off |
|---|---|---|
| A | partial order graph | 根拠の無い比較をunknownのまま保持できる |
| B | global integerによるtotal order | 表示は単純だが、比較不能・枝分かれ・同時性を無理に直列化しやすい |
| C | partial orderを正とし、review済み範囲だけ表示用sequenceを派生 | 正と表示を分離できるが、派生規則と再生成契約が必要になる |

**採択: A。** partial order graphを正とする。total orderや表示用sequenceは、partial orderのcoverageと利用目的が確認できた後に検討する。

## D3. 関係状態

少なくとも次を区別するか決める。

- `before`
- `after`
- `same_time`（明示的根拠がある場合だけ。値の一致から推定しない）
- `unknown`
- `conflict`

**採択: 5状態を分離する。** `unknown`と`conflict`を同じnullへ潰さない。

## D4. 許容するcross-story根拠

候補sourceごとに、candidate生成とcanonical昇格の可否を決める。

| source | candidate化 | canonical昇格の候補条件 |
|---|---|---|
| official | 許容候補 | 出典・対象・関係を直接または委任reviewで確認 |
| manual | 許容候補 | reviewerと根拠要約を記録 |
| ai_inferred | 許容候補または不採用 | confidenceだけで昇格せず、直接または委任reviewで根拠を確認 |
| script / rule-based | 許容候補または不採用 | 抽出規則とEvidenceを確認 |
| unknown | 保留 | sourceが解決するまで昇格しない |

**採択:** source種別にかかわらずcandidateとcanonicalを分離し、human-confirmed gateを必須とする。

2026-08-28のユーザー決定により、このgateは直接の個別確認に加え、ユーザーが明示委任したagent reviewを含む。委任reviewは、Normalized Story本文だけを根拠に親agentと独立監査agentが同じ関係を高信頼で支持し、根拠要約・Evidence・両者の一致を`humanDecision`へ記録できる場合に限る。reviewerは`user-delegated-agent-review`とする。固定の数値閾値は採択せず、日付、ファイル名、episode番号、配列順、story-local `canonicalOrder`は根拠にしない。

1 edgeごとのユーザー確認は行わない。結論不一致、低信頼、曖昧性、`unknown` / `conflict`、追加資料が必要な場合は確定せず、保留事項をbatch単位でユーザーへ確認する。検証済みinternal artifactへの可逆なlocal反映も同じ委任範囲に含めるが、公開、scope拡張、削除、rollback、既存canonical値の変更は含めない。

## D5. Review unitとpromotion gate

候補は少なくとも次の単位から選ぶ必要がある。

- 1 cross-story edgeずつreview
- 2 story間のedge集合をreview
- 1 connected componentをまとめてreview

**採択:** 2 story間の小さなedge集合を1 packetとし、`pending` / `confirmed` / `rejected` / `needs_more_context`をedge単位で記録する。packet validationやconfidence閾値だけでは自動promotionしない。

## D6. Internal / public出力

| 候補 | 内容 |
|---|---|
| A | canonical artifactとreview reportをinternal-onlyにする |
| B | canonical artifactはinternal、公開Wikiはreview済みprojectionだけを表示する |
| C | canonical artifact自体を公開する |

**採択: A。** public ID completeness、source表記、unknown/conflict表示、公開目的が別途決まるまで公開しない。

---

# 6. 採択した初期profile

2026-08-23のユーザー承認により、次の組み合わせを初期profileとして採択した。

```text
D1=A  EVENT限定
D2=A  partial order graph
D3=before/after/same_time/unknown/conflictを分離
D4=candidateとcanonicalを分離し、全sourceでhuman-confirmed gate必須（直接確認または明示委任review）
D5=2 story間の小さなedge集合をreview、edge単位status
D6=A  internal-only
```

この承認は、個別edgeの確定、global整数値の付与、total order化、category拡張、public表示を許可しない。§4の不変則を維持したまま、§8の段階を小さいPRで進める。

---

# 7. 採択記録

採択内容と、後続実装へ引き継ぐ境界は次の通り。

1. D1〜D6は§6のprofileを推奨どおり採択し、変更は無い
2. `story_manifest.yaml`はstory-local `canonicalOrder`の正として維持し、cross-story canonical artifactとは分離する
3. cross-story artifactはadditiveな専用契約とし、正確なschema・保存先・ID安定性は後続の設計・実装PRで合成fixtureとともに固定する
4. `same_time`は明示的根拠がある場合だけ採用し、`unknown` / `conflict`を欠落やnullへ潰さない
5. review packet、human decision、promotionを分離し、未委任では自動promotionしない
6. 初期artifactとreview reportはinternal-onlyとし、public projectionは別decisionまで実装しない
7. 現行v0.5 checkと`story_manifest.yaml`は破壊的に変更せず、必要なinventory機能をadditiveに実装する
8. 最初の実装検証は合成fixtureで行い、実edgeのreview段階でのみ承認済みlocal sampleを使う

---

# 8. 次段階

1. ~~**cross-story constraint inventory**~~: `scripts/build_cross_story_constraint_inventory.py`と専用v0.1 report schemaで、既存candidateを判定・変換せずprovenance付きの2 story単位review queueへ集計する。EVENT固定・internal-onlyで、現行v0.5は変更しない
2. ~~**canonical Timeline schema**~~: `schemas/canonical_timeline.schema.json` v0.1と`Canonical_Timeline_Schema.md`で、採択profileを合成fixtureだけで表現する。実node / edge、validator、CLI、review / promotion、保存先、公開は作らない
3. ~~**consistency check**~~: `agents/extractor/canonical_timeline_consistency.py`の純粋関数で、schema-validな単一documentのcross-story参照・完全重複record・canonical partial-order cycle / same-time矛盾・conflict provenanceを合成fixtureだけで検査する。実edge生成、CLI / report、review / promotionは行わない
4. **review / promotion tooling**:
   1. ~~**review packet contract**~~: `schemas/canonical_timeline_review_packet.schema.json`と`Canonical_Timeline_Review_Packet.md`で、2 distinct EVENT story、edge単位4 status、human decision、candidate provenance、internal-only / commit禁止を合成fixtureだけで固定する。実packet、CLI / validator、promotionは作らない
   2. ~~**read-only validator**~~: 固定workspace root内の既存packetをoffline schema・semantic・free-text境界で検証し、safe aggregateだけを出す。file / report write、retention、promotionは行わない
   3. ~~**review packet builder**~~: ユーザー決定（2026-08-27）の90日保持・期限切れwarningのみ・自動削除なしをv0.2 packetへ固定し、既存Stage A `relative_order`の1 story pairだけをpending packetへ変換するdefault dry-run / no-clobber builderを実装する
   4. ~~**promotion plan contract**~~: `schemas/canonical_timeline_promotion_plan.schema.json`と`Canonical_Timeline_Promotion_Plan.md`で、v0.2 packetのhuman-confirmedなknown relationだけを元edge・全provenance保持の`proposed_canonical_edge`へ写すlocal internal / plan-only契約を合成fixtureで固定する。builder / validator / CLI、canonical artifact write、promotion実行は作らない
   5. ~~**promotion plan projector / semantic validator**~~: 検証済みv0.2 packetの全適格edgeを非実行planへ決定的にdeep copyし、source packet / story pair / expiry / edge 1:1対応を純粋関数で検査する。CLI / file I/O、canonical artifact preflight / write、promotion実行は行わない
   6. ~~**promotion read-only preflight**~~: plan edgeをメモリ内だけで仮canonical化し、既存canonical Timelineへの追加時のcycle / same-time矛盾 / 完全重複をsafe aggregateで検査する。baseline不正はfail-closedとし、artifact write / adoptionは行わない
   7. ~~**promotion executor**~~: 固定ignored workspace内のplan / packetを再検証し、default dry-run、入力・現artifact digest pin、seed no-clobber、update lock / snapshot / atomic replaceでinternal canonical artifactへ反映する。実データ実行は行わない
5. ~~**small local sample**~~: 単独sample 2件と15回の小規模batchで40 relationをlocal artifactへ反映し、明示接続候補の初回走査を完了した。曖昧候補は確定せず、schema / semantic finding 0を維持する
6. ~~**public projection decision / schema / projector / preflight / renderer**~~: `../07_Wiki/Canonical_Timeline_Public_Projection_Decision.md`で2026-09-01に推奨P1〜P7を採択し、専用v0.1 schema、pure projector、cross-document validator、safe aggregate report、read-only preflight、`timelines/index.md` renderer、link checkを合成fixtureで固定した。詳細は`../07_Wiki/Canonical_Timeline_Public_Projection_Schema.md`、`../07_Wiki/Canonical_Timeline_Public_Projector.md`、`../07_Wiki/Canonical_Timeline_Public_Preflight.md`、`../07_Wiki/Canonical_Timeline_Public_Renderer.md`を参照。次はignored workspace local previewとmanual visual reviewである。実データ公開・hosting・deployは未許可

第1段階の運用契約は`docs/runbooks/Cross_Story_Constraint_Inventory.md`を正とする。現行rule-based extractorは通常`relative_order`を生成しない。2026-08-27のユーザー承認によりNormalized Storyをagentが読む小規模候補提示が、2026-08-28のユーザー委任により高信頼・親/独立監査一致時の確認済み記録とinternal local反映が許可された。曖昧・競合候補の確定、公開、および`agents/extractor/`へのLLM provider実装は許可されていない。

---

# 9. このDecisionの完了条件

- D1〜D6の選択肢、採択値、承認日が一か所で確認できる
- story-local値をglobalへ自動昇格しないfreezeが明記されている
- 禁止する代用根拠と、unknown / conflict / provenanceの不破棄が明記されている
- 現行v0.5、manifest、schema、CLI、Wikiの変更を含まない
- 実データ由来のID・タイトル・ファイル名・本文・pathを含まない

---

# 10. Non-goals

- 採択profileを別の人間判断なしに拡張・変更すること
- global値、cross-story edge、same-time classの実値作成
- 既存`canonicalOrder`の再採番、連番化、一意化
- `releaseOrder` / `displayOrder` / `episodeNumber`等からの補完
- 既存Timeline schema、v0.5 report schema / CLI、parser、merger、rendererの破壊的変更
- 実manifest、review packet、Normalized Story、Stage A、report、Wiki生成物のcommit
- canonical Timelineのpromotionまたは公開

---

# 11. 関連文書

- `docs/runbooks/Timeline_Consistency_Check.md`
- `docs/runbooks/Cross_Story_Constraint_Inventory.md`
- `docs/runbooks/Canonical_Order_Review.md`
- `docs/architecture/03_Data_Model/Canonical_Timeline_Schema.md`
- `docs/architecture/05_Parser/Story_Metadata.md` §OD-002
- `docs/architecture/05_Parser/Story_Manifest_Design.md` §13.4
- `docs/architecture/06_AI/Extraction_Pipeline.md` Timeline節
- `docs/architecture/06_AI/Merged_Knowledge_Design.md` §7
- `docs/architecture/07_Wiki/Timeline_Page.md`
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.11
