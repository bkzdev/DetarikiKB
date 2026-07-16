"""
DKB Story Parser - H_scene Variant Dynamic Subset Judgment

`character`カテゴリのH_sceneN本体ファイルに対し、同ディレクトリの変種ファイル
(`_n`/`_spine`/`#K`/`_n #K`/`_spine #K`)が本体の内容の部分集合かどうかを
実行時に動的判定する (`_VR`は判定対象外、常にスキップする)。

設計根拠:
    docs/architecture/01_Project/03_Scope.md §5.3・§5.5.1
    docs/architecture/05_Parser/Character_Story_ID_Manifest_Design.md §6

比較手法 (§5.3と同一):
    識別子集合 = 発話系コマンド (@ChTalk/@ChTalkMono/@ChTalkSoundOff/
    @ChTalkSoundOffMono/@ChTalkName/@SpineTalk + config/script_commands.yaml
    登録済みの既知表記ゆれ) が参照するvoice/textアセット参照path、
    および正規化済み日本語TEXT行 (開発用ログ行`log ----- ...`・
    モザイク指定行`mozaiku ...`等の非セリフ行を除く) の集合。
    変種側の集合が本体側の集合の部分集合なら"subset" (パースしない)、
    部分集合でなければ"exception" (パース対象、§6のepisodeId suffix規則で
    別episodeとして取り込む)。空集合の変種はsubset扱い。

実ファイル名を含む判定結果を固定リストとしてcommitしてはならない
(`03_Scope.md` §5.5.1 (1)、`docs/runbooks/AI_PR_Playbook.md` §7)。
本モジュールは判定ロジックのみを提供し、判定は常に実行時に行う。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .tokenizer import ScriptToken, Tokenizer, TokenType

# ----------------------------------------------------------------
# 発話系コマンド (identifier抽出対象)
# ----------------------------------------------------------------

# config/script_commands.yaml の speech カテゴリそのもの
# (@ChTalk/@ChTalkMono/@ChTalkSoundOff/@ChTalkSoundOffMono/@ChTalkName/
# @SpineTalk)。
SPEECH_LIKE_COMMANDS: frozenset[str] = frozenset(
    {
        "@ChTalk",
        "@ChTalkMono",
        "@ChTalkSoundOff",
        "@ChTalkSoundOffMono",
        "@ChTalkName",
        "@SpineTalk",
    }
)

# config/script_commands.yaml に登録済みの既知表記ゆれ
# (speech-command-likeだが安全側でstage_direction分類されているもの、
# config/script_commands.yaml 288-293行)。§5.3の比較手法はコマンド名一致
# ではなくアセットpath/TEXT行の集合比較のため、識別子抽出時にはこれらの
# 表記ゆれが指すアセットpathも取りこぼさないよう対象に含める
# (実parserのstage_direction分類自体は変更しない、本モジュール限定の
# 識別子抽出ルール)。
SPEECH_CASE_VARIANTS: dict[str, str] = {
    "@ChTalkSoundOffmono": "@ChTalkSoundOffMono",
    "@ChTalkSoundoff": "@ChTalkSoundOff",
    "@ChTalkmono": "@ChTalkMono",
    "@ChTalkname": "@ChTalkName",
    "@Chtalkname": "@ChTalkName",
}

# 非セリフTEXT行の除外プレフィックス (§5.3/§5.5.1の識別子定義)。
# 開発用ログ行 (`log ----- $arg0 ...`) ・モザイク指定行 (`mozaiku ... `) は
# 正規化済み日本語TEXT行の集合から除外する。
NON_DIALOGUE_TEXT_PREFIXES: tuple[str, ...] = ("log ", "mozaiku ")


def _is_speech_like(command: str | None) -> bool:
    if command is None:
        return False
    return command in SPEECH_LIKE_COMMANDS or command in SPEECH_CASE_VARIANTS


def _extract_asset_path(args: list[str]) -> str | None:
    """発話系コマンドの引数列からvoice/textアセット参照pathを抽出する。

    実データ確認 (data/raw/character/ 全量) では:
        @ChTalk/@ChTalkMono/@SpineTalk   -> [slot, path]
        @ChTalkName                      -> [slot, speakerName, path]
        @ChTalkSoundOff/@ChTalkSoundOffMono -> [slot] (pathなし)
    のいずれかで固定されている。コマンドごとの引数位置に依存せず、
    「末尾の引数が'/'を含めばpathとみなす」という位置非依存の判定にする
    (表記ゆれコマンドも同じ判定で処理できる)。
    """
    if not args:
        return None
    last = args[-1]
    return last if "/" in last else None


def _is_non_dialogue_text(raw_line: str) -> bool:
    return raw_line.startswith(NON_DIALOGUE_TEXT_PREFIXES)


def extract_identifier_set(
    file_path: str | Path,
    tokenizer: Tokenizer | None = None,
) -> frozenset[str]:
    """H_scene系ファイルの識別子集合を抽出する。

    識別子は "asset:<path>" (発話系コマンドのvoice/textアセットpath) と
    "text:<line>" (正規化済み日本語TEXT行、非セリフ行を除く) の2種類の
    文字列として、区別できるようprefixを付けて1つの集合にまとめる。
    """
    tok = tokenizer or Tokenizer()
    tokens = tok.tokenize_file(file_path)
    return extract_identifier_set_from_tokens(tokens)


def extract_identifier_set_from_tokens(tokens: list[ScriptToken]) -> frozenset[str]:
    """トークン列から識別子集合を抽出する (合成fixtureテスト用に
    ファイルI/Oを介さず呼べるようextract_identifier_setから分離)。
    """
    identifiers: set[str] = set()
    for token in tokens:
        if token.token_type == TokenType.COMMAND and _is_speech_like(token.command):
            path = _extract_asset_path(token.args)
            if path:
                identifiers.add(f"asset:{path}")
            continue
        if token.token_type == TokenType.TEXT:
            if _is_non_dialogue_text(token.raw):
                continue
            identifiers.add(f"text:{token.text}")
    return frozenset(identifiers)


# ----------------------------------------------------------------
# 部分集合判定
# ----------------------------------------------------------------


@dataclass(frozen=True)
class SubsetJudgment:
    """本体識別子集合に対する変種識別子集合の部分集合判定結果"""

    is_subset: bool
    body_identifier_count: int
    variant_identifier_count: int
    extra_in_variant_count: int
    """変種側にあって本体側に無い識別子の件数 (0ならsubset)"""

    @property
    def classification(self) -> str:
        return "subset" if self.is_subset else "exception"


def judge_subset(
    body_identifiers: frozenset[str],
    variant_identifiers: frozenset[str],
) -> SubsetJudgment:
    """変種識別子集合が本体識別子集合の部分集合かどうかを判定する。

    空集合の変種は常にsubset扱い (§6.1)。
    """
    extra = variant_identifiers - body_identifiers
    return SubsetJudgment(
        is_subset=len(extra) == 0,
        body_identifier_count=len(body_identifiers),
        variant_identifier_count=len(variant_identifiers),
        extra_in_variant_count=len(extra),
    )


# ----------------------------------------------------------------
# 変種ファイル検出 (ファイル名パターン)
# ----------------------------------------------------------------

# 変種パターン識別子。"vr" は判定対象外 (常にskip)。
VariantPattern = str  # "n" / "spine" / "hash" / "n_hash" / "spine_hash" / "vr"

# episodeId suffix規則 (Character_Story_ID_Manifest_Design.md §6.2)。
# "hash"/"n_hash"/"spine_hash" はdup_index (#Kの数値K) が必要なため
# ここには含めず、derive_variant_episode_idで個別に組み立てる。
_SIMPLE_SUFFIX_MAP: dict[str, str] = {
    "n": "_VN",
    "spine": "_VSP",
}

# H_sceneN本体ファイルの stem (拡張子除くファイル名) パターン。
# 末尾が "H_scene<digits>" で終わり、それ以降に何も続かないもの
# (続きがあれば `_n`/`_spine`/` #K`等の変種、またはH_sceneN_img等の
# 特殊ファイルであり、本体ではない)。
_BODY_STEM_PATTERN = re.compile(r"^(?P<prefix>.*)H_scene(?P<num>\d+)$")


def match_hscene_body_stem(stem: str) -> re.Match[str] | None:
    """stem (拡張子を除くファイル名) がH_sceneN本体パターンに一致するか判定する。"""
    return _BODY_STEM_PATTERN.match(stem)


def is_hscene_body_file(path: Path) -> bool:
    """pathがH_sceneN本体ファイル (H_scene_s・変種・特殊ファイルを除く) かどうか。"""
    return match_hscene_body_stem(path.stem) is not None


def hscene_number(path: Path) -> int | None:
    """H_sceneN本体ファイルのNを返す (本体でなければNone)。"""
    match = match_hscene_body_stem(path.stem)
    return int(match.group("num")) if match else None


@dataclass(frozen=True)
class VariantCandidate:
    """H_sceneN本体に対応する変種ファイル候補"""

    path: Path
    pattern: VariantPattern
    dup_index: int | None = None
    """#Kのファイル名末尾の複製番号K (hash系パターンのみ、他はNone)"""


def find_variant_candidates(body_path: Path) -> list[VariantCandidate]:
    """body_pathと同じディレクトリから、対応する変種ファイル (`_n`/`_spine`/
    `#K`/`_n #K`/`_spine #K`/`_VR`) を検出する。

    本体ファイル名の完全なstem (プレフィックス+H_scene+番号) を基準に
    厳密一致させる (character export directory自体の命名規則
    `CAB-csl_script_charastory_character{N}-H_scene{M}...` に依存しない、
    body_pathから導出したprefixベースの照合)。
    """
    match = match_hscene_body_stem(body_path.stem)
    if match is None:
        raise ValueError(f"H_sceneN本体ファイルのパターンに一致しません: {body_path}")

    prefix = re.escape(match.group("prefix"))
    num = match.group("num")
    suffix = body_path.suffix
    directory = body_path.parent

    pattern_defs: list[tuple[VariantPattern, re.Pattern[str]]] = [
        ("n", re.compile(rf"^{prefix}H_scene{num}_n$")),
        ("spine", re.compile(rf"^{prefix}H_scene{num}_spine$")),
        ("hash", re.compile(rf"^{prefix}H_scene{num} #(?P<k>\d+)$")),
        ("n_hash", re.compile(rf"^{prefix}H_scene{num}_n #(?P<k>\d+)$")),
        ("spine_hash", re.compile(rf"^{prefix}H_scene{num}_spine #(?P<k>\d+)$")),
        ("vr", re.compile(rf"^{prefix}H_scene{num}_VR$")),
    ]

    if not directory.is_dir():
        return []

    candidates: list[VariantCandidate] = []
    for sibling in sorted(directory.iterdir()):
        if not sibling.is_file() or sibling == body_path or sibling.suffix != suffix:
            continue
        stem = sibling.stem
        for pattern_name, regex in pattern_defs:
            m = regex.match(stem)
            if not m:
                continue
            dup_index = int(m.group("k")) if "k" in m.groupdict() else None
            candidates.append(
                VariantCandidate(
                    path=sibling, pattern=pattern_name, dup_index=dup_index
                )
            )
            break

    return candidates


def find_hscene_body_files(root: Path) -> list[Path]:
    """rootディレクトリ配下 (再帰的) からH_sceneN本体ファイルを検出する。

    キャラクターexportディレクトリ (例: csl_script_charastory_character10_export)
    を直接指定した場合と、その親ディレクトリ (character/ 全体) を指定した
    場合の両方で使える (再帰的にglobする)。rootがファイルそのものの場合は
    そのファイル自身が本体かどうかだけを判定する。
    """
    if root.is_file():
        return [root] if is_hscene_body_file(root) else []

    return sorted(p for p in root.rglob("*") if p.is_file() and is_hscene_body_file(p))


# ----------------------------------------------------------------
# episodeId suffix導出 (Character_Story_ID_Manifest_Design.md §6.2)
# ----------------------------------------------------------------


def derive_variant_episode_id(
    base_episode_id: str,
    pattern: VariantPattern,
    dup_index: int | None = None,
) -> str:
    """§6.2のepisodeId suffix規則に従い、例外変種のepisodeIdを導出する。

    "vr" はこの関数の対象外 (常にskipされるため呼び出されない想定であり、
    渡された場合はValueErrorにする)。
    """
    if pattern in _SIMPLE_SUFFIX_MAP:
        return f"{base_episode_id}{_SIMPLE_SUFFIX_MAP[pattern]}"

    if pattern in ("hash", "n_hash", "spine_hash"):
        if dup_index is None:
            raise ValueError(
                f"{pattern}パターンにはdup_indexが必要です: {base_episode_id}"
            )
        if pattern == "hash":
            return f"{base_episode_id}_VD{dup_index}"
        if pattern == "n_hash":
            return f"{base_episode_id}_VN_D{dup_index}"
        return f"{base_episode_id}_VSP_D{dup_index}"

    raise ValueError(f"未対応のvariant pattern (動的判定対象外): {pattern}")


# ----------------------------------------------------------------
# 本体単位の判定オーケストレーション
# ----------------------------------------------------------------


@dataclass(frozen=True)
class VariantJudgmentResult:
    """1変種ファイルに対する判定結果"""

    variant: VariantCandidate
    judgment: str
    """"subset" / "exception" / "skipped_vr" のいずれか"""
    body_identifier_count: int
    variant_identifier_count: int
    extra_in_variant_count: int
    derived_episode_id: str | None
    """base_episode_idが与えられ、かつjudgment=="exception"の場合のみ設定"""


@dataclass(frozen=True)
class BodyJudgmentResult:
    """1つのH_sceneN本体に対する全変種の判定結果"""

    body_path: Path
    hscene_number: int
    body_identifier_count: int
    base_episode_id: str | None
    variants: list[VariantJudgmentResult]

    @property
    def exception_variants(self) -> list[VariantJudgmentResult]:
        return [v for v in self.variants if v.judgment == "exception"]


def judge_body_variants(
    body_path: Path,
    base_episode_id: str | None = None,
    tokenizer: Tokenizer | None = None,
) -> BodyJudgmentResult:
    """1つのH_sceneN本体ファイルについて、対応する全変種を動的判定する。

    Args:
        body_path: H_sceneN本体ファイルのパス
        base_episode_id: 指定するとexception判定された変種のepisodeIdを
            §6.2の規則で導出する (未指定ならderived_episode_idは常にNone)
        tokenizer: 識別子抽出に使うTokenizer (省略時はデフォルト設定)
    """
    num = hscene_number(body_path)
    if num is None:
        raise ValueError(f"H_sceneN本体ファイルのパターンに一致しません: {body_path}")

    tok = tokenizer or Tokenizer()
    body_identifiers = extract_identifier_set(body_path, tok)

    results: list[VariantJudgmentResult] = []
    for candidate in find_variant_candidates(body_path):
        if candidate.pattern == "vr":
            # _VR は判定対象外、常にスキップする (§6.2)。
            # スキップした事実は報告に残すため、identifier抽出は行わず
            # judgment="skipped_vr"のみ記録する。
            results.append(
                VariantJudgmentResult(
                    variant=candidate,
                    judgment="skipped_vr",
                    body_identifier_count=len(body_identifiers),
                    variant_identifier_count=0,
                    extra_in_variant_count=0,
                    derived_episode_id=None,
                )
            )
            continue

        variant_identifiers = extract_identifier_set(candidate.path, tok)
        subset_judgment = judge_subset(body_identifiers, variant_identifiers)

        derived_episode_id: str | None = None
        if not subset_judgment.is_subset and base_episode_id is not None:
            derived_episode_id = derive_variant_episode_id(
                base_episode_id, candidate.pattern, candidate.dup_index
            )

        results.append(
            VariantJudgmentResult(
                variant=candidate,
                judgment=subset_judgment.classification,
                body_identifier_count=subset_judgment.body_identifier_count,
                variant_identifier_count=subset_judgment.variant_identifier_count,
                extra_in_variant_count=subset_judgment.extra_in_variant_count,
                derived_episode_id=derived_episode_id,
            )
        )

    return BodyJudgmentResult(
        body_path=body_path,
        hscene_number=num,
        body_identifier_count=len(body_identifiers),
        base_episode_id=base_episode_id,
        variants=results,
    )
