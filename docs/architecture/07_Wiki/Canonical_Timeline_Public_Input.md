# Canonical Timeline Public Input

Version: 0.1
Status: Implemented
Updated: 2026-09-04

---

# 1. 目的

trusted localで生成・検査・人間確認したCanonical Timeline public projectionを、hosted buildが読めるcommit済みpublic-safe入力へ昇格する境界を固定する。internal canonical artifactの縮小copyではなく、既存`canonical_timeline_public_projection`をpayloadとする公開専用envelopeである。

本契約の`approved_for_build`は、push前reviewを通過してbuild入力にできることだけを表す。`publish-ready`、公開承認、deploy承認ではない。

---

# 2. 保存場所とschema

- 保存先: `knowledge/public/timelines/canonical_timeline_public_input.json`
- envelope schema: `schemas/canonical_timeline_public_input.schema.json`
- local review schema: `schemas/canonical_timeline_public_input_review.schema.json`
- local preflight record schema: `schemas/canonical_timeline_public_preflight_record.schema.json`
- payload schema: `schemas/canonical_timeline_public_projection.schema.json`
- real candidate / review / preflight: `workspace/public_wiki_inputs/`（ignore・非commit）

このPRでは保存先directoryの`.gitkeep`だけを追加し、実入力も合成入力も正式保存先へ昇格しない。合成データはtestsとdocs templateだけで検証する。

---

# 3. Public input envelope

rootは次だけを許可し、全objectを`additionalProperties: false`とする。

| field | 固定条件 |
|---|---|
| `schemaVersion` | `0.1` |
| `documentType` | `canonical_timeline_public_input` |
| `visibility` | `public` |
| `buildStatus` | `approved_for_build` |
| `contentType` | `canonical_timeline_public_projection` |
| `payloadSha256` | canonical JSON化したprojectionのSHA-256 |
| `pushReview` | 匿名の承認結果・時刻・固定checkだけ |
| `projection` | 既存public projection schemaへの完全適合 |

`pushReview`にはreviewer名、自由記述、internal input digest、path、URLを保持しない。payloadも引き続き`publishStatus: projection_candidate`であり、unknown / conflictの個別情報、provenance、Evidence、internal IDを含まない。

---

# 4. Local review record

real review recordは`workspace/public_wiki_inputs/`だけに置き、commitしない。`docs/templates/canonical_timeline_public_input_review_template.json`は合成placeholder値を持つ安全なtemplateであり、既定decisionを`needs_revision`、全checkをfalseとする。

`approved_for_build`にするには次をすべて満たす。

- `preflightStatus: clean`
- projection schema valid
- projection semanticsを確認
- internal value exposure 0を確認
- local visual reviewを完了
- reviewの`projectionSha256`とpreflight 5入力のprojection digestが、昇格対象のcanonical JSON SHA-256に一致

5入力digestはreviewとpreflight recordの両方へ保持し、promotion時にobject全体の完全一致を要求する。これにより別runのclean結果や残る4入力digestの混在を拒否する。digestはpublic inputへ転記しない。reviewer identityと自由記述field自体をschemaで許可しない。

---

# 5. Promotion

`scripts/promote_canonical_timeline_public_input.py`は固定workspace内のprojection / review / preflight JSONを読み、既定dry-runでenvelopeを構築する。`--execute`時だけ固定保存先へ新規作成する。

必須gate:

1. 3入力が固定workspaceの非追跡・ignore済み通常fileである
2. filenameが種別ごとの固定patternに一致する
3. operator指定expected projection SHA-256、review digest、preflight projection digest、実payload digestが一致する
4. review schema validかつ`approved_for_build`
5. preflight record schema valid、5入力digestがreviewと完全一致、かつ`clean` / `projection_candidate` / finding 0
6. projectionと完成envelopeがschema valid
7. execute直前に全入力を再読込し、結果bytesがdry-run計画と一致する
8. targetがGit indexで未追跡かつworktreeにも存在しない場合だけtemporary fileからatomicに新規作成する
9. input fileをdirectory descriptor相対・no-followで読み、targetも固定directory descriptor相対でcreate / link / read / cleanupする
10. write後のraw bytes、通常file identity、schema、payload digestを再検査し、失敗時は今回作成した同一fileだけを回収する

`--execute`は上記directory descriptor相対APIをすべて提供するplatformだけで許可する。Windows nativeなど未対応platformでは入力の2回目の読込やwriteを開始する前に`secure-directory-api-unavailable`でfail-closedする。Windowsではdry-runを行い、executeはWSL / Linuxの同一checkoutで実施する。

初期v0.1はno-clobberのみとし、既存targetの更新・削除を行わない。将来の更新は既存target digest pin、lock、history snapshot、atomic replaceを備えた別実装gateで扱う。

---

# 6. 公開境界

commit可能なのはschema、script、合成fixture/test、template、runbook、そして別PRで人間がpush前確認したpublic inputだけである。次はcommitしない。

- internal canonical artifact / promotion plan / review packet
- private mapping / public label source
- real preflight report / 5入力digest / review record
- renderer生成Markdown / HTML / site output
- reviewer identity / note / source text / provenance / Evidence / internal ID

本実装はrenderer、site manifest、hosted exposure scan、public workflow、Pages artifact、deploy、rollbackを変更しない。
