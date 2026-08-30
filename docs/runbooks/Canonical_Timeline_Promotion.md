# Canonical Timeline Promotion

対象: internal canonical Timelineへの明示的なlocal反映

実装: `scripts/apply_canonical_timeline_promotion.py`

## 目的と保存先

検証済みpromotion planと元review packetを再検証し、`workspace/canonical_timeline/canonical_timeline.json`へ反映する。artifact、plan、packet、`history/` snapshotはlocal internalであり、Gitへcommitしない。defaultはdry-runで、preflight PASSやconfirmed reviewだけでは書き込まない。

入力は固定rootのbasenameだけを受け付ける。

- plan: `workspace/canonical_timeline/plans/`
- packet: `workspace/review_packets/canonical_timeline/`
- history: `workspace/canonical_timeline/history/`

## Dry-run

```powershell
uv run python scripts/apply_canonical_timeline_promotion.py `
  --plan-name canonical_timeline_plan_example.json `
  --packet-name canonical_timeline_review_example.json
```

出力されるplan / packet / current / proposedのSHA-256とnode / edge件数を確認する。内部ID、path、raw text、provenance本文は標準出力へ出さない。

## Seedとupdate

初期seedは`--create-seed --execute`と、dry-runで得た`--expected-plan-sha256` / `--expected-packet-sha256`を必須とする。既存artifactがあればno-clobberで拒否する。

updateは`--execute`、2つの入力digestに加え、`--expected-artifact-sha256`を必須とする。executorは排他lock取得後にartifact / plan / packetを再読込・再検証し、read-only preflightを再実行する。旧artifactをdigest名で`history/`へno-clobber保存し、境界とdigestを再確認してからatomic replaceする。

```powershell
uv run python scripts/apply_canonical_timeline_promotion.py `
  --plan-name canonical_timeline_plan_example.json `
  --packet-name canonical_timeline_review_example.json `
  --execute `
  --expected-plan-sha256 <dry-run value> `
  --expected-packet-sha256 <dry-run value> `
  --expected-artifact-sha256 <current value>
```

## 失敗と復旧

schema / semantic / preflight / digest / lock / path境界の不一致は反映前にfail-closedする。seed publish後またはupdate replace後の一時file / lock cleanup失敗は、artifactが反映済みなのでexit 0と`seed-applied-*` / `update-applied-*` warningを返す。warning時は表示されたproposed digestとartifactを照合し、残存lock / tempを人が確認する。自動削除、自動rollbackしない。snapshotは自動cleanupせず保持する。

atomic replaceはprocess間の可視性を守るが、電源断まで含むdirectory durabilityを保証するものではない。復旧時もdigestとsnapshotを確認し、明示承認なしにrollbackしない。

期限切れpacketはwarning-onlyで、自動削除・自動却下・承認取消しをしない。期限状態だけでpromotionを許可することもない。

## 現在の境界

executor本体は合成fixtureで検証する。実データ由来のartifact、packet、planはlocal ignored workspaceだけに保持し、commitしない。promotion plan builder CLI、review結果の自動import、自動promotion、複数plan統合、EVENT外、public projectionは対象外である。

## 初回小規模sample（2026-08-28）

Normalized Story本文だけを根拠として、先行事件の未解決予告と後続事件冒頭の継続状態が明確につながる2 EVENT storyを選定した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`はcross-story関係の根拠に使用していない。親agentと独立agentの一致を内部IDなしで説明し、ユーザーの明示承認後に`before` 1件をconfirmed review packetへ記録した。

packetのschema / semantic / free-text検証と期限確認、promotion planのprojection / preflight、executor dry-runを順に通した。dry-runで得たplan / packet digestを明示指定して初期seedを実行し、書込後artifactが候補digestと一致することを確認した。結果は2 nodes / 1 edge、schema error 0、semantic finding 0だった。

packet、plan、artifactは固定ignored workspaceへだけ保存し、実story / episode / Evidence ID、本文、path、digestは文書化・commitしていない。追加候補の自動抽出、2件目以降のedge、総順序化、公開は行っていない。

## 2件目と委任review（2026-08-28）

先行事件の帰還後、後続事件が同じ異常の再発・症状の二回目・前回の装置と来訪記憶を明示する2 EVENT storyを選定した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。親agentと独立監査agentが`before`をconfidence 0.99で支持し、ユーザーの関係承認と今後の高信頼review委任に基づいてconfirmed packetへ記録した。

packet validation、plan projection、既存artifactへのdry-run / preflightを通し、固定digestを指定してlocal updateを実行した。旧artifactはhistoryへsnapshotされ、更新後は4 nodes / 2 edges、schema error 0、semantic finding 0である。packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。

以後、親agentと独立監査agentが一致する高信頼relationは同じ委任reviewを使い、1 edgeごとのユーザー確認を行わない。固定の数値閾値は採択しない。不一致、低信頼、曖昧、`unknown` / `conflict`は保留してbatchで確認する。公開、scope拡張、削除、rollback、既存canonical値の変更は委任範囲外である。

## 初回小規模batch（2026-08-28）

過去の来訪・研修、前回と同じ対処方法、帰還前の交流を後続事件が具体的に参照する3組をまとめてreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持し、曖昧・競合・追加資料要求は0だった。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

3組を別々のv0.2 packet / planへ保持し、各packetのschema / semantic / free-text検証、planのbuilder一致 / semantic検証、現artifactへのdry-run / preflightを順に通した。digest pin付きlocal updateを1組ずつ実行し、毎回直前artifactをhistoryへsnapshotした。最終結果は10 nodes / 5 edges、schema error 0、semantic finding 0である。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。relationの統合・推移edge生成、総順序化、EVENT外拡張、public projectionは行っていない。

## 2回目の小規模batch（2026-08-28）

前回の共同戦線、活動再開時の固有発言、前回と同じ制作担当を後続事件が具体的に参照する3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持し、曖昧・競合・追加資料要求は0だった。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

候補探索時に既存story pairと重複する1組を検出したため、その追加観測はfinal artifactへ重ねず、未登録の明示接続1組へ差し替えた。これは同一batch内の未完了追加の是正であり、作業開始時の既存5 canonical edgeは変更・rollbackしていない。除外前の中間artifactも内容digest名のhistory snapshotとして復元し、過程を不破棄保持した。最終3組は別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通し、digest pin付きlocal updateを実行した。final artifactは16 nodes / 8 edges、8 distinct story pair、schema error 0、semantic finding 0である。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。既存canonical値の変更、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 3回目の小規模batch（2026-08-28）

同じ選挙企画における開始直後から一定期間後、コンセプトカフェの設置から開店後、後半対決の予告から実現へ進む3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持し、曖昧・競合・追加資料要求は0だった。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存8 story pairとの重複がないことをpacket作成前に確認し、3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは22 nodes / 11 edges、11 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存16 nodes / 8 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 4回目の小規模batch（2026-08-28）

同じ投票の開始から参加者のアピール施策、周年会場トラブルの解決からその直接回顧、首謀者の再会予告から前回襲撃を踏まえた再接触へ進む3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持し、曖昧・競合・追加資料要求は0だった。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存11 story pairとの重複がないことをpacket作成前に確認し、3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは28 nodes / 14 edges、14 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存22 nodes / 11 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 5回目の小規模batch（2026-08-29）

異世界来訪者の帰還から同じ来訪者の再来訪、カフェ運営から同じスタッフとの再協力、会場に出現した敵が囮と判明した未解決状態から本命捜索へ直接続く3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持した。一方、題材と人物だけが共通し出来事自体を参照しない別候補1組は`unknown`として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存14 story pairとの重複がないことをpacket作成前に確認し、採用3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは34 nodes / 17 edges、17 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存28 nodes / 14 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 6回目の小規模batch（2026-08-29）

転送光に巻き込まれた状態から孤島転送後、未知の敵の逃走からその作戦会議、拘束した元敵対者の受入れから帰属意識の変化へ進む3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持した。一方、共通題材だけで出来事自体を結ぶ本文根拠がない別候補1組は`unknown`として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存17 story pairとの重複がないことをpacket作成前に確認し、採用3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは40 nodes / 20 edges、20 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存34 nodes / 17 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 7回目の小規模batch（2026-08-29）

倫理観を崩す敵への対策完了から同じ敵・装備・担当者による再対策、無人島での特殊な敵への直接出動から同じ場所への再派遣、人気投票二位・三位の贈呈からその内容を回収した一位の贈呈へ進む3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持した。一方、シリーズ内の状態継承は支持されるが当該先行事件の直接回収について評価が一致しない別候補1組は`needs_more_context`相当として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存20 story pairとの重複がないことをpacket作成前に確認し、採用3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは46 nodes / 23 edges、23 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存40 nodes / 20 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 8回目の小規模batch（2026-08-29）

前回事件で固有の当事者2名を、後続事件が前回の同種事件の当事者として同時に具体名で回収する1組をreviewした。親agentと独立監査agentが`before`を高信頼で支持した。一方、共通人物・題材や複数の既往事件までは支持されるものの、直接の先行事件を一意に特定できない別候補5組は`needs_more_context`相当として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存23 story pairとの重複がないことをpacket作成前に確認し、採用1組をv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは48 nodes / 24 edges、24 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存46 nodes / 23 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 9回目の小規模batch（2026-08-29）

以前の身体縮小を原因とする再発、総選挙で登場した固有呼称の衣装の再登場、デビュー公演直前の衣装破損とリーダーへの叱咤の具体的な回想へ進む3組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持した。一方、相互の出来事を参照しない、当事者を一意に結べない、参照先が別事件である別候補3組は`needs_more_context`相当として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存24 story pairとの重複がないことをpacket作成前に確認し、採用3組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは54 nodes / 27 edges、27 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存48 nodes / 24 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 10回目の小規模batch（2026-08-30）

初代アイドルユニットの結成から、その成功を前提とする後継ユニット結成と初代ユニット再始動へ進む2組、前回総選挙の店舗企画を次回企画が具体的に回想する1組、異世界一行の初回来訪時の交流を再来時に具体的に回想する1組、周年記念中の事件を翌周年に明示回想する1組の計5組をreviewした。全組で親agentと独立監査agentが`before`を高信頼で支持した。一方、季節題材と当事者の一部は共通するが相互参照がない別候補1組は`unknown`として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存27 story pairとの重複がないことをpacket作成前に確認し、採用5組を別々のv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal updateでは共有済みepisode nodeを再利用し、final artifactは60 nodes / 32 edges、32 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存54 nodes / 27 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

## 11回目の小規模batch（2026-08-30）

先行事件でデビューしたアイドルユニットを、後続事件が既存の複数ユニットの一つとして具体名で比較する1組をreviewした。親agentと独立監査agentが`before`を高信頼で支持した。一方、周年番号・企画名・共通人物だけでは出来事を直接接続できない、または両agentの評価が一致しない別候補5組は`unknown`として確定せず、packet化・反映から除外した。日付、番号、ファイル名、配列順、story-local `canonicalOrder`は根拠に使用していない。

既存32 story pairとの重複がないことをpacket作成前に確認し、採用1組をv0.2 packet / planとしてschema / semantic / free-text検証、builder一致、dry-run / preflightを通した。digest pin付きlocal update後のfinal artifactは62 nodes / 33 edges、33 distinct story pair、schema error 0、semantic finding 0である。作業開始時の既存60 nodes / 32 edgesは内容不変でhistoryへsnapshotした。

packet、plan、artifact、snapshotはignored workspaceだけに保持し、実story / episode / Evidence ID、本文、path、digestはcommitしていない。保留候補の自動確定、既存canonical値の変更・rollback、relation統合、総順序化、EVENT外拡張、public projectionは行っていない。

```powershell
uv run pytest tests/scripts/test_apply_canonical_timeline_promotion.py
```
