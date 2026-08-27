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

本executorは合成fixtureだけで検証しており、実データでは実行していない。promotion plan builder CLI、review結果の自動import、自動promotion、複数plan統合、実artifactのcommit、EVENT外、public projectionは対象外である。

```powershell
uv run pytest tests/scripts/test_apply_canonical_timeline_promotion.py
```
