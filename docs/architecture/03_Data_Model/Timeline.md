# Timeline

現行のTimeline候補・Stage A / Stage B契約は`../06_AI/Extraction_Pipeline.md`と`../06_AI/Merged_Knowledge_Design.md`、整合性checkは`../../runbooks/Timeline_Consistency_Check.md`を正とする。

episode-level `canonicalOrder`は、同一story内だけで比較するstory-localな運用値である。`Canonical_Timeline_Scope_Decision.md`で、EVENT限定のpartial order graph、5状態分離、human-confirmed gate、2 story単位review、internal-onlyを初期profileとして採択した。global整数値・total order・公開は採択しておらず、story-local値から補完しない。

採択profileのJSON表現とsemantic consistency境界は`Canonical_Timeline_Schema.md`と`schemas/canonical_timeline.schema.json`を正とする。2 story単位の人間review入力契約、read-only validator、pending packet builderは`Canonical_Timeline_Review_Packet.md`および`../../runbooks/Canonical_Timeline_Review.md`を参照する。builderは固定workspace root、default dry-run、no-clobberでv0.2 packetを生成できるが、実corpusの候補は0件であり実packetは生成していない。

human-confirmedなknown relationをcanonical artifactへまだ書き込まない非実行proposalとして表す契約は`Canonical_Timeline_Promotion_Plan.md`を正とする。in-memory projectorとcross-document semantic validatorまで実装済みであるが、plan CLI / file I/O、review結果import、既存artifactとのpreflight、canonical artifact write、promotion executor、実plan、公開は未実装である。
