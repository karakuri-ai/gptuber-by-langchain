from pathlib import Path
from typing import Optional, Union
from collections import Counter

import pandas as pd

from lib.utils import extract_emojis


class EmojiToEmoteConverter:
    def __init__(self, path_to_csv: Union[str, Path], path_to_emotes: Union[str, Path]):
        df = pd.read_csv(path_to_csv)
        filenames = set(f.name for f in Path(path_to_emotes).glob("*") if f.is_file())
        # 一致するファイル名のみを残す
        df = df[df["emote"].isin(filenames)]
        self.dictionary = dict(zip(df["emoji"], df["emote"]))

    def convert(self, emoji: str) -> Optional[str]:
        return self.dictionary.get(emoji)


emoji_to_emote_converter = EmojiToEmoteConverter(
    path_to_csv="./lib/emoji-to-emote.csv",
    path_to_emotes="../public/img/streamer/"
)


def determine_emote_from_text(text: str) -> Optional[str]:
    emojis = extract_emojis(text)
    if len(emojis) == 0:
        return None
    emote = Counter(map(emoji_to_emote_converter.convert, emojis)).most_common(1)[0][0]  # type: ignore
    return emote
