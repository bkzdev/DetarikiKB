# Timeline Page

Timeline pageの詳細設計（source・kind別セクション分割・「順序を確定しない」表示方針・テンプレート名案）は `Wiki_Output_Design.md` §9.11 を参照。

global chronologyとcanonical Timelineの初期profileは`../03_Data_Model/Canonical_Timeline_Scope_Decision.md`を参照。internal-onlyを採択しており、story-local `canonicalOrder`やcross-story候補をWikiで確定年表として表示しない。

`../03_Data_Model/Canonical_Timeline_Schema.md`と`schemas/canonical_timeline.schema.json`はinternal artifactのデータ契約だけを定義する。v0.1 schema追加はpublic表示を許可せず、本ページのrenderer・source・URLを変更しない。

公開目的・relation適格性・partial order表示・unknown/conflict・public-safe field・page / URL・publish gateは`Canonical_Timeline_Public_Projection_Decision.md`で2026-09-01に採択した。次段階はpublic projection schemaと合成fixtureであり、本Decisionだけでは本ページのrenderer・source・URLを変更せず、実データを公開しない。

このファイルは個別ページ実装時に、実装済みの内容へ更新する予定のプレースホルダーである。
