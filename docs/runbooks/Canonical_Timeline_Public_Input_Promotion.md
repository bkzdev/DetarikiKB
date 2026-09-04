# Canonical Timeline Public Input Promotion

Version: 0.1
Status: Active
Updated: 2026-09-04

---

# 1. 前提

`Canonical_Timeline_Public_Preflight.md`の5入力digest pin付きpreflightがcleanで、同じprojectionをlocal visual review済みであること。実入力は次の固定ignored directoryへ置く。

```text
workspace/public_wiki_inputs/
  canonical_timeline_public_projection_<run>.json
  canonical_timeline_public_input_review_<run>.json
  canonical_timeline_public_preflight_<run>.json
```

絶対pathや`../`をCLIへ渡さず、basenameだけを指定する。real file、digest、review recordはcommitしない。

---

# 2. Preflight / review record

preflightの返却reportと同じ実行で使った5入力digestを、`docs/templates/canonical_timeline_public_preflight_record_template.json`へ転記する。`status` / `publishStatus` / `findings`はreportからそのまま転記し、clean時だけfinding 0とする。real recordは`schemas/canonical_timeline_public_preflight_record.schema.json`へ適合させ、commitしない。

templateをignored workspaceへコピーし、実行結果でplaceholderを置換する。

```powershell
Copy-Item docs/templates/canonical_timeline_public_input_review_template.json workspace/public_wiki_inputs/canonical_timeline_public_input_review_<run>.json
```

projectionのcanonical JSON SHA-256には`canonical_timeline_public_preflight_input_digests(...)["projection"]`を使う。同じ5入力digest objectをpreflight recordの`inputDigests`とreviewの`preflightInputDigests`へ記録し、projection値を`projectionSha256`にも記録する。全check完了後だけ`decision: approved_for_build`、`preflightStatus: clean`、全check trueへ変更する。promotionは両recordの5入力digest完全一致を機械検査する。

reviewer名やnoteを追加してはならない。判断根拠に追加資料が必要なら、public input promotionを止めて別の非commit review経路で扱う。

---

# 3. Dry-run

```powershell
uv run python scripts/promote_canonical_timeline_public_input.py `
  --projection-name canonical_timeline_public_projection_<run>.json `
  --review-name canonical_timeline_public_input_review_<run>.json `
  --preflight-name canonical_timeline_public_preflight_<run>.json `
  --expected-projection-sha256 <64 lowercase hex>
```

exit 0と`status=dry_run`を確認する。この段階では`knowledge/public/timelines/canonical_timeline_public_input.json`を作成しない。

---

# 4. Execute gate

人間が実projectionのpush前表示と公開範囲を承認した別PRだけで、同じ引数に`--execute`を追加する。今回の合成実装PRでは実行しない。

executeはdirectory descriptor相対のno-follow read / create / link / cleanupを提供するplatform（Linux / WSL）で行う。Windows nativeでは`secure-directory-api-unavailable`でwrite前にfail-closedするため、同じcheckoutをWSLから開いて実行する。dry-runはWindows nativeでも実行できる。

```powershell
uv run python scripts/promote_canonical_timeline_public_input.py `
  --projection-name canonical_timeline_public_projection_<run>.json `
  --review-name canonical_timeline_public_input_review_<run>.json `
  --preflight-name canonical_timeline_public_preflight_<run>.json `
  --expected-projection-sha256 <64 lowercase hex> `
  --execute
```

targetが既に存在する場合、またはworktreeから削除済みでもGit indexで追跡済みの場合はblockingとなる。`--overwrite`は存在しない。実行後は意図したpublic input 1ファイルだけが`git status --short`へ現れ、review / preflight / Markdown / HTML / workspace出力が追跡対象になっていないことを確認する。post-write検査が失敗した場合は今回作成した同一fileだけを回収する。cleanup自体が失敗した匿名codeが出た場合は自動再実行せず、targetのidentityと内容を人間が確認する。

---

# 5. Exit code

| code | 意味 |
|---:|---|
| 0 | dry-run成功、または新規作成成功 |
| 1 | schema、review、preflight、digest、workspace境界、secure directory API、no-clobber、再読込、atomic writeのいずれかでblocked |
| 2 | expected digestの形式不正 |

出力はstatus / 匿名code / public projection digestだけで、ID、label、path、reviewer、内部digestを表示しない。

---

# 6. Non-goals

- 実public inputの生成・昇格・commit
- 既存public inputの更新・削除・rollback
- `publish-ready`化
- renderer / site manifest / hosted exposure scan
- GitHub Pages / artifact upload / deploy
