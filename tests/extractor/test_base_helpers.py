"""agents.extractor.baseの共通evidence helper単体テスト。"""

from agents.extractor.base import add_block_evidence_if_needed, iter_blocks_recursive


def test_iter_blocks_recursive_uses_depth_first_preorder():
    blocks = [
        {"id": "TOP_001", "type": "dialogue"},
        {
            "id": "CHOICE_001",
            "type": "choice",
            "options": [
                {
                    "blocks": [
                        {"id": "NESTED_001", "type": "stage_direction"},
                        {
                            "id": "CHOICE_002",
                            "type": "choice",
                            "options": [
                                {"blocks": [{"id": "NESTED_002", "type": "dialogue"}]}
                            ],
                        },
                    ]
                },
                {"blocks": [{"id": "NESTED_003", "type": "narration"}]},
            ],
        },
        {"id": "TOP_002", "type": "monologue"},
    ]

    assert [block["id"] for block in iter_blocks_recursive(blocks)] == [
        "TOP_001",
        "CHOICE_001",
        "NESTED_001",
        "CHOICE_002",
        "NESTED_002",
        "NESTED_003",
        "TOP_002",
    ]


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
