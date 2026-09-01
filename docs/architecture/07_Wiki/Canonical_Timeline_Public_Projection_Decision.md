# Canonical Timeline Public Projection Decision（公開表示判断枠）

Version: 0.1
Status: Accepted
Decision date: 2026-09-01
Project: Detariki Knowledge Base (DKB)

---

# 1. 目的

internal-onlyのCanonical Timelineから、公開Wikiへ安全に投影する場合の目的・対象・表示粒度・未解決状態・失敗時境界を一枚に集約する。

2026-09-01のユーザー継続指示により、§5の推奨初期profileを一括採択した。採択はpublic projectionの設計と合成fixture実装へ進む許可であり、実データ公開、hosting、deploy、既存URL変更、個別relationの公開承認を意味しない。

---

# 2. 現在確定している境界

- Canonical TimelineはEVENT限定のpartial order graphである
- internal artifactでは`before` / `after` / `same_time` / `unknown` / `conflict`を分離し、provenanceを不破棄保持する
- canonical edgeはhuman-confirmed gateとadoption状態を満たす必要がある
- story-local `canonicalOrder`、日付、番号、ファイル名、配列順、release/display順はcross-story順序の代用根拠にしない
- internal artifactとreview資料はcommitせず、公開用IDとpublic-safe projectionを別契約にする
- 明示接続候補の初回走査と15回の小規模batch運用を終え、40関係を矛盾0でlocal artifactへ保持している

この運用実績と本Decisionの採択は公開の安全性を自動的に保証しない。公開対象Story/Episodeのpublic ID completeness、本文・内部IDの非露出、unknown/conflictの読者向け表現は、§3とP1〜P7のgateを実装・検証して初めてpublish-readyになる。

---

# 3. 公開projectionの不変則

1. internal canonical artifactをそのまま公開しない
2. 公開対象を「全時系列」や「完全な年表」と表現しない
3. partial orderに無い隣接、順位、期間、日付を補完しない
4. `unknown` / `conflict`を既知relationへ変換せず、internal artifactから削除しない
5. raw本文、Evidence ID、candidate ID、内部story / episode ID、local path、digestを公開出力へ含めない
6. 公開対象の両端にpublic IDと公開可能な表示名が揃わないrelationはfail-closedで除外する
7. 除外・保留件数はpublic-safe aggregate reportへ残し、projection処理中に黙って消さない
8. semantic finding、ID衝突、内部値露出、source不整合が1件でもあればpublish-readyにしない

---

# 4. 判断項目

## P1. 公開目的

| 候補 | 内容 |
|---|---|
| A | 確認済みの出来事間関係を辿る補助導線。網羅的な年表ではない |
| B | EVENT全体の代表的な時系列を一つの年表として提示する |
| C | internal review状況や未解決候補を含む監査dashboardを公開する |

**採択: A。** 現行artifactはpartial orderであり、Bは根拠のない総順序を読者へ暗示する。Cは内部provenanceやreview状態の公開境界を広げるため初期公開に適さない。

## P2. relationの公開適格性

| 候補 | 内容 |
|---|---|
| A | canonical adoption済みの`before` / `after` / `same_time`だけを対象にする |
| B | confirmedだが未adoptionのrelationも対象にする |
| C | candidate、`unknown`、`conflict`まで個別relationとして表示する |

**採択: A。** さらに両端が公開対象EVENTであり、public Story/Episode IDとpublic-safe labelが揃い、projection時のschema・semantic・exposure検査に合格することを必須とする。

## P3. partial orderの表示粒度

| 候補 | 内容 |
|---|---|
| A | 確認済みrelationを1件ずつ表示し、connected component単位で緩くまとめる |
| B | topological sortで一本の一覧へ並べる |
| C | 各Storyへglobal rankを付ける |

**採択: A。** relationの矢印は根拠のある両端だけを結び、画面上の上下や隣接を追加relationとして扱わない。component間の順序は表示しない。`same_time`は明示根拠があるrelationだけを「同時期」と表示する。

## P4. `unknown` / `conflict`の読者向け表現

| 候補 | 内容 |
|---|---|
| A | 個別の両端や内部理由は表示せず、ページ冒頭で未確定・競合関係が公開年表に含まれないことを説明し、public-safe aggregateだけを任意表示する |
| B | 個別のStory pairと保留理由を公開する |
| C | 存在自体を説明せず、公開対象から除外する |

**採択: A。** 「不明情報を破棄しない」はinternal canonical artifactで維持する。公開projectionでは内部情報を漏らさず、除外が網羅性の欠落であることだけを明示する。aggregateは0件を含め決定的に生成し、個別ID・本文・理由・provenanceを含めない。

## P5. 表示するsourceとlabel

| 候補 | 内容 |
|---|---|
| A | public ID、公開表示名、relation label、短い定型注記だけを表示する |
| B | evidence本文やconfidenceを併記する |
| C | internal candidate / review metadataも表示する |

**採択: A。** 初期projectionは`before`を「この出来事より前」、`after`を「この出来事より後」、`same_time`を「同時期」とする定型labelへ写す。自由記述のreason、confidence、reviewer、candidate provenanceは公開しない。根拠導線が必要な場合は、別途public-safe Evidence Indexとの接続を設計する。

## P6. pageとURL

| 候補 | 内容 |
|---|---|
| A | 既存設計の`timelines/index.md`を使い、確認済みcross-story relation専用ページとする |
| B | Story page内だけにrelationを分散表示する |
| C | 新しいURLを追加し、既存Timeline pageと並存させる |

**採択: A。** 初期版は単一集約ページとし、Story pageへの逆リンクは後続判断とする。既存`entities.timeline`由来の「観測されたstory-local順序情報」と混在させず、renderer sourceをCanonical Timeline public projectionへ切り替える実装計画を別PRで決める。本Decisionだけでは現行placeholderとURLを変更しない。

## P7. publish gateとrollback

| 候補 | 内容 |
|---|---|
| A | projection生成をfail-closedにし、検証済み生成物だけを公開workflowへ渡す |
| B | relation単位のwarningを出し、残りをbest-effortで公開する |

**採択: A。** 最低限、input digest pin、canonical schema / semantic valid、adoption適格性、public ID completeness、一意性、内部値露出0、出力schema valid、決定性を必須gateとする。失敗時は現行公開物を変更せず、前回検証済みdeployへ戻せることを公開workflowの受入条件にする。

---

# 5. 採択した初期profile

2026-09-01のユーザー継続指示により、初期profileを次の組み合わせで採択した。

```text
P1=A  確認済み関係を辿る補助導線
P2=A  adoption済みknown relationのみ
P3=A  relation / connected component表示、総順序化なし
P4=A  unknown/conflictは個別非公開、制約説明とsafe aggregateのみ
P5=A  public ID・public label・定型relation labelのみ
P6=A  timelines/index.mdの単一集約ページ
P7=A  fail-closed publish gateと検証済みrollback
```

採択はpublic projectionの設計・合成fixture実装へ進む許可であり、実データ公開、ホスティング開始、既存URL変更、個別relationの公開承認を意味しない。

---

# 6. 採択後の段階案

1. public projection schemaとinternal→publicのfield allowlistを合成fixtureだけで固定する
2. 入力不変・決定的なpure projectorとpublic-safe aggregate reportを実装する
3. public ID completeness、内部値露出、schema / semantic整合を検査するread-only preflightを実装する
4. 合成fixtureで`timelines/index.md` rendererとlink checkを実装する
5. ignored workspaceの匿名aggregateを用いたlocal previewとmanual visual reviewを行う
6. public publishing workflow、deploy gate、rollbackを別decisionで採択する

各段階は小さいPRに分ける。実artifactや公開生成物は、公開workflowが別途採択されるまでcommit・deployしない。

---

# 7. 採択記録

P1〜P7は個別に分割せず、推奨Aを一括採択した。

1. P1=A: 確認済み関係を辿る補助導線
2. P2=A: adoption済みknown relationだけを公開適格とする
3. P3=A: relation / connected component表示とし、総順序化しない
4. P4=A: unknown / conflictは個別非公開とし、制約説明とsafe aggregateだけを許容する
5. P5=A: public ID・public label・定型relation labelだけを表示する
6. P6=A: `timelines/index.md`の単一集約ページを使用する
7. P7=A: fail-closed publish gateと検証済みrollbackを必須とする

この採択により§6の第1段階へ進める。実データを用いるlocal preview、個別relationの公開、hosting / deploy、既存公開物の変更は、それぞれの後続gateを満たすまで開始しない。

---

# 8. Non-goals

- 本Decisionだけを根拠にした実データ公開・hosting・deploy
- canonical Timeline schema、artifact、review packet、promotion planの変更
- projector、validator、renderer、CLI、page、URLの実装
- public IDの採番・割当・Registry変更
- Story / Episode / Evidence pageの変更
- individual edge、unknown、conflict、provenance、本文の公開
- 実データ由来artifact、packet、plan、report、Wiki生成物のcommit
- hosting、deploy、rollbackの実行

---

# 9. 関連文書

- `../03_Data_Model/Canonical_Timeline_Scope_Decision.md`
- `../03_Data_Model/Canonical_Timeline_Schema.md`
- `Timeline_Page.md`
- `Wiki_Output_Design.md`
- `../06_AI/Public_ID_Registry_Design.md`
- `../../runbooks/Canonical_Timeline_Promotion.md`
- `../../runbooks/AI_PR_Playbook.md`
