# Character Profile Wiki Import（デタリキZ攻略Wikiからのプロフィール取り込み手順）

Version: 0.1 Draft
Project: Detariki Knowledge Base (DKB)
Path: `docs/runbooks/Character_Profile_Wiki_Import.md`

---

# 1. 目的

デタリキZ攻略Wikiのメンバー一覧テーブルから、`knowledge/dictionaries/character_profiles.yaml`（公式プロフィール辞書、`docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`参照）へ投入可能な中間形式（import candidate）を取得・変換する手順を定義する。

**このスクリプトは`character_profiles.yaml`を直接更新しない。** 出力は必ずローカルのcandidate file（`.gitignore`対象）であり、人間が確認してから次の`character profile import batch`で反映する。

---

# 2. 取得元候補

- デタリキZ攻略Wiki メンバー一覧（テーブル）ページ
- URLは`docs/runbooks/`に固定記載せず、`scripts/import_character_profiles_from_wiki.py`の`--source-url`引数で都度指定する（Wiki側のURL構造変更に備えるため）

**このPRでは一覧テーブル1ページの取得に限定し、個別キャラページの巡回は行わない**（§9参照）。

## 2.1 確認済みのメンバー一覧テーブルURL（`feature/character-profile-wiki-url-discovery`で特定）

- ページ種別: PukiWiki系Wiki（wikiru.jp）の「メンバー」ページ（トップページから1回だけリンクを辿って特定。個別キャラページ巡回は行っていない）
- URL形式: `https://detarikiz.wikiru.jp/?<URLエンコードされたページ名>`（ページ名自体はURLエンコードされた日本語文字列。具体的なエンコード済み文字列は`scripts/import_character_profiles_from_wiki.py --source-url`実行時に指定する。Wiki側の構造変更に備え、本ドキュメントには固定文字列としては記載しない）
- ページ内の`<table>`要素のうち、認識済み見出し（キャラ名/よみがな/所属/身長(cm)/誕生日/血液型/特記事項/CV）を最も多く含むテーブルがメンバー一覧テーブルとして自動検出される
- 取得できた列: 画像（対応項目なし、無視）/キャラ名/よみがな/所属/身長(cm)/誕生日/血液型/特記事項/CV/実装日（対応項目なし、無視）/追加（編集リンク列、対応項目なし、無視）
- **見出しセル内に`<br>`が含まれ（例:「身長」の後に改行を挟んで「(cm)」）、素朴な文字列一致では認識できないケースがあることが判明した**（§10・§17参照、本PRで修正済み）
- **長いテーブルの途中で見出し行がそのまま繰り返されることがある**ことも判明した（本PRで修正済み、§17参照）

---

# 3. 取得できる項目とcharacter_profiles.yamlとの対応表

| WIKI列見出し（表記ゆれ含む） | character_profiles.yamlのフィールド | 変換方針 |
|---|---|---|
| キャラ名 / 名前 / キャラクター名 | `displayName` | そのまま（前後空白除去） |
| よみがな / ふりがな | `reading.kana` | そのまま。`reading.romaji`は一覧テーブルには無いため常に`null` |
| 所属 | `affiliation` | 文字列配列にする（1件でも配列） |
| 身長(cm) / 身長 | `heightCm` | 数字以外を除去して整数化（`"153cm"`→`153`）。空欄・不明は`null` |
| 誕生日 | `birthday` | `{month, day, display}`に分解（§7参照） |
| 血液型 | `bloodType` | そのまま（表記ゆれ吸収のため自由文字列） |
| 特記事項 | `profileHighlight` | `{label, value}`に分解（§6参照） |
| CV | `cv` | そのまま。空欄は`null` |
| 実装日 | （対応項目なし） | 無視する |

**自己紹介文（`selfIntroduction`）は一覧テーブルには存在しないため、常に`null`のまま取得される。** 個別キャラページからの取得は本PRのスコープ外（§8参照）。

---

# 4. displayName照合方針

WIKIのキャラ名（`displayName`）を、`knowledge/dictionaries/characters.yaml`の**confirmed済みcharacterId**を持つエントリの`displayName`と**完全一致**でのみ照合する。

- `status: confirmed`のエントリのみを照合対象にする（`status: name_only`・辞書に無い名前は絶対にmatchさせない）
- 完全一致のみを自動matchとする（表記ゆれ・空白差分・旧字体差分等は`unmatched`として人間確認に回す）
- **characterIdは自動生成しない**（`agents/parser/character_profile_wiki_import.py`の`match_candidates`が機械的にこの方針を担保する）

---

# 5. matched / unmatchedの扱い

| matchStatus | 条件 | candidateの内容 |
|---|---|---|
| `matched` | confirmed済みcharacterIdのdisplayNameと完全一致 | `characterId`（マッチしたconfirmed ID）+ `profile`（変換済みプロフィール候補、`status: draft`） |
| `unmatched` | 上記に該当しない | `characterId: null` + `reason`（マッチしなかった理由） |

`unmatched`のcandidateは人間が個別に確認し、必要なら`characters.yaml`のconfirmed化（`docs/runbooks/Character_Dictionary_Review.md`）を先に行ってから、次回のimportで再照合する。

---

# 6. 特記事項（profileHighlight）の変換方針

- `"【好きなこと】値"`のように`【...】`または`[...]`で囲まれたラベルがある場合、`{label: "好きなこと", value: "値"}`に分解する
- ラベルが無い（括弧が無い）場合は`{label: "特記事項", value: <列の値そのまま>}`とする
- 列が空欄の場合は`profileHighlight: null`

---

# 7. 誕生日（birthday）の変換方針

- `"4/23"`/`"04/23"`のような`月/日`形式を`{month, day, display}`に分解する（`display`には元の文字列をそのまま保持）
- 月日として不正な値（範囲外・パース不能）は`birthday: null`
- 空欄・不明も`birthday: null`

---

# 8. 自己紹介文（selfIntroduction）を今回取得しない方針

一覧テーブルには自己紹介文が含まれない可能性が高いため、本PRでは**自己紹介文の自動取得を行わない**。

- import candidateの`selfIntroduction`は常に`null`
- 個別キャラページから自己紹介文を取得する仕組みは、**future task**として別途扱う（`TASKS.md`参照）
- 自己紹介文は長文になりうり、引用量・著作権面の確認が必要なため、取得する場合も人間確認前提の別PRで扱う

---

# 9. サイト負荷への配慮

- **一覧テーブル1ページのみを取得する。個別キャラページの巡回はこのPRでは行わない**
- 取得前に対象サイトの`robots.txt`を確認し（`urllib.robotparser`）、許可されていない場合は取得しない（`scripts/import_character_profiles_from_wiki.py`の`check_robots_allowed`）
- HTTPリクエストには識別可能な`User-Agent`を明示する（デフォルト: `DetarikiKB-CharacterProfileImportBot/0.1`）
- 1回の実行で1ページのみを取得し、ループ・リトライによる連続アクセスは行わない

---

# 10. WIKI側の構造変更への備え

- 列見出しの表記ゆれ（`"キャラ名"`/`"名前"`等）は`agents/parser/character_profile_wiki_import.py`の`_HEADER_ALIASES`で吸収する
- 複数の`<table>`が存在する場合、認識済み見出しの一致数が最も多いテーブルを自動選択する（`find_member_table`、最小一致数`_MIN_RECOGNIZED_HEADERS`未満なら検出失敗として扱う）
- Wiki側の列追加・削除・並び替えには対応できるが、見出し文言自体が全く変わった場合は`_HEADER_ALIASES`の追加が必要になる

---

# 11. 失敗時のfallback

| 症状 | 想定される原因 | 対応 |
|---|---|---|
| exit code 1 | `--input-html`のファイルが見つからない、または`--source-url`/`--input-html`のどちらも未指定 | パスを確認、引数を見直す |
| exit code 2 | メンバー一覧テーブルを検出できなかった | Wiki側のページ構造変更を疑う。`_HEADER_ALIASES`の追加を検討 |
| exit code 3 | `robots.txt`により取得が許可されていない | 無理に取得しない。Wiki管理者への確認、または取得元の変更を検討 |
| matched件数が想定より少ない | `characters.yaml`のconfirmed化が進んでいない、または表記ゆれで完全一致しない | `docs/runbooks/Character_Dictionary_Review.md`の運用でconfirmed化を進める。unmatched一覧を人間が確認する |

---

# 12. 実行コマンド例

```bash
# 合成HTML/ローカルHTMLファイルから (テスト・オフライン確認用)
uv run python scripts/import_character_profiles_from_wiki.py \
    --input-html tests/fixtures/character_profiles/synthetic_wiki_member_table.html \
    --characters knowledge/dictionaries/characters.yaml \
    --dry-run

# 実WIKIから取得 (dry-run、summaryのみ表示、candidate fileは書き出さない)
uv run python scripts/import_character_profiles_from_wiki.py \
    --source-url "<WIKI_MEMBER_TABLE_URL>" \
    --characters knowledge/dictionaries/characters.yaml \
    --output workspace/profile_import/character_profile_candidates_batch_001.yaml \
    --dry-run

# 実際にcandidate fileを書き出す場合 (--dry-runを外す。出力先は.gitignore対象)
uv run python scripts/import_character_profiles_from_wiki.py \
    --source-url "<WIKI_MEMBER_TABLE_URL>" \
    --characters knowledge/dictionaries/characters.yaml \
    --output workspace/profile_import/character_profile_candidates_batch_001.yaml \
    --format both
```

---

# 13. 取得データは人間確認後にimportする方針

`scripts/import_character_profiles_from_wiki.py`が書き出すcandidate fileは、そのまま`knowledge/dictionaries/character_profiles.yaml`へ反映してはならない。

1. candidate file（YAML/CSV）を人間が確認する
2. `matched`エントリの`profile`内容が正しいか（誤字・表記ゆれ・特記事項の分解結果等）を確認する
3. `unmatched`エントリについて、`characters.yaml`側のconfirmed化が必要か検討する
4. 確認済みのエントリだけを、次の`character profile import batch`PRで`knowledge/dictionaries/character_profiles.yaml`へ手動反映し、`scripts/validate_character_profiles.py`で検証する

---

# 14. commit禁止対象（最重要）

- `scripts/import_character_profiles_from_wiki.py`が生成するcandidate file（YAML/CSVいずれも、`workspace/profile_import/`配下）
- 取得したraw HTML
- 実キャラクター名・実プロフィール値・実自己紹介文
- 上記いずれも`.gitignore`でカバー済み（`workspace/profile_import/`・`character_profile_candidates_batch_*.yaml`等）。`tests/fixtures/character_profiles/`配下の合成HTMLはcommitしてよい

---

# 15. 次のprofile import batchへの流れ

1. 本runbookの手順でcandidate fileを生成する
2. 人間がcandidate fileを確認し、`matched`エントリの内容を精査する
3. 確認済みエントリを次のPR（`character profile import batch 001`）で`character_profiles.yaml`へ反映する
4. 自己紹介文が必要な場合は、個別キャラページ取得の仕組み（future task）を別途検討する

---

# 17. URL特定・dry-run結果（`feature/character-profile-wiki-url-discovery`実施記録）

## 17.1 実施内容

1. Wikiのトップページを1回だけ取得し、「メンバー」ページへのリンクを発見した（個別キャラページへのリンクは辿っていない）
2. 発見したメンバー一覧ページを1回だけ取得し、`scripts/import_character_profiles_from_wiki.py`のロジックでテーブル検出・変換・照合を実施した
3. 発見したURLで`--dry-run`によるCLI実行を確認した

合計2回のHTTP GET（トップページ1回・メンバーページ1回）のみ。個別キャラページの巡回・追加のURL探索は行っていない。

## 17.2 dry-run結果（件数概要のみ）

- 検出したテーブルの行数（見出し・重複見出し除く）: 206行
- `matched`（characters.yamlのconfirmed済みcharacterIdとdisplayName完全一致）: 6件
- `unmatched`: 200件
- `selfIntroduction`: 全candidateで`null`（一覧テーブルには自己紹介文が存在しないため、想定通り）
- `profileHighlight`/`birthday`/`heightCm`/`cv`: matchedエントリで正しく変換されることを確認（型・構造のみ確認、値そのものはここに記載しない）
- raw HTML/candidate出力: 確認後すぐにローカルから削除し、commitしていない

## 17.3 見つかった問題と修正（script軽微改善）

実WIKIのテーブル構造を確認する中で、以下2点の実データ起因の問題が判明し、`agents/parser/character_profile_wiki_import.py`を修正した。

1. **見出しセル内の`<br>`による改行**: 「身長」列の見出しが`<br>`タグで改行を挟んで`(cm)`が続く構造だったため、`_HEADER_ALIASES`との単純な文字列一致に失敗し、`heightCm`が一切変換されない状態だった。`normalize_header`で見出し文字列内の空白文字（改行含む）をすべて除去してから照合するよう修正した
2. **テーブル途中での見出し行の繰り返し**: 長いテーブルでは可読性のため見出し行がそのまま繰り返されることがあり、これが偽のcandidate（displayNameが見出し文字列そのもの）として扱われていた。`rows_to_dicts`で、見出し行と完全一致する行をデータ行として取り込まないよう修正した

いずれも合成fixtureによる回帰テストを追加済み（`tests/parser/test_character_profile_wiki_import.py`の`test_normalize_header_handles_embedded_newline_from_br_tag`・`test_rows_to_dicts_skips_duplicate_header_row`）。**個別ページ巡回・自己紹介文取得・characterId自動生成・AI推測match・name_onlyへの自動matchはいずれも変更していない。**

---

# 18. 関連ドキュメント

- `docs/architecture/06_AI/Character_Profile_Dictionary_Design.md`（`character_profiles.yaml`全体の設計）
- `schemas/character_profiles.schema.json`（`character_profiles.yaml`のJSON Schema）
- `docs/runbooks/Character_Dictionary_Review.md`（`characters.yaml`のconfirmed化運用、matched判定の前提）
- `agents/parser/character_profile_wiki_import.py`（パース・変換・照合の実装）
- `scripts/import_character_profiles_from_wiki.py`（CLIエントリポイント）
- `TASKS.md` §5（実データ・生成物をcommitしない既存ルール）
