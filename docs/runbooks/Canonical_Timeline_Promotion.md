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

```powershell
uv run pytest tests/scripts/test_apply_canonical_timeline_promotion.py
```
