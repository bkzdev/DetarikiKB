# DKB v1 Release Record

Status: Released
Decision date: 2026-09-21
Decision owner: repository owner（human）

## Candidate

- Source SHA: `a18122cb1ae8e196d1b5bdf4de0fc77061453277`
- Lock SHA-256: `8cdc81c9895a242563ddf8a9818dee2c578df303b5b215802eaef74000399f35`
- Reviewed public input SHA-256: `182f170fef1aa29566c7eb64c40fa8549155234d2d00bb49c68ffe9da5a887fe`
- Validation completed: 2026-09-21
- Public URL: <https://bkzdev.github.io/DetarikiKB/>

release scopeはMAIN 213、EVENT 537、RAID 62、CHAR_MAIN 216、CHAR_EXTRA 220、
CHAR_DATE 859、CHAR_HS 733の合計2,840 episodeである。raw / private artifact、
未レビューのpublic contentは公開対象外とし、公開siteはcommit済みreviewed public inputだけから
生成した。

## Milestone gate evidence

| Gate | Result | Evidence |
|---|---|---|
| M1 | PASS | [PR #308](https://github.com/bkzdev/DetarikiKB/pull/308)、[main CI](https://github.com/bkzdev/DetarikiKB/actions/runs/35536996124) |
| M2 | PASS | 2,840 episode、invalid / skipped 0、candidate SHA束縛済み |
| M3 | PASS | extraction / merge invalid / skipped 0、4,778 entity、candidate SHA束縛済み |
| M4 | PASS（reviewable） | 4領域すべて`reviewable: true`、Timeline finding 0 |
| M5 | PASS | 2026-09-21にhumanが公開Landing→Canonical Timeline→Story導線を目視確認 |
| M6 | PASS | [Public Build](https://github.com/bkzdev/DetarikiKB/actions/runs/35536996132)、[protected production](https://github.com/bkzdev/DetarikiKB/actions/runs/35585381055) |

M2匿名report SHA-256は
`f550157140288df0567fbaf4898aec2ca5b8a11c6cb766a125e7ed81f6671d5b`、M3匿名reportは
`eb79814e1fd16672f51de67ca2939af371dda1dc22ba6f666fb491c539910ceb`、M4匿名reportは
`20521de32fa3a3814efa83a86249acae03b184b89b41856d2308c39707034c80`である。
実artifactと個別対応は既存方針どおりignored workspace限定とし、commitしていない。

## Local rehearsal public build

- Dual build route count: 139
- MkDocs manifest SHA-256: `55d633f7ba1f3a5941d9a8b59e7369c7aa06858f94220a82cb1a18b09c6ab190`
- MkDocs tree SHA-256: `1553e8944b8c6f8af8671bcbfc29dfca3f6f9bac8f260df851ab6b8907c24374`
- Zensical manifest SHA-256: `171e0c8c968d9d0cdb99b7e902c63bd48b0810fa8b70d2ec8dbc4f87f0844aff`
- Zensical tree SHA-256: `59e07e25d53fac86bb2356d418f7ca4d86b52d1a0bf8072c0d2e30d95e8e3b66`

これらはWindows上のcandidate rehearsal recordが固定したdigestである。hosted Linux buildの
manifest / tree digestとは実行環境が異なるため混用せず、production rollbackには以下の
production job出力を使用する。

## Hosted production

- Production workflow: [35585381055](https://github.com/bkzdev/DetarikiKB/actions/runs/35585381055)（preflight / protected environment / deploy success）
- GitHub Pages deployment: candidate SHAと一致
- Production Zensical manifest SHA-256: `cc578d0a27664bb8821326f6eadad5838beace00e1921eeb410da74a2d8b269f`
- Production Zensical tree SHA-256: `eebbd70af0916ec5d7c0108757cd0092ce9b55d1a8a797018d6d11aa26f11c74`
- Post-deploy check: Landing、Canonical Timeline、代表Story 5 routeがHTTP 200

## Known non-blocking state

M4の`fullyConfirmed`はfalseである。canonical ID、Character Profile、story内順序、
story間Timelineにはreview可能な保留が残るが、黙示破棄、schema / semantic error、公開対象への
内部情報露出ではない。確定済み情報だけをpublic projectionへ含め、保留情報はinternal artifactに
保持する既存境界を満たすため、v1 releaseのblocking条件には該当しない。

## Rollback and decision

通常rollback先を本candidateへ更新する。

- Rollback source SHA: `a18122cb1ae8e196d1b5bdf4de0fc77061453277`
- Rollback Zensical tree SHA-256: `eebbd70af0916ec5d7c0108757cd0092ce9b55d1a8a797018d6d11aa26f11c74`
- Rollback workflow run: [35585381055](https://github.com/bkzdev/DetarikiKB/actions/runs/35585381055)

Final decision: **released**。M1〜M6、同一candidate SHAの再生成・品質・code・public gate、
人間目視、protected production承認、post-deploy確認、rollback記録を満たしたため、M7を完了とする。
