# Canonical Timeline Scope Decision（global chronology判断枠）

Version: 0.1
Status: Proposed — 実装前に人間判断が必要
Decision date: Pending
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

story内の`canonicalOrder`付与と全EVENT corpusのreadiness確認が完了した後、cross-story chronologyやcanonical Timelineへ進む前に必要な判断を一枚へ集約する。

本書はglobal chronologyの値・順序・公開可否を決定しない。現行仕様を安全側で維持しながら、次の実装を開始できる条件、選択肢、推奨初期案、review gateを明確にするためのDecision Record候補である。

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

人間が本書の判断事項を確定するまで、既存`canonicalOrder`は**運用上story-localな順序値**として扱う。数値が同じ、隣接する、または大小関係を持つことをstory間の前後・同時性の根拠にしない。

これは将来のglobal表現を禁止する恒久決定ではない。未確定の値域を誤ってglobalへ昇格させないためのfreezeである。

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

# 4. 判断前に維持する不変則

1. 既存`canonicalOrder`の数値をstory間で比較しない
2. `releaseOrder` / `displayOrder` / `episodeNumber`、manifest配列順、ファイル名、ID、タイトルをglobal chronologyの補完根拠にしない
3. `cross_story_constraint`を黙って比較・削除・winner選択せず、candidate・Evidence・`extractionRun`を保持する
4. unknownとconflictを欠落扱いにせず、保留理由とprovenanceを保持する
5. AI候補、機械抽出、review済みcanonical関係を同じstatusで扱わない
6. internal review artifactとpublic表示を分離し、公開許可前にcanonical Timelineとして表示しない
7. schema・CLI・既存manifest・v0.5 report・Wiki rendererは、後続の採択・実装PRまで変更しない

---

# 5. 人間が決める事項

## D1. 初期global scope

| 候補 | 内容 | 主なtrade-off |
|---|---|---|
| A | EVENT categoryだけ | 現在のready corpusをそのまま母集団にでき、初期検証を限定できる |
| B | MAIN / EVENT / RAID / CHARACTER等を最初から横断 | 最終像に近いが、category固有の時間軸と入力被覆を同時に設計する必要がある |
| C | categoryではなく、明示的なcross-story根拠で接続されたsubsetだけ | 根拠中心だが、全体coverageの定義が別途必要になる |

**推奨初期案: A。** EVENTで契約とreview運用を検証し、category追加は独立decisionにする。

## D2. 順序表現

| 候補 | 内容 | 主なtrade-off |
|---|---|---|
| A | partial order graph | 根拠の無い比較をunknownのまま保持できる |
| B | global integerによるtotal order | 表示は単純だが、比較不能・枝分かれ・同時性を無理に直列化しやすい |
| C | partial orderを正とし、review済み範囲だけ表示用sequenceを派生 | 正と表示を分離できるが、派生規則と再生成契約が必要になる |

**推奨初期案: A。** total orderや表示用sequenceは、partial orderのcoverageと利用目的が確認できた後に検討する。

## D3. 関係状態

少なくとも次を区別するか決める。

- `before`
- `after`
- `same_time`（明示的根拠がある場合だけ。値の一致から推定しない）
- `unknown`
- `conflict`

**推奨初期案: 5状態を分離する。** `unknown`と`conflict`を同じnullへ潰さない。

## D4. 許容するcross-story根拠

候補sourceごとに、candidate生成とcanonical昇格の可否を決める。

| source | candidate化 | canonical昇格の候補条件 |
|---|---|---|
| official | 許容候補 | 出典・対象・関係を人間確認 |
| manual | 許容候補 | reviewerと根拠要約を記録 |
| ai_inferred | 許容候補または不採用 | confidenceだけで昇格せず、人間が根拠を確認 |
| script / rule-based | 許容候補または不採用 | 抽出規則とEvidenceを確認 |
| unknown | 保留 | sourceが解決するまで昇格しない |

**推奨初期案:** source種別にかかわらずcandidateとcanonicalを分離し、human-confirmed gateを必須とする。

## D5. Review unitとpromotion gate

候補は少なくとも次の単位から選ぶ必要がある。

- 1 cross-story edgeずつreview
- 2 story間のedge集合をreview
- 1 connected componentをまとめてreview

**推奨初期案:** 2 story間の小さなedge集合を1 packetとし、`pending` / `confirmed` / `rejected` / `needs_more_context`をedge単位で記録する。packet validationやconfidence閾値だけでは自動promotionしない。

## D6. Internal / public出力

| 候補 | 内容 |
|---|---|
| A | canonical artifactとreview reportをinternal-onlyにする |
| B | canonical artifactはinternal、公開Wikiはreview済みprojectionだけを表示する |
| C | canonical artifact自体を公開する |

**推奨初期案: A。** public ID completeness、source表記、unknown/conflict表示、公開目的が別途決まるまで公開しない。

---

# 6. 推奨初期profile（未採択）

本書作成時点の推奨は次の組み合わせである。

```text
D1=A  EVENT限定
D2=A  partial order graph
D3=before/after/same_time/unknown/conflictを分離
D4=candidateとcanonicalを分離し、全sourceでhuman-confirmed gate必須
D5=2 story間の小さなedge集合をreview、edge単位status
D6=A  internal-only
```

このprofileは**未採択**であり、実装指示ではない。人間が明示的に採択・修正するまでは§4のfreezeを維持する。

---

# 7. 採択時に記録する内容

Decision Recordを`Status: Accepted`へ変更する際は、次を同じcommitに記録する。

1. D1〜D6の採択値と、推奨から変更した理由
2. canonical artifactのsource of truthとschema owner
3. ID・node・edgeの安定性契約
4. unknown / conflict / same-timeの保存・表示規則
5. review packet、reviewer、review日時、promotionの責務分離
6. internal/public境界と、公開を再評価するgate
7. 既存v0.5 checkと`story_manifest.yaml`を変更するか、additiveに維持するか
8. 最初の合成fixtureと、必要なら承認済みlocal sampleの範囲

---

# 8. 採択後の段階案

1. **cross-story constraint inventory**: 判定せず、既存candidateをprovenance付きで集計してreview queueを作る
2. **canonical Timeline schema**: 採択profileを合成fixtureだけで表現する
3. **consistency check**: partial order、same-time、unknown、conflictの不変則を検査する
4. **review / promotion tooling**: default dry-run、no-clobber、human-confirmed gateでcanonical artifactへ反映する
5. **small local sample**: 承認済みcross-story根拠だけでend-to-end検証する
6. **public projection decision**: internal artifact完成後、公開目的とpublic-safe要件を別途判断する

現行rule-based extractorは通常`relative_order`を生成しない。実データinventoryが空の場合、自然文からの自動推定器を先に実装せず、合成fixtureで契約を固定した上で承認済み根拠の入手方法を判断する。

---

# 9. このDecision Frameの完了条件

- D1〜D6の選択肢、推奨初期案、採択条件が一か所で確認できる
- story-local値をglobalへ自動昇格しないfreezeが明記されている
- 禁止する代用根拠と、unknown / conflict / provenanceの不破棄が明記されている
- 現行v0.5、manifest、schema、CLI、Wikiの変更を含まない
- 実データ由来のID・タイトル・ファイル名・本文・pathを含まない

---

# 10. Non-goals

- D1〜D6の採択
- global値、cross-story edge、same-time classの実値作成
- 既存`canonicalOrder`の再採番、連番化、一意化
- `releaseOrder` / `displayOrder` / `episodeNumber`等からの補完
- Timeline schema、report schema、parser、extractor、merger、checker、rendererの変更
- 実manifest、review packet、Normalized Story、Stage A、report、Wiki生成物のcommit
- canonical Timelineのpromotionまたは公開

---

# 11. 関連文書

- `docs/runbooks/Timeline_Consistency_Check.md`
- `docs/runbooks/Canonical_Order_Review.md`
- `docs/architecture/05_Parser/Story_Metadata.md` §OD-002
- `docs/architecture/05_Parser/Story_Manifest_Design.md` §13.4
- `docs/architecture/06_AI/Extraction_Pipeline.md` Timeline節
- `docs/architecture/06_AI/Merged_Knowledge_Design.md` §7
- `docs/architecture/07_Wiki/Timeline_Page.md`
- `docs/architecture/07_Wiki/Wiki_Output_Design.md` §9.11
