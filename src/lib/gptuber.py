import asyncio
import json
import sys
import time
from typing import Awaitable, Callable, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, Field

from agent import FnSmartAgent
from lib.tts.tts import SpeechModeEnum, speak
from lib.utils import WordInfo, build_time_expression, count_mora, get_error_message, mecab_parser, remove_emojis, remove_linebreaks
from lib.youtube import ChatLog
from lib.emotes import determine_emote_from_text


class Action(BaseModel):
    """
    行動を表すクラス
    """
    text: str = Field(..., description="発話するテキスト")
    query_to_google_home: Optional[str] = Field(None, description="Google Home に対しての質問文（あれば）")
    by: Optional[str] = Field(None, description="発話者")


class GPTuber:
    def __init__(
        self,
        fn_streamer_llm: Callable[[str], Action],
        fn_get_recent_chats: Optional[Callable[[], List[ChatLog]]] = None,
        fn_distract: Optional[Callable[[], Awaitable[str]]] = None,
        fn_send_message: Optional[Callable[[str], None]] = None,
        fn_smart_agent: Optional[FnSmartAgent] = None,
        no_neural_tts: bool = False
    ):
        """
        「配信者」のクラス
        ----
        Args:
            fn_streamer_llm: 大規模言語モデルを用いた，YouTuberの行動を生成する関数．この関数は「直近の出来事を表すレポート」を引数にとり，行動を返す必要がある．
                直近の出来事を表すレポートは，基本的に以下のようなフォーマットである．
                ```
                Audience: こんにちは
                Audience: おはよう
                Audience: おはようございます
                ```
                これに加えて，Google Home からの返答がある場合は，以下のような行が追加される．
                ```
                (Google Home の答え: ............ )
                ```
                なお，視聴者からのチャットが一件もなかった場合は，Audience の行が無い代わりに，以下のような行が追加される．
                ```
                (視聴者のチャットが無く ... 分経過)
                ```
                さらに，一定時間視聴者からのチャットがなかった場合には，TV の放送内容を表す以下のような行が追加される場合がある．
                ```
                (TV: 「........」)
                ```
            fn_get_recent_chats: 直近のチャットを取得する関数．この関数は，前回呼ばれたときからの差分のチャットの一覧を返す必要がある．
            fn_distract: YouTuber の話題を変えるために置かれた「TVが喋っている内容（トークスクリプト）」を生成する関数．
            fn_send_message: フロントエンド側にメッセージ送信する（字幕やエモートの表示指示）ための関数
            fn_smart_agent: Google Home を発動させるための関数．この関数は，クエリ(str) に加えて，ログ内容をコールバックするための関数 (Callable[[str], None]) を引数にとる．
                ログ内容およびログ回数は任意であるが，Google Home からの最終返答を YouTuber にフィードバックするには，"Final Answer: " という文字列を含むログ内容を
                一度コールバックする必要がある．
            no_neural_tts: True の場合，Neural TTS を使用せず，標準の TTS を使用する（品質は下がる）．      
        """
        self.fn_streamer_llm = fn_streamer_llm
        self.fn_get_recent_chats = fn_get_recent_chats
        self.fn_distract = fn_distract
        self.fn_send_message = fn_send_message
        self.fn_smart_agent = fn_smart_agent
        self.no_neural_tts = no_neural_tts
        self.main_loop_wait_sec = 10.0
        self.actions_reserved: List[Action] = []
        self.is_now_acting: bool = False
        self.last_chat_time: float = time.time()
        self.last_non_boring_time: float = time.time()
        self.boring_patience_sec = 120.0
        self.final_answer_from_google_home: Optional[str] = None

    async def main_loop(self):
        """
        行動生成のためのメインループ
        """
        await asyncio.sleep(5)
        while True:
            if len(self.actions_reserved) < 3:
                current_time = time.time()
                # 最新のコメントを取得
                new_chat_logs = self.fn_get_recent_chats() if self.fn_get_recent_chats is not None else []
                # レポート（直近の動き）を作成
                if len(new_chat_logs) > 0:
                    report = "".join(
                        [f"Audience: {remove_linebreaks(log.message)[:256]}" + "\n" for log in new_chat_logs]
                    )
                    self.last_chat_time = current_time
                    self.last_non_boring_time = current_time
                else:
                    elapsed_sec = current_time - self.last_chat_time
                    report = f"(視聴者のチャットが無く{build_time_expression(elapsed_sec)}経過)" + "\n"
                    # 暇時間が一定に達した場合，TVの情報が割り込む
                    if self.fn_distract is not None and current_time - self.last_non_boring_time > self.boring_patience_sec:
                        report += f"(TV: 「...{remove_linebreaks(await self.fn_distract())}」)" + "\n"
                        self.last_non_boring_time = current_time
                    # Google Home が答えを返してきた場合，その情報が割り込む
                    if self.final_answer_from_google_home is not None:
                        report += f"(Google Home の答え: {remove_linebreaks(self.final_answer_from_google_home)})" + "\n"
                        self.final_answer_from_google_home = None
                try:
                    # LLM に聞く（メモリー付きのChainの場合は，内部的にメモリーも更新される）
                    action = self.fn_streamer_llm(report)
                    print(f"{action=}")
                    action.by = "streamer"
                    # 行動の予約
                    self.reserve_action(action)
                except Exception:
                    # 503 が多分多い
                    print(get_error_message(), file=sys.stderr)
            # 待機
            await asyncio.sleep(self.main_loop_wait_sec)

    async def main_loop2(self):
        """
        行動消化のためのメインループ
        """
        await asyncio.sleep(5)
        while True:
            self.check_acting_and_act()
            await asyncio.sleep(1)

    def reserve_action(self, action: Action):
        """
        未完了の行動がある場合は，行動を予約する．ない場合は，直ちに行動する．
        """
        self.actions_reserved.append(action)
        self.check_acting_and_act()

    def check_acting_and_act(self):
        """
        行動中でなければ，予約された行動を実行する．
        """
        if not self.is_now_acting:
            if len(self.actions_reserved) > 0:
                # a = self.actions_reserved.pop(0)
                # 先頭を取り出すが，agent の行動がある場合は優先して取り出したほうが良さそう．
                idx_agent = [i for i, a in enumerate(self.actions_reserved) if a.by == "agent"]
                if len(idx_agent) > 0:
                    a = self.actions_reserved.pop(idx_agent[0])
                else:
                    a = self.actions_reserved.pop(0)
                self.act_now(a)

    def on_finish_action(self):
        """
        行動終了時に呼び出される関数．呼び出される設定は行動開始時になされる．
        """
        self.is_now_acting = False

    def act_now(self, action: Action):
        """
        直ちに行動を実行する．
        """
        self.is_now_acting = True
        if action.by == "streamer":
            # if action.emote is not None:
            #     asyncio.create_task(self.emote_now(action.emote))
            if action.text is not None:
                asyncio.create_task(self.speak_now(action.text, by=action.by))
            if action.query_to_google_home is not None:
                asyncio.create_task(self.query_to_google_home_now(action.query_to_google_home))
        elif action.by == "agent":
            if action.text is not None:
                asyncio.create_task(self.speak_now(action.text, by=action.by))

    async def speak_now(self, text: str, by: str):
        """
        直ちに喋る
        """
        if by == "streamer":
            speak(
                text,
                mode=SpeechModeEnum.CLASSIC_JP if self.no_neural_tts else SpeechModeEnum.NEURAL_JP,
                callback=self.on_finish_action
            )
        elif by == "agent":
            speak(
                text,
                mode=SpeechModeEnum.CLASSIC_EN,
                callback=self.on_finish_action
            )
        else:
            raise ValueError(f"Invalid by: {by}")

        if self.fn_send_message is not None:
            # 字幕の表示指示
            timeline = generate_subtitle_timeline(
                text,
                flg_split=by == "streamer",
                prefix="" if by == "streamer" else "(Google Home) "
            )
            self.fn_send_message(
                json.dumps({
                    "type": "subtitle",
                    "timeline": timeline
                }, ensure_ascii=False)
            )

    async def emote_streamer_now(self, kind: str):
        """
        直ちに表情を変える（現在不使用）
        """
        if self.fn_send_message is not None:
            self.fn_send_message(
                json.dumps({
                    "type": "emote",
                    "kind": kind
                }, ensure_ascii=False)
            )

    async def query_to_google_home_now(self, query: str):
        """
        直ちに Google Home に問い合わせる．実際には，追加のアクションを予約する．
        """
        def _fn_report(text: str):
            text = text.strip()
            if text != "":
                self.reserve_action(Action(
                    by="agent",
                    text=text
                ))
                if "Final Answer: " in text:
                    self.final_answer_from_google_home = text.split("Final Answer: ")[1]

        if self.fn_smart_agent is not None:
            print(f"fn_smart_agent is started. {query=}")
            await self.fn_smart_agent(query, fn_report=_fn_report)
            print(f"fn_smart_agent is finished. {query=}")


def generate_subtitle_timeline(
    text: str,
    flg_split: bool = True,
    prefix: str = ""
) -> List[Tuple[float, str, Optional[str]]]:
    """発話内容テキストから字幕表示指示を生成する．
    ----
    Args:
        text (str): 発話内容テキスト
        flg_split (bool, optional): 文節ごとに字幕を表示するか． Defaults to True.
        prefix (str, optional): 全ての発話の先頭に付与する文字列（例えば，発話者を表す目的で使用可能である）． Defaults to "".

    Returns:
        List[Tuple[float, str, Optional[str]]]: (時刻(sec), 字幕表示内容, エモート変更指示) のリスト．
    """
    words = mecab_parser.parse(text)[1:-1]
    chunks: List[Tuple[int, str]] = []
    buffer = ""
    mora_count = 0
    for i, word in enumerate(words):
        buffer += word.surface
        mora_count += count_mora(word.yomi)
        # きりの良いところでバッファクリアする
        if i == len(words) - 1 or (flg_split and is_likely_to_split(word, words[i + 1])):
            chunks.append((mora_count, buffer))  # まとめて出す方式に変更
            buffer = ""
            mora_count = 0

    # モーラカウントを適切な秒数に変換する
    coef = 0.14  # 1モーラあたりの秒数
    timeline = list(zip(
        coef * np.cumsum([0] + [chunk[0] for chunk in chunks]),
        [remove_emojis(chunk[1], "") for chunk in chunks] + [""],  # 最後は字幕消す
        [determine_emote_from_text(chunk[1]) for chunk in chunks] + [None]  # 最後は表情指示無し
    ))

    # prefix の付与（最後以外）
    timeline = [(
        t,
        (prefix if i + 1 < len(timeline) else "") + text,
        emote
    ) for i, (t, text, emote) in enumerate(timeline)]

    return timeline


def is_likely_to_split(word1: WordInfo, word2: WordInfo) -> bool:
    """
    与えられた単語のペアが，文節の区切りとして適切かどうかを判定する．
    """
    brachet_start = "「『【（〈《〔［｛〘〖〝〟‘“([{"
    if word1.hinshi in ["記号"] and word1.surface not in brachet_start and word2.hinshi not in ["記号"]:
        return True
    if word1.hinshi in ["助詞", "助動詞"] and word2.hinshi in ["名詞", "動詞", "形容詞", "副詞", "連体詞", "形容動詞"] and word2.surface not in "ー♪":
        return True
    return False
