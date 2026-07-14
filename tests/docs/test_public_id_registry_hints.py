"""
tests/docs/test_public_id_registry_hints.py

`tests/docs/_public_id_registry_hints.py`（Registry連動許可リスト拡張、
`feature/public-id-naming-v2-design`で新設）の単体テスト。

合成fixture registryのみを使い、以下を確認する:
- Registryに登録済みのpublicStoryId/publicEpisodeIdから6桁日付断片を
  正しく抽出できること
- `filter_unregistered_hints`が、Registry登録済みの6桁数字hintのみを
  除外し、未登録の数字hint・英字を含むhint（イベント名断片等）は
  引き続き検出対象として残すこと（検出能力を弱めないことの確認）
- Registryファイル不在・空・不正YAML時に安全側（許可リスト空、
  すなわち全hint禁止）へfallbackすること
"""

from pathlib import Path

import pytest
from _public_id_registry_hints import (
    DEFAULT_REGISTRY_PATH,
    filter_unregistered_hints,
    load_registered_date_fragments,
)

SYNTHETIC_REGISTRY = """\
registryVersion: 1
stories:
  - publicStoryId: EVENT_001_990101
    category: event
    episodes:
      - publicEpisodeId: EVENT_001_990101_E01
        episodeOrder: 1
      - publicEpisodeId: EVENT_001_990101_E02
        episodeOrder: 2
  - publicStoryId: RAID_001_990202
    category: raid
    episodes:
      - publicEpisodeId: RAID_001_990202_E01
        episodeOrder: 1
"""


@pytest.fixture
def synthetic_registry_path(tmp_path: Path) -> Path:
    path = tmp_path / "story_public_ids.yaml"
    path.write_text(SYNTHETIC_REGISTRY, encoding="utf-8")
    return path


def test_load_registered_date_fragments_extracts_from_story_and_episode(
    synthetic_registry_path: Path,
):
    fragments = load_registered_date_fragments(synthetic_registry_path)
    assert fragments == frozenset({"990101", "990202"})


def test_load_registered_date_fragments_missing_file_returns_empty(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist.yaml"
    assert load_registered_date_fragments(missing_path) == frozenset()


def test_load_registered_date_fragments_empty_file_returns_empty(tmp_path: Path):
    path = tmp_path / "empty.yaml"
    path.write_text("", encoding="utf-8")
    assert load_registered_date_fragments(path) == frozenset()


def test_load_registered_date_fragments_no_stories_key_returns_empty(tmp_path: Path):
    path = tmp_path / "no_stories.yaml"
    path.write_text("registryVersion: 1\n", encoding="utf-8")
    assert load_registered_date_fragments(path) == frozenset()


def test_load_registered_date_fragments_invalid_yaml_returns_empty(tmp_path: Path):
    path = tmp_path / "invalid.yaml"
    path.write_text("stories: [this is not: valid: yaml:\n", encoding="utf-8")
    assert load_registered_date_fragments(path) == frozenset()


def test_filter_unregistered_hints_allows_registered_date_fragment(
    synthetic_registry_path: Path,
):
    hints = ("990101", "CAMI3RD")
    result = filter_unregistered_hints(hints, synthetic_registry_path)
    assert "990101" not in result
    assert "CAMI3RD" in result


def test_filter_unregistered_hints_keeps_unregistered_date_fragment(
    synthetic_registry_path: Path,
):
    # 990101/990202はRegistry登録済みだが、990303は未登録のため引き続き禁止
    hints = ("990101", "990303")
    result = filter_unregistered_hints(hints, synthetic_registry_path)
    assert "990101" not in result
    assert "990303" in result


def test_filter_unregistered_hints_keeps_event_name_fragment_even_if_similar(
    synthetic_registry_path: Path,
):
    # 英字を含むhintは、Registryのvalue文字列に部分一致していても対象外
    # （本モジュールは6桁数字ちょうどのhintのみを許可対象にする）
    hints = ("EVENT_001_990101", "990101")
    result = filter_unregistered_hints(hints, synthetic_registry_path)
    assert "EVENT_001_990101" in result  # 英字を含むため常に残る
    assert "990101" not in result  # 6桁数字ちょうどなので許可される


def test_filter_unregistered_hints_keeps_non_six_digit_numeric_hint(
    synthetic_registry_path: Path,
):
    # 5桁・7桁など6桁ちょうどでない数字列は許可対象外のまま
    hints = ("99010", "9901011")
    result = filter_unregistered_hints(hints, synthetic_registry_path)
    assert result == hints


def test_filter_unregistered_hints_missing_registry_forbids_everything(
    tmp_path: Path,
):
    missing_path = tmp_path / "does_not_exist.yaml"
    hints = ("990101", "CAMI3RD", "260707")
    result = filter_unregistered_hints(hints, missing_path)
    assert result == hints


def test_filter_unregistered_hints_does_not_mutate_input(synthetic_registry_path: Path):
    hints = ("990101", "CAMI3RD")
    filter_unregistered_hints(hints, synthetic_registry_path)
    assert hints == ("990101", "CAMI3RD")


def test_default_registry_path_points_at_knowledge_public_ids():
    assert DEFAULT_REGISTRY_PATH.parts[-3:] == (
        "knowledge",
        "public_ids",
        "story_public_ids.yaml",
    )


def test_load_registered_date_fragments_against_real_registry_does_not_crash():
    # 実Registry（committed済み実データ）を読み込めること自体の確認のみ。
    # 実値（具体的な日付断片）はここではassertしない
    # （移行実行PRでRegistry内容が変わってもこのテストは壊れない設計とする）。
    fragments = load_registered_date_fragments()
    assert isinstance(fragments, frozenset)
