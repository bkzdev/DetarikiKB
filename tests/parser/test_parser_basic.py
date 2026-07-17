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


# ----------------------------------------------------------------
# @ScenarioCos 変数引数形式 (feature/scenario-cos-variable-variant-support)
# 第2引数が $numX/$valueX 等の変数の場合、@ScenarioCosLoad と同じ意味論
# (変数マップからIDを引いてスロットへ束縛) で処理されることを確認する。
# ----------------------------------------------------------------


def test_scenario_cos_numeric_direct_form_unaffected(char_dict):
    """既存の数値直接指定形式 (@ScenarioCos slot id) の挙動に無回帰であること。"""
    script = """@ScenarioCos 6 26
@ChTalk 6
数値直接指定のセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    dlg = result.episodes[0].scenes[0].blocks[0]

    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.speaker.is_resolved is True


def test_scenario_cos_variable_form_slot_equals_index_matches_numeric_form(char_dict):
    """$numX形式でslot==変数indexのケースは、数値直接指定と同一の結果になること。"""
    script_var = """$num1 = 26
@ScenarioCos 1 $num1
@ChTalk 1
こんにちは、レインです。
"""
    script_numeric = """$num1 = 26
@ScenarioCos 1 26
@ChTalk 1
こんにちは、レインです。
"""
    dlg_var = (
        StoryParser(char_dict=char_dict)
        .parse_text(script_var)
        .episodes[0]
        .scenes[0]
        .blocks[0]
    )
    dlg_num = (
        StoryParser(char_dict=char_dict)
        .parse_text(script_numeric)
        .episodes[0]
        .scenes[0]
        .blocks[0]
    )

    assert dlg_var.speaker.speaker_name == "レイン"
    assert dlg_var.speaker.is_resolved is True
    assert dlg_var.speaker.speaker_name == dlg_num.speaker.speaker_name
    assert dlg_var.speaker.speaker_id == dlg_num.speaker.speaker_id


def test_scenario_cos_variable_form_slot_not_equal_index(char_dict):
    """
    $num7 = 1 は resolver.assign_variable の副作用でスロット "7" にも自動束縛するが、
    @ScenarioCos 2 $num7 はそれとは別に、変数を参照してスロット "2" (indexとは異なる)
    を正しく同じキャラクターへ束縛できることを確認する。
    """
    script = """$num7 = 1
@ScenarioCos 2 $num7
@ChTalk 2
スロット2のセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    dlg = result.episodes[0].scenes[0].blocks[0]

    assert dlg.speaker.speaker_name == "赤城陽菜"
    assert dlg.speaker.is_resolved is True


def test_scenario_cos_variable_form_value_variable(char_dict):
    """$valueN形式の変数も @ScenarioCos の第2引数として正しく参照されること。"""
    script = """$value0 = 1
@ScenarioCos 4 $value0
@ChTalk 4
スロット4のセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    dlg = result.episodes[0].scenes[0].blocks[0]

    assert dlg.speaker.speaker_name == "赤城陽菜"
    assert dlg.speaker.is_resolved is True


def test_scenario_cos_variable_form_undefined_variable_yields_unknown_speaker(
    char_dict,
):
    """未定義変数を参照した場合、話者を破棄せずunknown speakerとして保持すること。"""
    script = """@ScenarioCos 2 $numUndefined
@ChTalk 2
定義されていない変数のセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    dlg = result.episodes[0].scenes[0].blocks[0]

    assert dlg.speaker.is_resolved is False
    assert dlg.speaker.speaker_id is None
    assert "slot2" in dlg.speaker.speaker_name


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


def test_dict_expansion_batch_002_new_commands_become_stage_direction():
    """script-command-dictionary-expansion-batch-002 (実データ全量scan、
    本編系2,301件) で見つかった未知コマンド172種のうち、代表的な新規
    stage_directionコマンドが unknown ではなく stage_direction として
    正しい direction_type に分類されることを確認する。"""
    script = """@ChEye2Off
@Bg_Default
@Timeline/Play 0 0 False
@TalkPosRR
@ChTalkname 8 ? Event/example
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 5
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    assert scene.blocks[0].raw_command == "@ChEye2Off"
    assert scene.blocks[0].direction_type == "character_display"
    assert scene.blocks[1].raw_command == "@Bg_Default"
    assert scene.blocks[1].direction_type == "background"
    assert scene.blocks[2].raw_command == "@Timeline/Play"
    assert scene.blocks[2].direction_type == "system"
    assert scene.blocks[3].raw_command == "@TalkPosRR"
    assert scene.blocks[3].direction_type == "ui"
    assert scene.blocks[4].raw_command == "@ChTalkname"
    assert scene.blocks[4].direction_type == "character_display"


def test_dict_expansion_batch_002_case_variants_normalize_to_canonical():
    """script-command-dictionary-expansion-batch-002 で見つかった表記ゆれが、
    CASE_VARIANTS_MAP経由で正規形へ正規化されつつ stage_direction として
    分類されることを確認する。"""
    script = """@cheye2off
@talkposRR
@chcamera
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 3

    assert scene.blocks[0].raw_command == "@cheye2off"
    assert scene.blocks[0].normalized_command == "@ChEye2Off"
    assert scene.blocks[0].direction_type == "character_display"

    assert scene.blocks[1].raw_command == "@talkposRR"
    assert scene.blocks[1].normalized_command == "@TalkPosRR"
    assert scene.blocks[1].direction_type == "ui"

    assert scene.blocks[2].raw_command == "@chcamera"
    assert scene.blocks[2].normalized_command == "@ChCamera"
    assert scene.blocks[2].direction_type == "camera"


def test_stage2_batch_promotion_new_commands_become_stage_direction():
    """evidence-index-stage2-batch-promotionで実データnormalize時に見つかった
    未登録コマンド3種 (vol/{/}) が、unknownではなくstage_directionとして
    正しいdirection_typeに分類されることを確認する。"""
    script = """sound Bgm ca_battle_event_boss
vol 0
sound Bgm ca_battle_event_boss
vol 1
{
ch 0
@Visible

ch 1
@Visible
}
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    stage_blocks = [b for b in scene.blocks if b.block_type == "stage_direction"]
    assert all(b.block_type == "stage_direction" for b in scene.blocks)

    vol_blocks = [b for b in stage_blocks if b.raw_command == "vol"]
    assert len(vol_blocks) == 2
    assert vol_blocks[0].direction_type == "sound"
    assert vol_blocks[0].command_args == ["0"]
    assert vol_blocks[1].direction_type == "sound"
    assert vol_blocks[1].command_args == ["1"]

    open_brace_blocks = [b for b in stage_blocks if b.raw_command == "{"]
    close_brace_blocks = [b for b in stage_blocks if b.raw_command == "}"]
    assert len(open_brace_blocks) == 1
    assert len(close_brace_blocks) == 1
    assert open_brace_blocks[0].direction_type == "character_display"
    assert close_brace_blocks[0].direction_type == "character_display"


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


def test_dict_h_scene_parse_target_batch_new_commands_become_stage_direction():
    """script-command-dictionary-h-scene-parse-target-batch (character/配下の
    パース対象ファイル: H_sceneN本体・H_scene_s・episodeN/episode_EXに
    1回以上出現する未登録コマンド24種のうち) で見つかった新規
    stage_directionコマンド8種が、unknownではなくstage_directionとして
    正しいdirection_typeに分類されることを確認する。"""
    script = """@ShadowOff
@ChBlueMan/SynchroMotionMirror 1 h_03_09_05 0 BlueMan/h_03_09_05_ 0.2
@Cache Motion Human/h_04_05_00
@SpringBone/BreastTouchRemoveCollider 2 1 1 2
@Spine/EyeRight
@Spine/EyeLeft
@Spine/EyeCenter
@ChBlueMan/BlueManSuimedo 0 0 17
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 8
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    assert scene.blocks[0].raw_command == "@ShadowOff"
    assert scene.blocks[0].direction_type == "character_display"
    assert scene.blocks[1].raw_command == "@ChBlueMan/SynchroMotionMirror"
    assert scene.blocks[1].direction_type == "motion"
    assert scene.blocks[2].raw_command == "@Cache"
    assert scene.blocks[2].direction_type == "system"
    assert scene.blocks[3].raw_command == "@SpringBone/BreastTouchRemoveCollider"
    assert scene.blocks[3].direction_type == "motion"
    assert scene.blocks[4].raw_command == "@Spine/EyeRight"
    assert scene.blocks[4].direction_type == "character_display"
    assert scene.blocks[5].raw_command == "@Spine/EyeLeft"
    assert scene.blocks[5].direction_type == "character_display"
    assert scene.blocks[6].raw_command == "@Spine/EyeCenter"
    assert scene.blocks[6].direction_type == "character_display"
    assert scene.blocks[7].raw_command == "@ChBlueMan/BlueManSuimedo"
    assert scene.blocks[7].direction_type == "character_display"


def test_dict_h_scene_parse_target_batch_case_variants_normalize_to_canonical():
    """script-command-dictionary-h-scene-parse-target-batchで見つかった
    表記ゆれ7種が、CASE_VARIANTS_MAP経由で正規形へ正規化されつつ
    stage_directionとして分類されることを確認する。"""
    script = """@motionwaitU h_02_01_016_
@ChEYe2RightLow
@ChEye2RIghtLow
@ChEye2LeftlOW
@ChEYe2RightHigh
@MotioNReset
@Shadowoff
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 7

    assert scene.blocks[0].raw_command == "@motionwaitU"
    assert scene.blocks[0].normalized_command == "@MotionWaitU"
    assert scene.blocks[0].direction_type == "motion"

    assert scene.blocks[1].raw_command == "@ChEYe2RightLow"
    assert scene.blocks[1].normalized_command == "@ChEye2RightLow"
    assert scene.blocks[1].direction_type == "character_display"

    assert scene.blocks[2].raw_command == "@ChEye2RIghtLow"
    assert scene.blocks[2].normalized_command == "@ChEye2RightLow"
    assert scene.blocks[2].direction_type == "character_display"

    assert scene.blocks[3].raw_command == "@ChEye2LeftlOW"
    assert scene.blocks[3].normalized_command == "@ChEye2LeftLow"
    assert scene.blocks[3].direction_type == "character_display"

    assert scene.blocks[4].raw_command == "@ChEYe2RightHigh"
    assert scene.blocks[4].normalized_command == "@ChEye2RightHigh"
    assert scene.blocks[4].direction_type == "character_display"

    assert scene.blocks[5].raw_command == "@MotioNReset"
    assert scene.blocks[5].normalized_command == "@MotionReset"
    assert scene.blocks[5].direction_type == "motion"

    assert scene.blocks[6].raw_command == "@Shadowoff"
    assert scene.blocks[6].normalized_command == "@ShadowOff"
    assert scene.blocks[6].direction_type == "character_display"


# ----------------------------------------------------------------
# @SpineTalk + variant-only 17種
# (script-command-dictionary-spinetalk-variant-only-batch)
# ----------------------------------------------------------------


def test_spine_talk_variable_slot_form_produces_dialogue(char_dict):
    """@SpineTalk $numN <path> (実データで支配的な形式、延べ2,893回中2,891回)
    が、@ChTalkと同様にdialogueブロックを生成し、$numN代入時に自動束縛
    されたスロット (slot番号==変数index) 経由で話者解決されることを
    確認する。"""
    script = """$num2 = 26
@SpineTalk $num2 H_scene/1/1_h14_42
セリフ本文
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.text == "セリフ本文"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.speaker.is_resolved is True
    assert dlg.has_voice is True
    assert dlg.parser_rule == "spine_talk_dialogue"


def test_spine_talk_numeric_slot_direct_form_produces_dialogue(char_dict):
    """@SpineTalk slot <path> (数値スロット直接指定形式、実データでは
    延べ2回のみ) も@ChTalkと同じ意味論でスロット解決されることを確認する。"""
    script = """@ScenarioCos 1 26
@SpineTalk 1 H_scene/217/217_h12_57
数値スロット直接指定のセリフ
"""
    parser = StoryParser(char_dict=char_dict)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.speaker.speaker_name == "レイン"
    assert dlg.speaker.is_resolved is True
    assert dlg.has_voice is True


def test_spine_talk_unresolved_slot_not_dropped():
    """未割り当てスロットを参照する@SpineTalkでも、不明人物placeholderと
    してブロックが生成され破棄されないこと (AI_CONTEXT.md §13.3の
    不明情報を破棄しない不変則)。"""
    script = """@SpineTalk $num9 H_scene/1/1_h1_1
未解決スロットのセリフ
"""
    parser = StoryParser()
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    dlg = scene.blocks[0]
    assert dlg.block_type == "dialogue"
    assert dlg.speaker.is_resolved is False
    assert dlg.text == "未解決スロットのセリフ"


def test_dict_spinetalk_variant_only_batch_new_commands_become_stage_direction():
    """script-command-dictionary-spinetalk-variant-only-batchで見つかった
    variant-only(パース対象外ファイル集合にのみ出現)の新規stage_direction
    コマンド6種が、unknownではなくstage_directionとして正しい
    direction_typeに分類されることを確認する。"""
    script = """@ToCloud
@VR/VRSelect
@SpringBone/BreastTouchAddCollider 2 1 1 2
@WebParsonal $value10 $arg3
@Spine/EyeDown
@ChMotionGree 0
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 6
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    assert scene.blocks[0].raw_command == "@ToCloud"
    assert scene.blocks[0].direction_type == "screen"
    assert scene.blocks[1].raw_command == "@VR/VRSelect"
    assert scene.blocks[1].direction_type == "system"
    assert scene.blocks[2].raw_command == "@SpringBone/BreastTouchAddCollider"
    assert scene.blocks[2].direction_type == "motion"
    assert scene.blocks[3].raw_command == "@WebParsonal"
    assert scene.blocks[3].direction_type == "system"
    assert scene.blocks[4].raw_command == "@Spine/EyeDown"
    assert scene.blocks[4].direction_type == "character_display"
    assert scene.blocks[5].raw_command == "@ChMotionGree"
    assert scene.blocks[5].direction_type == "motion"


def test_dict_spinetalk_variant_only_batch_case_variants_normalize_to_canonical():
    """script-command-dictionary-spinetalk-variant-only-batchで見つかった
    表記ゆれ2種が、CASE_VARIANTS_MAP経由で正規形へ正規化されつつ
    stage_directionとして分類されることを確認する。"""
    script = """@motionWait sg_standup_sigh4
@FadeOutblack
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2

    assert scene.blocks[0].raw_command == "@motionWait"
    assert scene.blocks[0].normalized_command == "@MotionWait"
    assert scene.blocks[0].direction_type == "motion"

    assert scene.blocks[1].raw_command == "@FadeOutblack"
    assert scene.blocks[1].normalized_command == "@FadeOutBlack"
    assert scene.blocks[1].direction_type == "screen"


# ----------------------------------------------------------------
# 裸単語パラメータトークン14種+表記ゆれ1種
# (bare-word-parameter-token-registration、
# Character_Story_ID_Manifest_Design.md §9.1.2の1)
# ----------------------------------------------------------------


def test_bare_word_parameter_token_registration_becomes_stage_direction():
    """character/配下の`_spine`系ファイルに出現する、@接頭辞を持たない
    継続パラメータ行のうち、カメラ/ポストエフェクト系と機械分類できた
    14種が、unknownではなくstage_directionとして正しいdirection_typeに
    分類されることを確認する。"""
    script = """postProcess 1
depth length 33
bloom intensity 2
enable 0 false
volume enable true
analogGlitch
retroGlitch
digitalGlitch
mozaiku koyuki_9 0.018 cutoff
fade\t0\t0
mask SET CAMERA0
layer CAMERA1 true
duplication true
shadow type None
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 14
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    expected = [
        ("postProcess", "screen"),
        ("depth", "screen"),
        ("bloom", "screen"),
        ("enable", "screen"),
        ("volume", "screen"),
        ("analogGlitch", "screen"),
        ("retroGlitch", "screen"),
        ("digitalGlitch", "screen"),
        ("mozaiku", "screen"),
        ("fade", "screen"),
        ("mask", "camera"),
        ("layer", "camera"),
        ("duplication", "camera"),
        ("shadow", "camera"),
    ]
    pairs = zip(scene.blocks, expected, strict=True)
    for block, (raw_command, direction_type) in pairs:
        assert block.raw_command == raw_command
        assert block.direction_type == direction_type


def test_bare_word_parameter_token_registration_case_variant_normalizes_to_camera():
    """ "caemra" ("camera"のtypo) が、CASE_VARIANTS_MAP経由で正規形
    "camera" へ正規化されつつstage_direction(camera)として分類される
    ことを確認する。"""
    script = """caemra 0
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 1
    block = scene.blocks[0]
    assert block.block_type == "stage_direction"
    assert block.raw_command == "caemra"
    assert block.normalized_command == "camera"
    assert block.direction_type == "camera"


# ----------------------------------------------------------------
# 裸単語パラメータトークン残り17種
# (bare-word-parameter-token-batch-002、
# Character_Story_ID_Manifest_Design.md §9.1.2の1)
# ----------------------------------------------------------------


def test_bare_word_parameter_token_batch_002_becomes_stage_direction():
    """PR #153で「要判断」のまま未登録とした残り17種が、unknownでは
    なくstage_directionとして正しいdirection_typeに分類されることを
    確認する。分類はFable決定(2026-07-17)に基づく安全側割り当て
    (character_display=spine/eye/hlook、motion=timeScale/springEnable/
    add/moPart、system=それ以外)。"""
    script = """spine 0
eye 0,0
hlook false
timeScale -1 1.2
springEnable\tF_L_ribbon\tfalse
add 0 animation3 true 0
moPart speed $common0
func ui_massage breast1
log --------------------HighGraphicsFlag:$value7
init
setup 0
skin normal face/H02
segment\tEye\ttrue $target(Unique,0,Head)
cset\ti 999 neck\t1,1,1\tmind\t2\ttall\t4\theadBlueMan30/hair30\t-
rdrawMat tatoo1 keep_alpha 0 @,@,@,@\t@,@,@,1
acc\t1\twset\tChara/Parts/Accessory/body564_0_acc\t@body564_0_acc\tbody564_0_acc_0
oneAuto
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 17
    for block in scene.blocks:
        assert block.block_type == "stage_direction"

    expected = [
        ("spine", "character_display"),
        ("eye", "character_display"),
        ("hlook", "character_display"),
        ("timeScale", "motion"),
        ("springEnable", "motion"),
        ("add", "motion"),
        ("moPart", "motion"),
        ("func", "system"),
        ("log", "system"),
        ("init", "system"),
        ("setup", "system"),
        ("skin", "system"),
        ("segment", "system"),
        ("cset", "system"),
        ("rdrawMat", "system"),
        ("acc", "system"),
        ("oneAuto", "system"),
    ]
    pairs = zip(scene.blocks, expected, strict=True)
    for block, (raw_command, direction_type) in pairs:
        assert block.raw_command == raw_command
        assert block.direction_type == direction_type


def test_bare_word_parameter_tokens_left_unregistered_remain_unknown():
    """PR #153・本PRいずれの登録対象にも含まれない合成裸単語行
    (実データ由来ではない) が、引き続きunknownブロックとして保持
    されること (不破棄不変則、AI_CONTEXT.md §13.3) の無回帰を確認する。"""
    script = """synthUnregisteredBareWordAlpha 0
synthUnregisteredBareWordBeta true
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    assert len(scene.blocks) == 2
    for block in scene.blocks:
        assert block.block_type == "unknown"


def test_bare_word_parameter_token_registration_no_regression_on_text_and_keywords():
    """裸単語パラメータトークン登録が、日本語TEXT行検出・既存keyword
    (msg/branch/#if等)・既存コマンドの挙動に影響しないこと (無回帰) を
    確認する。"""
    script = """$num0 = 26
@ChTalk 0
セリフ本文
msg
ナレーション本文
branch 選択肢A 選択肢B
#if $branch
@ChTalk 0
ルートA
#else
@ChTalk 0
ルートB
#endif
camera 0
pos 1,2,3
"""
    parser = StoryParser(preserve_stage_directions=True)
    result = parser.parse_text(script)
    scene = result.episodes[0].scenes[0]

    unknown_blocks = [b for b in scene.blocks if b.block_type == "unknown"]
    assert unknown_blocks == []

    block_types = [b.block_type for b in scene.blocks]
    assert "dialogue" in block_types
    assert "narration" in block_types
    assert "choice" in block_types
