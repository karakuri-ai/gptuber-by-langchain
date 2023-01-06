import sys
import traceback
import threading
import subprocess
import re
from typing import Callable, List, Optional, TypeVar

import emoji
import numpy as np
import MeCab


T = TypeVar("T")


def get_error_message():
    exc_type, exc_value, exc_traceback = sys.exc_info()
    return "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))


def random_choice(ary: List[T]) -> T:
    return np.random.choice(ary)  # type: ignore


def count_mora(yomi: str) -> int:
    if len(yomi) == 0:
        return 4
    else:
        return len([c for c in yomi if c not in "ャュョァィゥェォ"])


def remove_linebreaks(s: str) -> str:
    return s.replace("\n", " ")


def remove_successive_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s)


def remove_control_characters(s: str) -> str:
    # \x1b で始まり m で終わる「色指定」を除去する
    return re.sub(r"\x1b\[[0-9;]*m", "", s)


def pick_first_row(s: str) -> str:
    return s.split("\n")[0]


def remove_emojis(s: str, to: str = " ") -> str:
    # return re.sub(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff]', ' ', s)
    return emoji.replace_emoji(s, to)


def extract_emojis(s: str) -> List[str]:
    # REF: https://stackoverflow.com/questions/33404752/removing-emojis-from-a-string-in-python
    # return re.findall(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f1e0-\U0001f1ff]', s)
    return [_["emoji"] for _ in emoji.emoji_list(s)]


def build_time_expression(sec: float) -> str:
    if sec < 60:
        return f"{int(sec)}秒"
    elif sec < 60 * 60:
        return f"{int(sec / 60)}分"
    else:
        return f"{int(sec / 60 / 60)}時間{int((sec / 60) % 60)}分"


def popen_with_callback(on_exit: Optional[Callable], *popen_args, **popen_kwargs):
    """
    REF: https://stackoverflow.com/questions/2581817/python-subprocess-callback-when-cmd-exits
    """
    def run_in_thread(on_exit, popen_args, popen_kwargs):
        proc = subprocess.Popen(*popen_args, **popen_kwargs)
        proc.wait()
        if on_exit is not None:
            on_exit()
        return

    thread = threading.Thread(
        target=run_in_thread,
        args=(on_exit, popen_args, popen_kwargs)
    )
    thread.start()
    return thread  # returns immediately after the thread starts


class WordInfo:
    # TODO: Pydantic 使うともっと簡潔にかけるかも
    def __init__(self, surface: str, feature: List[str]):
        self.surface = surface  # 通れ
        self.hinshi = feature[0]  # 動詞
        self.hinshi_detail1 = feature[1]  # 自立
        self.hinshi_detail2 = feature[2]  # *
        self.hinshi_detail3 = feature[3]  # *
        self.katsuyougata = feature[4]  # 一段
        self.katsuyoukei = feature[5]  # 連用形
        self.genkei = feature[6] if feature[6] != "*" else surface  # 通れる
        self.yomi = feature[7] if len(feature) > 7 else surface  # トオレ
        self.hatsuon = feature[8] if len(feature) > 8 else surface  # トーレ

    def __repr__(self):
        return f"WordInfo({repr(self.surface)}, {repr(self.get_feature_list())})"

    def __eq__(self, other):
        return self.surface == other.surface and self.get_feature_list() == other.get_feature_list()

    def get_feature_list(self):
        return [
            self.hinshi,
            self.hinshi_detail1,
            self.hinshi_detail2,
            self.hinshi_detail3,
            self.katsuyougata,
            self.katsuyoukei,
            self.genkei,
            self.yomi,
            self.hatsuon
        ]


class MeCabParser:
    def __init__(self):
        self.mt = MeCab.Tagger("")
        self.mt.parse("")  # バグ対処のため最初に一度行う必要がある

    def parse(self, text: str) -> List[WordInfo]:
        """
        mecab で parse を行う．
        ----
        Args:
            text (str):
                分かち書きを行いたい文字列
        Returns:
            (list of WordInfo):
                単語情報のリスト
        """
        assert isinstance(text, str), "text must be str"  # parseToNode に str 以外が入ると Kernel Death が生じて厄介のため
        tokens = []
        node = self.mt.parseToNode(text)
        while node:
            tokens.append(WordInfo(node.surface, node.feature.split(",")))
            node = node.next

        # 空白抜け補正処理
        offset = 0
        for token in tokens[1:-1]:
            index = text.find(token.surface, offset)
            if index < 0:
                print("WARNING: 空白抜け補正処理に失敗しました．")
                index = 0
            token.surface = text[offset:index] + token.surface
            offset += len(token.surface)

        return tokens


mecab_parser = MeCabParser()
