# Wiki狭幅表示の横はみ出し点検（2026-09-26）

## 目的と範囲

PR #313〜#317で変更したWikiの縦並び表示を含め、現行rendererの合成サイトを一括点検した。実データや公開設定の変更、production deployは行わない。実URL、個別ID、生成Markdown・HTMLはこの記録へ含めない。

## 手順と結果

- schema-validな既存の合成Merged Collectionと合成Character Profileから、ローカルpreviewに22 routeを生成した。一時MkDocs設定・生成物はignored `workspace/wiki_preview/`限定とした。
- `mkdocs serve`上で全22 routeを320pxと390pxのviewportで開き、各ページのdocument幅と、残る`table` / `pre` / `code`要素の内部幅をブラウザーDOMで測定した。両幅ともdocument横はみ出し0件、要素内横スクロール0件だった。
- 対象はTop、6種entity index、Character個別ページ、Unresolved report、Story index、Story / Episode pageである。合成fixtureに生成対象がないLocation / Organization / Item / Lore / Eventの個別ページは、この22 routeに含まれない。
- 公開済みStoryを匿名の1 routeだけ読み取り専用で320pxと390pxにて測定し、document横はみ出し0件だった。公開サイトの全routeや画面上の美観を網羅した結果ではない。
- ブラウザーの幅計測が主な確認手段であり、スクリーンショットによる全ページの目視判定は行っていない。横はみ出し以外の可読性は、後続の実ページ確認に残す。

## 判断と残件

今回の測定範囲では追加のrenderer修正を要する再現例は無かった。短い集計表を形式だけで一律に縦並びへ変更しない。長い実値、新規page種別、テーマ・公開generatorの更新時には、対象routeを同じ幅で再測定し、実際の問題を確認してから個別に改善する。実データ由来の生成物は引き続きcommitしない。
