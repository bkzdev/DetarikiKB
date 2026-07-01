import json
import re
import os
import shutil
from datetime import datetime
import argparse # 追加
import sys

# 外部の整形スクリプトをインポート
try:
    from convert_script import convert_script as format_for_coeiroink
except ImportError:
    print("[警告] convert_script.py が見つかりません。COEIROINK用の最終整形はスキップされます。")
    format_for_coeiroink = None

# キャラクター設定の読み込み
def load_characters(path='characters.json'):
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"JSON読み込みエラー: {e}")
    return {}

# 1ファイルの変換処理 (最新ロジック適用版)
def format_for_tts(file_path, char_map):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    output = []
    # 変数名とIDの対応を保存する辞書
    variable_map = {}
    
    current_speakers = {} 
    pending_speaker = None
    forced_name = None
    max_num_index = -1
    
    branch_options = []
    branch_index = 0

    # 削除対象コマンド群
    command_keywords = [
        'wType', 'prefab', 'costume', 'fa', 'nf', 'mo', 'hide', 'click', 'init',
        'bg', 'set', 'wait', 'pos', 'euler', 'fov', 'sound', 'ui', 'rdraw',
        'uniq', 'camera', 'visible', 'active', 'ch', 'vo', 'vol', 'color',
        'char', 'speed', 'face', 'fade', 'se', 'shake', 'move', 'alpha',
        'item', 'effect', 'btl', 'cam', 'cset', 'func', 'lips', 'loading',
        'lset', 'parent', 'remove', 'scale', 'screen', 'segment', 'wset',
        'pcon', 'mset', '@MotionWait', '@ScenarioCos',
        'call', 'jump', 'flag', 'flg', 'env', 'vib', 'mac', 'macro', 'param',
        'movie', 'scene', 'logo', 'title',
        '@ScenarioCosLoad'
    ]
    command_pattern = re.compile(r'^(' + '|'.join(command_keywords) + r')(\s|$)')

    # 制御文字除去用 (U+000Fなどを削除)
    control_chars_pattern = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')

    for line in lines:
        # 1. 制御文字を削除
        line = control_chars_pattern.sub('', line)
        line = line.strip()
        
        if not line: continue
        if line.startswith('//'): continue
        
        # 2. 演出用ハイフン行を無視
        if line.startswith('-'): continue

        # --- キャラ定義・変数解析 ---
        
        # $numX = ID
        num_match = re.match(r'(\$num(\d+))\s*=\s*(\d+)', line)
        if num_match:
            var_name = num_match.group(1)
            idx = int(num_match.group(2))
            char_id = num_match.group(3)
            variable_map[var_name] = char_id
            current_speakers[str(idx)] = char_map.get(str(char_id), f"不明人物(ID:{char_id})")
            if idx > max_num_index: max_num_index = idx
            continue

        # $valueX = ID
        val_match = re.match(r'(\$value(\d+))\s*=\s*(\d+)', line)
        if val_match:
            var_name = val_match.group(1)
            v_idx = int(val_match.group(2))
            char_id = val_match.group(3)
            variable_map[var_name] = char_id
            target_slot = str(max_num_index + 1 + v_idx)
            current_speakers[target_slot] = char_map.get(str(char_id), f"不明人物(ID:{char_id})")
            continue

        # @ScenarioCos Slot ID ... (直接指定)
        scenario_match = re.match(r'@ScenarioCos\s+(\d+)\s+(\d+)', line)
        if scenario_match:
            slot = scenario_match.group(1)
            char_id = scenario_match.group(2)
            current_speakers[slot] = char_map.get(str(char_id), f"不明人物(ID:{char_id})")
            continue

        # @ScenarioCosLoad Slot Variable ... (変数ロード)
        cosload_match = re.match(r'@ScenarioCosLoad\s+(\d+)\s+(\$[\w\d]+)', line)
        if cosload_match:
            slot = cosload_match.group(1)
            var_name = cosload_match.group(2)
            if var_name in variable_map:
                char_id = variable_map[var_name]
                current_speakers[slot] = char_map.get(str(char_id), f"不明人物(ID:{char_id})")
            continue

        # --- 分岐 (branch) 解析 ---
        if line.startswith('branch'):
            parts = line.replace('branch', '', 1).strip().split()
            branch_options = parts if parts else []
            branch_index = 0
            continue

        if line.startswith('#if') and '$branch' in line:
            opt_text = branch_options[0] if len(branch_options) > 0 else "ルートA"
            output.append(f"\n====== 選択肢分岐：{opt_text} ======")
            branch_index = 1 
            continue

        if line.startswith('#elseif') and '$branch' in line:
            opt_text = branch_options[branch_index] if len(branch_options) > branch_index else f"ルート{branch_index+1}"
            output.append(f"\n====== 選択肢分岐：{opt_text} ======")
            branch_index += 1
            continue

        if line.startswith('#else'):
            opt_text = branch_options[-1] if branch_options else "ルートB"
            output.append(f"\n====== 選択肢分岐：{opt_text} ======")
            continue

        if line.startswith('#endif'):
            output.append(f"====== 選択肢分岐終了 ======\n")
            continue

        if line.startswith('#'): continue

        # --- セリフ解析 ---
        name_match = re.match(r'^name\s*(.*)', line)
        if name_match:
            val = name_match.group(1).strip()
            forced_name = val if val else "-"
            continue

        talk_match = re.match(r'@ChTalk(?:Mono)?\s+(\d+)', line)
        if talk_match:
            slot = talk_match.group(1)
            pending_speaker = current_speakers.get(slot, f"不明人物(ID:Slot{slot})")
            continue

        if line.startswith('msg'):
            pending_speaker = "-"
            continue

        # --- ゴミ除外 ---
        if command_pattern.match(line) or line.startswith(('@', '$')):
            continue

        # --- 出力 ---
        clean_line = line.replace('\t', ' ').strip()
        
        if re.match(r'^[a-zA-Z]', clean_line):
             continue

        if clean_line:
            if forced_name or pending_speaker:
                speaker = forced_name if forced_name else pending_speaker
                output.append(f"\n【{speaker}】")
                forced_name = None
                pending_speaker = None
            
            output.append(clean_line)

    return output

# --- ファイルの結合処理 ---
def merge_files_in_folder(source_dir, timestamp):
    merged_filename = f"merged_scripts_{timestamp}.txt"
    merged_path = os.path.join(source_dir, merged_filename)
    
    # _tts.txt で終わるファイルのみを対象にし、名前順でソート
    files = sorted([f for f in os.listdir(source_dir) if f.endswith('_tts.txt')])
    
    if not files:
        return None

    print(f"--- 結合ファイル作成中 ({len(files)} 件) ---")
    
    with open(merged_path, 'w', encoding='utf-8') as outfile:
        for filename in files:
            filepath = os.path.join(source_dir, filename)
            
            # ファイル区切りのヘッダー書き込み
            outfile.write(f"\n==================================================\n")
            outfile.write(f"FILE: {filename}\n")
            outfile.write(f"==================================================\n\n")
            
            # 内容を読み込んで書き込み
            with open(filepath, 'r', encoding='utf-8') as infile:
                outfile.write(infile.read())
                outfile.write("\n")
                
    print(f"[OK] 結合完了: {merged_path}")
    return merged_path

# メイン処理
def run_batch(input_files=None, episode_title=""): # 引数を追加
    input_dir = 'INPUT'
    output_base_dir = 'OUTPUT'
    
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        # フォルダがない場合は作成して案内を出す
        if len(sys.argv) <= 1:
            print(f"[{input_dir}] フォルダを作成しました。処理したいファイルを中に入れてください。")
            return

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_output_dir = os.path.join(output_base_dir, timestamp)
    current_output_dir = base_output_dir
    
    # フォルダが既に存在する場合、枝番を付ける
    suffix = 1
    while os.path.exists(current_output_dir):
        current_output_dir = f"{base_output_dir}_{suffix}"
        suffix += 1

    if(suffix > 1):
        timestamp = f"{timestamp}_{suffix-1}"
    
    backin_dir = os.path.join(current_output_dir, 'BACKIN')

    os.makedirs(current_output_dir, exist_ok=True)
    os.makedirs(backin_dir, exist_ok=True)

    char_map = load_characters()
    
    # 処理対象ファイルのリスト作成（引数モード or INPUTフォルダモード）
    file_paths_to_process = []
    
    if input_files: # 新しい引数 input_files を優先
        # 引数モード
        print("--- 引数ファイルモードで実行 ---")
        valid_files = [p for p in input_files if os.path.isfile(p)]
        file_paths_to_process = valid_files
    else:
        # INPUTフォルダモード
        print("--- INPUTフォルダモードで実行 (引数なし) ---")
        files = [f for f in os.listdir(input_dir) if os.path.isfile(os.path.join(input_dir, f))]
        file_paths_to_process = [os.path.join(input_dir, f) for f in files]

    if not file_paths_to_process:
        print("処理対象のファイルがありません。")
        return

    print(f"--- 台本変換開始 ({len(file_paths_to_process)} 件) ---")

    # 1. 各ファイルの変換 (TTS用テキスト生成)
    for input_path in file_paths_to_process:
        filename = os.path.basename(input_path)
        tts_output_filename = filename + "_tts.txt"
        tts_output_path = os.path.join(current_output_dir, tts_output_filename)
        
        try:
            formatted_script = format_for_tts(input_path, char_map)
            with open(tts_output_path, "w", encoding="utf-8") as f:
                f.write("\n".join(formatted_script))
            
            print(f"[OK] {filename} -> 中間変換完了")

            # フォルダモードの場合のみ元のファイルを移動
            if not input_files: # input_files がない場合（INPUTフォルダモード）
                 shutil.move(input_path, os.path.join(backin_dir, filename))
            
        except Exception as e:
            print(f"[Error] {filename}: {e}")

    # 2. ファイルの結合処理
    merged_file_path = merge_files_in_folder(current_output_dir, timestamp)

    # 3. 結合ファイルに対してCOEIROINK用変換を実行
    if merged_file_path and format_for_coeiroink:
        print("--- COEIROINK用ファイル生成中 ---")
        final_output_filename = f"merged_scripts_{timestamp}_coeiroink.txt"
        final_output_path = os.path.join(current_output_dir, final_output_filename)
        
        # episode_title を convert_script に渡す
        try:
            if episode_title:
                format_for_coeiroink(merged_file_path, final_output_path, episode_title=episode_title)
            else:
                format_for_coeiroink(merged_file_path, final_output_path)
            print(f"[OK] COEIROINK用出力完了: {final_output_filename}")
        except Exception as e:
            print(f"[Error] COEIROINK変換エラー: {e}")

    print(f"\n全工程完了。出力先: {current_output_dir}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="台本ファイルを解析し、TTS/COEIROINK用に整形します。")
    parser.add_argument("files", nargs="*", help="処理するファイルパス (省略時はINPUTフォルダ内のファイルを処理)")
    parser.add_argument("-t", "--title", default="", help="COEIROINK出力時のエピソード名 (第X期 第Y章 \"エピソード名\" エピソードZ の形式で挿入されます)")
    args = parser.parse_args()
    
    # run_batch に引数を渡す
    run_batch(input_files=args.files, episode_title=args.title)