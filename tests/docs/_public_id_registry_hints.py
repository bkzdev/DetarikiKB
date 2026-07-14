"""
tests/docs/_public_id_registry_hints.py

`tests/docs/`配下のdocs testsが使う、REAL_DATA_HINTS方式のRegistry連動
許可リスト拡張ヘルパー（`feature/public-id-naming-v2-design`で新設）。

## 背景

既存のdocs tests（`test_evidence_index_public_id_policy_docs.py`等）は、
実データ由来の断片（sourceKeyの日付・イベント名断片等）を静的なタプル
`REAL_DATA_HINTS`で禁止する方式を使ってきた。

`Evidence_Index_Public_ID_Policy.md` §16で確定した匿名化方針の改定
（「sourceKeyの日付部分のみ、正式に割当済みの公開IDの構成要素として
使用可。イベント名部分は引き続き使用禁止」）に伴い、
`knowledge/public_ids/story_public_ids.yaml`へ正式登録済みの
publicStoryId/publicEpisodeIdに含まれる日付断片（6桁数字）だけは、
docsに書いてよいものとして動的に許可する必要が生じた。

## 方式

- 許可対象はRegistryへ**正式登録済み**のpublicStoryId/publicEpisodeId
  値に含まれる6桁数字（`\\d{6}`）断片のみ
- 英字を含むhint（イベント名断片・raw path断片等）は本モジュールの
  対象外とし、常にそのまま禁止され続ける（`filter_unregistered_hints`
  はそれらを一切除外しない）
- Registry未登録の日付断片（例: 移行実行前の新publicStoryId実値）は、
  本モジュールを使っても許可リストに含まれないため、引き続き検出される
- Registryファイルが存在しない場合は許可リストが空になり、既存の
  REAL_DATA_HINTS方式と完全に同じ（全hintを禁止する）挙動になる
  （後方互換、検出能力を弱めない）
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
DEFAULT_REGISTRY_PATH = (
    PROJECT_ROOT / "knowledge" / "public_ids" / "story_public_ids.yaml"
)

_DATE_FRAGMENT_PATTERN = re.compile(r"\d{6}")


def load_registered_date_fragments(
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> frozenset[str]:
    """Registryに正式登録済みのpublicStoryId/publicEpisodeId値から、
    6桁の日付断片のみを抽出して返す。

    Registryファイルが存在しない、または`stories`が空/欠落している場合は
    空集合を返す（=許可リストが空になり、既存の全面禁止方式と同じ挙動）。
    """
    if not registry_path.is_file():
        return frozenset()

    try:
        data = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return frozenset()

    fragments: set[str] = set()
    for story in data.get("stories", []) or []:
        if not isinstance(story, dict):
            continue
        public_story_id = story.get("publicStoryId")
        if isinstance(public_story_id, str):
            fragments.update(_DATE_FRAGMENT_PATTERN.findall(public_story_id))
        for episode in story.get("episodes", []) or []:
            if not isinstance(episode, dict):
                continue
            public_episode_id = episode.get("publicEpisodeId")
            if isinstance(public_episode_id, str):
                fragments.update(_DATE_FRAGMENT_PATTERN.findall(public_episode_id))
    return frozenset(fragments)


def filter_unregistered_hints(
    hints: tuple[str, ...],
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> tuple[str, ...]:
    """`hints`のうち、Registryに正式登録済みの日付断片（6桁数字ちょうど
    のhintのみが対象）を除いたタプルを返す。

    - 6桁数字ちょうどのhintで、かつRegistryに登録済みの断片と一致する
      場合のみ除外する（＝許可する）
    - それ以外のhint（英字を含むもの、6桁以外の数字列等）は無条件で
      そのまま残す（常に禁止され続ける）
    """
    registered = load_registered_date_fragments(registry_path)
    return tuple(
        hint
        for hint in hints
        if not (hint.isdigit() and len(hint) == 6 and hint in registered)
    )
