# Evidence Index Promotion Review（合成テンプレート）

このテンプレートは、Evidence Index候補（`workspace/evidence_index_dry_runs/.../stories`）を
`knowledge/evidence/stories/`へ昇格する前の人間レビュー記録の見本である。**このファイル自体は
合成の空欄テンプレートであり、実施結果の記入・commitはしないこと。** 実施結果は各自のローカル・
社内共有ドライブ等、commit対象外の場所へ記録する
（`docs/runbooks/Evidence_Index_Promotion_Check.md` §7参照）。

記入時の注意（`docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md` §12参照）:

- 記録してよいもの: story/episode/entry件数、type別件数、check結果（PASS/FAIL）、見つかった問題（抽象化した説明）
- 記録してはいけないもの: 実イベント名・実キャラ名、実セリフ・raw DEC本文、ローカル絶対パス、実データ由来Evidence Index YAML全文

---

## Target

- Source directory:
- Target storyId:
- publicStoryId:
- Generated at:
- Reviewed at:
- Reviewer:

## Validation

- [ ] schema validation passed
- [ ] validate_evidence_index.py passed
- [ ] check_evidence_index_promotion.py passed
- [ ] source text exposure check passed
- [ ] render_wiki.py --evidence-index passed
- [ ] mkdocs build --strict passed

## Entry Summary

- Story count:
- Episode count:
- Entry count:
- Entries by type:
  - dialogue:
  - monologue:
  - narration:
  - choice:
  - unknown:
  - stage_direction:

## Public Type Policy

- [ ] Only public-default types are included
- [ ] stage_direction is absent or explicitly justified
- [ ] scene/episode/story/speaker_label are absent or explicitly justified

## Source Text Exposure

- [ ] no raw DEC text
- [ ] no raw dialogue text
- [ ] no raw command
- [ ] no local absolute path
- [ ] no `.dec`
- [ ] no `$num`
- [ ] no `<script>`

## Summary Evidence Refs

- [ ] reviewed/approved summary evidenceRefs resolved
- [ ] unresolved refs reviewed
- [ ] stage_direction refs reviewed

## Decision

- [ ] Approved for promotion
- [ ] Needs revision
- [ ] Rejected

## Notes
