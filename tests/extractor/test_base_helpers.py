"""agents.extractor.baseの共通evidence helper単体テスト。"""

from agents.extractor.base import add_block_evidence_if_needed


def test_add_block_evidence_skips_standard_evidence_block():
    extra_evidence = {}
    block = {
        "id": "EP01_DLG0001",
        "type": "dialogue",
        "source": {"confidence": 0.4},
    }

    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id="TEST_STORY",
        episode_id="EP01",
        scene_id="EP01_SC001",
    )

    assert extra_evidence == {}


def test_add_block_evidence_preserves_explicit_zero_confidence():
    extra_evidence = {}
    block = {
        "id": "EP01_STAGE0001",
        "type": "stage_direction",
        "source": {"confidence": 0.0},
    }

    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id="TEST_STORY",
        episode_id="EP01",
        scene_id="EP01_SC001",
    )

    assert extra_evidence["EP01_STAGE0001"] == {
        "sourceId": "EP01_STAGE0001",
        "storyId": "TEST_STORY",
        "episodeId": "EP01",
        "sceneId": "EP01_SC001",
        "confidence": 0.0,
    }


def test_add_block_evidence_uses_default_and_keeps_first_value():
    extra_evidence = {}
    block = {
        "id": "EP01_STAGE0001",
        "type": "stage_direction",
        "source": {},
    }

    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id="TEST_STORY",
        episode_id="EP01",
        scene_id="EP01_SC001",
    )
    block["source"]["confidence"] = 0.2
    add_block_evidence_if_needed(
        extra_evidence,
        block,
        story_id="TEST_STORY",
        episode_id="EP01",
        scene_id="EP01_SC999",
    )

    assert extra_evidence["EP01_STAGE0001"] == {
        "sourceId": "EP01_STAGE0001",
        "storyId": "TEST_STORY",
        "episodeId": "EP01",
        "sceneId": "EP01_SC001",
        "confidence": 1.0,
    }
