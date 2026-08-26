# Timeline

現行のTimeline候補・Stage A / Stage B契約は`../06_AI/Extraction_Pipeline.md`と`../06_AI/Merged_Knowledge_Design.md`、整合性checkは`../../runbooks/Timeline_Consistency_Check.md`を正とする。

episode-level `canonicalOrder`は、同一story内だけで比較するstory-localな運用値である。`Canonical_Timeline_Scope_Decision.md`で、EVENT限定のpartial order graph、5状態分離、human-confirmed gate、2 story単位review、internal-onlyを初期profileとして採択した。global整数値・total order・公開は採択しておらず、story-local値から補完しない。

採択profileのJSON表現とsemantic consistency境界は`Canonical_Timeline_Schema.md`と`schemas/canonical_timeline.schema.json`を正とする。v0.1は合成fixtureだけで状態・review / adoption gate・provenanceを固定し、schema-validな単一documentのcross-story partial-order不変則を純粋関数で検査する。実artifact生成、CLI / report、review / promotion、公開は未実装である。
