from enum import Enum
import os
import re
import subprocess
from typing import Callable, Optional

from lib.utils import popen_with_callback, remove_emojis, remove_successive_spaces, remove_control_characters


class SpeechModeEnum(str, Enum):
    """
    TTS のモード
    """
    NEURAL_JP = "neural-jp"
    CLASSIC_JP = "classic-jp"
    CLASSIC_EN = "classic-en"


def speak(
    text: str,
    mode: SpeechModeEnum,
    callback: Optional[Callable] = None
) -> None:
    """
    text を喋る．
    """
    this_directory = os.path.dirname(__file__)
    text = convert_text_for_speech(text)
    if mode is SpeechModeEnum.NEURAL_JP:
        # 日本語を綺麗に喋る
        text_for_tts = convert_text_for_speech(text)
        proc = subprocess.run(
            ["sh", "./tts.sh", text_for_tts],
            cwd=this_directory,
            stdout=subprocess.PIPE
        )
        path_to_audio_file = proc.stdout.decode("utf-8").strip()
        # 音声ファイルの再生開始（再生終了まで待たない．再生終了時に callback 実行）
        popen_with_callback(
            callback,
            ["mpg123", "-q", path_to_audio_file],
            cwd=this_directory
        )
    elif mode is SpeechModeEnum.CLASSIC_JP:
        # 日本語を雑に喋る
        text_for_tts = convert_text_for_speech(text)
        popen_with_callback(
            callback,
            ["say", "-v", "Kyoko", text_for_tts]
        )
    elif mode is SpeechModeEnum.CLASSIC_EN:
        # 英語を雑に喋る
        text_for_tts = convert_text_for_speech(text)
        popen_with_callback(
            callback,
            ["say", "-v", "Samantha", text_for_tts]
        )
    else:
        raise ValueError(f"Invalid mode: {mode}")


def convert_text_for_speech(text: str) -> str:
    """
    TTS に入力するために，テキストを最適化する
    """
    text = remove_control_characters(text)
    text = remove_emojis(text)
    text = remove_successive_spaces(text)
    # 空白の左側がひらがなカタカナ漢字である場合は，読点を挿入する
    text = re.sub(r"([ぁ-んァ-ン一-龥〜])\s", r"\1、", text)
    return text
