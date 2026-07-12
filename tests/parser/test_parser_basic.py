"""
tests/parser/test_parser_basic.py
StoryParser の基本動作テスト
"""

import pytest

from agents.parser.parser import StoryParser
from agents.parser.resolver import CharacterDictionary


@pytest.fixture
def char_dict():
    cd = CharacterDictionary()
    cd._name_map = {"26": "レイン", "1": "赤城陽菜"}
    cd._id_map = {"26": "CHAR_RAIN", "1": "CHAR_AKAGI_HINA"}
    return cd


def test_basic_dialogue(char_dict):
    script = """$num0 = 26
@ChTalk 0
こんにちは、レインです。
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)

    assert len(result.episodes) == 1
    scene = result.episodes[0].scenes[0]

    # blocks: 1(dialogue)
    # $num0 は変数割り当てなのでブロックにはならない
    assert len(scene.blocks) == 1

    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.text == "こんにちは、レインです。"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.has_voice is True


def test_sound_off_and_mono(char_dict):
    script = """$num0 = 1
@ChTalkSoundOff 0
声に出さないセリフ
@ChTalkMono 0
（モノローグ）
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2

    b1 = scene.blocks[0]
    assert b1.block_type == "dialogue"
    assert b1.has_voice is False
    assert b1.text == "声に出さないセリフ"

    b2 = scene.blocks[1]
    assert b2.block_type == "monologue"
    assert b2.has_voice is True
    assert b2.text == "（モノローグ）"


def test_ellipsis_only_monologue_not_lost(char_dict):
    """「……」のみの本文行が、モノローグの本文として欠落せずに
    正しく抽出されることを確認する回帰テスト
    (feature/branch-choice-dry-run、tokenizer.pyのJAPANESE_PATTERN
    範囲外のUnicodeブロックのみで構成される行がUNKNOWN化していた不具合)。
    """
    script = """$num0 = 1
@ChTalkMono 0
……
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    mono = scene.blocks[0]
    assert mono.block_type == "monologue"
    assert mono.text == "……"


def test_chtalk_name():
    script = """@ChTalkName 0 美海＆恵茉 Story/64/m64_1_186
ジャマー召喚！
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "dialogue"
    assert b.speaker.speaker_name == "美海＆恵茉"
    assert b.speaker.is_resolved is False
    assert b.text == "ジャマー召喚！"


def test_forced_name():
    script = """name 謎の声
@ChTalk 0
聞こえますか。
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "dialogue"
    assert b.speaker.speaker_name == "謎の声"
    assert b.speaker.is_resolved is False


def test_empty_name_line_does_not_blank_resolved_speaker(char_dict):
    """
    実スクリプトでは、話者名を解除するための空の `name` 行が単独で
    現れることがある (例: CAB-csl_script_charastory_character234-episode1.dec)。
    これが直後のスロット解決済み話者を空文字名で潰さないことを確認する。
    """
    script = """$num0 = 26
@ScenarioCosLoad 0 $num0
name
@ChTalkSoundOff 0
スロットで解決された話者のはずのセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.speaker.speaker_name != ""


def test_narration():
    script = """msg
異形生物対策班　本部
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    b = scene.blocks[0]
    assert b.block_type == "narration"
    assert b.text == "異形生物対策班　本部"
    assert b.narration_type == "plain"


def test_choice_branch():
    script = """branch 選択肢A 選択肢B
#if $branch
@ChTalk 0
ルートA
#elseif $branch
@ChTalk 0
ルートB
#endif
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    choice = scene.blocks[0]
    assert choice.block_type == "choice"

    assert len(choice.options) == 2
    assert choice.options[0]["optionText"] == "選択肢A"
    assert len(choice.options[0]["blocks"]) == 1
    assert choice.options[0]["blocks"][0].text == "ルートA"

    assert choice.options[1]["optionText"] == "選択肢B"
    assert len(choice.options[1]["blocks"]) == 1
    assert choice.options[1]["blocks"][0].text == "ルートB"


def test_content_after_choice_endif_returns_to_scene_level():
    """#endif以降のブロックが、選択肢の最後のoptionに閉じ込められず
    シーンレベルへ正しく戻ることを確認する回帰テスト。

    実データdry-run trialで、branch/#if/#else/#endifの直後に続く
    大量のstage_direction/dialogueが、#endif以降であるにもかかわらず
    最後のoption (#else側) のblocksに丸ごと取り込まれてしまう不具合を
    発見した (feature/branch-choice-dry-run)。原因は#if側でbranch_stackへ
    現在のchoiceそのものをpushしており、#endifで同じchoiceがpopされ
    current_choiceがNoneに戻らなかったこと。
    """
    script = """branch 選択肢A 選択肢B
#if $branch
@ChTalk 0
ルートA
#else
@ChTalk 0
ルートB
#endif
@ChTalk 0
分岐後のセリフ
msg
分岐後のナレーション
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    # choice + 分岐後dialogue + 分岐後narration がシーンレベルに3件並ぶ
    assert len(scene.blocks) == 3
    choice, after_dialogue, after_narration = scene.blocks

    assert choice.block_type == "choice"
    assert len(choice.options[0]["blocks"]) == 1
    assert choice.options[0]["blocks"][0].text == "ルートA"
    assert len(choice.options[1]["blocks"]) == 1
    assert choice.options[1]["blocks"][0].text == "ルートB"

    assert after_dialogue.block_type == "dialogue"
    assert after_dialogue.text == "分岐後のセリフ"

    assert after_narration.block_type == "narration"
    assert after_narration.text == "分岐後のナレーション"


def test_nested_branch_inside_choice_option_restores_outer_choice():
    """choiceのoption内にさらにネストしたbranchがあっても、内側の#endifで
    外側のchoiceへ正しく戻ることを確認する (branch_stackのpush/pop対象を
    branch呼び出し時のcurrent_choiceに変更した際の副作用が無いことの確認)。
    """
    script = """branch 外側A 外側B
#if $branch
branch 内側1 内側2
#if $branch
@ChTalk 0
内側ルート1
#else
@ChTalk 0
内側ルート2
#endif
@ChTalk 0
外側Aの続き
#else
@ChTalk 0
外側B
#endif
@ChTalk 0
分岐後のセリフ
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2
    outer_choice, after = scene.blocks
    assert outer_choice.block_type == "choice"
    assert after.block_type == "dialogue"
    assert after.text == "分岐後のセリフ"

    # 外側option0の中に、内側choice + 外側Aの続き の2ブロックがあること
    outer_opt0_blocks = outer_choice.options[0]["blocks"]
    assert len(outer_opt0_blocks) == 2
    inner_choice, outer_a_continued = outer_opt0_blocks
    assert inner_choice.block_type == "choice"
    assert outer_a_continued.block_type == "dialogue"
    assert outer_a_continued.text == "外側Aの続き"

    assert len(inner_choice.options[0]["blocks"]) == 1
    assert inner_choice.options[0]["blocks"][0].text == "内側ルート1"
    assert len(inner_choice.options[1]["blocks"]) == 1
    assert inner_choice.options[1]["blocks"][0].text == "内側ルート2"

    # 外側option1 (外側B) は1ブロックのみ
    outer_opt1_blocks = outer_choice.options[1]["blocks"]
    assert len(outer_opt1_blocks) == 1
    assert outer_opt1_blocks[0].text == "外側B"


def test_stage_direction():
    script = """bg 1 1002
@Visibleoff 1 0.5
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2

    bg = scene.blocks[0]
    assert bg.block_type == "stage_direction"
    assert bg.direction_type == "background"
    assert bg.raw_command == "bg"

    vis = scene.blocks[1]
    assert vis.block_type == "stage_direction"
    assert vis.direction_type == "character_display"
    assert vis.raw_command == "@Visibleoff"
    assert vis.normalized_command == "@VisibleOff"


def test_real_data_camera_commands_become_stage_direction():
    """実データdry-run trialでunknown扱いだったcamera/pos/euler/fov等が
    stage_directionとして分類されることを確認する
    (docs/runbooks/Real_Data_Dry_Run_Result_Template.md §3.2)。"""
    script = """camera 0
pos -7.94,1.4,22.08
euler 3.821,141.302,0
fov 21
ch 1
nf 0.3 500
wait 0.5
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 7
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    assert scene.blocks[0].raw_command == "camera"
    assert scene.blocks[0].direction_type == "camera"
    assert scene.blocks[1].raw_command == "pos"
    assert scene.blocks[1].direction_type == "camera"
    assert scene.blocks[2].raw_command == "euler"
    assert scene.blocks[2].direction_type == "camera"
    assert scene.blocks[3].raw_command == "fov"
    assert scene.blocks[3].direction_type == "camera"
    assert scene.blocks[4].raw_command == "ch"
    assert scene.blocks[4].direction_type == "camera"
    assert scene.blocks[5].raw_command == "nf"
    assert scene.blocks[5].direction_type == "camera"
    assert scene.blocks[6].raw_command == "wait"
    assert scene.blocks[6].direction_type == "system"


def test_dialogue_count_unaffected_by_interleaved_camera_commands(char_dict):
    """camera系演出コマンドがセリフの間に挟まっても、dialogue/monologueの
    数・本文・evidence用の行番号が変わらないことを確認する。"""
    script = """$num0 = 26
camera 0
pos -7.94,1.4,22.08
@ChTalk 0
一言目のセリフ
euler 3.821,141.302,0
fov 21
wait 0.5
@ChTalkMono 0
（モノローグ）
ui 0
"""
    parser = StoryParser(char_dict=char_dict, preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    dialogue_blocks = [b for b in scene.blocks if b.block_type == "dialogue"]
    monologue_blocks = [b for b in scene.blocks if b.block_type == "monologue"]
    unknown_blocks = [b for b in scene.blocks if b.block_type == "unknown"]
    stage_blocks = [b for b in scene.blocks if b.block_type == "stage_direction"]

    assert len(dialogue_blocks) == 1
    assert dialogue_blocks[0].text == "一言目のセリフ"
    assert dialogue_blocks[0].speaker.speaker_name == "レイン"

    assert len(monologue_blocks) == 1
    assert monologue_blocks[0].text == "（モノローグ）"

    assert len(unknown_blocks) == 0
    assert len(stage_blocks) == 6

    # evidence用の行番号 (line_start/line_end) が壊れていないこと
    assert dialogue_blocks[0].line_start == 5
    assert monologue_blocks[0].line_end == 10


def test_branch_choice_dry_run_commands_become_stage_direction():
    """branch/choice included dry-runで見つかったcostume/fa/@TalkPosR/
    @TalkPosL/@ChEyeOff/@VisibleS/@FadeOutBlackが、unknownではなく
    stage_directionとして分類されることを確認する。"""
    script = """costume 1 2
fa 3
@TalkPosR
@TalkPosL
@ChEyeOff 0
@VisibleS 1
@FadeOutBlack 1
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 7
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    assert scene.blocks[0].raw_command == "costume"
    assert scene.blocks[0].direction_type == "character_display"
    assert scene.blocks[1].raw_command == "fa"
    assert scene.blocks[1].direction_type == "character_display"
    assert scene.blocks[2].raw_command == "@TalkPosR"
    assert scene.blocks[2].direction_type == "ui"
    assert scene.blocks[3].raw_command == "@TalkPosL"
    assert scene.blocks[3].direction_type == "ui"
    assert scene.blocks[4].raw_command == "@ChEyeOff"
    assert scene.blocks[4].direction_type == "character_display"
    assert scene.blocks[5].raw_command == "@VisibleS"
    assert scene.blocks[5].direction_type == "character_display"
    assert scene.blocks[6].raw_command == "@FadeOutBlack"
    assert scene.blocks[6].direction_type == "screen"


def test_dict_expansion_batch_001_command_becomes_stage_direction():
    """script-command-dictionary-expansion-batch-001 dry-runで見つかった
    @ChBlueMan/BlueMan2が、unknownではなくstage_direction(character_display)
    として分類されることを確認する。"""
    script = """@ChBlueMan/BlueMan2 0 1 22
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    block = scene.blocks[0]
    assert block.block_type == "stage_direction"
    assert block.raw_command == "@ChBlueMan/BlueMan2"
    assert block.direction_type == "character_display"
    assert block.command_args == ["0", "1", "22"]


def test_dialogue_count_unaffected_by_branch_choice_dry_run_commands(char_dict):
    """costume/fa/@TalkPosR等がセリフの間に挟まっても、dialogue/monologueの
    数・本文・evidence用の行番号が変わらないことを確認する。"""
    script = """$num0 = 26
costume 1 2
fa 3
@ChTalk 0
一言目のセリフ
@TalkPosR
@ChEyeOff 0
@ChTalkMono 0
（モノローグ）
@VisibleS 1
@FadeOutBlack 1
"""
    parser = StoryParser(char_dict=char_dict, preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    dialogue_blocks = [b for b in scene.blocks if b.block_type == "dialogue"]
    monologue_blocks = [b for b in scene.blocks if b.block_type == "monologue"]
    unknown_blocks = [b for b in scene.blocks if b.block_type == "unknown"]
    stage_blocks = [b for b in scene.blocks if b.block_type == "stage_direction"]

    assert len(dialogue_blocks) == 1
    assert dialogue_blocks[0].text == "一言目のセリフ"
    assert dialogue_blocks[0].speaker.speaker_name == "レイン"

    assert len(monologue_blocks) == 1
    assert monologue_blocks[0].text == "（モノローグ）"

    assert len(unknown_blocks) == 0
    assert len(stage_blocks) == 6

    assert dialogue_blocks[0].line_start == 5
    assert monologue_blocks[0].line_end == 9


def test_truly_unknown_command_still_reported_as_unknown():
    """既知演出コマンド追加後も、本当に未知のコマンドは引き続き
    unknownとして保持・報告されることを確認する。"""
    script = """camera 0
totallyUnknownCommand123 foo bar
"""
    parser = StoryParser(preserve_unknown=True, preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2
    assert scene.blocks[0].block_type == "stage_direction"
    assert scene.blocks[1].block_type == "unknown"
    assert "totallyUnknownCommand123" in scene.blocks[1].raw_text
