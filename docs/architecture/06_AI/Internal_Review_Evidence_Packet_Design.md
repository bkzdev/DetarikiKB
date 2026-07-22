# Internal Review Evidence Packet Design

Version: 0.2 Draft
Status: Phase 5.1設計確定・Phase 5.2 schema/validator実装済み
Project: Detariki Knowledge Base (DKB)
Path: `docs/architecture/06_AI/Internal_Review_Evidence_Packet_Design.md`

---

# 1. Background

Public Evidence Indexは、公開IDを中心とした索引であり、raw text・raw command・local path・sourceKey由来の内部trace IDを含めない。一方、人間reviewでは、Public Evidence IndexのentryがどのNormalized Story blockに対応するか、speaker解決やparser判定が妥当かを、元の情報へ戻って確認する必要がある。

この照合をPublic Evidence Indexへ持ち込むと公開境界が崩れるため、詳細情報は**Internal Review Evidence Packet**（以下、Packet）として完全に分離する。本設計は、次を確定する。

- Packetの保存境界とbundle単位
- 内部IDと公開IDのmapping table
- raw text・raw command・前後contextの最小保持方針
- 専用schema・validator・CLIの責務
- human review、Public promotion、保持・削除との関係

Packetは内部reviewを助ける一時的なローカル成果物であり、Knowledge Baseのsource of truthでも、公開成果物でも、承認記録でもない。

---

# 2. Goals

- Public Evidence Indexから内部trace情報とraw内容を分離したまま、人間が根拠へ戻れるようにする
- `publicEvidenceId`から内部`evidenceId`・`storyId`・`episodeId`・`sceneId`・`blockId`へ照合できるようにする
- reviewに必要なNormalized Story block、speaker/parser/extraction/validation情報だけをallowlistで保持する
- raw内容がconsole、report、Git、公開Wikiへ流出しないfail-closedな生成・検証境界を定義する
- Packetをhuman reviewの補助資料に限定し、Packet生成だけでpromotionが承認されないことを保証する
- 後続PRをschema/validator、generator、運用CLIへ安全に分割できる状態にする

---

# 3. Non-goals

本設計およびPhase 5.2では、次を行わない。

- Packet generator、cleanup CLI、実データ入力を読むloaderの実装
- 実データPacket、raw text、raw command、内部ID mappingの生成・commit
- Public Evidence Index schema/loader/validator/rendererの変更
- Public ID Registry、Story Summary、promotion filter/check/copyの挙動変更
- Packetからの自動promotion、review noteの自動承認・取り込み
- raw DEC file全体、Normalized Story JSON全体、Extraction Result全体の複製
- Packetの外部共有、クラウド同期、暗号化・アクセス制御基盤の実装
- Story Summary用mappingをPacket v1へ統合すること

実装後も、Packetそのものをcommitすることは恒久的なNon-goalとする。

---

# 4. Trust boundaryと責務分離

## 4.1 3つの成果物を混在させない

| 成果物 | 保存先 | 内容 | commit |
|---|---|---|---|
| Public Evidence Index | `knowledge/evidence/stories/` | 公開ID中心、rawなし | review後のみ可 |
| Human review note | 既存promotion workflowのreview note | 人間のDecisionと確認記録 | 既存policyに従う |
| Internal Review Evidence Packet | `workspace/review_packets/evidence/` | 内部ID、raw、debug情報を含みうる | **常に禁止** |

PacketをPublic Evidence Indexの`visibility.public: false` entryとして混在させる設計は採用しない。Public側の`visibility.public: true`、`rawTextIncluded: false`という機械的保証を維持し、Packetには別schema・別loader/validator・別CLIを用意する。

## 4.2 Packetの権限

Packetは次の権限を持たない。

- Public ID Registryを書き換える
- Public Evidence Indexを生成済み・承認済みとみなす
- human review noteのDecisionを代替する
- `promote_evidence_index.py --execute`を起動する
- 公開Wiki rendererの入力になる

Packetは**他成果物へ書き戻す権限を持たないreview補助資料**である。Packet generator/cleanup以外の処理がPacketを変更しないという論理的なread-only境界を指し、OSのread-only ACLを意味しない。承認主体と承認記録は既存のhuman review note側に残す。

## 4.3 用語

- **safe component / safe report**: raw内容、内部ID、title、sourceKey、local pathを持たず、consoleへ要約してよい`manifest.json`と`reports/validation.json`
- **sensitive component**: 内部IDまたはraw内容を含みうる`mappings/`と`stories/`
- **cross-consistent snapshot**: mapping、Public-safe candidate、Normalized StoryのID対応とdigestが相互に矛盾しない組。現在のprojection出力にはrun IDがないため、同一の過去process invocationで作られたことまで証明する用語ではない
- **Packet v1**: 後続schemaで`packetVersion: 1`として実装する本設計の初期contract
- **review完了**: human review noteにDecisionが記録され、operatorが当該Packetをcleanup対象と判断した状態。Packetが自動検知する状態ではない

---

# 5. Bundle単位と保存layout

## 5.1 採用単位

1回のgenerator実行を1 bundleとし、1 bundleは1件以上のstoryを含められる。batch reviewでも入力snapshot・mapping・validation結果を同じ単位で固定でき、storyごとの巨大な単一ファイルも避けられるためである。

`packetId`はsourceKey、title、内部ID、公開IDから作らない。形式は次とする。

```text
erp-YYYYMMDDTHHMMSSZ-<8 lowercase hex>
```

末尾は衝突回避用のopaque suffixであり、意味を持たない。bundle内のstory file名も内部IDを使わず、generatorが付ける`story-0001.json`形式のordinalにする。

## 5.2 固定rootとlayout

```text
workspace/review_packets/evidence/
  erp-20990101T000000Z-a1b2c3d4/
    manifest.json
    mappings/
      evidence-id-map.csv
    stories/
      story-0001.json
      story-0002.json
    reports/
      validation.json
```

- output rootは`workspace/review_packets/evidence/`に固定する
- `manifest.json`と`reports/validation.json`はraw内容・内部ID・local pathを持たないsafe metadataとする
- `mappings/`と`stories/`は内部IDまたはraw内容を含みうるsensitive componentとする
- file名にはsourceKey、story title、内部/公開IDを使わない
- 一時出力は同root直下の`.tmp-<packetId>/`に作り、検証成功後に同一filesystem上でatomic renameする
- 既存bundleは既定で上書きしない

`.gitignore`は補助防壁であり、安全性の根拠を`.gitignore`だけに置かない。後続generatorはroot固定、Git ignore確認、tracked file確認、symlink/junction確認を実行時に強制する（§10）。

---

# 6. 入力とsource snapshot

## 6.1 入力

Packet v1は、次を入力候補とする。

- Normalized Story JSON: block本文・speaker・parser由来metadataのsource
- Extraction Result（任意）: candidate参照・抽出debug metadataのsource
- `project_evidence_index_public_ids.py --mapping-output`: 内部IDと公開IDの対応
- 同じprojection作業の組として渡すPublic-safe candidateとreport: 公開側との照合・検証用（過去run identityではなく§6.2のcross-reference整合を検証する）
- local selection file（任意、commit禁止）: review対象entryを明示的に絞る場合の入力

raw DEC fileをPacket generatorへ直接入力しない。raw情報が必要でも、Parserを通過したNormalized Story JSONから必要なfieldだけを抽出する。これは`AI_CONTEXT.md` §3.1の「Raw Scriptを直接AIに渡さない」方針と、不要なsource全体を複製しない方針を両立させる。

## 6.2 Cross-consistent snapshotの保証

`manifest.json`には入力pathやfile名ではなく、次のaggregate metadataを記録する。

- input種別ごとのfile count
- input種別ごとのSHA-256 digest（複数fileは各file digestをbyte順に並べて集約）
- projection mappingのSHA-256 digest
- Public-safe candidateのSHA-256 digest
- Public ID Registryを使った場合はRegistryのSHA-256 digest
- projection mode（`public-safe`）とpolicy
- generator version
- `createdAt`（UTC）
- component fileごとのrelative path、media type、record count、SHA-256 digest

Normalized Story、mapping、Public-safe candidateのID対応・対象entry・digestが相互に整合しない場合は生成を失敗させる。既存projection出力には共通run IDや親digestがないため、v1が機械的に保証するのは**cross-reference整合**であり、「同一process invocationだったこと」の証明ではない。同じprojection作業で得たmapping/candidate/reportを組として渡すこと自体はoperator要件とする。将来projection reportへ相互digestを埋め込むまで、文書上も「同一runを証明」とは扱わない。

digestは改ざん防止の完全なsecurity boundaryではなく、review中の取り違え・後更新を検知するintegrity markerである。v1で必須にするdigestは入力種別、projection mapping/Public-safe candidate/Registry、bundle component単位までとし、entry単位のdigestはcontext切り詰め元を除いて導入しない。

絶対path、raw file名、title、sourceKeyは`manifest.json`とsafe reportに記録しない。

## 6.3 Entry selection

raw内容の不要な複製を避けるため、Packet v1は次の2 modeだけを持つ。

| mode | 対象 | 用途 |
|---|---|---|
| `public-candidate`（既定） | Public-safe candidateに含まれるentry | promotion前の通常review |
| `explicit-entry-list` | local selection fileで明示した内部`evidenceId` | parser/speaker等の限定診断 |

- `full`/`review` profileの全blockを無条件にraw化するmodeは設けない
- `stage_direction`等のPublic policy除外entryは`explicit-entry-list`で必要なものだけを含める
- 内部IDをCLI引数へ直接並べず、`workspace/local_inputs/evidence_packet_selection/`配下のignored local selection fileから読む。shell historyやprocess listへの内部ID露出を避けるためである
- selection fileは`{"selectionVersion": 1, "evidenceIds": ["..."]}`だけを持つJSONとし、`additionalProperties: false`、ID重複禁止、raw/title/path field禁止とする。root外・symlink/junction経由の入力は拒否する
- selection file自体もcommit・共有禁止、Packetと同じaccess policyの対象とし、Packet生成後はoperatorが削除する。bundle内へ複製しない
- `mappings/evidence-id-map.csv`には選択されたentryの行だけを、元mappingの順序を維持して取り込む
- `manifest.sourceSnapshot.projectionMappingDigest`は入力mapping全体、manifestのcomponent digestは選択後CSVを表し、両者を区別する
- entryがselectionに無いのにraw componentへ現れた場合、またはselection対象に対応するmapping/blockが無い場合はblockingとする

---

# 7. Data model

## 7.1 Manifest

後続schemaでは、少なくとも次を必須とする。

```json
{
  "packetVersion": 1,
  "packetId": "erp-20990101T000000Z-a1b2c3d4",
  "classification": "internal-review-local",
  "purpose": "evidence-review",
  "selectionMode": "public-candidate",
  "commitAllowed": false,
  "retentionClass": "ephemeral",
  "generatorVersion": "internal-review-evidence-packet-generator-1",
  "createdAt": "2099-01-01T00:00:00Z",
  "expiresAt": "2099-01-15T00:00:00Z",
  "sourceSnapshot": {
    "normalizedStoryFileCount": 2,
    "normalizedStoryDigest": "<sha256>",
    "extractionDigest": null,
    "projectionMappingDigest": "<sha256>",
    "publicCandidateDigest": "<sha256>",
    "registryDigest": null,
    "projectionMode": "public-safe",
    "projectionPolicy": "public-default"
  },
  "components": []
}
```

全階層を`additionalProperties: false`にし、未知fieldを黙って受理しない。`commitAllowed`は`false`のconst、`classification`も上記文字列のconstとする。

## 7.2 Story component

`stories/story-NNNN.json`は、次の責務を持つ。

```json
{
  "packetVersion": 1,
  "reviewStoryKey": "story-0001",
  "identifiers": {
    "internal": { "storyId": "TEST_INTERNAL_STORY" },
    "public": { "publicStoryId": "TEST_PUBLIC_001" }
  },
  "entries": [
    {
      "reviewEntryId": "entry-000001",
      "identifiers": {
        "internal": {
          "episodeId": "TEST_INTERNAL_EPISODE",
          "evidenceId": "TEST_INTERNAL_BLOCK",
          "sceneId": "TEST_INTERNAL_SCENE",
          "blockId": "TEST_INTERNAL_BLOCK"
        },
        "public": {
          "publicEpisodeId": "TEST_PUBLIC_001_E01",
          "publicEvidenceId": "TEST_PUBLIC_001_E01_DLG0001"
        }
      },
      "evidenceType": "dialogue",
      "rawContent": {
        "reason": "evidence-review",
        "text": "Synthetic review text.",
        "rawCommand": null,
        "arguments": []
      },
      "context": { "before": [], "after": [] },
      "speaker": null,
      "extraction": null,
      "diagnostics": []
    }
  ]
}
```

設計上の要点:

- `reviewStoryKey`/`reviewEntryId`はPacket内だけで有効なordinalであり、公開IDでも永続IDでもない
- `identifiers.internal`には照合に必要な内部IDだけを保持する
- `identifiers.public`は未採番・public policy除外entryではnullを許容し、Packet側で推測しない
- `speaker`はsource label、resolved speaker ID、resolution status等のreview必要項目だけを持つ。Character辞書全体を埋め込まない
- `extraction`は該当candidate ID・candidate type・confidence等の限定metadataだけを持つ。Extraction Result全体やLLM生出力を埋め込まない
- `diagnostics`はissue code、severity、対象`reviewEntryId`等の構造化情報に限定し、stack traceやlocal pathを保存しない
- `rawContent.reason`は`evidence-review` / `parser-diagnostic` / `speaker-resolution` / `extraction-diagnostic`の4値だけを許可する
- `rawContent.text`は文字列またはnull、最大20,000 Unicode code pointとし、超過時は黙って切り詰めずvalidation failureにする
- `rawContent.rawCommand`は文字列またはnull、最大128 Unicode code pointとし、`parser-diagnostic`の場合だけ許可する
- `rawContent.arguments`は`rawCommand`がある場合だけ許可するprimitive stringの配列で、最大16要素、1要素256 code point、合計2,048 code pointとする。nested object、absolute/UNC path、raw source file名、無関係なpayloadを許可しない
- `rawContent`は`text`または`rawCommand`の少なくとも一方を持ち、両方とも不要ならobject自体をnullにする

## 7.3 schema分離

bundle形式のため、Phase 5.2では次をPublic Evidence Indexとは別に実装した。

- `schemas/internal_review_evidence_packet_manifest.schema.json`
- `schemas/internal_review_evidence_packet_story.schema.json`
- `schemas/internal_review_evidence_packet_selection.schema.json`
- `schemas/internal_review_evidence_packet_validation_report.schema.json`
- `scripts/validate_internal_review_evidence_packet.py`

validatorは固定root配下の既存bundleを**read-only**で検査する。`reports/validation.json`は将来のgeneratorがsafeな集計として作成するcomponentであり、validator自身は作成・更新しない。Public Evidence Indexの`FORBIDDEN_TEXT_PATTERNS`はPacket validatorへ流用しない。Packetではraw内容が正当に存在し得るためである。代わりに、raw fieldの配置を`rawContent`/`context`へ限定し、safe componentへの混入、絶対path、未知field、bundle外参照を検査する。

Phase 5.2 CLIの入力はpathではなく固定root直下のopaqueな識別子へ限定する。`--packet-id`は`workspace/review_packets/evidence/<packetId>/`、`--selection-file`は`workspace/local_inputs/evidence_packet_selection/<fileName>`だけを対象とし、後者もbasenameだけを受け取る。

```bash
uv run python scripts/validate_internal_review_evidence_packet.py --packet-id erp-20990101T000000Z-a1b2c3d4
uv run python scripts/validate_internal_review_evidence_packet.py --selection-file review-selection.json
```

---

# 8. 内部ID・公開ID mapping policy

## 8.1 正式なPacket component

`mappings/evidence-id-map.csv`は、現行`project_evidence_index_public_ids.py --mapping-output`と同じ列を保持する。

```text
storyId,publicStoryId,episodeId,publicEpisodeId,evidenceId,publicEvidenceId,
evidenceType,sceneId,blockId,episodeOrder,publicEpisodeIdSource,
registryMatched,registryConflict,registryPublicEpisodeId
```

Packet generatorは公開IDを再採番せず、operatorが同じprojection作業の組として渡したmapping/candidate/reportをcross-reference検証してbundleへ取り込む。現在はrun identity自体を証明できないため、§6.2のcross-consistent snapshotを保証範囲とする。これにより、projection scriptとPacket側に採番ロジックを二重実装しない。Phase 5.2 validatorの責務は、生成済みbundleのschema・digest・mapping・story component間の自己整合性である。外部のsource candidate、Normalized Story、Registry入力とのcross-checkは、入力を読むPhase 5.3 generatorの責務とする。

## 8.2 Cardinalityと欠損

- 1行は1つの複合internal key（`storyId`, `episodeId`, `evidenceId`）に対応し、この複合keyはbundle内で一意とする
- cross-consistent snapshot内で、複合internal keyから非null `publicEvidenceId`への対応は0または1件
- 非null `publicEvidenceId`から複合internal keyへの対応は必ず1件。重複はblocking
- `public-default`対象entryでPublic-safe candidateに含まれるものは、3つの公開IDが必須
- `stage_direction`等のpublic policy除外entryは`publicEvidenceId`が空でもよい
- Registry conflict、mapping内のstory/episode矛盾、Public-safe candidateとの不一致はblocking
- 既存CSV writerが重複を排除するとは仮定せず、Packet validatorが複合internal keyと非null `publicEvidenceId`の一意性を全行で検査する
- mapping欠損をPacket generatorがtitle、順序、類似IDから推測して埋めない

## 8.3 Registryとの境界

Public ID Registryは公開IDだけを保持し、内部`storyId`/`episodeId`とのmappingを持たない。Packetのmapping tableをRegistryへ転記しない。Packet削除後にmappingが必要になった場合は、Registry・Normalized Story・projection入力から再生成する。

Packet v1はEvidence Index mappingだけを対象とする。Story Summary projectionのmapping統合は、実際のreview需要が観測された時点で別設計とする。

---

# 9. Raw contentとcontext policy

## 9.1 最小保持の原則

raw内容を含められることは、入力document全体のdumpを許可することを意味しない。entryごとにreview目的を明示し、次のallowlistだけを保持する。

- 対象blockのtext（review対象なら全block textを保持可）
- parser診断に必要な`rawCommand`と限定されたarguments
- choice option等、対象evidenceを解釈するために不可欠な本文
- source speaker labelとspeaker resolution metadata
- 該当Extraction Candidateの限定metadata
- 構造化されたvalidation/parser issue code

禁止するもの:

- raw DEC file全体、episode全文、Normalized Story/Extraction Resultの全dump
- prompt、LLM生出力、環境変数、stack trace
- local absolute path、UNC path、raw source file名
- 関係のないCharacter辞書・Registry・Merged Collection全体

## 9.2 Context

前後contextは既定で空とする。将来generatorへ明示opt-inを追加する場合も、次をhard limitとする。

- 前後それぞれ最大1 block
- context blockごとに最大500 Unicode code point
- 各要素は`internalBlockId`、`text`、`truncated`、`originalTextSha256`だけを持つ。`internalBlockId`は同じstory component内のblockへ解決できなければならない
- `truncated: false`では`originalTextSha256: null`、切り詰めた場合だけ`truncated: true`と切り詰め前textのUTF-8 byte列に対するSHA-256 digestを記録する
- `before`は近いblockから遠いblockの順、`after`も近いblockから遠いblockの順とする（v1の上限は各1件）
- contextからさらに再帰的に前後contextを展開しない

対象block自体のtextは、正確なreviewのためblock単位で保持できる。ただしepisode/file単位へ結合しない。raw内容を持たないentryでは`rawContent`をnullにし、空文字やplaceholderを作らない。

## 9.3 Non-raw surface

CLI stdout/stderr、`manifest.json`、`reports/validation.json`、exception message、CI logへは次だけを出してよい。

- `packetId`
- component相対path
- story/entry件数
- issue codeと`reviewStoryKey`/`reviewEntryId`
- file size、SHA-256 digest、validation結果

raw text、raw command、内部ID、title、sourceKey、local pathは出さない。debug時もこの規則を緩めず、reviewerはPacket fileをローカルで開く。

---

# 10. Generationとvalidation boundary

## 10.1 入出力先のfail-closed check

後続generatorは書き込み前に、Phase 5.2 validatorは既存bundleまたはselection fileを読み込む前に、該当する次の境界をすべて確認する。

1. outputがrepo内の固定root `workspace/review_packets/evidence/`配下へresolveされる
2. `..`、absolute component、root外へのpath traversalがない
3. rootからtargetまでにsymlink、junction、reparse pointがない
4. repo root内のGit worktreeで実行されている。非Git環境・Git command失敗は安全側で拒否する
5. fixed root、temporary path、final pathのそれぞれについて`git check-ignore --no-index -q -- <repo-relative POSIX path>`が成功する
6. `git ls-files`でfixed root/target配下にtracked fileが1件もない
7. `knowledge/`、`docs/`、`tests/fixtures/`、`data/`をoutputに指定できない
8. 同名bundleが存在しない

いずれかが満たされなければ、raw入力を読み込む前にconfig errorとして終了する。temporary directoryは検証済みfixed root直下へ作り、atomic rename直前にもfixed root・temporary path・final parentのreparse point/ignore/tracked状態を再検査する。Windowsでreparse pointを判定できない場合も「安全」と推測せずexit 2にする。既存final directoryがある場合は常に拒否する。

## 10.2 Structural / semantic validation

Phase 5.2 validatorはbundle内の次を検証する。Phase 5.3 generatorは生成後、atomic rename前に同じ検証を通す。

- manifest/story schemaと`additionalProperties: false`
- manifest記載componentの存在、逆に未記載fileがないこと
- component digest、record count、relative pathの一致
- `reviewStoryKey`/`reviewEntryId`のbundle内一意性
- mapping cardinalityとstory/episode/evidenceのcross-reference
- manifest内のprojection mode/policyとcomponent digestの整合
- `rawContent.reason`があり、raw fieldがallowlist位置にだけ存在すること
- contextのblock数・code point上限
- safe componentにraw内容・内部IDがないこと
- 全文字列にabsolute/UNC pathがないこと

validatorはread-onlyのため、validation失敗時にもbundleを変更しない。Phase 5.3 generatorではvalidation失敗時にfinal bundleを作らないで、一時directoryを削除する。いずれもstdout/stderrにはsafe aggregateだけを出す。一時directory削除にも失敗した場合は、固定root内のopaqueな`.tmp-<packetId>`相対pathだけを示してnon-zero終了する。

## 10.3 Exit code方針

既存CLI慣習に合わせる。

- `0`: 生成・検証成功
- `1`: 内容・mapping・cross-reference validation failure
- `2`: input/output path、Git境界、schema、CLI設定等のconfig/IO error

---

# 11. Human reviewとpromotion workflow

```text
Normalized Story / Extraction Result
  -> Public candidate + public ID projection + mapping
  -> Internal Review Evidence Packet generation
  -> Packet validation
  -> human review
  -> separate review note
  -> existing promotion check / copy (public-safe candidate only)
  -> Packet cleanup
```

運用規則:

- PacketはPublic-safe candidateとcross-consistentな入力組から生成する
- reviewerはreview noteへ`packetId`とmanifest digestを参照として記録できるが、raw本文を転記しない
- Decision、reviewer、reviewedAtは既存review noteへ記録し、Packet story componentへ書かない
- promotion check/copyはPublic-safe candidateとreview noteだけを入力とし、Packet raw componentを読まない
- Packetが存在するだけで`Approved for promotion`とみなさない
- Packetが期限切れ、digest不一致、validation failureの場合、そのPacketだけを根拠に新しい承認を行わず、必要なら再生成する
- unknown比率10%超〜30%以下の`human-review-required` storyをPacketが自動で`promotion-candidate`へ変更しない。review note取り込み経路は別Backlogのままとする

これにより、raw review経路と公開copy経路の間にデータの一方向境界を保つ。

---

# 12. Access、retention、cleanup

## 12.1 Access policy

- PacketはローカルOS userだけが扱う前提とする
- network share、クラウド同期folder、メール、chat、issue/PR添付へコピーしない
- `workspace/review_packets/evidence/`がnetwork drive・同期folder・共有ACL配下でないことをoperatorが生成前に確認する。OS/同期製品横断の自動判定とACL強制はv1の保証範囲外であり、後続runbookのpreflightへ明記する
- repository外へ共有する機能はv1で提供しない
- file permissionの強化・暗号化はv1の機能に含めず、必要になった時点で別途security reviewする
- 絶対pathをPacket内に保存しないため、bundle単体から元配置を復元できない設計にする

## 12.2 Retention

- retention classは`ephemeral`固定
- 既定保持期間は生成から14日
- 将来CLIで変更可能にする場合も1〜30日の範囲に限定する
- `createdAt`/`expiresAt`はRFC 3339 UTCの`Z`表記とし、`createdAt < expiresAt <= createdAt + 30 days`をsemantic validationする
- review完了・中止・candidate差し替えのいずれかが先に起きたら、operatorが期限を待たずcleanup対象へ指定する。generatorがreview noteを監視して自動判定・自動削除はしない
- 30日を超える保管や長期archiveはサポートしない。必要時に最新snapshotから再生成する
- generatorは既存Packetを自動削除しない。`expiresAt`超過はinventory/cleanup CLIがwarningする
- 期限切れはschema/validatorのfailureにせずwarningとする。新規reviewの根拠には使わず、inventoryが表示し、cleanup候補として扱う

## 12.3 Cleanup

後続cleanup CLIは次の安全策を持つ。

- dry-run既定、削除には`--execute`必須
- `packetId`を1件以上明示し、root全体やglobだけの削除を許可しない
- generatorと同じresolve/symlink/junction/reparse point/Git checkを削除直前にも再実行し、検査できない・途中で状態が変わった場合は削除しない
- 対象component数・合計size・manifest digestだけを事前表示し、raw/内部IDを表示しない
- 通常のfilesystem削除を行い、SSD・backup・journalに対するsecure eraseは保証しない

削除後もhuman review noteとPublic Evidence Indexは残るが、Packet mapping/raw内容は残らない。後日の再照合は、保存済みの公開ID、review noteの`packetId`/manifest digest、再生成可能なsource snapshotを使う。

---

# 13. Security / failure model

| Failure | 扱い |
|---|---|
| output root外・tracked path・symlink/junction | raw入力読込前にexit 2 |
| mapping conflict/duplicate public ID | exit 1、final bundleなし |
| input snapshot不一致 | exit 1、final bundleなし |
| schema/semantic validation failure | exit 1、temporary bundleを削除 |
| safe reportへのraw/internal ID混入 | blocking、final bundleなし |
| 既存packetId衝突 | 上書きせずexit 2 |
| Packet期限切れ | promotionを直接blockはしないが、新規review根拠として使わず再生成 |
| cleanup対象がroot外へresolve | 削除せずexit 2 |

Packet validatorは「rawがあるから失敗」させるのではなく、「rawが許可位置以外へ出た」「公開経路へ渡り得るcomponentへ混入した」場合に失敗させる。

---

# 14. Implementation phases

| Phase | 内容 | 状態 |
|---|---|---|
| Phase 5.1: `internal-review-evidence-packet-design` | 本文書、既存docsとの境界、data model/lifecycle/security方針 | **完了（設計のみ）** |
| Phase 5.2: `internal-review-evidence-packet-schema-validator` | 専用manifest/story/selection/safe validation report schema、合成fixture、既存bundleを変更しないvalidator | **完了** |
| Phase 5.3: `internal-review-evidence-packet-generator` | Normalized Story + 既存mappingからのbundle生成、atomic write、出力境界 | 未着手 |
| Phase 5.4: `internal-review-evidence-packet-operations` | runbook、inventory、期限warning、dry-run既定cleanup CLI | 未着手 |

Phase 5.2〜5.4は分離PRとする。Phase 5.2は合成fixtureだけを使って完了した。Phase 5.3以降の実データ確認も`workspace/`限定・非commitとする。review note取り込みや自動promotionはこれらのphaseへ便乗させない。

---

# 15. Open questions

次はv1実装のblockerではなく、実利用を観測してから判断する。

- Extraction Candidate詳細を標準で含めるか、明示option時だけにするか
- 14日以内でもraw componentだけを先に削除しmappingだけ残す需要があるか
- Packetを読む専用local UIが必要か、JSON/CSVのままで十分か
- Story Summary用mappingを同じbundleへ拡張する需要があるか
- OS file permission・暗号化をproject側で強制する必要があるか

---

# 16. References

- `docs/architecture/06_AI/Evidence_Index_Design.md`
- `docs/architecture/06_AI/Evidence_Index_Public_ID_Policy.md`
- `docs/architecture/06_AI/Public_ID_Registry_Design.md`
- `docs/architecture/06_AI/Evidence_Index_Promotion_Policy.md`
- `docs/runbooks/Evidence_Index_Promotion_Check.md`
- `docs/runbooks/Evidence_Index_Promotion_Copy.md`
- `docs/runbooks/Evidence_Index_Batch_Promotion_Policy.md`
- `scripts/project_evidence_index_public_ids.py`
- `schemas/evidence_index.schema.json`
- `AI_CONTEXT.md` §3.1/§3.11
- `docs/runbooks/AI_PR_Playbook.md` §5/§7
