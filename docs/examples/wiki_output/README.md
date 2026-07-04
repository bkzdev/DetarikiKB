# Wiki Output Examples（合成サンプル）

このディレクトリには、`docs/architecture/07_Wiki/Wiki_Output_Design.md` で設計したWikiページ構成・front matter方針の**合成サンプル**を置く。

**重要**:

- ここに置くファイルはすべて**合成データ**（`CHAR_EXAMPLE`のような架空ID・架空名）のみで構成する。
- 実データ（実際の`.dec`スクリプト由来のキャラクター名・セリフ・場所名等）から生成したファイルは、このディレクトリを含め**一切commitしない**（`docs/runbooks/Real_Data_Dry_Run.md`・`docs/runbooks/Character_Dictionary_Review.md`と同じ既存ルール）。
- これらはWiki生成パイプライン（未実装、`Wiki_Output_Design.md` §15参照）が将来生成するページの**見本**であり、実際に生成されたページそのものではない。

## ファイル一覧

- `character_page_example.md`: Character page（`Wiki_Output_Design.md` §9.4）の合成サンプル
- `episode_page_example.md`: Episode page（`Wiki_Output_Design.md` §9.3）の合成サンプル
